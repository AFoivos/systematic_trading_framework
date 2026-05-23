from __future__ import annotations

import math
import re
from collections.abc import Iterable
from typing import Any

import pandas as pd


class DataSchemaError(ValueError):
    """Raised when a local dataset cannot be normalized into dashboard contracts."""


TIMESTAMP_COLUMN_CANDIDATES = ("timestamp", "datetime", "date", "time")
OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")
NON_SERIES_COLUMNS = {"timestamp", "datetime", "date", "time", "asset", "symbol"}


def normalize_timeframe(value: str | None) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    compact = raw.replace("_", "").replace("-", "").replace(" ", "").upper()
    match = re.fullmatch(r"(?:(M|H|D|W)(\d+)|(\d+)(M|H|D|W))", compact)
    if not match:
        return compact
    if match.group(1):
        unit = match.group(1)
        number = match.group(2)
    else:
        number = match.group(3)
        unit = match.group(4)
    return f"{unit}{int(number)}"


def infer_timeframe_from_name(name: str) -> str | None:
    lowered = name.lower()
    patterns = [
        r"(?:^|[_\-.])m(\d+)(?:$|[_\-.])",
        r"(?:^|[_\-.])(\d+)m(?:$|[_\-.])",
        r"(?:^|[_\-.])h(\d+)(?:$|[_\-.])",
        r"(?:^|[_\-.])(\d+)h(?:$|[_\-.])",
        r"(?:^|[_\-.])d(\d+)(?:$|[_\-.])",
        r"(?:^|[_\-.])(\d+)d(?:$|[_\-.])",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if not match:
            continue
        token = match.group(0).strip("_-.")
        return normalize_timeframe(token)
    return None


def infer_asset_from_name(name: str) -> str | None:
    stem = re.sub(r"\.(csv|parquet)$", "", name, flags=re.IGNORECASE)
    parts = [part for part in re.split(r"[_\-.]+", stem) if part]
    ignored = {"bid", "ask", "mid", "clean", "raw", "ohlcv", "data"}
    candidates: list[str] = []
    for part in parts:
        normalized_tf = normalize_timeframe(part)
        if normalized_tf == part.upper() and re.fullmatch(r"[MHDW]\d+", normalized_tf):
            continue
        if part.lower() in ignored:
            continue
        if re.fullmatch(r"\d+[mhdwMHDW]", part):
            continue
        candidates.append(part)
    if not candidates:
        return None
    return candidates[0].upper()


def _infer_epoch_unit(values: pd.Series) -> str:
    numeric = pd.to_numeric(values, errors="raise")
    if numeric.empty:
        raise DataSchemaError("Timestamp column cannot be empty.")
    max_abs = float(numeric.abs().max())
    if max_abs >= 1e17:
        return "ns"
    if max_abs >= 1e14:
        return "us"
    if max_abs >= 1e11:
        return "ms"
    return "s"


def coerce_timestamps(values: pd.Series | Iterable[Any]) -> pd.DatetimeIndex:
    series = pd.Series(values)
    if series.empty:
        raise DataSchemaError("Timestamp column cannot be empty.")
    try:
        if pd.api.types.is_numeric_dtype(series):
            unit = _infer_epoch_unit(series)
            parsed = pd.to_datetime(pd.to_numeric(series, errors="raise"), unit=unit, utc=True, errors="raise")
        else:
            stripped = series.astype(str).str.strip()
            if stripped.str.fullmatch(r"[+-]?\d+").all():
                numeric = pd.to_numeric(stripped, errors="raise")
                unit = _infer_epoch_unit(numeric)
                parsed = pd.to_datetime(numeric, unit=unit, utc=True, errors="raise")
            else:
                parsed = pd.to_datetime(series, utc=True, errors="raise")
    except Exception as exc:  # pandas raises several concrete parser exceptions
        raise DataSchemaError(f"Could not parse timestamp values: {exc}") from exc
    return pd.DatetimeIndex(parsed)


def coerce_time_boundary(value: str | None) -> pd.Timestamp | None:
    if value is None or str(value).strip() == "":
        return None
    return coerce_timestamps(pd.Series([value]))[0]


def normalize_market_frame(frame: pd.DataFrame, *, require_ohlcv: bool = False) -> pd.DataFrame:
    if frame.empty:
        raise DataSchemaError("Dataset is empty.")

    out = frame.copy()
    out.columns = [str(column).strip() for column in out.columns]
    lowered = {column.lower(): column for column in out.columns}
    timestamp_col = next((lowered[name] for name in TIMESTAMP_COLUMN_CANDIDATES if name in lowered), None)

    if timestamp_col is not None:
        timestamps = coerce_timestamps(out[timestamp_col])
        out = out.drop(columns=[timestamp_col])
    elif isinstance(out.index, pd.DatetimeIndex):
        timestamps = coerce_timestamps(pd.Series(out.index))
    else:
        expected = ", ".join(TIMESTAMP_COLUMN_CANDIDATES)
        raise DataSchemaError(f"Dataset must include one timestamp column: {expected}.")

    rename_map: dict[str, str] = {}
    for column in out.columns:
        normalized = column.lower()
        if normalized in OHLCV_COLUMNS:
            rename_map[column] = normalized
    out = out.rename(columns=rename_map)

    if require_ohlcv:
        missing = [column for column in OHLCV_COLUMNS if column not in out.columns]
        if missing:
            raise DataSchemaError(f"Dataset is missing OHLCV columns: {missing}.")

    for column in OHLCV_COLUMNS:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")

    out.index = timestamps
    out.index.name = "time"
    out = out.loc[~out.index.isna()].sort_index()
    out = out.loc[~out.index.duplicated(keep="last")]
    return out


def filter_by_date(frame: pd.DataFrame, *, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    out = frame
    start_ts = coerce_time_boundary(start)
    end_ts = coerce_time_boundary(end)
    if start_ts is not None:
        out = out.loc[out.index >= start_ts]
    if end_ts is not None:
        out = out.loc[out.index < end_ts]
    return out


def to_iso_z(value: Any) -> str:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.isoformat().replace("+00:00", "Z")


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    return value


def frame_to_candles(frame: pd.DataFrame) -> list[dict[str, Any]]:
    missing = [column for column in OHLCV_COLUMNS if column not in frame.columns]
    if missing:
        raise DataSchemaError(f"Dataset is missing OHLCV columns: {missing}.")
    rows = frame.dropna(subset=["open", "high", "low", "close"])
    return [
        {
            "time": to_iso_z(index),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": _json_value(row.get("volume")),
        }
        for index, row in rows.iterrows()
    ]


def frame_to_series(frame: pd.DataFrame, columns: Iterable[str]) -> dict[str, list[dict[str, Any]]]:
    selected = [str(column) for column in columns]
    missing = [column for column in selected if column not in frame.columns]
    if missing:
        raise DataSchemaError(f"Dataset is missing requested columns: {missing}.")
    response: dict[str, list[dict[str, Any]]] = {}
    for column in selected:
        series = frame[column]
        response[column] = [
            {"time": to_iso_z(index), "value": _json_value(value)}
            for index, value in series.items()
        ]
    return response


def _column_dtype_name(frame: pd.DataFrame, column: str) -> str:
    if column not in frame.columns:
        return "unknown"
    return str(frame[column].dtype)


def is_signal_column(column: str) -> bool:
    name = column.lower()
    return (
        "signal" in name
        or name.endswith("_side")
        or name.endswith("_position")
        or "candidate" in name
        or name in {"side", "position", "positions"}
    )


def is_target_column(column: str) -> bool:
    name = column.lower()
    return name.startswith("target") or "target_" in name or name.startswith("r_target") or "label" in name


def is_prediction_column(column: str) -> bool:
    name = column.lower()
    return name.startswith("pred") or "prediction" in name or name.endswith("_prob") or "probability" in name


def feature_category(column: str) -> str:
    name = column.lower()
    if any(token in name for token in ("ret", "return", "logret", "pnl")):
        return "returns"
    if any(token in name for token in ("vol", "atr", "true_range", "range", "spread")):
        return "volatility"
    if any(token in name for token in ("ema", "sma", "trend", "roc", "momentum", "macd", "ppo")):
        return "trend"
    if any(token in name for token in ("adx", "mfi", "bollinger", "bb_", "support", "resistance", "volume", "vwap")):
        return "indicators"
    if any(token in name for token in ("rsi", "stoch", "oscillator")):
        return "oscillators"
    if any(token in name for token in ("macro", "vix", "dxy", "yield", "rate")):
        return "macro"
    if any(token in name for token in ("session", "hour", "weekday", "weekend", "london", "ny_", "orb")):
        return "session"
    if any(token in name for token in ("regime", "state", "shock")):
        return "regime"
    return "custom"


def catalog_columns(frame: pd.DataFrame, *, source_type: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for column in frame.columns:
        lowered = str(column).lower()
        if lowered in NON_SERIES_COLUMNS or lowered in OHLCV_COLUMNS:
            continue
        if source_type == "feature" and (is_signal_column(column) or is_target_column(column) or is_prediction_column(column)):
            continue
        if source_type == "signal" and not is_signal_column(column):
            continue
        if source_type == "target" and not is_target_column(column):
            continue
        if source_type == "prediction" and not is_prediction_column(column):
            continue
        items.append(
            {
                "name": str(column),
                "category": feature_category(column) if source_type == "feature" else source_type,
                "dtype": _column_dtype_name(frame, column),
            }
        )
    return items


def group_catalog_items(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {
        "returns": [],
        "volatility": [],
        "trend": [],
        "indicators": [],
        "oscillators": [],
        "macro": [],
        "session": [],
        "regime": [],
        "custom": [],
    }
    for item in items:
        category = str(item.get("category") or "custom")
        grouped.setdefault(category, []).append(item)
    return grouped
