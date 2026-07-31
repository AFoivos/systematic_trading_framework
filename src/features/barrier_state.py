from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from src.features.helpers.rolling_linear_regression import compute_rolling_linear_regression
from src.features.session_context import index_in_timezone, session_mask


def _require_columns(df: pd.DataFrame, columns: Sequence[str], *, family: str) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for {family}: {missing}")


def _positive_window(value: int, *, name: str, minimum: int = 2) -> int:
    if isinstance(value, bool) or int(value) < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}.")
    return int(value)


def _safe_divide(numerator: pd.Series, denominator: pd.Series, *, epsilon: float) -> pd.Series:
    denom = denominator.astype(float)
    return numerator.astype(float) / denom.where(denom.abs() > epsilon)


def _rolling_zscore(series: pd.Series, window: int, *, epsilon: float) -> pd.Series:
    mean = series.rolling(window, min_periods=window).mean()
    std = series.rolling(window, min_periods=window).std(ddof=0)
    return (series - mean) / std.where(std > epsilon)


def _rolling_percentile(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=window).apply(
        lambda values: float(np.mean(values <= values[-1])),
        raw=True,
    )


def add_barrier_equilibrium_features(
    df: pd.DataFrame,
    *,
    close_col: str = "close",
    high_col: str = "high",
    low_col: str = "low",
    atr_col: str = "atr_14",
    kalman_level_col: str | None = "kalman_level",
    kalman_level_is_log: bool = True,
    vwap_col: str | None = "vwap_48",
    window: int = 48,
    zscore_window: int = 96,
    robust_median_window: int = 5,
    epsilon: float = 1e-12,
    inplace: bool = False,
) -> pd.DataFrame:
    """Describe price location relative to causal local-equilibrium estimates.

    YAML declaration::

        features:
          - step: barrier_equilibrium
            params:
              close_col: close
              high_col: high
              low_col: low
              atr_col: atr_14
              window: 48
              zscore_window: 96

    Required input columns
    ----------------------
    close_col, high_col, low_col, atr_col:
        Point-in-time price and ATR columns. Configured Kalman/VWAP columns are
        also required when they are not ``null``.

    Parameters
    ----------
    window, zscore_window, robust_median_window:
        Strictly trailing windows used for local levels and normalization.
    kalman_level_is_log:
        Exponentiate the configured Kalman level before computing deviations.
    """
    resolved_window = _positive_window(window, name="window")
    resolved_z_window = _positive_window(zscore_window, name="zscore_window")
    median_window = _positive_window(robust_median_window, name="robust_median_window")
    _require_columns(df, [close_col, high_col, low_col, atr_col], family="barrier equilibrium")
    out = df if inplace else df.copy()
    close = pd.to_numeric(out[close_col], errors="coerce").astype(float)
    high = pd.to_numeric(out[high_col], errors="coerce").astype(float)
    low = pd.to_numeric(out[low_col], errors="coerce").astype(float)
    atr = pd.to_numeric(out[atr_col], errors="coerce").astype(float)

    rolling_median = close.rolling(resolved_window, min_periods=resolved_window).median()
    median_filtered = close.rolling(median_window, min_periods=median_window).median()
    robust_slope, robust_intercept, _ = compute_rolling_linear_regression(
        median_filtered,
        window=resolved_window,
    )
    robust_level = robust_intercept.astype(float) + robust_slope.astype(float) * float(resolved_window - 1)
    rolling_high = high.rolling(resolved_window, min_periods=resolved_window).max()
    rolling_low = low.rolling(resolved_window, min_periods=resolved_window).min()

    out[f"rolling_median_{resolved_window}"] = rolling_median.astype("float32")
    out[f"robust_regression_level_{resolved_window}"] = robust_level.astype("float32")
    out[f"range_position_{resolved_window}"] = _safe_divide(
        close - rolling_low,
        rolling_high - rolling_low,
        epsilon=epsilon,
    ).clip(0.0, 1.0).astype("float32")
    out[f"distance_local_high_atr_{resolved_window}"] = _safe_divide(
        rolling_high - close,
        atr,
        epsilon=epsilon,
    ).astype("float32")
    out[f"distance_local_low_atr_{resolved_window}"] = _safe_divide(
        close - rolling_low,
        atr,
        epsilon=epsilon,
    ).astype("float32")

    equilibria: dict[str, pd.Series] = {
        "median": rolling_median,
        "robust_regression": robust_level,
    }
    for name, configured_col in (("kalman", kalman_level_col), ("vwap", vwap_col)):
        if configured_col is None:
            continue
        if configured_col not in out.columns:
            raise KeyError(f"Configured {name} equilibrium column '{configured_col}' not found.")
        level = pd.to_numeric(out[configured_col], errors="coerce").astype(float)
        if name == "kalman" and kalman_level_is_log:
            level = np.exp(level)
        equilibria[name] = level

    for name, level in equilibria.items():
        deviation_atr = _safe_divide(close - level, atr, epsilon=epsilon)
        out[f"deviation_{name}_atr"] = deviation_atr.astype("float32")
        out[f"deviation_{name}_z_{resolved_z_window}"] = _rolling_zscore(
            deviation_atr,
            resolved_z_window,
            epsilon=epsilon,
        ).astype("float32")
    return out


def _run_length(signs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    up = np.zeros(len(signs), dtype=float)
    down = np.zeros(len(signs), dtype=float)
    up_count = 0
    down_count = 0
    for idx, value in enumerate(signs):
        if np.isfinite(value) and value > 0.0:
            up_count += 1
            down_count = 0
        elif np.isfinite(value) and value < 0.0:
            down_count += 1
            up_count = 0
        else:
            up_count = 0
            down_count = 0
        up[idx] = up_count
        down[idx] = down_count
    return up, down


def _max_drawdown(values: np.ndarray) -> float:
    if not np.isfinite(values).all() or len(values) < 2:
        return np.nan
    peak = np.maximum.accumulate(values)
    return float(np.min(values / peak - 1.0))


def _max_drawup(values: np.ndarray) -> float:
    if not np.isfinite(values).all() or len(values) < 2:
        return np.nan
    trough = np.minimum.accumulate(values)
    return float(np.max(values / trough - 1.0))


def add_barrier_path_features(
    df: pd.DataFrame,
    *,
    open_col: str = "open",
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    atr_col: str = "atr_14",
    window: int = 48,
    epsilon: float = 1e-12,
    inplace: bool = False,
) -> pd.DataFrame:
    """Describe recent path asymmetry and excursions using trailing OHLC only.

    YAML declaration::

        features:
          - step: barrier_path
            params:
              open_col: open
              high_col: high
              low_col: low
              close_col: close
              atr_col: atr_14
              window: 48

    Required input columns
    ----------------------
    open_col, high_col, low_col, close_col, atr_col:
        Point-in-time OHLC and ATR columns.

    Parameters
    ----------
    window:
        Strictly trailing window for semivariance, efficiency, excursions,
        roughness, drawdown, and drawup features.
    """
    resolved_window = _positive_window(window, name="window", minimum=3)
    _require_columns(df, [open_col, high_col, low_col, close_col, atr_col], family="barrier path")
    out = df if inplace else df.copy()
    open_ = pd.to_numeric(out[open_col], errors="coerce").astype(float)
    high = pd.to_numeric(out[high_col], errors="coerce").astype(float)
    low = pd.to_numeric(out[low_col], errors="coerce").astype(float)
    close = pd.to_numeric(out[close_col], errors="coerce").astype(float)
    atr = pd.to_numeric(out[atr_col], errors="coerce").astype(float)
    returns = close.pct_change()
    squared = returns.pow(2)
    positive_semivariance = squared.where(returns > 0.0, 0.0).rolling(
        resolved_window,
        min_periods=resolved_window,
    ).mean()
    negative_semivariance = squared.where(returns < 0.0, 0.0).rolling(
        resolved_window,
        min_periods=resolved_window,
    ).mean()
    candle_range = high - low
    upper_wick = high - pd.concat([open_, close], axis=1).max(axis=1)
    lower_wick = pd.concat([open_, close], axis=1).min(axis=1) - low
    path_length = close.diff().abs().rolling(resolved_window - 1, min_periods=resolved_window - 1).sum()
    net_move = (close - close.shift(resolved_window - 1)).abs()
    start_price = close.shift(resolved_window - 1)
    rolling_high = high.rolling(resolved_window, min_periods=resolved_window).max()
    rolling_low = low.rolling(resolved_window, min_periods=resolved_window).min()
    up_runs, down_runs = _run_length(np.sign(returns.to_numpy(dtype=float)))

    out[f"positive_realized_semivariance_{resolved_window}"] = positive_semivariance.astype("float32")
    out[f"negative_realized_semivariance_{resolved_window}"] = negative_semivariance.astype("float32")
    out[f"semivariance_imbalance_{resolved_window}"] = (
        (positive_semivariance - negative_semivariance)
        / (positive_semivariance + negative_semivariance + epsilon)
    ).astype("float32")
    out["upper_wick_ratio"] = _safe_divide(upper_wick, candle_range, epsilon=epsilon).astype("float32")
    out["lower_wick_ratio"] = _safe_divide(lower_wick, candle_range, epsilon=epsilon).astype("float32")
    out["wick_asymmetry"] = _safe_divide(
        lower_wick - upper_wick,
        candle_range,
        epsilon=epsilon,
    ).astype("float32")
    out["candle_close_location"] = _safe_divide(close - low, candle_range, epsilon=epsilon).astype("float32")
    out["consecutive_up_transitions"] = pd.Series(up_runs, index=out.index, dtype="float32")
    out["consecutive_down_transitions"] = pd.Series(down_runs, index=out.index, dtype="float32")
    out[f"path_efficiency_{resolved_window}"] = _safe_divide(
        net_move,
        path_length,
        epsilon=epsilon,
    ).clip(0.0, 1.0).astype("float32")
    out[f"backward_mfe_atr_{resolved_window}"] = _safe_divide(
        rolling_high - start_price,
        atr,
        epsilon=epsilon,
    ).astype("float32")
    out[f"backward_mae_atr_{resolved_window}"] = _safe_divide(
        rolling_low - start_price,
        atr,
        epsilon=epsilon,
    ).astype("float32")
    out[f"return_path_roughness_{resolved_window}"] = _safe_divide(
        path_length,
        net_move + epsilon,
        epsilon=epsilon,
    ).astype("float32")
    out[f"maximum_drawdown_{resolved_window}"] = close.rolling(
        resolved_window,
        min_periods=resolved_window,
    ).apply(_max_drawdown, raw=True).astype("float32")
    out[f"maximum_drawup_{resolved_window}"] = close.rolling(
        resolved_window,
        min_periods=resolved_window,
    ).apply(_max_drawup, raw=True).astype("float32")
    return out


def add_barrier_persistence_features(
    df: pd.DataFrame,
    *,
    close_col: str = "close",
    residual_col: str = "deviation_kalman_atr",
    window: int = 96,
    variance_ratio_lag: int = 4,
    autocorrelation_lags: Sequence[int] = (1, 4, 8),
    include_adf: bool = False,
    adf_stride: int = 24,
    epsilon: float = 1e-12,
    inplace: bool = False,
) -> pd.DataFrame:
    """Estimate persistence/mean-reversion state without assigning a trade side.

    YAML declaration::

        features:
          - step: barrier_persistence
            params:
              close_col: close
              residual_col: deviation_kalman_atr
              window: 96
              variance_ratio_lag: 4
              autocorrelation_lags: [1, 4, 8]
              include_adf: false

    Required input columns
    ----------------------
    close_col, residual_col:
        Point-in-time close and equilibrium-residual columns.

    Parameters
    ----------
    window, variance_ratio_lag, autocorrelation_lags:
        Trailing persistence horizons. ``include_adf`` enables the optional
        rolling residual ADF diagnostic at ``adf_stride`` intervals.
    """
    resolved_window = _positive_window(window, name="window", minimum=8)
    vr_lag = _positive_window(variance_ratio_lag, name="variance_ratio_lag")
    if vr_lag >= resolved_window:
        raise ValueError("variance_ratio_lag must be smaller than window.")
    lags = [int(lag) for lag in autocorrelation_lags]
    if not lags or any(lag <= 0 or lag >= resolved_window for lag in lags):
        raise ValueError("autocorrelation_lags must contain positive values smaller than window.")
    _require_columns(df, [close_col, residual_col], family="barrier persistence")
    out = df if inplace else df.copy()
    close = pd.to_numeric(out[close_col], errors="coerce").astype(float)
    residual = pd.to_numeric(out[residual_col], errors="coerce").astype(float)
    log_close = np.log(close.where(close > 0.0))
    returns = log_close.diff()
    one_period_variance = returns.rolling(resolved_window, min_periods=resolved_window).var(ddof=1)
    lagged_returns = log_close.diff(vr_lag)
    lagged_variance = lagged_returns.rolling(resolved_window, min_periods=resolved_window).var(ddof=1)
    variance_ratio = lagged_variance / (float(vr_lag) * one_period_variance).where(
        one_period_variance.abs() > epsilon
    )
    slope, _, r2 = compute_rolling_linear_regression(log_close, window=resolved_window)
    time_index = pd.Series(np.arange(len(out), dtype=float), index=out.index)
    correlation_trend = close.rolling(resolved_window, min_periods=resolved_window).corr(time_index)
    lagged_residual = residual.shift(1)
    delta_residual = residual.diff()
    rolling_cov = lagged_residual.rolling(resolved_window, min_periods=resolved_window).cov(delta_residual)
    rolling_var = lagged_residual.rolling(resolved_window, min_periods=resolved_window).var(ddof=1)
    ou_beta = rolling_cov / rolling_var.where(rolling_var.abs() > epsilon)
    ou_half_life = (-np.log(2.0) / ou_beta).where(ou_beta < -epsilon)
    ou_half_life = ou_half_life.clip(lower=0.0, upper=float(resolved_window * 10))

    out[f"variance_ratio_{vr_lag}_{resolved_window}"] = variance_ratio.astype("float32")
    for lag in lags:
        out[f"return_autocorrelation_lag_{lag}_{resolved_window}"] = returns.rolling(
            resolved_window,
            min_periods=resolved_window,
        ).corr(returns.shift(lag)).astype("float32")
    out[f"rolling_regression_slope_{resolved_window}"] = slope.astype("float32")
    out[f"rolling_regression_r2_{resolved_window}"] = r2.astype("float32")
    out[f"ou_half_life_{resolved_window}"] = ou_half_life.astype("float32")
    out[f"correlation_trend_{resolved_window}"] = correlation_trend.astype("float32")

    if include_adf:
        stride = _positive_window(adf_stride, name="adf_stride", minimum=1)
        try:
            from statsmodels.tsa.stattools import adfuller
        except Exception as exc:  # pragma: no cover - dependency is declared by the project
            raise ImportError("Rolling residual ADF requires statsmodels.") from exc
        pvalues = np.full(len(out), np.nan, dtype=float)
        values = residual.to_numpy(dtype=float)
        for end in range(resolved_window - 1, len(out), stride):
            sample = values[end - resolved_window + 1 : end + 1]
            if np.isfinite(sample).all() and float(np.std(sample)) > epsilon:
                try:
                    pvalues[end] = float(adfuller(sample, maxlag=1, regression="c", autolag=None)[1])
                except (ValueError, np.linalg.LinAlgError):
                    pvalues[end] = np.nan
        out[f"residual_adf_pvalue_{resolved_window}"] = pd.Series(
            pvalues,
            index=out.index,
        ).ffill(limit=max(stride - 1, 0)).astype("float32")
    return out


def _cusum_states(values: np.ndarray, threshold: float) -> tuple[np.ndarray, np.ndarray]:
    positive = np.full(len(values), np.nan, dtype=float)
    negative = np.full(len(values), np.nan, dtype=float)
    pos_state = 0.0
    neg_state = 0.0
    for idx, value in enumerate(values):
        if not np.isfinite(value):
            pos_state = 0.0
            neg_state = 0.0
            continue
        pos_state = max(0.0, pos_state + float(value))
        neg_state = min(0.0, neg_state + float(value))
        positive[idx] = np.tanh(pos_state / threshold)
        negative[idx] = -np.tanh(abs(neg_state) / threshold)
        if pos_state >= threshold:
            pos_state = 0.0
        if abs(neg_state) >= threshold:
            neg_state = 0.0
    return positive, negative


def add_barrier_volatility_features(
    df: pd.DataFrame,
    *,
    close_col: str = "close",
    atr_col: str = "atr_14",
    short_window: int = 12,
    long_window: int = 48,
    percentile_window: int = 252,
    cusum_threshold: float = 5.0,
    epsilon: float = 1e-12,
    inplace: bool = False,
) -> pd.DataFrame:
    """Describe volatility, jump, CUSUM, and change-point state causally.

    YAML declaration::

        features:
          - step: barrier_volatility
            params:
              close_col: close
              atr_col: atr_14
              short_window: 12
              long_window: 48
              percentile_window: 252
              cusum_threshold: 5.0

    Required input columns
    ----------------------
    close_col, atr_col:
        Point-in-time close and ATR columns.

    Parameters
    ----------
    short_window, long_window, percentile_window:
        Strictly trailing volatility and normalization windows.
    cusum_threshold:
        Positive threshold for the causal standardized-return CUSUM states.
    """
    short = _positive_window(short_window, name="short_window", minimum=3)
    long = _positive_window(long_window, name="long_window", minimum=4)
    percentile = _positive_window(percentile_window, name="percentile_window", minimum=long)
    if short >= long:
        raise ValueError("short_window must be smaller than long_window.")
    if not np.isfinite(cusum_threshold) or cusum_threshold <= 0.0:
        raise ValueError("cusum_threshold must be finite and > 0.")
    _require_columns(df, [close_col, atr_col], family="barrier volatility")
    out = df if inplace else df.copy()
    close = pd.to_numeric(out[close_col], errors="coerce").astype(float)
    atr = pd.to_numeric(out[atr_col], errors="coerce").astype(float)
    returns = np.log(close.where(close > 0.0)).diff()
    realized_var_short = returns.pow(2).rolling(short, min_periods=short).sum()
    realized_var_long = returns.pow(2).rolling(long, min_periods=long).sum()
    realized_vol_short = np.sqrt(realized_var_short)
    realized_vol_long = np.sqrt(realized_var_long)
    bipower = (np.pi / 2.0) * (returns.abs() * returns.shift(1).abs()).rolling(
        long,
        min_periods=long,
    ).sum()
    jump_variation = (realized_var_long - bipower).clip(lower=0.0)
    jump_share = jump_variation / (realized_var_long + epsilon)
    atr_percentile = _rolling_percentile(atr, percentile)
    normalized_returns = returns / returns.rolling(long, min_periods=long).std(ddof=0).where(
        lambda values: values > epsilon
    )
    cusum_positive, cusum_negative = _cusum_states(
        normalized_returns.to_numpy(dtype=float),
        float(cusum_threshold),
    )
    short_mean = returns.rolling(short, min_periods=short).mean()
    long_mean = returns.rolling(long, min_periods=long).mean()
    long_std = returns.rolling(long, min_periods=long).std(ddof=0)
    mean_shift_score = (short_mean - long_mean).abs() / long_std.where(long_std > epsilon)
    variance_shift_score = (realized_vol_short / realized_vol_long.where(realized_vol_long > epsilon) - 1.0).abs()
    change_score = mean_shift_score.fillna(0.0) + variance_shift_score.fillna(0.0)
    change_probability_proxy = 1.0 - np.exp(-change_score.clip(lower=0.0))

    out[f"realized_volatility_{short}"] = realized_vol_short.astype("float32")
    out[f"realized_volatility_{long}"] = realized_vol_long.astype("float32")
    out[f"short_long_volatility_ratio_{short}_{long}"] = (
        realized_vol_short / realized_vol_long.where(realized_vol_long > epsilon)
    ).astype("float32")
    out[f"bipower_variation_{long}"] = bipower.astype("float32")
    out[f"jump_variation_{long}"] = jump_variation.astype("float32")
    out[f"jump_share_{long}"] = jump_share.astype("float32")
    out[f"atr_percentile_{percentile}"] = atr_percentile.astype("float32")
    out["cusum_positive_state"] = pd.Series(cusum_positive, index=out.index, dtype="float32")
    out["cusum_negative_state"] = pd.Series(cusum_negative, index=out.index, dtype="float32")
    out[f"change_point_probability_proxy_{short}_{long}"] = change_probability_proxy.astype("float32")
    return out


def _sample_entropy(values: np.ndarray, *, tolerance_scale: float = 0.2) -> float:
    if not np.isfinite(values).all() or len(values) < 8:
        return np.nan
    tolerance = float(tolerance_scale * np.std(values))
    if tolerance <= 0.0:
        return 0.0

    def count_matches(order: int) -> int:
        vectors = np.asarray([values[idx : idx + order] for idx in range(len(values) - order + 1)])
        count = 0
        for idx in range(len(vectors) - 1):
            distance = np.max(np.abs(vectors[idx + 1 :] - vectors[idx]), axis=1)
            count += int(np.sum(distance <= tolerance))
        return count

    matches_m = count_matches(2)
    matches_m1 = count_matches(3)
    if matches_m <= 0 or matches_m1 <= 0:
        return np.nan
    return float(-np.log(matches_m1 / matches_m))


def add_barrier_market_organization_features(
    df: pd.DataFrame,
    *,
    shannon_entropy_col: str = "shannon_entropy_48",
    permutation_entropy_col: str = "permutation_entropy_48",
    returns_col: str | None = None,
    close_col: str = "close",
    window: int = 48,
    percentile_window: int = 252,
    include_sample_entropy: bool = False,
    inplace: bool = False,
) -> pd.DataFrame:
    """Add changes and trailing percentiles to registered entropy estimates.

    YAML declaration::

        features:
          - step: barrier_market_organization
            params:
              shannon_entropy_col: shannon_entropy_48
              permutation_entropy_col: permutation_entropy_48
              window: 48
              percentile_window: 252
              include_sample_entropy: false

    Required input columns
    ----------------------
    shannon_entropy_col, permutation_entropy_col:
        Previously computed point-in-time entropy columns. ``returns_col`` or
        ``close_col`` is additionally required when sample entropy is enabled.

    Parameters
    ----------
    window, percentile_window:
        Trailing sample-entropy and empirical-percentile windows.
    include_sample_entropy:
        Opt-in higher-cost sample entropy calculation.
    """
    resolved_window = _positive_window(window, name="window", minimum=8)
    percentile = _positive_window(percentile_window, name="percentile_window", minimum=resolved_window)
    _require_columns(
        df,
        [shannon_entropy_col, permutation_entropy_col],
        family="barrier market organization",
    )
    out = df if inplace else df.copy()
    for name, column in (("shannon", shannon_entropy_col), ("permutation", permutation_entropy_col)):
        entropy = pd.to_numeric(out[column], errors="coerce").astype(float)
        out[f"{name}_entropy_change"] = entropy.diff().astype("float32")
        out[f"{name}_entropy_percentile_{percentile}"] = _rolling_percentile(
            entropy,
            percentile,
        ).astype("float32")
    if include_sample_entropy:
        if returns_col is not None:
            _require_columns(out, [returns_col], family="sample entropy")
            source = pd.to_numeric(out[returns_col], errors="coerce").astype(float)
        else:
            _require_columns(out, [close_col], family="sample entropy")
            source = np.log(pd.to_numeric(out[close_col], errors="coerce").astype(float)).diff()
        out[f"sample_entropy_{resolved_window}"] = source.rolling(
            resolved_window,
            min_periods=resolved_window,
        ).apply(_sample_entropy, raw=True).astype("float32")
    return out


def add_barrier_microstructure_features(
    df: pd.DataFrame,
    *,
    open_col: str = "open",
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    volume_col: str = "volume",
    window: int = 48,
    baseline_window: int = 252,
    volume_is_tick_activity: bool = False,
    epsilon: float = 1e-12,
    inplace: bool = False,
) -> pd.DataFrame:
    """Build explicitly named bar/tick-activity proxies; never claim true OFI.

    YAML declaration::

        features:
          - step: barrier_microstructure
            params:
              open_col: open
              high_col: high
              low_col: low
              close_col: close
              volume_col: volume
              window: 48
              baseline_window: 252
              volume_is_tick_activity: true

    Required input columns
    ----------------------
    open_col, high_col, low_col, close_col, volume_col:
        Point-in-time OHLC and reviewed tick-activity columns.

    Parameters
    ----------
    volume_is_tick_activity:
        Must be explicitly true to acknowledge that the volume input is a
        proxy and not exchange order flow.
    window, baseline_window:
        Strictly trailing aggregation and normalization windows.
    """
    if not volume_is_tick_activity:
        raise ValueError(
            "barrier_microstructure requires volume_is_tick_activity=true after source-volume review."
        )
    resolved_window = _positive_window(window, name="window", minimum=4)
    baseline = _positive_window(baseline_window, name="baseline_window", minimum=resolved_window)
    _require_columns(
        df,
        [open_col, high_col, low_col, close_col, volume_col],
        family="barrier microstructure",
    )
    out = df if inplace else df.copy()
    open_ = pd.to_numeric(out[open_col], errors="coerce").astype(float)
    high = pd.to_numeric(out[high_col], errors="coerce").astype(float)
    low = pd.to_numeric(out[low_col], errors="coerce").astype(float)
    close = pd.to_numeric(out[close_col], errors="coerce").astype(float)
    volume = pd.to_numeric(out[volume_col], errors="coerce").astype(float).clip(lower=0.0)
    returns = close.pct_change()
    direction = np.sign(close - open_)
    signed_activity = direction * volume
    rolling_volume = volume.rolling(resolved_window, min_periods=resolved_window).sum()
    tick_flow_proxy = signed_activity.rolling(resolved_window, min_periods=resolved_window).sum() / (
        rolling_volume + epsilon
    )
    activity_ratio = volume / volume.rolling(baseline, min_periods=baseline).median().where(
        lambda values: values > epsilon
    )
    impact = returns.abs() / (volume + epsilon)
    impact_baseline = impact.rolling(baseline, min_periods=baseline).median()
    low_impact_score = (1.0 - (impact / (impact_baseline + epsilon)).clip(0.0, 1.0)).clip(0.0, 1.0)
    candle_range = high - low
    lower_wick_ratio = _safe_divide(
        pd.concat([open_, close], axis=1).min(axis=1) - low,
        candle_range,
        epsilon=epsilon,
    ).clip(0.0, 1.0)
    upper_wick_ratio = _safe_divide(
        high - pd.concat([open_, close], axis=1).max(axis=1),
        candle_range,
        epsilon=epsilon,
    ).clip(0.0, 1.0)
    selling_activity = (-signed_activity).clip(lower=0.0) / (volume + epsilon)
    buying_activity = signed_activity.clip(lower=0.0) / (volume + epsilon)

    out[f"tick_flow_proxy_{resolved_window}"] = tick_flow_proxy.astype("float32")
    out[f"signed_tick_volume_imbalance_proxy_{resolved_window}"] = tick_flow_proxy.astype("float32")
    out[f"tick_activity_ratio_{baseline}"] = activity_ratio.astype("float32")
    out["price_impact_per_tick_volume_proxy"] = impact.astype("float32")
    out[f"amihud_tick_illiquidity_proxy_{resolved_window}"] = impact.rolling(
        resolved_window,
        min_periods=resolved_window,
    ).mean().astype("float32")
    out["bullish_absorption_proxy"] = (
        selling_activity * lower_wick_ratio * low_impact_score
    ).clip(0.0, 1.0).astype("float32")
    out["bearish_absorption_proxy"] = (
        buying_activity * upper_wick_ratio * low_impact_score
    ).clip(0.0, 1.0).astype("float32")
    return out


def _minutes_from_session_open(minutes: np.ndarray, start: int, end: int) -> tuple[np.ndarray, np.ndarray]:
    start_minute = int(start) * 60
    end_minute = int(end) * 60
    if start_minute < end_minute:
        active = (minutes >= start_minute) & (minutes < end_minute)
        since = minutes - start_minute
        to_close = end_minute - minutes
    else:
        active = (minutes >= start_minute) | (minutes < end_minute)
        since = np.where(minutes >= start_minute, minutes - start_minute, minutes + 1440 - start_minute)
        to_close = np.where(minutes < end_minute, end_minute - minutes, end_minute + 1440 - minutes)
    return np.where(active, since, np.nan), np.where(active, to_close, np.nan)


def add_barrier_session_features(
    df: pd.DataFrame,
    *,
    timezone: str = "UTC",
    spread_col: str | None = "spread_bps",
    activity_col: str | None = "volume",
    percentile_window: int = 252,
    sessions: Mapping[str, Sequence[int]] | None = None,
    inplace: bool = False,
) -> pd.DataFrame:
    """Add session timing and causal spread/activity percentiles.

    YAML declaration::

        features:
          - step: barrier_session
            params:
              timezone: UTC
              spread_col: spread_bps
              activity_col: volume
              percentile_window: 252

    Required input columns
    ----------------------
    spread_col, activity_col:
        Point-in-time liquidity columns when configured. The dataframe index
        must be datetime-like for timezone/session calculations.

    Parameters
    ----------
    timezone, sessions:
        Local timezone and optional session ``[start_hour, end_hour]`` pairs.
    percentile_window:
        Strictly trailing liquidity percentile window.
    """
    percentile = _positive_window(percentile_window, name="percentile_window", minimum=8)
    out = df if inplace else df.copy()
    local_index = index_in_timezone(out.index, timezone)
    hour = local_index.hour.to_numpy(dtype=float)
    day = local_index.dayofweek.to_numpy(dtype=float)
    minute_of_day = local_index.hour.to_numpy(dtype=int) * 60 + local_index.minute.to_numpy(dtype=int)
    out["hour_sin_24"] = np.sin(2.0 * np.pi * hour / 24.0).astype("float32")
    out["hour_cos_24"] = np.cos(2.0 * np.pi * hour / 24.0).astype("float32")
    out["day_of_week_sin_7"] = np.sin(2.0 * np.pi * day / 7.0).astype("float32")
    out["day_of_week_cos_7"] = np.cos(2.0 * np.pi * day / 7.0).astype("float32")

    configured_sessions: dict[str, tuple[int, int]] = {
        "asia": (0, 8),
        "london": (7, 16),
        "new_york": (13, 21),
    }
    if sessions is not None:
        for name, bounds in dict(sessions).items():
            if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
                raise ValueError("sessions entries must be [start_hour, end_hour] pairs.")
            configured_sessions[str(name)] = (int(bounds[0]), int(bounds[1]))
    flags: dict[str, pd.Series] = {}
    hours_index = pd.Index(local_index.hour, dtype="int32")
    for name, (start, end) in configured_sessions.items():
        flags[name] = session_mask(hours_index, out.index, start_hour=start, end_hour=end)
        out[f"session_{name}"] = flags[name]
        since_open, to_close = _minutes_from_session_open(minute_of_day, start, end)
        out[f"minutes_since_{name}_open"] = since_open.astype("float32")
        out[f"minutes_to_{name}_close"] = to_close.astype("float32")
    if {"london", "new_york"}.issubset(flags):
        out["session_london_new_york_overlap"] = (
            (flags["london"] > 0.0) & (flags["new_york"] > 0.0)
        ).astype("float32")
    if spread_col is not None:
        _require_columns(out, [spread_col], family="barrier session spread")
        out[f"spread_percentile_{percentile}"] = _rolling_percentile(
            pd.to_numeric(out[spread_col], errors="coerce").astype(float),
            percentile,
        ).astype("float32")
    if activity_col is not None:
        _require_columns(out, [activity_col], family="barrier session activity")
        out[f"activity_percentile_{percentile}"] = _rolling_percentile(
            pd.to_numeric(out[activity_col], errors="coerce").astype(float),
            percentile,
        ).astype("float32")
    return out


__all__ = [
    "add_barrier_equilibrium_features",
    "add_barrier_market_organization_features",
    "add_barrier_microstructure_features",
    "add_barrier_path_features",
    "add_barrier_persistence_features",
    "add_barrier_session_features",
    "add_barrier_volatility_features",
]
