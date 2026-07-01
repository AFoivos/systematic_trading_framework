from __future__ import annotations

from numbers import Real

import numpy as np
import pandas as pd


def add_scalp_microstructure_proxy(
    df: pd.DataFrame,
    *,
    open_col: str = "open",
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    volume_col: str = "volume",
    bid_open_col: str = "bid_open",
    bid_high_col: str = "bid_high",
    bid_low_col: str = "bid_low",
    bid_close_col: str = "bid_close",
    ask_open_col: str = "ask_open",
    ask_high_col: str = "ask_high",
    ask_low_col: str = "ask_low",
    ask_close_col: str = "ask_close",
    spread_close_col: str = "spread_close",
    spread_bps_col: str = "spread_bps",
    eps: float = 1.0e-12,
    mid_open_col: str = "mid_open",
    mid_high_col: str = "mid_high",
    mid_low_col: str = "mid_low",
    mid_close_col: str = "mid_close",
    bid_ask_spread_abs_col: str = "bid_ask_spread_abs",
    bid_ask_spread_bps_col: str = "bid_ask_spread_bps",
    spread_bps_change_col: str = "spread_bps_change",
    bar_range_col: str = "bar_range",
    bar_body_col: str = "bar_body",
    close_pos_in_bar_col: str = "close_pos_in_bar",
    body_to_range_col: str = "body_to_range",
    upper_wick_col: str = "upper_wick",
    lower_wick_col: str = "lower_wick",
    candle_pressure_col: str = "candle_pressure",
    signed_volume_proxy_col: str = "signed_volume_proxy",
    buy_volume_proxy_col: str = "buy_volume_proxy",
    sell_volume_proxy_col: str = "sell_volume_proxy",
    ofi_proxy_norm_1_col: str = "ofi_proxy_norm_1",
) -> pd.DataFrame:
    """
    Apply the registered ``scalp_microstructure_proxy`` feature transformation.

    This feature builds causal quote/spread/candle-flow proxy features from
    same-bar OHLCV and bid/ask quote columns. It computes spread outputs from
    bid/ask close prices; legacy ``spread_close_col`` and ``spread_bps_col``
    parameters are accepted for compatibility but are not required inputs.

    YAML declaration::

        features:
          - step: scalp_microstructure_proxy
            params:
              open_col: open
              high_col: high
              low_col: low
              close_col: close
              volume_col: volume
              bid_open_col: bid_open
              bid_high_col: bid_high
              bid_low_col: bid_low
              bid_close_col: bid_close
              ask_open_col: ask_open
              ask_high_col: ask_high
              ask_low_col: ask_low
              ask_close_col: ask_close
              spread_close_col: spread_close
              spread_bps_col: spread_bps

    Required input columns
    ----------------------
    open_col, high_col, low_col, close_col, volume_col:
        Current-bar OHLCV columns.
    bid_open_col, bid_high_col, bid_low_col, bid_close_col:
        Current-bar bid quote columns.
    ask_open_col, ask_high_col, ask_low_col, ask_close_col:
        Current-bar ask quote columns.

    Parameters
    ----------
    spread_close_col, spread_bps_col:
        Backward-compatible parameter names retained for older configs. These
        columns are not read by the calculation.
    eps:
        Positive numeric floor used for safe divisions.
    *_col:
        Input and output column names used by this feature.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")
    resolved_eps = _validate_eps(eps)
    input_cols = [
        open_col,
        high_col,
        low_col,
        close_col,
        volume_col,
        bid_open_col,
        bid_high_col,
        bid_low_col,
        bid_close_col,
        ask_open_col,
        ask_high_col,
        ask_low_col,
        ask_close_col,
    ]
    output_cols = [
        mid_open_col,
        mid_high_col,
        mid_low_col,
        mid_close_col,
        bid_ask_spread_abs_col,
        bid_ask_spread_bps_col,
        spread_bps_change_col,
        bar_range_col,
        bar_body_col,
        close_pos_in_bar_col,
        body_to_range_col,
        upper_wick_col,
        lower_wick_col,
        candle_pressure_col,
        signed_volume_proxy_col,
        buy_volume_proxy_col,
        sell_volume_proxy_col,
        ofi_proxy_norm_1_col,
    ]
    _validate_column_names(input_cols, field="input columns")
    _validate_column_names(output_cols, field="output columns")
    _require_columns(df, input_cols)

    out = df.copy()
    open_ = _numeric(out, open_col)
    high = _numeric(out, high_col)
    low = _numeric(out, low_col)
    close = _numeric(out, close_col)
    volume = _numeric(out, volume_col)
    bid_open = _numeric(out, bid_open_col)
    bid_high = _numeric(out, bid_high_col)
    bid_low = _numeric(out, bid_low_col)
    bid_close = _numeric(out, bid_close_col)
    ask_open = _numeric(out, ask_open_col)
    ask_high = _numeric(out, ask_high_col)
    ask_low = _numeric(out, ask_low_col)
    ask_close = _numeric(out, ask_close_col)

    mid_open = (bid_open + ask_open) / 2.0
    mid_high = (bid_high + ask_high) / 2.0
    mid_low = (bid_low + ask_low) / 2.0
    mid_close = (bid_close + ask_close) / 2.0

    spread_abs = ask_close - bid_close
    computed_spread_bps = spread_abs / mid_close.where(mid_close.abs() > resolved_eps, np.nan) * 10_000.0

    bar_range = high - low
    safe_range = bar_range.where(bar_range.abs() > resolved_eps, resolved_eps)
    bar_body = close - open_
    close_pos = ((close - low) / safe_range).clip(lower=0.0, upper=1.0)
    body_to_range = (bar_body.abs() / safe_range).replace([np.inf, -np.inf], np.nan)
    upper_wick = high - pd.concat([open_, close], axis=1).max(axis=1)
    lower_wick = pd.concat([open_, close], axis=1).min(axis=1) - low

    candle_pressure = (2.0 * close_pos - 1.0).clip(lower=-1.0, upper=1.0)
    signed_volume = volume * candle_pressure
    buy_volume = ((volume + signed_volume) / 2.0).clip(lower=0.0)
    sell_volume = ((volume - signed_volume) / 2.0).clip(lower=0.0)
    safe_volume = volume.where(volume.abs() > resolved_eps, np.nan)
    ofi_norm = (signed_volume / safe_volume).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    out[mid_open_col] = mid_open
    out[mid_high_col] = mid_high
    out[mid_low_col] = mid_low
    out[mid_close_col] = mid_close
    out[bid_ask_spread_abs_col] = spread_abs
    out[bid_ask_spread_bps_col] = computed_spread_bps
    out[spread_bps_change_col] = computed_spread_bps - computed_spread_bps.shift(1)
    out[bar_range_col] = bar_range
    out[bar_body_col] = bar_body
    out[close_pos_in_bar_col] = close_pos
    out[body_to_range_col] = body_to_range
    out[upper_wick_col] = upper_wick
    out[lower_wick_col] = lower_wick
    out[candle_pressure_col] = candle_pressure
    out[signed_volume_proxy_col] = signed_volume
    out[buy_volume_proxy_col] = buy_volume
    out[sell_volume_proxy_col] = sell_volume
    out[ofi_proxy_norm_1_col] = ofi_norm.clip(lower=-1.0, upper=1.0)
    return out


def _numeric(df: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(df[column], errors="coerce").astype(float)


def _validate_eps(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("eps must be a finite positive number.")
    resolved = float(value)
    if not np.isfinite(resolved) or resolved <= 0.0:
        raise ValueError("eps must be a finite positive number.")
    return resolved


def _validate_column_names(columns: list[str], *, field: str) -> None:
    invalid = [column for column in columns if not isinstance(column, str) or not column.strip()]
    if invalid:
        raise ValueError(f"{field} must be non-empty strings.")


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for scalp_microstructure_proxy: {missing}")


__all__ = ["add_scalp_microstructure_proxy"]
