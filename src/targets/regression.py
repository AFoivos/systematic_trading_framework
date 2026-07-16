from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping

import numpy as np
import pandas as pd

from src.targets.output_aliases import apply_target_output_aliases
from src.targets.regression_helpers import (
    as_float_series,
    build_future_realized_volatility,
    build_future_return,
    build_return_series,
    finalize_regression_target,
    flatten_target_cfg,
    future_window,
    numeric_stats,
    positive_denominator,
    require_columns,
    require_finite_number,
    require_min_int,
    require_positive_int,
    validate_choice,
    validate_returns_type,
    volatility_normalizer,
)


REGRESSION_TARGET_KINDS = frozenset(
    {
        "volatility_normalized_future_return",
        "risk_adjusted_future_return",
        "r_multiple_regression",
        "mfe_regression",
        "mae_regression",
        "mfe_mae_ratio_regression",
        "downside_adjusted_future_return",
        "future_trend_slope",
        "future_path_efficiency",
        "excess_return_regression",
        "residual_return_regression",
        "future_range_regression",
        "future_realized_volatility",
        "future_drawdown_regression",
    }
)

# ``(default_horizon, minimum_horizon)`` for regression targets whose
# estimands require at least two future observations.  Builders and config
# validation consume this single contract so an accepted config is runnable.
REGRESSION_TARGET_HORIZON_CONTRACTS: Mapping[str, tuple[int, int]] = MappingProxyType(
    {
        "risk_adjusted_future_return": (2, 2),
        "future_trend_slope": (5, 2),
        "future_path_efficiency": (2, 2),
        "future_realized_volatility": (5, 2),
    }
)


def _cfg(target_cfg: dict[str, Any] | None) -> dict[str, Any]:
    return apply_target_output_aliases(flatten_target_cfg(target_cfg))


def _optional_col(cfg: dict[str, Any], key: str) -> str | None:
    value = cfg.get(key)
    return str(value) if value is not None else None


def _horizon(cfg: dict[str, Any], *, default: int = 1, minimum: int = 1) -> int:
    return require_min_int(
        cfg.get("horizon_bars", cfg.get("horizon", default)),
        field="target.horizon_bars",
        minimum=minimum,
    )


def _target_horizon(cfg: dict[str, Any], *, kind: str) -> int:
    default, minimum = REGRESSION_TARGET_HORIZON_CONTRACTS.get(kind, (1, 1))
    return _horizon(cfg, default=default, minimum=minimum)


def _finite(series: pd.Series) -> pd.Series:
    return series.astype(float).where(np.isfinite(series.astype(float))).astype(float)


def _future_extremes(
    out: pd.DataFrame,
    *,
    high_col: str,
    low_col: str,
    horizon: int,
) -> tuple[pd.Series, pd.Series]:
    require_columns(out, [high_col, low_col])
    high_window = future_window(as_float_series(out, high_col), horizon, prefix="high")
    low_window = future_window(as_float_series(out, low_col), horizon, prefix="low")
    valid = high_window.notna().all(axis=1) & low_window.notna().all(axis=1)
    max_high = high_window.max(axis=1).where(valid)
    min_low = low_window.min(axis=1).where(valid)
    return max_high.astype(float), min_low.astype(float)


def _mfe_mae_values(
    out: pd.DataFrame,
    *,
    price_col: str,
    high_col: str,
    low_col: str,
    horizon: int,
    direction: str,
) -> tuple[pd.Series, pd.Series]:
    direction = validate_choice(direction, field="target.direction", choices={"long", "short"})
    price = as_float_series(out, price_col)
    max_high, min_low = _future_extremes(out, high_col=high_col, low_col=low_col, horizon=horizon)
    if direction == "long":
        mfe = max_high / price - 1.0
        mae = min_low / price - 1.0
    else:
        mfe = 1.0 - min_low / price
        mae = 1.0 - max_high / price
    return _finite(mfe), _finite(mae)


def _maybe_vol_normalize(
    out: pd.DataFrame,
    target: pd.Series,
    *,
    normalize_by_volatility: bool,
    price_col: str,
    volatility_col: str,
    volatility_floor: float,
) -> pd.Series:
    if not normalize_by_volatility:
        return target.astype(float)
    normalizer = volatility_normalizer(
        out,
        price_col=price_col,
        volatility_col=volatility_col,
        volatility_floor=volatility_floor,
    )
    return (target.astype(float) / normalizer).astype(float)


def build_volatility_normalized_future_return_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Apply the registered ``volatility_normalized_future_return`` target transformation.

    YAML declaration::

        target:
          kind: volatility_normalized_future_return
          params:
            price_col: close
            volatility_col: atr_14
            horizon_bars: 1

    Required input columns
    ----------------------
    price_col, volatility_col, returns_col:
        Price, local volatility, and optional returns columns.

    Parameters
    ----------
    price_col, volatility_col, horizon_bars, returns_col, returns_type, volatility_floor, clip:
        Fixed-horizon return divided by local volatility over price.
    """
    cfg = _cfg(target_cfg)
    price_col = str(cfg.get("price_col", "close"))
    volatility_col = str(cfg.get("volatility_col", "atr_14"))
    returns_col = _optional_col(cfg, "returns_col")
    returns_type = validate_returns_type(cfg.get("returns_type", "simple"))
    if returns_col is None and returns_type == "log":
        raise ValueError("target.returns_type='log' requires target.returns_col.")
    horizon = _horizon(cfg)
    volatility_floor = require_finite_number(cfg.get("volatility_floor", 1e-12), field="target.volatility_floor")
    if volatility_floor <= 0.0:
        raise ValueError("target.volatility_floor must be > 0.")
    raw_fwd_col = str(cfg.get("raw_fwd_col", f"target_future_return_raw_{horizon}"))
    normalizer_col = str(cfg.get("normalizer_col", f"{volatility_col}*over*{price_col}"))
    fwd_col = str(cfg.get("fwd_col", f"target_vol_norm_return_{horizon}"))
    label_col = str(cfg.get("label_col", fwd_col))

    out = df.copy()
    raw_future = build_future_return(
        out,
        price_col=price_col,
        returns_col=returns_col,
        returns_type=returns_type,
        horizon=horizon,
    )
    normalizer = volatility_normalizer(
        out,
        price_col=price_col,
        volatility_col=volatility_col,
        volatility_floor=volatility_floor,
    )
    out[raw_fwd_col] = raw_future.astype(float)
    out[normalizer_col] = normalizer.astype(float)
    target = raw_future / normalizer
    return finalize_regression_target(
        out,
        target=target,
        kind="volatility_normalized_future_return",
        price_col=price_col,
        horizon=horizon,
        fwd_col=fwd_col,
        label_col=label_col,
        clip=cfg.get("clip"),
        intermediate_cols=[raw_fwd_col, normalizer_col],
        meta_extra={
            "returns_col": returns_col,
            "returns_type": returns_type,
            "volatility_col": volatility_col,
            "volatility_floor": volatility_floor,
            "raw_fwd_col": raw_fwd_col,
            "normalizer_col": normalizer_col,
            "raw_future_return_stats": numeric_stats(out[raw_fwd_col]),
        },
    )


def build_risk_adjusted_future_return_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Apply the registered ``risk_adjusted_future_return`` target transformation.

    YAML declaration::

        target:
          kind: risk_adjusted_future_return
          params:
            price_col: close
            horizon_bars: 2

    Required input columns
    ----------------------
    price_col, returns_col:
        Price column and optional one-step returns column.

    Parameters
    ----------
    price_col, returns_col, returns_type, horizon_bars, volatility_floor, clip:
        Future return divided by future realized volatility from the same horizon.
    """
    cfg = _cfg(target_cfg)
    price_col = str(cfg.get("price_col", "close"))
    returns_col = _optional_col(cfg, "returns_col")
    returns_type = validate_returns_type(cfg.get("returns_type", "simple"))
    if returns_col is None and returns_type == "log":
        raise ValueError("target.returns_type='log' requires target.returns_col.")
    horizon = _target_horizon(cfg, kind="risk_adjusted_future_return")
    volatility_floor = require_finite_number(cfg.get("volatility_floor", 1e-12), field="target.volatility_floor")
    raw_fwd_col = str(cfg.get("raw_fwd_col", f"target_future_return_raw_{horizon}"))
    realized_vol_col = str(cfg.get("realized_vol_col", f"target_realized_vol_{horizon}"))
    fwd_col = str(cfg.get("fwd_col", f"target_risk_adjusted_return_{horizon}"))
    label_col = str(cfg.get("label_col", fwd_col))

    out = df.copy()
    raw_future = build_future_return(
        out,
        price_col=price_col,
        returns_col=returns_col,
        returns_type=returns_type,
        horizon=horizon,
    )
    realized_vol = build_future_realized_volatility(
        out,
        price_col=price_col,
        returns_col=returns_col,
        returns_type=returns_type,
        horizon=horizon,
    )
    denom = positive_denominator(realized_vol, floor=volatility_floor, field="target.volatility_floor")
    out[raw_fwd_col] = raw_future.astype(float)
    out[realized_vol_col] = realized_vol.astype(float)
    return finalize_regression_target(
        out,
        target=raw_future / denom,
        kind="risk_adjusted_future_return",
        price_col=price_col,
        horizon=horizon,
        fwd_col=fwd_col,
        label_col=label_col,
        clip=cfg.get("clip"),
        intermediate_cols=[raw_fwd_col, realized_vol_col],
        meta_extra={
            "returns_col": returns_col,
            "returns_type": returns_type,
            "volatility_floor": volatility_floor,
            "raw_fwd_col": raw_fwd_col,
            "realized_vol_col": realized_vol_col,
            "realized_vol_stats": numeric_stats(out[realized_vol_col]),
        },
    )


def build_r_multiple_regression_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Apply the registered ``r_multiple_regression`` target transformation.

    YAML declaration::

        target:
          kind: r_multiple_regression
          params:
            price_col: close
            volatility_col: atr_14
            atr_multiple: 2.0

    Required input columns
    ----------------------
    price_col, volatility_col, returns_col:
        Price, ATR-like volatility, and optional returns columns.

    Parameters
    ----------
    price_col, volatility_col, atr_multiple, horizon_bars, returns_col, returns_type, volatility_floor, clip:
        Future return in ATR stop-risk units.
    """
    cfg = _cfg(target_cfg)
    price_col = str(cfg.get("price_col", "close"))
    volatility_col = str(cfg.get("volatility_col", "atr_14"))
    returns_col = _optional_col(cfg, "returns_col")
    returns_type = validate_returns_type(cfg.get("returns_type", "simple"))
    if returns_col is None and returns_type == "log":
        raise ValueError("target.returns_type='log' requires target.returns_col.")
    horizon = _horizon(cfg)
    atr_multiple = require_finite_number(cfg.get("atr_multiple", 2.0), field="target.atr_multiple")
    if atr_multiple <= 0.0:
        raise ValueError("target.atr_multiple must be > 0.")
    volatility_floor = require_finite_number(cfg.get("volatility_floor", 1e-12), field="target.volatility_floor")
    if volatility_floor <= 0.0:
        raise ValueError("target.volatility_floor must be > 0.")
    raw_fwd_col = str(cfg.get("raw_fwd_col", f"target_future_return_raw_{horizon}"))
    risk_distance_col = str(cfg.get("risk_distance_col", f"target_risk_distance_{horizon}"))
    fwd_col = str(cfg.get("fwd_col", f"target_r_multiple_{horizon}"))
    label_col = str(cfg.get("label_col", fwd_col))

    out = df.copy()
    raw_future = build_future_return(
        out,
        price_col=price_col,
        returns_col=returns_col,
        returns_type=returns_type,
        horizon=horizon,
    )
    normalizer = volatility_normalizer(
        out,
        price_col=price_col,
        volatility_col=volatility_col,
        volatility_floor=volatility_floor,
    )
    risk_distance = atr_multiple * normalizer
    out[raw_fwd_col] = raw_future.astype(float)
    out[risk_distance_col] = risk_distance.astype(float)
    return finalize_regression_target(
        out,
        target=raw_future / risk_distance,
        kind="r_multiple_regression",
        price_col=price_col,
        horizon=horizon,
        fwd_col=fwd_col,
        label_col=label_col,
        clip=cfg.get("clip"),
        intermediate_cols=[raw_fwd_col, risk_distance_col],
        meta_extra={
            "returns_col": returns_col,
            "returns_type": returns_type,
            "volatility_col": volatility_col,
            "atr_multiple": atr_multiple,
            "volatility_floor": volatility_floor,
            "raw_fwd_col": raw_fwd_col,
            "risk_distance_col": risk_distance_col,
        },
    )


def build_mfe_regression_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Apply the registered ``mfe_regression`` target transformation.

    YAML declaration::

        target:
          kind: mfe_regression
          params:
            price_col: close
            high_col: high
            low_col: low

    Required input columns
    ----------------------
    price_col, high_col, low_col, volatility_col:
        OHLC columns and optional volatility column for normalization.

    Parameters
    ----------
    price_col, high_col, low_col, direction, horizon_bars, normalize_by_volatility, clip:
        Maximum favorable excursion over the future path.
    """
    cfg = _cfg(target_cfg)
    price_col = str(cfg.get("price_col", "close"))
    high_col = str(cfg.get("high_col", "high"))
    low_col = str(cfg.get("low_col", "low"))
    direction = validate_choice(str(cfg.get("direction", "long")), field="target.direction", choices={"long", "short", "signed"})
    horizon = _horizon(cfg)
    normalize_by_volatility = bool(cfg.get("normalize_by_volatility", False))
    volatility_col = str(cfg.get("volatility_col", "atr_14"))
    volatility_floor = require_finite_number(cfg.get("volatility_floor", 1e-12), field="target.volatility_floor")
    fwd_col = str(cfg.get("fwd_col", f"target_mfe_{horizon}"))
    label_col = str(cfg.get("label_col", fwd_col))

    out = df.copy()
    price = as_float_series(out, price_col)
    max_high, min_low = _future_extremes(out, high_col=high_col, low_col=low_col, horizon=horizon)
    long_mfe = _finite(max_high / price - 1.0)
    short_mfe = _finite(1.0 - min_low / price)
    if direction == "long":
        target = long_mfe
    elif direction == "short":
        target = short_mfe
    else:
        target = long_mfe.where(long_mfe.abs() >= short_mfe.abs(), -short_mfe)
    target = _maybe_vol_normalize(
        out,
        target,
        normalize_by_volatility=normalize_by_volatility,
        price_col=price_col,
        volatility_col=volatility_col,
        volatility_floor=volatility_floor,
    )
    return finalize_regression_target(
        out,
        target=target,
        kind="mfe_regression",
        price_col=price_col,
        horizon=horizon,
        fwd_col=fwd_col,
        label_col=label_col,
        clip=cfg.get("clip"),
        meta_extra={
            "high_col": high_col,
            "low_col": low_col,
            "direction": direction,
            "normalize_by_volatility": normalize_by_volatility,
            "volatility_col": volatility_col if normalize_by_volatility else None,
            "volatility_floor": volatility_floor if normalize_by_volatility else None,
            "signed_convention": "positive means upside favorable excursion dominates; negative means downside favorable excursion dominates.",
        },
    )


def build_mae_regression_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Apply the registered ``mae_regression`` target transformation.

    YAML declaration::

        target:
          kind: mae_regression
          params:
            price_col: close
            high_col: high
            low_col: low

    Required input columns
    ----------------------
    price_col, high_col, low_col, volatility_col:
        OHLC columns and optional volatility column for normalization.

    Parameters
    ----------
    price_col, high_col, low_col, direction, horizon_bars, normalize_by_volatility, clip:
        Maximum adverse excursion over the future path.
    """
    cfg = _cfg(target_cfg)
    price_col = str(cfg.get("price_col", "close"))
    high_col = str(cfg.get("high_col", "high"))
    low_col = str(cfg.get("low_col", "low"))
    direction = validate_choice(str(cfg.get("direction", "long")), field="target.direction", choices={"long", "short", "signed"})
    horizon = _horizon(cfg)
    normalize_by_volatility = bool(cfg.get("normalize_by_volatility", False))
    volatility_col = str(cfg.get("volatility_col", "atr_14"))
    volatility_floor = require_finite_number(cfg.get("volatility_floor", 1e-12), field="target.volatility_floor")
    fwd_col = str(cfg.get("fwd_col", f"target_mae_{horizon}"))
    label_col = str(cfg.get("label_col", fwd_col))

    out = df.copy()
    price = as_float_series(out, price_col)
    max_high, min_low = _future_extremes(out, high_col=high_col, low_col=low_col, horizon=horizon)
    long_mae = _finite(min_low / price - 1.0)
    short_mae = _finite(1.0 - max_high / price)
    if direction == "long":
        target = long_mae
    elif direction == "short":
        target = short_mae
    else:
        upside_adverse = _finite(max_high / price - 1.0)
        downside_adverse = long_mae
        target = downside_adverse.where(downside_adverse.abs() >= upside_adverse.abs(), upside_adverse)
    target = _maybe_vol_normalize(
        out,
        target,
        normalize_by_volatility=normalize_by_volatility,
        price_col=price_col,
        volatility_col=volatility_col,
        volatility_floor=volatility_floor,
    )
    return finalize_regression_target(
        out,
        target=target,
        kind="mae_regression",
        price_col=price_col,
        horizon=horizon,
        fwd_col=fwd_col,
        label_col=label_col,
        clip=cfg.get("clip"),
        meta_extra={
            "high_col": high_col,
            "low_col": low_col,
            "direction": direction,
            "normalize_by_volatility": normalize_by_volatility,
            "volatility_col": volatility_col if normalize_by_volatility else None,
            "volatility_floor": volatility_floor if normalize_by_volatility else None,
            "signed_convention": "negative means downside adverse excursion dominates; positive means upside adverse excursion dominates.",
        },
    )


def build_mfe_mae_ratio_regression_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Apply the registered ``mfe_mae_ratio_regression`` target transformation.

    YAML declaration::

        target:
          kind: mfe_mae_ratio_regression
          params:
            direction: long
            mode: ratio

    Required input columns
    ----------------------
    price_col, high_col, low_col:
        OHLC inputs for future MFE and MAE.

    Parameters
    ----------
    price_col, high_col, low_col, direction, horizon_bars, mode, denominator_floor, clip:
        Reward/risk path quality using MFE and MAE.
    """
    cfg = _cfg(target_cfg)
    price_col = str(cfg.get("price_col", "close"))
    high_col = str(cfg.get("high_col", "high"))
    low_col = str(cfg.get("low_col", "low"))
    direction = validate_choice(str(cfg.get("direction", "long")), field="target.direction", choices={"long", "short"})
    mode = validate_choice(str(cfg.get("mode", "ratio")), field="target.mode", choices={"ratio", "difference"})
    denominator_floor = require_finite_number(cfg.get("denominator_floor", 1e-12), field="target.denominator_floor")
    if denominator_floor <= 0.0:
        raise ValueError("target.denominator_floor must be > 0.")
    horizon = _horizon(cfg)
    mfe_col = str(cfg.get("mfe_col", f"target_mfe_{horizon}"))
    mae_col = str(cfg.get("mae_col", f"target_mae_{horizon}"))
    fwd_col = str(cfg.get("fwd_col", f"target_mfe_mae_ratio_{horizon}"))
    label_col = str(cfg.get("label_col", fwd_col))

    out = df.copy()
    mfe, mae = _mfe_mae_values(
        out,
        price_col=price_col,
        high_col=high_col,
        low_col=low_col,
        horizon=horizon,
        direction=direction,
    )
    out[mfe_col] = mfe.astype(float)
    out[mae_col] = mae.astype(float)
    if mode == "ratio":
        denominator = positive_denominator(mae.abs(), floor=denominator_floor, field="target.denominator_floor")
        target = mfe / denominator
    else:
        target = mfe - mae.abs()
    return finalize_regression_target(
        out,
        target=target,
        kind="mfe_mae_ratio_regression",
        price_col=price_col,
        horizon=horizon,
        fwd_col=fwd_col,
        label_col=label_col,
        clip=cfg.get("clip"),
        intermediate_cols=[mfe_col, mae_col],
        meta_extra={
            "high_col": high_col,
            "low_col": low_col,
            "direction": direction,
            "mode": mode,
            "denominator_floor": denominator_floor,
            "mfe_col": mfe_col,
            "mae_col": mae_col,
        },
    )


def build_downside_adjusted_future_return_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Apply the registered ``downside_adjusted_future_return`` target transformation.

    YAML declaration::

        target:
          kind: downside_adjusted_future_return
          params:
            direction: long
            penalty_lambda: 1.0

    Required input columns
    ----------------------
    price_col, high_col, low_col, volatility_col:
        OHLC inputs and optional volatility column.

    Parameters
    ----------
    price_col, high_col, low_col, direction, horizon_bars, penalty_lambda, normalize_by_volatility, clip:
        Directional future return penalized by adverse excursion.
    """
    cfg = _cfg(target_cfg)
    price_col = str(cfg.get("price_col", "close"))
    high_col = str(cfg.get("high_col", "high"))
    low_col = str(cfg.get("low_col", "low"))
    direction = validate_choice(str(cfg.get("direction", "long")), field="target.direction", choices={"long", "short"})
    horizon = _horizon(cfg)
    penalty_lambda = require_finite_number(cfg.get("penalty_lambda", 1.0), field="target.penalty_lambda")
    if penalty_lambda < 0.0:
        raise ValueError("target.penalty_lambda must be >= 0.")
    normalize_by_volatility = bool(cfg.get("normalize_by_volatility", False))
    volatility_col = str(cfg.get("volatility_col", "atr_14"))
    volatility_floor = require_finite_number(cfg.get("volatility_floor", 1e-12), field="target.volatility_floor")
    raw_fwd_col = str(cfg.get("raw_fwd_col", f"target_future_return_raw_{horizon}"))
    mae_col = str(cfg.get("mae_col", f"target_mae_{horizon}"))
    fwd_col = str(cfg.get("fwd_col", f"target_downside_adjusted_return_{horizon}"))
    label_col = str(cfg.get("label_col", fwd_col))

    out = df.copy()
    price = as_float_series(out, price_col)
    terminal = price.shift(-horizon)
    if direction == "long":
        raw_future = _finite(terminal / price - 1.0)
    else:
        raw_future = _finite(1.0 - terminal / price)
    _, mae = _mfe_mae_values(
        out,
        price_col=price_col,
        high_col=high_col,
        low_col=low_col,
        horizon=horizon,
        direction=direction,
    )
    raw_target = raw_future - penalty_lambda * mae.abs()
    target = _maybe_vol_normalize(
        out,
        raw_target,
        normalize_by_volatility=normalize_by_volatility,
        price_col=price_col,
        volatility_col=volatility_col,
        volatility_floor=volatility_floor,
    )
    out[raw_fwd_col] = raw_future.astype(float)
    out[mae_col] = mae.astype(float)
    return finalize_regression_target(
        out,
        target=target,
        kind="downside_adjusted_future_return",
        price_col=price_col,
        horizon=horizon,
        fwd_col=fwd_col,
        label_col=label_col,
        clip=cfg.get("clip"),
        intermediate_cols=[raw_fwd_col, mae_col],
        meta_extra={
            "high_col": high_col,
            "low_col": low_col,
            "direction": direction,
            "penalty_lambda": penalty_lambda,
            "normalize_by_volatility": normalize_by_volatility,
            "volatility_col": volatility_col if normalize_by_volatility else None,
            "volatility_floor": volatility_floor if normalize_by_volatility else None,
            "raw_fwd_col": raw_fwd_col,
            "mae_col": mae_col,
        },
    )


def build_future_trend_slope_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Apply the registered ``future_trend_slope`` target transformation.

    YAML declaration::

        target:
          kind: future_trend_slope
          params:
            price_col: close
            horizon_bars: 5

    Required input columns
    ----------------------
    price_col, volatility_col:
        Future price window and optional volatility column.

    Parameters
    ----------
    price_col, horizon_bars, normalize_by_price, normalize_by_volatility, volatility_col, clip:
        Linear-regression slope over future prices.
    """
    cfg = _cfg(target_cfg)
    price_col = str(cfg.get("price_col", "close"))
    horizon = _target_horizon(cfg, kind="future_trend_slope")
    normalize_by_price = bool(cfg.get("normalize_by_price", True))
    normalize_by_volatility = bool(cfg.get("normalize_by_volatility", False))
    volatility_col = str(cfg.get("volatility_col", "atr_14"))
    volatility_floor = require_finite_number(cfg.get("volatility_floor", 1e-12), field="target.volatility_floor")
    fwd_col = str(cfg.get("fwd_col", f"target_future_trend_slope_{horizon}"))
    label_col = str(cfg.get("label_col", fwd_col))

    out = df.copy()
    price = as_float_series(out, price_col)
    matrix = future_window(price, horizon, prefix="price")
    values = matrix.to_numpy(dtype=float)
    valid = np.isfinite(values).all(axis=1)
    slopes = np.full(len(out), np.nan, dtype=float)
    x = np.arange(1, horizon + 1, dtype=float)
    x_centered = x - float(x.mean())
    denom = float(np.square(x_centered).sum())
    if bool(valid.any()):
        y = values[valid]
        y_centered = y - y.mean(axis=1, keepdims=True)
        slopes[valid] = (y_centered * x_centered).sum(axis=1) / denom
    target = pd.Series(slopes, index=out.index, dtype=float)
    if normalize_by_price:
        target = target / price.abs().where(price.abs() > 0.0)
    if normalize_by_volatility:
        if normalize_by_price:
            denom_series = volatility_normalizer(
                out,
                price_col=price_col,
                volatility_col=volatility_col,
                volatility_floor=volatility_floor,
            )
        else:
            denom_series = positive_denominator(
                as_float_series(out, volatility_col),
                floor=volatility_floor,
                field="target.volatility_floor",
            )
        target = target / denom_series
    target = _finite(target)
    return finalize_regression_target(
        out,
        target=target,
        kind="future_trend_slope",
        price_col=price_col,
        horizon=horizon,
        fwd_col=fwd_col,
        label_col=label_col,
        clip=cfg.get("clip"),
        meta_extra={
            "normalize_by_price": normalize_by_price,
            "normalize_by_volatility": normalize_by_volatility,
            "volatility_col": volatility_col if normalize_by_volatility else None,
            "volatility_floor": volatility_floor if normalize_by_volatility else None,
        },
    )


def build_future_path_efficiency_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Apply the registered ``future_path_efficiency`` target transformation.

    YAML declaration::

        target:
          kind: future_path_efficiency
          params:
            price_col: close
            horizon_bars: 2

    Required input columns
    ----------------------
    price_col:
        Price path from t through t+horizon.

    Parameters
    ----------
    price_col, horizon_bars, signed, path_floor, clip:
        Net movement divided by absolute path length.
    """
    cfg = _cfg(target_cfg)
    price_col = str(cfg.get("price_col", "close"))
    horizon = _target_horizon(cfg, kind="future_path_efficiency")
    signed = bool(cfg.get("signed", True))
    path_floor = require_finite_number(cfg.get("path_floor", 1e-12), field="target.path_floor")
    if path_floor <= 0.0:
        raise ValueError("target.path_floor must be > 0.")
    fwd_col = str(cfg.get("fwd_col", f"target_path_efficiency_{horizon}"))
    label_col = str(cfg.get("label_col", fwd_col))

    out = df.copy()
    price = as_float_series(out, price_col)
    path = pd.concat(
        [price.shift(-step).rename(f"path_{step}") for step in range(0, horizon + 1)],
        axis=1,
    )
    valid = path.notna().all(axis=1)
    start = path.iloc[:, 0]
    terminal = path.iloc[:, -1]
    net_move = (terminal - start).abs()
    total_path = path.diff(axis=1).abs().iloc[:, 1:].sum(axis=1).where(valid)
    denom = positive_denominator(total_path, floor=path_floor, field="target.path_floor")
    target = net_move / denom
    if signed:
        target = np.sign(terminal - start) * target
    target = _finite(pd.Series(target, index=out.index, dtype=float))
    return finalize_regression_target(
        out,
        target=target,
        kind="future_path_efficiency",
        price_col=price_col,
        horizon=horizon,
        fwd_col=fwd_col,
        label_col=label_col,
        clip=cfg.get("clip"),
        meta_extra={"signed": signed, "path_floor": path_floor},
    )


def build_excess_return_regression_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Apply the registered ``excess_return_regression`` target transformation.

    YAML declaration::

        target:
          kind: excess_return_regression
          params:
            benchmark_price_col: benchmark_close

    Required input columns
    ----------------------
    price_col, benchmark_price_col, returns_col, benchmark_returns_col:
        Asset and benchmark price or returns inputs.

    Parameters
    ----------
    price_col, benchmark_price_col, horizon_bars, returns_col, benchmark_returns_col, returns_type, clip:
        Asset future return minus benchmark future return.
    """
    cfg = _cfg(target_cfg)
    price_col = str(cfg.get("price_col", "close"))
    benchmark_price_col = _optional_col(cfg, "benchmark_price_col")
    returns_col = _optional_col(cfg, "returns_col")
    benchmark_returns_col = _optional_col(cfg, "benchmark_returns_col")
    returns_type = validate_returns_type(cfg.get("returns_type", "simple"))
    if returns_type == "log" and (returns_col is None or benchmark_returns_col is None):
        raise ValueError("target.returns_type='log' requires target.returns_col and target.benchmark_returns_col.")
    if benchmark_price_col is None and benchmark_returns_col is None:
        raise KeyError("benchmark_price_col or benchmark_returns_col is required.")
    horizon = _horizon(cfg)
    benchmark_fwd_col = str(cfg.get("benchmark_fwd_col", f"target_benchmark_future_return_{horizon}"))
    fwd_col = str(cfg.get("fwd_col", f"target_excess_return_{horizon}"))
    label_col = str(cfg.get("label_col", fwd_col))

    out = df.copy()
    asset_future = build_future_return(
        out,
        price_col=price_col,
        returns_col=returns_col,
        returns_type=returns_type,
        horizon=horizon,
    )
    benchmark_future = build_future_return(
        out,
        price_col=str(benchmark_price_col or price_col),
        returns_col=benchmark_returns_col,
        returns_type=returns_type,
        horizon=horizon,
    )
    out[benchmark_fwd_col] = benchmark_future.astype(float)
    return finalize_regression_target(
        out,
        target=asset_future - benchmark_future,
        kind="excess_return_regression",
        price_col=price_col,
        horizon=horizon,
        fwd_col=fwd_col,
        label_col=label_col,
        clip=cfg.get("clip"),
        intermediate_cols=[benchmark_fwd_col],
        meta_extra={
            "benchmark_price_col": benchmark_price_col,
            "returns_col": returns_col,
            "benchmark_returns_col": benchmark_returns_col,
            "returns_type": returns_type,
            "benchmark_fwd_col": benchmark_fwd_col,
        },
    )


def build_residual_return_regression_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Apply the registered ``residual_return_regression`` target transformation.

    YAML declaration::

        target:
          kind: residual_return_regression
          params:
            benchmark_price_col: benchmark_close
            beta_window: 100

    Required input columns
    ----------------------
    price_col, benchmark_price_col, returns_col, benchmark_returns_col:
        Asset and benchmark price or returns inputs for rolling beta and future returns.

    Parameters
    ----------
    price_col, benchmark_price_col, horizon_bars, beta_window, min_periods, returns_col, benchmark_returns_col, returns_type, clip:
        Future return residual after removing rolling benchmark beta exposure.
    """
    cfg = _cfg(target_cfg)
    price_col = str(cfg.get("price_col", "close"))
    benchmark_price_col = _optional_col(cfg, "benchmark_price_col")
    returns_col = _optional_col(cfg, "returns_col")
    benchmark_returns_col = _optional_col(cfg, "benchmark_returns_col")
    returns_type = validate_returns_type(cfg.get("returns_type", "simple"))
    if returns_type == "log" and (returns_col is None or benchmark_returns_col is None):
        raise ValueError("target.returns_type='log' requires target.returns_col and target.benchmark_returns_col.")
    if benchmark_price_col is None and benchmark_returns_col is None:
        raise KeyError("benchmark_price_col or benchmark_returns_col is required.")
    horizon = _horizon(cfg)
    beta_window = require_positive_int(cfg.get("beta_window", 100), field="target.beta_window")
    min_periods = require_positive_int(cfg.get("min_periods", beta_window), field="target.min_periods")
    if min_periods > beta_window:
        raise ValueError("target.min_periods must be <= target.beta_window.")
    raw_fwd_col = str(cfg.get("raw_fwd_col", f"target_future_return_raw_{horizon}"))
    benchmark_fwd_col = str(cfg.get("benchmark_fwd_col", f"target_benchmark_future_return_{horizon}"))
    beta_col = str(cfg.get("beta_col", f"target_beta_{beta_window}"))
    fwd_col = str(cfg.get("fwd_col", f"target_residual_return_{horizon}"))
    label_col = str(cfg.get("label_col", fwd_col))

    out = df.copy()
    asset_returns = build_return_series(
        out,
        price_col=price_col,
        returns_col=returns_col,
        returns_type=returns_type,
    )
    benchmark_returns = build_return_series(
        out,
        price_col=str(benchmark_price_col or price_col),
        returns_col=benchmark_returns_col,
        returns_type=returns_type,
    )
    beta = asset_returns.rolling(beta_window, min_periods=min_periods).cov(benchmark_returns)
    beta = beta / benchmark_returns.rolling(beta_window, min_periods=min_periods).var(ddof=1)
    beta = _finite(beta)
    raw_future = build_future_return(
        out,
        price_col=price_col,
        returns_col=returns_col,
        returns_type=returns_type,
        horizon=horizon,
    )
    benchmark_future = build_future_return(
        out,
        price_col=str(benchmark_price_col or price_col),
        returns_col=benchmark_returns_col,
        returns_type=returns_type,
        horizon=horizon,
    )
    out[raw_fwd_col] = raw_future.astype(float)
    out[benchmark_fwd_col] = benchmark_future.astype(float)
    out[beta_col] = beta.astype(float)
    return finalize_regression_target(
        out,
        target=raw_future - beta * benchmark_future,
        kind="residual_return_regression",
        price_col=price_col,
        horizon=horizon,
        fwd_col=fwd_col,
        label_col=label_col,
        clip=cfg.get("clip"),
        intermediate_cols=[raw_fwd_col, benchmark_fwd_col, beta_col],
        meta_extra={
            "benchmark_price_col": benchmark_price_col,
            "returns_col": returns_col,
            "benchmark_returns_col": benchmark_returns_col,
            "returns_type": returns_type,
            "beta_window": beta_window,
            "min_periods": min_periods,
            "raw_fwd_col": raw_fwd_col,
            "benchmark_fwd_col": benchmark_fwd_col,
            "beta_col": beta_col,
            "leakage_note": "Rolling beta uses only returns through timestamp t; future benchmark return is used only to construct the residual target.",
        },
    )


def build_future_range_regression_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Apply the registered ``future_range_regression`` target transformation.

    YAML declaration::

        target:
          kind: future_range_regression
          params:
            normalize: price

    Required input columns
    ----------------------
    price_col, high_col, low_col, volatility_col:
        OHLC inputs and optional volatility column.

    Parameters
    ----------
    price_col, high_col, low_col, horizon_bars, normalize, volatility_col, volatility_floor, clip:
        Future high-low range normalized by price, volatility, or not at all.
    """
    cfg = _cfg(target_cfg)
    price_col = str(cfg.get("price_col", "close"))
    high_col = str(cfg.get("high_col", "high"))
    low_col = str(cfg.get("low_col", "low"))
    horizon = _horizon(cfg)
    normalize = validate_choice(str(cfg.get("normalize", "price")), field="target.normalize", choices={"price", "volatility", "none"})
    volatility_col = str(cfg.get("volatility_col", "atr_14"))
    volatility_floor = require_finite_number(cfg.get("volatility_floor", 1e-12), field="target.volatility_floor")
    fwd_col = str(cfg.get("fwd_col", f"target_future_range_{horizon}"))
    label_col = str(cfg.get("label_col", fwd_col))

    out = df.copy()
    max_high, min_low = _future_extremes(out, high_col=high_col, low_col=low_col, horizon=horizon)
    future_range = (max_high - min_low).astype(float)
    if normalize == "price":
        denominator = as_float_series(out, price_col).abs().where(as_float_series(out, price_col).abs() > 0.0)
        target = future_range / denominator
    elif normalize == "volatility":
        denominator = positive_denominator(
            as_float_series(out, volatility_col),
            floor=volatility_floor,
            field="target.volatility_floor",
        )
        target = future_range / denominator
    else:
        target = future_range
    return finalize_regression_target(
        out,
        target=_finite(target),
        kind="future_range_regression",
        price_col=price_col,
        horizon=horizon,
        fwd_col=fwd_col,
        label_col=label_col,
        clip=cfg.get("clip"),
        meta_extra={
            "high_col": high_col,
            "low_col": low_col,
            "normalize": normalize,
            "volatility_col": volatility_col if normalize == "volatility" else None,
            "volatility_floor": volatility_floor if normalize == "volatility" else None,
        },
    )


def build_future_realized_volatility_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Apply the registered ``future_realized_volatility`` target transformation.

    YAML declaration::

        target:
          kind: future_realized_volatility
          params:
            price_col: close
            horizon_bars: 5

    Required input columns
    ----------------------
    price_col, returns_col:
        Price column or optional one-step returns column.

    Parameters
    ----------
    price_col, returns_col, returns_type, horizon_bars, annualize, periods_per_year, clip:
        Standard deviation of future one-step returns.
    """
    cfg = _cfg(target_cfg)
    price_col = str(cfg.get("price_col", "close"))
    returns_col = _optional_col(cfg, "returns_col")
    returns_type = validate_returns_type(cfg.get("returns_type", "simple"))
    horizon = _target_horizon(cfg, kind="future_realized_volatility")
    annualize = bool(cfg.get("annualize", False))
    periods_per_year = cfg.get("periods_per_year")
    fwd_col = str(cfg.get("fwd_col", f"target_future_realized_vol_{horizon}"))
    label_col = str(cfg.get("label_col", fwd_col))

    out = df.copy()
    target = build_future_realized_volatility(
        out,
        price_col=price_col,
        returns_col=returns_col,
        returns_type=returns_type,
        horizon=horizon,
        annualize=annualize,
        periods_per_year=periods_per_year,
    )
    return finalize_regression_target(
        out,
        target=target,
        kind="future_realized_volatility",
        price_col=price_col,
        horizon=horizon,
        fwd_col=fwd_col,
        label_col=label_col,
        clip=cfg.get("clip"),
        meta_extra={
            "returns_col": returns_col,
            "returns_type": returns_type,
            "annualize": annualize,
            "periods_per_year": float(periods_per_year) if periods_per_year is not None else None,
            "annualization_convention": "std(future one-step returns) * sqrt(periods_per_year)",
            "annualization_convention_version": 2,
        },
    )


def build_future_drawdown_regression_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Apply the registered ``future_drawdown_regression`` target transformation.

    YAML declaration::

        target:
          kind: future_drawdown_regression
          params:
            direction: long

    Required input columns
    ----------------------
    price_col, high_col, low_col, volatility_col:
        OHLC inputs and optional volatility column.

    Parameters
    ----------
    price_col, high_col, low_col, direction, horizon_bars, normalize_by_volatility, volatility_col, clip:
        Downside drawdown over the future path.
    """
    cfg = _cfg(target_cfg)
    price_col = str(cfg.get("price_col", "close"))
    high_col = str(cfg.get("high_col", "high"))
    low_col = str(cfg.get("low_col", "low"))
    direction = validate_choice(str(cfg.get("direction", "long")), field="target.direction", choices={"long", "short"})
    horizon = _horizon(cfg)
    normalize_by_volatility = bool(cfg.get("normalize_by_volatility", False))
    volatility_col = str(cfg.get("volatility_col", "atr_14"))
    volatility_floor = require_finite_number(cfg.get("volatility_floor", 1e-12), field="target.volatility_floor")
    fwd_col = str(cfg.get("fwd_col", f"target_future_drawdown_{horizon}"))
    label_col = str(cfg.get("label_col", fwd_col))

    out = df.copy()
    price = as_float_series(out, price_col)
    max_high, min_low = _future_extremes(out, high_col=high_col, low_col=low_col, horizon=horizon)
    if direction == "long":
        target = _finite(min_low / price - 1.0)
    else:
        target = _finite(1.0 - max_high / price)
    target = _maybe_vol_normalize(
        out,
        target,
        normalize_by_volatility=normalize_by_volatility,
        price_col=price_col,
        volatility_col=volatility_col,
        volatility_floor=volatility_floor,
    )
    return finalize_regression_target(
        out,
        target=target,
        kind="future_drawdown_regression",
        price_col=price_col,
        horizon=horizon,
        fwd_col=fwd_col,
        label_col=label_col,
        clip=cfg.get("clip"),
        meta_extra={
            "high_col": high_col,
            "low_col": low_col,
            "direction": direction,
            "normalize_by_volatility": normalize_by_volatility,
            "volatility_col": volatility_col if normalize_by_volatility else None,
            "volatility_floor": volatility_floor if normalize_by_volatility else None,
        },
    )


__all__ = [
    "REGRESSION_TARGET_KINDS",
    "build_downside_adjusted_future_return_target",
    "build_excess_return_regression_target",
    "build_future_drawdown_regression_target",
    "build_future_path_efficiency_target",
    "build_future_range_regression_target",
    "build_future_realized_volatility_target",
    "build_future_trend_slope_target",
    "build_mae_regression_target",
    "build_mfe_mae_ratio_regression_target",
    "build_mfe_regression_target",
    "build_r_multiple_regression_target",
    "build_residual_return_regression_target",
    "build_risk_adjusted_future_return_target",
    "build_volatility_normalized_future_return_target",
]
