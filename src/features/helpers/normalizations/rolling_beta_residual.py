from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.helpers.common import output_column, positive_int, require_columns

from ._common import clean_numeric, finite_non_negative, optional_min_periods


def add_rolling_beta_residual_features(
    df: pd.DataFrame,
    *,
    asset_return_col: str,
    benchmark_return_col: str,
    window: int = 252,
    min_periods: int | None = None,
    residual_col: str | None = None,
    beta_col: str | None = None,
    alpha_col: str | None = None,
    shift_stats: bool = True,
    eps: float = 1e-12,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``rolling_beta_residual`` normalization helper transformation.

    Fits a trailing single-factor beta and emits the current residual. By
    default, rolling beta/alpha use history ending at ``t-1``.
    """
    require_columns(df, [asset_return_col, benchmark_return_col], owner="rolling beta residual normalization")
    resolved_window = positive_int(window, field="window")
    if resolved_window <= 1:
        raise ValueError("window must be > 1.")
    resolved_min_periods = optional_min_periods(min_periods, window=resolved_window)
    resolved_eps = finite_non_negative(eps, field="eps")

    out = df if inplace else df.copy()
    asset = clean_numeric(out[asset_return_col])
    benchmark = clean_numeric(out[benchmark_return_col])
    benchmark_mean = benchmark.rolling(resolved_window, min_periods=resolved_min_periods).mean()
    asset_mean = asset.rolling(resolved_window, min_periods=resolved_min_periods).mean()
    covariance = asset.rolling(resolved_window, min_periods=resolved_min_periods).cov(benchmark)
    variance = benchmark.rolling(resolved_window, min_periods=resolved_min_periods).var(ddof=1)
    beta = covariance / variance.where(variance.abs() > resolved_eps, np.nan)
    alpha = asset_mean - beta * benchmark_mean
    if shift_stats:
        beta = beta.shift(1)
        alpha = alpha.shift(1)
    residual = asset - (alpha + beta * benchmark)

    resolved_residual_col = output_column(
        residual_col,
        default=f"{asset_return_col}_residual_vs_{benchmark_return_col}_{resolved_window}",
        field="residual_col",
    )
    out[resolved_residual_col] = residual.astype("float32")
    if beta_col is not None:
        out[
            output_column(
                beta_col,
                default=f"{asset_return_col}_beta_vs_{benchmark_return_col}_{resolved_window}",
                field="beta_col",
            )
        ] = beta.astype("float32")
    if alpha_col is not None:
        out[
            output_column(
                alpha_col,
                default=f"{asset_return_col}_alpha_vs_{benchmark_return_col}_{resolved_window}",
                field="alpha_col",
            )
        ] = alpha.astype("float32")
    return out


__all__ = ["add_rolling_beta_residual_features"]
