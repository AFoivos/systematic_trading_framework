from __future__ import annotations

from numbers import Integral

import numpy as np
import pandas as pd

from src.features.technical.ppo import compute_ppo


def add_ppo_rms(
    df: pd.DataFrame,
    source_col: str | None = "ppo_hist",
    price_col: str = "close",
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    use_histogram: bool = True,
    window: int = 20,
    output_col: str | None = None,
) -> pd.DataFrame:
    """Add trailing RMS of an existing PPO/PPO histogram or computed PPO series.

    When ``source_col`` is provided it must exist and is used directly. Set
    ``source_col=None`` to compute PPO causally from ``price_col``.
    """
    _validate_window(window, name="window")
    col = _resolve_output_col(output_col, f"ppo_rms_{window}")

    if source_col is not None:
        _validate_columns(df, [source_col], feature="PPO RMS")
        source = df[source_col].astype(float)
    else:
        _validate_span(fast, name="fast")
        _validate_span(slow, name="slow")
        _validate_span(signal, name="signal")
        if fast >= slow:
            raise ValueError("fast must be smaller than slow when computing PPO.")
        _validate_columns(df, [price_col], feature="PPO RMS")
        ppo = compute_ppo(df[price_col].astype(float), fast=fast, slow=slow, signal=signal)
        source = ppo[f"ppo_hist_{fast}_{slow}_{signal}" if use_histogram else f"ppo_{fast}_{slow}"]

    out = df.copy()
    out[col] = np.sqrt(source.pow(2).rolling(window=window, min_periods=window).mean())
    return out


def _validate_columns(df: pd.DataFrame, columns: list[str], *, feature: str) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for {feature}: {missing}")


def _validate_window(window: int, *, name: str) -> None:
    if isinstance(window, bool) or not isinstance(window, Integral) or window <= 0:
        raise ValueError(f"{name} must be a positive integer.")


def _validate_span(span: int, *, name: str) -> None:
    if isinstance(span, bool) or not isinstance(span, Integral) or span <= 0:
        raise ValueError(f"{name} must be a positive integer.")


def _resolve_output_col(output_col: str | None, default: str) -> str:
    if output_col is None:
        return default
    if not isinstance(output_col, str) or not output_col.strip():
        raise ValueError("output_col must be a non-empty string.")
    return output_col


__all__ = [
    "add_ppo_rms",
]
