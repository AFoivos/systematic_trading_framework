from __future__ import annotations

from numbers import Integral, Real

import numpy as np
import pandas as pd


def add_vpin(
    df: pd.DataFrame,
    buy_volume_col: str | None = "buy_volume",
    sell_volume_col: str | None = "sell_volume",
    signed_volume_col: str | None = None,
    volume_col: str = "volume",
    window: int = 50,
    bucket_volume: float | None = None,
    output_col: str | None = None,
) -> pd.DataFrame:
    """
    Add VPIN from real signed or buy/sell volume data.
    
    The function does not infer buy/sell volume from OHLC prices. Provide either
    ``buy_volume_col`` and ``sell_volume_col`` or ``signed_volume_col`` plus
    ``volume_col``. With ``bucket_volume=None`` it emits a bar-window VPIN ratio;
    with ``bucket_volume`` it uses causal volume buckets and forward-fills the
    last completed bucket estimate.
    
    YAML declaration::
    
        features:
          - step: vpin
            params: {}
    
    Required input columns
    ----------------------
    buy_volume_col:
        Input column configured by ``buy_volume_col``. Default: ``buy_volume``.
    sell_volume_col:
        Input column configured by ``sell_volume_col``. Default: ``sell_volume``.
    volume_col:
        Input column configured by ``volume_col``. Default: ``volume``.
    
    Parameters
    ----------
    buy_volume_col:
        Input dataframe column name consumed by the component. Default: ``buy_volume``.
    sell_volume_col:
        Input dataframe column name consumed by the component. Default: ``sell_volume``.
    signed_volume_col:
        Input dataframe column name consumed by the component. Default: ``None``.
    volume_col:
        Input dataframe column name consumed by the component. Default: ``volume``.
    window:
        Lookback, forecast horizon, or bar-count parameter used by the component. Default: ``50``.
    bucket_volume:
        Configuration value used by the registered component. Default: ``None``.
    output_col:
        Output column name emitted by the component. Default: ``None``.
    """
    _validate_positive_int(window, name="window")
    if bucket_volume is not None and (not isinstance(bucket_volume, Real) or isinstance(bucket_volume, bool) or bucket_volume <= 0):
        raise ValueError("bucket_volume must be a positive number when provided.")
    col = _resolve_output_col(output_col, f"vpin_{window}")

    out = df.copy()
    signed_volume, total_volume = _resolve_volume_inputs(
        out,
        buy_volume_col=buy_volume_col,
        sell_volume_col=sell_volume_col,
        signed_volume_col=signed_volume_col,
        volume_col=volume_col,
    )
    if bucket_volume is None:
        imbalance = signed_volume.abs()
        denominator = total_volume.rolling(window=window, min_periods=window).sum()
        out[col] = imbalance.rolling(window=window, min_periods=window).sum() / denominator.replace(0.0, np.nan)
    else:
        out[col] = _bucketed_vpin(
            signed_volume.to_numpy(dtype=float),
            total_volume.to_numpy(dtype=float),
            index=out.index,
            bucket_volume=float(bucket_volume),
            window=window,
        )
    return out


def _resolve_volume_inputs(
    df: pd.DataFrame,
    *,
    buy_volume_col: str | None,
    sell_volume_col: str | None,
    signed_volume_col: str | None,
    volume_col: str,
) -> tuple[pd.Series, pd.Series]:
    if signed_volume_col is not None:
        _validate_columns(df, [signed_volume_col, volume_col], feature="VPIN")
        signed = df[signed_volume_col].astype(float)
        total = df[volume_col].astype(float)
        return signed, total

    if buy_volume_col is not None and sell_volume_col is not None:
        _validate_columns(df, [buy_volume_col, sell_volume_col], feature="VPIN")
        buy = df[buy_volume_col].astype(float)
        sell = df[sell_volume_col].astype(float)
        return buy - sell, buy + sell

    raise KeyError(
        "Missing columns for VPIN: provide either buy_volume_col and sell_volume_col, "
        "or signed_volume_col plus volume_col."
    )


def _bucketed_vpin(
    signed_volume: np.ndarray,
    total_volume: np.ndarray,
    *,
    index: pd.Index,
    bucket_volume: float,
    window: int,
) -> pd.Series:
    values = np.full(total_volume.size, np.nan, dtype=float)
    bucket_imbalances: list[float] = []
    current_volume = 0.0
    current_signed = 0.0
    last_vpin = np.nan

    for idx, (signed, volume) in enumerate(zip(signed_volume, total_volume, strict=True)):
        if not np.isfinite(signed) or not np.isfinite(volume) or volume < 0.0:
            values[idx] = last_vpin
            continue
        remaining = float(volume)
        signed_density = 0.0 if volume == 0.0 else float(signed) / float(volume)
        while remaining > 0.0:
            fill = min(bucket_volume - current_volume, remaining)
            current_volume += fill
            current_signed += fill * signed_density
            remaining -= fill
            if current_volume >= bucket_volume - 1e-12:
                bucket_imbalances.append(abs(current_signed))
                if len(bucket_imbalances) >= window:
                    last_vpin = float(np.mean(bucket_imbalances[-window:]) / bucket_volume)
                current_volume = 0.0
                current_signed = 0.0
        values[idx] = last_vpin
    return pd.Series(values, index=index, dtype="float64")


def _validate_columns(df: pd.DataFrame, columns: list[str], *, feature: str) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for {feature}: {missing}")


def _validate_positive_int(value: int, *, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Integral) or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")


def _resolve_output_col(output_col: str | None, default: str) -> str:
    if output_col is None:
        return default
    if not isinstance(output_col, str) or not output_col.strip():
        raise ValueError("output_col must be a non-empty string.")
    return output_col


__all__ = [
    "add_vpin",
]
