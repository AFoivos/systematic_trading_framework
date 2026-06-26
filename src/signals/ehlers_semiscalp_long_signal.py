"""Causal long-only Ehlers semi-scalp signal.

The setup requires bullish MAMA/FAMA and decycler trend permission, Hilbert
amplitude above its trailing median, a positive and rising Roofing Filter,
and bullish Laguerre RSI/Fisher momentum.  An optional dominant-cycle range
filter can additionally gate entries.  Every comparison uses only the current
or an earlier bar; execution at the following open is deliberately left to the
backtest/target layer.
"""

from __future__ import annotations

from numbers import Integral, Real
from typing import Any, Mapping

import pandas as pd


_DEFAULT_CFG: dict[str, Any] = {
    "entry_mode": "transition",
    "require_mama_rising": False,
    "roofing_trigger_mode": "rising",
    "price_col": "close",
    "mama_col": "mama",
    "fama_col": "fama",
    "decycler_col": "decycler",
    "roofing_col": "roofing_filter_48_10",
    "laguerre_col": "laguerre_rsi",
    "fisher_col": "fisher_transform",
    "hilbert_amplitude_col": "hilbert_amplitude_64",
    "dominant_cycle_period_col": "dominant_cycle_period",
    "amplitude_lookback": 100,
    "laguerre_min": 0.50,
    "min_cycle_period": 10.0,
    "max_cycle_period": 48.0,
    "use_cycle_period_filter": False,
    "signal_col": "signal_side",
    "candidate_col": "signal_candidate",
}

_FLAG_COLUMNS = {
    "setup": "ehlers_semiscalp_long_setup",
    "trend": "ehlers_semiscalp_trend_permission",
    "active_cycle": "ehlers_semiscalp_active_cycle",
    "roofing": "ehlers_semiscalp_roofing_trigger",
    "momentum": "ehlers_semiscalp_momentum_confirm",
}


def _merge_cfg(signal_cfg: Mapping[str, Any] | None, overrides: Mapping[str, Any]) -> dict[str, Any]:
    cfg = dict(_DEFAULT_CFG)
    raw_cfg = dict(signal_cfg or {})
    nested_params = raw_cfg.pop("params", None)
    cfg.update(raw_cfg)
    if nested_params is not None:
        if not isinstance(nested_params, Mapping):
            raise TypeError("signal_cfg.params must be a mapping when provided.")
        cfg.update(dict(nested_params))
    cfg.update(dict(overrides))
    return cfg


def _validate_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(cfg)
    entry_mode = normalized.get("entry_mode")
    if entry_mode not in {"state", "transition"}:
        raise ValueError("entry_mode must be one of: state, transition.")
    roofing_trigger_mode = normalized.get("roofing_trigger_mode")
    if roofing_trigger_mode not in {"rising", "cross_up"}:
        raise ValueError("roofing_trigger_mode must be one of: rising, cross_up.")
    if not isinstance(normalized.get("require_mama_rising"), bool):
        raise ValueError("require_mama_rising must be boolean.")
    for key in (
        "price_col",
        "mama_col",
        "fama_col",
        "decycler_col",
        "roofing_col",
        "laguerre_col",
        "fisher_col",
        "hilbert_amplitude_col",
        "dominant_cycle_period_col",
        "signal_col",
        "candidate_col",
    ):
        value = normalized.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string.")
        normalized[key] = value.strip()

    lookback = normalized.get("amplitude_lookback")
    if isinstance(lookback, bool) or not isinstance(lookback, Integral) or int(lookback) <= 0:
        raise ValueError("amplitude_lookback must be a positive integer.")
    normalized["amplitude_lookback"] = int(lookback)

    for key in ("laguerre_min", "min_cycle_period", "max_cycle_period"):
        value = normalized.get(key)
        if isinstance(value, bool) or not isinstance(value, Real) or not pd.notna(float(value)):
            raise ValueError(f"{key} must be a finite number.")
        normalized[key] = float(value)
    if not 0.0 <= normalized["laguerre_min"] <= 1.0:
        raise ValueError("laguerre_min must be in [0, 1].")
    if normalized["min_cycle_period"] <= 0.0 or normalized["max_cycle_period"] <= 0.0:
        raise ValueError("cycle period bounds must be > 0.")
    if normalized["min_cycle_period"] > normalized["max_cycle_period"]:
        raise ValueError("min_cycle_period must be <= max_cycle_period.")
    if not isinstance(normalized.get("use_cycle_period_filter"), bool):
        raise ValueError("use_cycle_period_filter must be boolean.")
    return normalized


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for ehlers_semiscalp_long_signal: {missing}")


def _numeric(df: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(df[column], errors="coerce").astype(float)


def build_ehlers_semiscalp_long_signal(
    df: pd.DataFrame,
    signal_cfg: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build the causal long-only setup and return ``(output, metadata)``.

    The trailing amplitude median includes the current observation and prior
    observations only. Roofing and Fisher direction use ``shift(1)``. No
    signal is shifted forward: next-open execution belongs to the backtester.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")
    cfg = _validate_cfg(_merge_cfg(signal_cfg, overrides))

    required = [
        cfg["price_col"],
        cfg["mama_col"],
        cfg["fama_col"],
        cfg["decycler_col"],
        cfg["roofing_col"],
        cfg["laguerre_col"],
        cfg["fisher_col"],
        cfg["hilbert_amplitude_col"],
    ]
    if cfg["use_cycle_period_filter"]:
        required.append(cfg["dominant_cycle_period_col"])
    _require_columns(df, required)

    out = df.copy()
    close = _numeric(out, cfg["price_col"])
    mama = _numeric(out, cfg["mama_col"])
    fama = _numeric(out, cfg["fama_col"])
    decycler = _numeric(out, cfg["decycler_col"])
    roofing = _numeric(out, cfg["roofing_col"])
    laguerre = _numeric(out, cfg["laguerre_col"])
    fisher = _numeric(out, cfg["fisher_col"])
    amplitude = _numeric(out, cfg["hilbert_amplitude_col"])

    amplitude_median = amplitude.rolling(
        cfg["amplitude_lookback"],
        min_periods=cfg["amplitude_lookback"],
    ).median()
    trend_permission = mama.gt(fama) & close.gt(decycler)
    if cfg["require_mama_rising"]:
        trend_permission &= mama.gt(mama.shift(1))
    active_cycle = amplitude.gt(amplitude_median)
    if cfg["roofing_trigger_mode"] == "cross_up":
        roofing_trigger = roofing.gt(0.0) & roofing.shift(1).le(0.0)
    else:
        roofing_trigger = roofing.gt(0.0) & roofing.gt(roofing.shift(1))
    momentum_confirm = laguerre.gt(cfg["laguerre_min"]) & fisher.gt(fisher.shift(1))

    cycle_period_ok = pd.Series(True, index=out.index, dtype=bool)
    if cfg["use_cycle_period_filter"]:
        dominant_cycle = _numeric(out, cfg["dominant_cycle_period_col"])
        cycle_period_ok = dominant_cycle.between(
            cfg["min_cycle_period"], cfg["max_cycle_period"], inclusive="both"
        )

    setup = trend_permission & active_cycle & roofing_trigger & momentum_confirm & cycle_period_ok
    entry = setup & ~setup.shift(1, fill_value=False)
    selected = entry if cfg["entry_mode"] == "transition" else setup
    flags = {
        _FLAG_COLUMNS["trend"]: trend_permission,
        _FLAG_COLUMNS["active_cycle"]: active_cycle,
        _FLAG_COLUMNS["roofing"]: roofing_trigger,
        _FLAG_COLUMNS["momentum"]: momentum_confirm,
        _FLAG_COLUMNS["setup"]: setup,
    }
    for column, values in flags.items():
        out[column] = values.fillna(False).astype("int8")
    out[cfg["signal_col"]] = selected.fillna(False).astype("int8")
    out[cfg["candidate_col"]] = selected.fillna(False).astype("int8")

    return out, {
        "kind": "ehlers_semiscalp_long",
        "long_only": True,
        "setup_rows": int(setup.sum()),
        "entry_rows": int(entry.sum()),
        "entry_mode": cfg["entry_mode"],
        "roofing_trigger_mode": cfg["roofing_trigger_mode"],
        "require_mama_rising": cfg["require_mama_rising"],
        "use_cycle_period_filter": cfg["use_cycle_period_filter"],
        "signal_col": cfg["signal_col"],
        "candidate_col": cfg["candidate_col"],
    }


def ehlers_semiscalp_long_feature(df: pd.DataFrame, **params: Any) -> pd.DataFrame:
    """Apply the setup during the feature stage for model-based workflows."""
    out, _ = build_ehlers_semiscalp_long_signal(df, params)
    return out


def ehlers_semiscalp_long_signal(df: pd.DataFrame, **params: Any) -> pd.DataFrame:
    """
    Apply the registered ``ehlers_semiscalp_long`` signal transformation.
    
    This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        signals:
          kind: ehlers_semiscalp_long
          params:
            entry_mode: transition
            require_mama_rising: false
            roofing_trigger_mode: rising
            price_col: close
            mama_col: mama
            fama_col: fama
            decycler_col: decycler
            roofing_col: roofing_filter_48_10
            laguerre_col: laguerre_rsi
            fisher_col: fisher_transform
            hilbert_amplitude_col: hilbert_amplitude_64
            dominant_cycle_period_col: dominant_cycle_period
            amplitude_lookback: 100
            laguerre_min: 0.5
            min_cycle_period: 10.0
            max_cycle_period: 48.0
            use_cycle_period_filter: false
            signal_col: signal_side
            candidate_col: signal_candidate
          output_cols:
            - signal_side
            - signal_candidate
    
    Required input columns
    ----------------------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    mama_col:
        Input dataframe column configured by ``mama_col``. Default: ``mama``.
    fama_col:
        Input dataframe column configured by ``fama_col``. Default: ``fama``.
    decycler_col:
        Input dataframe column configured by ``decycler_col``. Default: ``decycler``.
    roofing_col:
        Input dataframe column configured by ``roofing_col``. Default: ``roofing_filter_48_10``.
    laguerre_col:
        Input dataframe column configured by ``laguerre_col``. Default: ``laguerre_rsi``.
    fisher_col:
        Input dataframe column configured by ``fisher_col``. Default: ``fisher_transform``.
    hilbert_amplitude_col:
        Input dataframe column configured by ``hilbert_amplitude_col``. Default: ``hilbert_amplitude_64``.
    dominant_cycle_period_col:
        Input dataframe column configured by ``dominant_cycle_period_col``. Default: ``dominant_cycle_period``.
    
    Parameters
    ----------
    entry_mode:
        Mode selector controlling how this signal is applied. Default: ``transition``.
    require_mama_rising:
        Configuration parameter accepted by this signal. Default: ``false``.
    roofing_trigger_mode:
        Mode selector controlling how this signal is applied. Default: ``rising``.
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    mama_col:
        Input dataframe column configured by ``mama_col``. Default: ``mama``.
    fama_col:
        Input dataframe column configured by ``fama_col``. Default: ``fama``.
    decycler_col:
        Input dataframe column configured by ``decycler_col``. Default: ``decycler``.
    roofing_col:
        Input dataframe column configured by ``roofing_col``. Default: ``roofing_filter_48_10``.
    laguerre_col:
        Input dataframe column configured by ``laguerre_col``. Default: ``laguerre_rsi``.
    fisher_col:
        Input dataframe column configured by ``fisher_col``. Default: ``fisher_transform``.
    hilbert_amplitude_col:
        Input dataframe column configured by ``hilbert_amplitude_col``. Default: ``hilbert_amplitude_64``.
    dominant_cycle_period_col:
        Input dataframe column configured by ``dominant_cycle_period_col``. Default: ``dominant_cycle_period``.
    amplitude_lookback:
        Configuration parameter accepted by this signal. Default: ``100``.
    laguerre_min:
        Numeric threshold used by this signal. Default: ``0.5``.
    min_cycle_period:
        Configuration parameter accepted by this signal. Default: ``10.0``.
    max_cycle_period:
        Configuration parameter accepted by this signal. Default: ``48.0``.
    use_cycle_period_filter:
        Boolean switch controlling optional signal behavior. Default: ``false``.
    signal_col:
        Output dataframe column configured by ``signal_col``. Default: ``signal_side``.
    candidate_col:
        Output dataframe column configured by ``candidate_col``. Default: ``signal_candidate``.
    """
    out, _ = build_ehlers_semiscalp_long_signal(df, params)
    return out


__all__ = [
    "build_ehlers_semiscalp_long_signal",
    "ehlers_semiscalp_long_feature",
    "ehlers_semiscalp_long_signal",
]
