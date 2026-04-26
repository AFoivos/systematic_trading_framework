from __future__ import annotations

import numpy as np
import pandas as pd

from src.utils.column_selectors import resolve_single_column_selector


_ALLOWED_MODES = {"long_only", "short_only", "long_short", "long_short_hold"}
_ALLOWED_FILTER_OPS = {"gt", "ge", "lt", "le"}


def _resolve_activation_filter_mask(
    df: pd.DataFrame,
    *,
    index: pd.Index,
    activation_filters: list[dict[str, object]] | None,
) -> pd.Series:
    """
    Build a boolean activation mask from config-defined column filters.

    Filters are applied causally on already-available feature columns and therefore
    can be used to gate trading activity without introducing additional model logic.
    """
    mask = pd.Series(True, index=index, dtype=bool)
    if not activation_filters:
        return mask

    for idx, raw_filter in enumerate(activation_filters):
        if not isinstance(raw_filter, dict):
            raise ValueError(f"activation_filters[{idx}] must be a mapping.")
        raw_col = raw_filter.get("col")
        raw_selector = raw_filter.get("selector")
        has_col = raw_col is not None
        has_selector = raw_selector is not None
        if has_col == has_selector:
            raise ValueError(f"activation_filters[{idx}] must define exactly one of col or selector.")
        if has_col:
            if not isinstance(raw_col, str) or not raw_col:
                raise ValueError(f"activation_filters[{idx}].col must be a non-empty string.")
            if raw_col not in df.columns:
                raise KeyError(f"activation_filters[{idx}].col '{raw_col}' not found in DataFrame")
            col = raw_col
        else:
            col = resolve_single_column_selector(
                [str(column) for column in df.columns],
                raw_selector,  # type: ignore[arg-type]
                field=f"activation_filters[{idx}].selector",
            )
        op = str(raw_filter.get("op", "ge"))
        if op not in _ALLOWED_FILTER_OPS:
            raise ValueError(
                f"activation_filters[{idx}].op must be one of {_ALLOWED_FILTER_OPS}, got '{op}'."
            )
        if "value" not in raw_filter:
            raise ValueError(f"activation_filters[{idx}].value is required.")
        value = float(raw_filter["value"])
        use_abs = bool(raw_filter.get("use_abs", False))

        series = df.loc[index, col].astype(float)
        if use_abs:
            series = series.abs()

        current = series.notna()
        if op == "gt":
            current &= series > value
        elif op == "ge":
            current &= series >= value
        elif op == "lt":
            current &= series < value
        elif op == "le":
            current &= series <= value
        mask &= current.fillna(False)

    return mask


def compute_forecast_threshold_signal(
    df: pd.DataFrame,
    forecast_col: str = "pred_ret",
    *,
    upper: float = 0.0,
    lower: float | None = None,
    signal_col: str = "forecast_threshold_signal",
    mode: str = "long_short_hold",
) -> pd.DataFrame:
    """
    Convert return forecasts into thresholded directional exposure.
    """
    if forecast_col not in df.columns:
        raise KeyError(f"forecast_col '{forecast_col}' not found in DataFrame")
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of {_ALLOWED_MODES}")

    out = df.copy()
    series = out[forecast_col].astype(float)
    out[signal_col] = 0.0

    if lower is None:
        lower = -abs(float(upper))

    long_mask = series > float(upper)
    short_mask = series < float(lower)
    if mode == "long_short_hold":
        hold = pd.Series(np.nan, index=out.index, dtype=float)
        hold.loc[long_mask] = 1.0
        hold.loc[short_mask] = -1.0
        out[signal_col] = hold.ffill().fillna(0.0).astype(float)
        return out

    if mode in {"long_only", "long_short"}:
        out.loc[long_mask, signal_col] = 1.0
    if mode in {"short_only", "long_short"}:
        out.loc[short_mask, signal_col] = -1.0
    return out


def compute_forecast_vol_adjusted_signal(
    df: pd.DataFrame,
    forecast_col: str = "pred_ret",
    *,
    vol_col: str = "pred_vol",
    signal_col: str = "forecast_vol_adjusted_signal",
    clip: float = 1.0,
    vol_floor: float = 1e-6,
) -> pd.DataFrame:
    """
    Convert return and volatility forecasts into a continuous conviction-sized signal.
    """
    if forecast_col not in df.columns:
        raise KeyError(f"forecast_col '{forecast_col}' not found in DataFrame")
    if vol_col not in df.columns:
        raise KeyError(f"vol_col '{vol_col}' not found in DataFrame")
    if clip <= 0:
        raise ValueError("clip must be > 0.")
    if vol_floor <= 0:
        raise ValueError("vol_floor must be > 0.")

    out = df.copy()
    forecast = out[forecast_col].astype(float)
    vol = out[vol_col].astype(float).clip(lower=float(vol_floor))
    scaled = np.tanh(forecast / vol).astype(float) * float(clip)
    out[signal_col] = scaled.astype(float)
    return out


def compute_probability_vol_adjusted_signal(
    df: pd.DataFrame,
    prob_col: str = "pred_prob",
    *,
    vol_col: str = "pred_vol",
    signal_col: str = "probability_vol_adjusted_signal",
    prob_center: float = 0.5,
    upper: float | None = None,
    lower: float | None = None,
    vol_target: float | None = 0.001,
    clip: float = 1.0,
    vol_floor: float = 1e-6,
    min_signal_abs: float = 0.0,
    activation_filters: list[dict[str, object]] | None = None,
    top_quantile: float | None = None,
    top_quantile_window: int | None = None,
    max_trade_rate: float | None = None,
) -> pd.DataFrame:
    """
    Convert classifier probabilities into signed conviction and scale them by predicted
    volatility. This is intended for classifier + GARCH overlay setups.

    Optional activation filters can gate the signal to trade only in selected regimes
    (for example high-volatility or strong-trend states) using already-available
    feature columns.
    """
    if prob_col not in df.columns:
        raise KeyError(f"prob_col '{prob_col}' not found in DataFrame")
    if vol_col not in df.columns:
        raise KeyError(f"vol_col '{vol_col}' not found in DataFrame")
    if clip <= 0:
        raise ValueError("clip must be > 0.")
    if vol_floor <= 0:
        raise ValueError("vol_floor must be > 0.")
    if vol_target is not None and vol_target <= 0:
        raise ValueError("vol_target must be > 0.")
    if not 0.0 < prob_center < 1.0:
        raise ValueError("prob_center must be in (0, 1).")
    if upper is not None and not 0.0 < float(upper) < 1.0:
        raise ValueError("upper must be in (0, 1).")
    if lower is not None and not 0.0 < float(lower) < 1.0:
        raise ValueError("lower must be in (0, 1).")
    if min_signal_abs < 0:
        raise ValueError("min_signal_abs must be >= 0.")
    if top_quantile is None and max_trade_rate is not None:
        top_quantile = max_trade_rate
    if top_quantile is not None and not 0.0 < float(top_quantile) <= 1.0:
        raise ValueError("top_quantile must be in (0, 1].")
    if max_trade_rate is not None and not 0.0 < float(max_trade_rate) <= 1.0:
        raise ValueError("max_trade_rate must be in (0, 1].")
    if top_quantile_window is not None and int(top_quantile_window) <= 1:
        raise ValueError("top_quantile_window must be > 1 when provided.")

    if upper is None and lower is not None:
        lower = float(lower)
        upper = float(prob_center) + (float(prob_center) - lower)
    elif lower is None and upper is not None:
        upper = float(upper)
        lower = float(prob_center) - (upper - float(prob_center))
    if upper is not None and lower is not None:
        upper = float(upper)
        lower = float(lower)
        if not lower < float(prob_center) < upper:
            raise ValueError("lower < prob_center < upper must hold for probability dead-zone.")

    out = df.copy()
    probs = out[prob_col].astype(float)
    vol = out[vol_col].astype(float)
    valid_mask = probs.notna() & vol.notna()
    scaled = pd.Series(0.0, index=out.index, dtype=float)
    if bool(valid_mask.any()):
        probs_valid = probs.loc[valid_mask].clip(lower=0.0, upper=1.0)
        vol_valid = vol.loc[valid_mask].clip(lower=float(vol_floor))
        centered_all = (probs_valid - float(prob_center)) / max(float(prob_center), 1.0 - float(prob_center))
        active_mask = pd.Series(True, index=probs_valid.index, dtype=bool)
        if upper is not None and lower is not None:
            active_mask = (probs_valid > upper) | (probs_valid < lower)
        if activation_filters:
            filter_mask = _resolve_activation_filter_mask(
                out,
                index=probs_valid.index,
                activation_filters=activation_filters,
            )
            active_mask &= filter_mask
        if top_quantile is not None:
            abs_conviction = centered_all.abs()
            threshold_q = max(0.0, 1.0 - float(top_quantile))
            if top_quantile_window is not None:
                min_periods = max(2, min(int(top_quantile_window), 24))
                threshold = (
                    abs_conviction.rolling(int(top_quantile_window), min_periods=min_periods)
                    .quantile(threshold_q)
                    .shift(1)
                )
            else:
                threshold = abs_conviction.expanding(min_periods=2).quantile(threshold_q).shift(1)
            active_mask &= abs_conviction.ge(threshold.fillna(np.inf))
        if bool(active_mask.any()):
            probs_active = probs_valid.loc[active_mask]
            vol_active = vol_valid.loc[active_mask]
            centered = centered_all.loc[active_mask]
            if vol_target is None:
                scaled_input = centered
            else:
                scaled_input = centered * (float(vol_target) / vol_active)
            scaled_active = np.tanh(scaled_input).astype(float) * float(clip)
            if min_signal_abs > 0:
                scaled_active = np.where(np.abs(scaled_active) < float(min_signal_abs), 0.0, scaled_active)
            scaled.loc[probs_active.index] = scaled_active.astype(float)
    out[signal_col] = scaled.astype(float)
    return out


__all__ = [
    "compute_forecast_threshold_signal",
    "compute_forecast_vol_adjusted_signal",
    "compute_probability_vol_adjusted_signal",
]
