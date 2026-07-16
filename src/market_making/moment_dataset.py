from __future__ import annotations

from pathlib import Path
from typing import Sequence
import math

import numpy as np
import pandas as pd


FUTURE_TARGET_PREFIXES = (
    "future_mid_return_",
    "buy_markout_bps_",
    "sell_markout_bps_",
    "buy_good_",
    "sell_good_",
)


def build_market_making_moment_dataset(
    *,
    orderbook_events_path: str | Path,
    quote_events_paths: Sequence[str | Path],
    output_path: str | Path,
    horizons: Sequence[int] = (1, 5, 10, 30),
    maker_fee_bps: float = 0.0,
    max_inventory: float | None = None,
) -> pd.DataFrame:
    """Build a quote-level MOMENT research dataset without leaking future targets into features."""
    normalized_horizons: list[int] = []
    for value in horizons:
        horizon = int(value)
        if horizon <= 0:
            raise ValueError("market-making target horizons must be positive integers")
        if horizon not in normalized_horizons:
            normalized_horizons.append(horizon)
    if not normalized_horizons:
        raise ValueError("at least one market-making target horizon is required")
    if not math.isfinite(float(maker_fee_bps)):
        raise ValueError("maker_fee_bps must be finite")
    if max_inventory is not None and (
        not math.isfinite(float(max_inventory)) or float(max_inventory) <= 0.0
    ):
        raise ValueError("max_inventory must be finite and > 0 when provided")

    orderbook = _load_orderbook(orderbook_events_path)
    quotes = _load_quotes(quote_events_paths)
    if quotes.empty:
        raise ValueError("at least one non-empty quote_events.csv is required")

    merge_kwargs: dict[str, object] = {}
    if "symbol" in quotes.columns and "symbol" in orderbook.columns:
        quotes["symbol"] = quotes["symbol"].astype(str)
        orderbook["symbol"] = orderbook["symbol"].astype(str)
        merge_kwargs["by"] = "symbol"
    elif ("symbol" in quotes.columns) != ("symbol" in orderbook.columns):
        raise ValueError("orderbook and quote events must either both contain symbol or both omit it")
    dataset = pd.merge_asof(
        quotes.sort_values("timestamp"),
        orderbook.sort_values("timestamp"),
        on="timestamp",
        direction="backward",
        suffixes=("_quote", ""),
        **merge_kwargs,
    )
    dataset["timestamp"] = pd.to_datetime(dataset["timestamp"], utc=True)
    dataset = dataset.sort_values("timestamp").reset_index(drop=True)
    dataset["book_best_bid"] = _coalesce_numeric(dataset, ["book_best_bid", "best_bid"])
    dataset["book_best_ask"] = _coalesce_numeric(dataset, ["book_best_ask", "best_ask"])
    dataset["book_mid"] = _coalesce_numeric(dataset, ["book_mid_price", "mid_price"])
    dataset["book_spread_bps"] = _coalesce_numeric(dataset, ["book_spread_bps", "spread_bps"])
    dataset["book_imbalance_1"] = _coalesce_numeric(dataset, ["book_imbalance_1", "imbalance_1"])
    dataset["book_imbalance_5"] = _coalesce_numeric(dataset, ["book_imbalance_5", "imbalance_5"])
    dataset["bid_depth_1"] = _coalesce_numeric(dataset, ["bid_depth_1", "bid_depth_5"])
    dataset["ask_depth_1"] = _coalesce_numeric(dataset, ["ask_depth_1", "ask_depth_5"])
    dataset["bid_depth_5"] = _coalesce_numeric(dataset, ["bid_depth_5", "bid_depth_1"])
    dataset["ask_depth_5"] = _coalesce_numeric(dataset, ["ask_depth_5", "ask_depth_1"])
    dataset["bid_depth_10"] = _coalesce_numeric(dataset, ["bid_depth_10", "bid_depth_5"])
    dataset["ask_depth_10"] = _coalesce_numeric(dataset, ["ask_depth_10", "ask_depth_5"])
    dataset["microprice"] = _microprice(dataset)
    dataset["fair_price"] = _coalesce_numeric(dataset, ["fair_price", "microprice", "book_mid"])
    dataset["fair_price_offset_bps"] = _safe_div(dataset["fair_price"] - dataset["book_mid"], dataset["book_mid"]) * 10_000.0
    symbol_groups = (
        dataset.groupby("symbol", sort=False, group_keys=False)
        if "symbol" in dataset.columns
        else None
    )
    if symbol_groups is None:
        mid_returns = dataset["book_mid"].pct_change(fill_method=None)
        recent_mid_return_5 = dataset["book_mid"].pct_change(5, fill_method=None)
        recent_mid_slope = dataset["book_mid"].diff().rolling(5, min_periods=2).mean()
        recent_volatility = mid_returns.rolling(10, min_periods=2).std()
    else:
        mid_returns = symbol_groups["book_mid"].pct_change(fill_method=None)
        recent_mid_return_5 = symbol_groups["book_mid"].pct_change(5, fill_method=None)
        recent_mid_slope = symbol_groups["book_mid"].transform(
            lambda values: values.diff().rolling(5, min_periods=2).mean()
        )
        recent_volatility = mid_returns.groupby(dataset["symbol"], sort=False).transform(
            lambda values: values.rolling(10, min_periods=2).std()
        )
    dataset["recent_mid_return_1"] = mid_returns.fillna(0.0)
    dataset["recent_mid_return_5"] = recent_mid_return_5.fillna(0.0)
    dataset["recent_mid_slope"] = recent_mid_slope.fillna(0.0)
    dataset["recent_volatility"] = recent_volatility.fillna(0.0)
    inventory_values = (
        dataset["inventory"]
        if "inventory" in dataset.columns
        else pd.Series(0.0, index=dataset.index, dtype="float64")
    )
    dataset["inventory"] = pd.to_numeric(inventory_values, errors="coerce").fillna(0.0)
    if max_inventory is None:
        max_abs_inventory = float(dataset["inventory"].abs().max())
        max_inventory = max_abs_inventory if max_abs_inventory > 0 else 1.0
    dataset["inventory_ratio"] = pd.to_numeric(dataset.get("inventory_ratio", dataset["inventory"] / max_inventory), errors="coerce").fillna(0.0)
    dataset["quoted_side_candidate"] = dataset.apply(_quoted_side_candidate, axis=1)
    dataset["maker_fee_bps"] = float(maker_fee_bps)
    dataset["current_strategy_decision"] = np.where(
        _as_bool(dataset.get("placed", pd.Series(False, index=dataset.index))),
        "placed",
        "blocked",
    )
    if "risk_reason" in dataset.columns:
        current_reason = dataset["risk_reason"]
    elif "quote_reason" in dataset.columns:
        current_reason = dataset["quote_reason"]
    else:
        current_reason = pd.Series("", index=dataset.index, dtype="object")
    dataset["current_strategy_reason"] = current_reason.fillna("")

    for horizon in normalized_horizons:
        future_mid = (
            dataset["book_mid"].shift(-horizon)
            if symbol_groups is None
            else symbol_groups["book_mid"].shift(-horizon)
        )
        suffix = f"h{horizon}"
        dataset[f"future_mid_return_{suffix}"] = _safe_div(future_mid - dataset["book_mid"], dataset["book_mid"])
        dataset[f"buy_markout_bps_{suffix}"] = _safe_div(future_mid - dataset["bid_price"], dataset["bid_price"]) * 10_000.0
        dataset[f"sell_markout_bps_{suffix}"] = _safe_div(dataset["ask_price"] - future_mid, dataset["ask_price"]) * 10_000.0
        dataset[f"buy_good_{suffix}"] = dataset[f"buy_markout_bps_{suffix}"] > 0
        dataset[f"sell_good_{suffix}"] = dataset[f"sell_markout_bps_{suffix}"] > 0
        dataset[f"buy_good_after_fees_{suffix}"] = (
            dataset[f"buy_markout_bps_{suffix}"] > maker_fee_bps
        )
        dataset[f"sell_good_after_fees_{suffix}"] = (
            dataset[f"sell_markout_bps_{suffix}"] > maker_fee_bps
        )

    dataset = dataset.loc[:, ~dataset.columns.duplicated()].copy()
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_parquet(output, index=False)
    return dataset


def chronological_split(
    frame: pd.DataFrame,
    *,
    train_fraction: float = 0.6,
    validation_fraction: float = 0.2,
) -> dict[str, pd.DataFrame]:
    """Split rows chronologically into train/validation/test partitions."""
    if not 0.0 < train_fraction < 1.0:
        raise ValueError("train_fraction must be in (0, 1)")
    if not 0.0 <= validation_fraction < 1.0:
        raise ValueError("validation_fraction must be in [0, 1)")
    if train_fraction + validation_fraction >= 1.0:
        raise ValueError("train_fraction + validation_fraction must be < 1")
    ordered = frame.sort_values("timestamp").reset_index(drop=True)
    n = len(ordered)
    train_end = max(1, int(n * train_fraction))
    validation_end = max(train_end, int(n * (train_fraction + validation_fraction)))
    if validation_fraction > 0 and validation_end == train_end and n - train_end > 1:
        validation_end += 1
    return {
        "train": ordered.iloc[:train_end].copy(),
        "validation": ordered.iloc[train_end:validation_end].copy(),
        "test": ordered.iloc[validation_end:].copy(),
    }


def feature_columns(frame: pd.DataFrame) -> list[str]:
    """Return leakage-safe numeric feature columns for MOMENT/head training."""
    excluded = {"timestamp", "quote_event_id", "symbol", "quoted_side_candidate", "current_strategy_decision", "current_strategy_reason"}
    columns: list[str] = []
    for column in frame.columns:
        if column in excluded or any(str(column).startswith(prefix) for prefix in FUTURE_TARGET_PREFIXES):
            continue
        if pd.api.types.is_numeric_dtype(frame[column]) or pd.api.types.is_bool_dtype(frame[column]):
            columns.append(str(column))
    return columns


def assert_no_target_leakage(input_columns: Sequence[str]) -> None:
    leaked = [col for col in input_columns if any(str(col).startswith(prefix) for prefix in FUTURE_TARGET_PREFIXES)]
    if leaked:
        raise ValueError(f"future target columns cannot be model inputs: {leaked}")


def _load_orderbook(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path, low_memory=False)
    if "timestamp" not in frame:
        raise ValueError("orderbook_events.csv must contain timestamp")
    frame["timestamp"] = _parse_timestamp_utc(frame["timestamp"], source=str(path))
    return frame.sort_values("timestamp")


def _load_quotes(paths: Sequence[str | Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        frame = pd.read_csv(path, low_memory=False)
        if frame.empty:
            continue
        if "timestamp" not in frame:
            raise ValueError(f"quote events missing timestamp: {path}")
        frame["timestamp"] = _parse_timestamp_utc(frame["timestamp"], source=str(path))
        frames.append(frame)
    return pd.concat(frames, ignore_index=True).sort_values("timestamp") if frames else pd.DataFrame()


def _parse_timestamp_utc(values: pd.Series, *, source: str) -> pd.Series:
    try:
        return pd.to_datetime(values, utc=True, format="mixed")
    except ValueError as exc:
        raise ValueError(f"{source} contains timestamps that cannot be parsed as mixed ISO8601 datetimes") from exc


def _coalesce_numeric(frame: pd.DataFrame, candidates: Sequence[str]) -> pd.Series:
    out = pd.Series(np.nan, index=frame.index, dtype="float64")
    for candidate in candidates:
        if candidate in frame:
            out = out.combine_first(pd.to_numeric(frame[candidate], errors="coerce"))
    return out


def _safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    denominator = pd.to_numeric(den, errors="coerce").replace(0.0, np.nan)
    return pd.to_numeric(num, errors="coerce") / denominator


def _microprice(frame: pd.DataFrame) -> pd.Series:
    bid = frame["book_best_bid"]
    ask = frame["book_best_ask"]
    bid_depth = frame["bid_depth_1"].fillna(0.0)
    ask_depth = frame["ask_depth_1"].fillna(0.0)
    total = bid_depth + ask_depth
    micro = (ask * bid_depth + bid * ask_depth) / total.replace(0.0, np.nan)
    return micro.combine_first(frame["book_mid"])


def _quoted_side_candidate(row: pd.Series) -> str:
    has_bid = pd.notna(row.get("bid_price")) and float(row.get("bid_size") or 0.0) > 0
    has_ask = pd.notna(row.get("ask_price")) and float(row.get("ask_size") or 0.0) > 0
    if has_bid and has_ask:
        return "both"
    if has_bid:
        return "buy"
    if has_ask:
        return "sell"
    return "none"


def _as_bool(value: object) -> pd.Series:
    if isinstance(value, pd.Series):
        if value.dtype == bool:
            return value
        return value.astype(str).str.lower().isin({"true", "1", "yes"})
    return pd.Series(bool(value))


__all__ = [
    "assert_no_target_leakage",
    "build_market_making_moment_dataset",
    "chronological_split",
    "feature_columns",
]
