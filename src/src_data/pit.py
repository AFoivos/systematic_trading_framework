from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from src.utils.paths import PROJECT_ROOT

_ALLOWED_DUPLICATE_POLICIES = {"first", "last", "raise"}
_ALLOWED_CORP_ACTION_POLICIES = {"none", "adj_close_ratio", "adj_close_replace_close"}
_ALLOWED_UNIVERSE_INACTIVE_POLICIES = {"raise", "drop_inactive_rows"}


def align_ohlcv_timestamps(
    df: pd.DataFrame,
    *,
    source_timezone: str = "UTC",
    output_timezone: str = "UTC",
    normalize_daily: bool = True,
    duplicate_policy: str = "last",
) -> pd.DataFrame:
    """
    Handle align OHLCV timestamps inside the data ingestion and storage layer. The helper
    isolates one focused responsibility so the surrounding code remains modular, readable, and
    easier to test.
    """
    if duplicate_policy not in _ALLOWED_DUPLICATE_POLICIES:
        raise ValueError(
            f"duplicate_policy must be one of {_ALLOWED_DUPLICATE_POLICIES}, got '{duplicate_policy}'."
        )
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    out = df.copy()
    idx = out.index
    if not isinstance(idx, pd.DatetimeIndex):
        idx = pd.to_datetime(idx, errors="raise")

    if idx.tz is None:
        idx = idx.tz_localize(source_timezone)
    idx = idx.tz_convert(output_timezone)
    if normalize_daily:
        idx = idx.normalize()
    idx = idx.tz_localize(None)
    out.index = idx

    out = out.sort_index()
    if out.index.has_duplicates:
        if duplicate_policy == "raise":
            raise ValueError("Duplicate timestamps found after alignment.")
        out = out[~out.index.duplicated(keep=duplicate_policy)]

    return out


def apply_corporate_actions_policy(
    df: pd.DataFrame,
    *,
    policy: str = "none",
    adj_close_col: str = "adj_close",
    price_cols: Iterable[str] = ("open", "high", "low", "close"),
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Apply corporate actions policy to the provided inputs in a controlled and reusable way. The
    helper makes a single transformation step explicit inside the broader data ingestion and
    storage workflow.
    """
    if policy not in _ALLOWED_CORP_ACTION_POLICIES:
        raise ValueError(f"policy must be one of {_ALLOWED_CORP_ACTION_POLICIES}.")
    out = df.copy()
    meta: dict[str, Any] = {"policy": policy, "adjusted_rows": 0}

    if policy == "none":
        return out, meta

    if adj_close_col not in out.columns:
        raise ValueError(
            f"Corporate actions policy '{policy}' requires '{adj_close_col}' column."
        )
    if "close" not in out.columns:
        raise ValueError("Corporate actions policies require 'close' column.")

    close = out["close"].astype(float)
    adj_close = out[adj_close_col].astype(float)

    factor = (adj_close / close.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
    valid = factor.notna() & (factor > 0)
    factor = factor.where(valid, 1.0).astype(float)

    if policy == "adj_close_ratio":
        for col in price_cols:
            if col in out.columns:
                out[col] = out[col].astype(float) * factor
        out["close"] = adj_close
    elif policy == "adj_close_replace_close":
        out["close"] = adj_close

    out["pit_adjustment_factor"] = factor
    meta["adjusted_rows"] = int(valid.sum())
    return out, meta


def _resolve_snapshot_path(path: str | Path) -> Path:
    """
    Handle snapshot path inside the data ingestion and storage layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    p = Path(path)
    if not p.is_absolute():
        p = (PROJECT_ROOT / p).resolve()
    return p


def load_universe_snapshot(path: str | Path) -> pd.DataFrame:
    """
    Load universe snapshot for the data ingestion and storage layer and normalize it into the
    shape expected by the rest of the project. The helper centralizes path or provider handling
    so callers do not duplicate I/O logic.
    """
    p = _resolve_snapshot_path(path)
    if not p.exists():
        raise FileNotFoundError(f"Universe snapshot file not found: {p}")
    if p.suffix.lower() == ".csv":
        df = pd.read_csv(p)
    elif p.suffix.lower() in {".parquet", ".pq"}:
        df = pd.read_parquet(p)
    else:
        raise ValueError("Universe snapshot path must be .csv or .parquet")

    if "symbol" not in df.columns:
        raise ValueError("Universe snapshot must include 'symbol' column.")
    if "effective_from" not in df.columns:
        raise ValueError("Universe snapshot must include 'effective_from' column.")

    out = df.copy()
    out["symbol"] = out["symbol"].astype(str)
    out["effective_from"] = pd.to_datetime(out["effective_from"], errors="coerce")
    if out["effective_from"].isna().any():
        raise ValueError("Universe snapshot has invalid 'effective_from' values.")

    if "effective_to" in out.columns:
        out["effective_to"] = pd.to_datetime(out["effective_to"], errors="coerce")
    else:
        out["effective_to"] = pd.NaT

    return out


def symbols_active_in_snapshot(snapshot_df: pd.DataFrame, as_of: str | pd.Timestamp) -> list[str]:
    """
    Handle symbols active in snapshot inside the data ingestion and storage layer. The helper
    isolates one focused responsibility so the surrounding code remains modular, readable, and
    easier to test.
    """
    ts = pd.Timestamp(as_of)
    effective_from = snapshot_df["effective_from"]
    effective_to = snapshot_df["effective_to"]

    active = snapshot_df.loc[
        (effective_from <= ts) & (effective_to.isna() | (effective_to >= ts)),
        "symbol",
    ]
    return sorted(set(active.astype(str)))


def assert_symbol_in_snapshot(
    symbol: str,
    snapshot_df: pd.DataFrame,
    *,
    as_of: str | pd.Timestamp,
) -> None:
    """
    Assert symbol in snapshot before the pipeline proceeds. This helper exists to fail loudly
    when a key assumption of the data ingestion and storage layer has been violated.
    """
    active = symbols_active_in_snapshot(snapshot_df, as_of=as_of)
    if symbol not in active:
        raise ValueError(
            f"Symbol '{symbol}' is not active in the universe snapshot for as_of={pd.Timestamp(as_of).date()}."
        )


def symbol_active_mask_over_time(
    snapshot_df: pd.DataFrame,
    *,
    symbol: str,
    index: pd.DatetimeIndex,
) -> pd.Series:
    """
    Build a per-timestamp membership mask for one symbol from a universe snapshot so PIT
    enforcement can validate the whole time series instead of only a single as-of date.
    """
    if not isinstance(index, pd.DatetimeIndex):
        raise TypeError("index must be a pandas DatetimeIndex.")

    idx = pd.DatetimeIndex(pd.to_datetime(index, errors="raise"))
    symbol_rows = snapshot_df.loc[snapshot_df["symbol"].astype(str) == str(symbol)]
    mask = pd.Series(False, index=idx, dtype=bool)
    if symbol_rows.empty or mask.empty:
        return mask

    for _, row in symbol_rows.iterrows():
        interval = row["effective_from"] <= idx
        effective_to = row["effective_to"]
        if pd.notna(effective_to):
            interval = interval & (idx <= effective_to)
        mask.loc[interval] = True
    return mask


def enforce_symbol_membership_over_time(
    df: pd.DataFrame,
    *,
    snapshot_df: pd.DataFrame,
    symbol: str,
    inactive_policy: str = "raise",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Enforce symbol membership across the entire dataframe index using the universe snapshot.
    """
    if inactive_policy not in _ALLOWED_UNIVERSE_INACTIVE_POLICIES:
        raise ValueError(
            f"inactive_policy must be one of {_ALLOWED_UNIVERSE_INACTIVE_POLICIES}."
        )

    active_mask = symbol_active_mask_over_time(
        snapshot_df,
        symbol=symbol,
        index=pd.DatetimeIndex(df.index),
    )
    inactive_mask = ~active_mask
    inactive_rows = int(inactive_mask.sum())
    meta = {
        "inactive_policy": inactive_policy,
        "rows_checked": int(len(df)),
        "active_rows": int(active_mask.sum()),
        "inactive_rows": inactive_rows,
    }
    if inactive_rows == 0:
        return df.copy(), meta

    if inactive_policy == "raise":
        examples = ", ".join(str(ts.date()) for ts in df.index[inactive_mask][:5])
        raise ValueError(
            f"Symbol '{symbol}' has {inactive_rows} row(s) outside the universe snapshot. "
            f"Example timestamps: {examples}"
        )

    out = df.loc[active_mask].copy()
    meta["inactive_rows_dropped"] = inactive_rows
    return out, meta


def apply_pit_hardening(
    df: pd.DataFrame,
    *,
    pit_cfg: Mapping[str, Any] | None = None,
    symbol: str | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Apply point-in-time (PIT) hardening to the provided inputs in a controlled and reusable way.
    The helper makes a single transformation step explicit inside the broader data ingestion and
    storage workflow.
    """
    cfg = dict(pit_cfg or {})
    ts_cfg = dict(cfg.get("timestamp_alignment", {}) or {})
    corp_cfg = dict(cfg.get("corporate_actions", {}) or {})
    universe_cfg = dict(cfg.get("universe_snapshot", {}) or {})

    out = align_ohlcv_timestamps(
        df,
        source_timezone=str(ts_cfg.get("source_timezone", "UTC")),
        output_timezone=str(ts_cfg.get("output_timezone", "UTC")),
        normalize_daily=bool(ts_cfg.get("normalize_daily", True)),
        duplicate_policy=str(ts_cfg.get("duplicate_policy", "last")),
    )
    out, corp_meta = apply_corporate_actions_policy(
        out,
        policy=str(corp_cfg.get("policy", "none")),
        adj_close_col=str(corp_cfg.get("adj_close_col", "adj_close")),
    )

    universe_meta: dict[str, Any] = {}
    snapshot_path = universe_cfg.get("path")
    as_of = universe_cfg.get("as_of")
    if snapshot_path and symbol:
        snapshot_df = load_universe_snapshot(snapshot_path)
        if as_of is not None:
            assert_symbol_in_snapshot(symbol, snapshot_df, as_of=as_of)
            universe_meta = {
                "path": str(_resolve_snapshot_path(snapshot_path)),
                "mode": "as_of_check",
                "as_of": str(pd.Timestamp(as_of)),
                "active_symbols": int(len(symbols_active_in_snapshot(snapshot_df, as_of=as_of))),
            }
        elif not out.empty:
            out, membership_meta = enforce_symbol_membership_over_time(
                out,
                snapshot_df=snapshot_df,
                symbol=symbol,
                inactive_policy=str(universe_cfg.get("inactive_policy", "raise")),
            )
            universe_meta = {
                "path": str(_resolve_snapshot_path(snapshot_path)),
                "mode": "full_history",
                **membership_meta,
            }

    meta = {
        "timestamp_alignment": {
            "source_timezone": str(ts_cfg.get("source_timezone", "UTC")),
            "output_timezone": str(ts_cfg.get("output_timezone", "UTC")),
            "normalize_daily": bool(ts_cfg.get("normalize_daily", True)),
            "duplicate_policy": str(ts_cfg.get("duplicate_policy", "last")),
        },
        "corporate_actions": corp_meta,
        "universe_snapshot": universe_meta,
    }
    return out, meta


__all__ = [
    "align_ohlcv_timestamps",
    "apply_corporate_actions_policy",
    "load_universe_snapshot",
    "symbols_active_in_snapshot",
    "assert_symbol_in_snapshot",
    "symbol_active_mask_over_time",
    "enforce_symbol_membership_over_time",
    "apply_pit_hardening",
]
