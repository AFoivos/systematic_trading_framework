from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import pandas as pd


_ALLOWED_MODES = frozenset({"long_only", "short_only", "long_short"})

_DEFAULT_CFG: dict[str, Any] = {
    "mode": "long_short",
    "ema_fast_col": "ema_50",
    "ema_slow_col": "ema_100",
    "roofing_col": "roofing_filter",
    "roofing_slope_col": "roofing_slope",
    "stc_col": "stc",
    "hilbert_cycle_ok_col": "hilbert_cycle_ok",
    "hilbert_amplitude_rising_col": "hilbert_amplitude_rising",
    "zscore_momentum_col": "zscore_momentum_20",
    "adx_col": "adx_14",
    "volatility_regime_col": "volatility_regime",
    "stc_long_cross_level": 25.0,
    "stc_short_cross_level": 75.0,
    "roofing_slope_bars": 3,
    "use_ema_regime": True,
    "use_roofing_filter": True,
    "use_roofing_slope": True,
    "use_hilbert_filter": False,
    "use_zscore_filter": False,
    "use_adx_filter": False,
    "adx_min": 18.0,
    "use_atr_vol_filter": False,
    "allowed_volatility_regimes": [0, 1],
    "entry_delay_bars": 0,
    "long_candidate_col": "stc_roofing_long_candidate",
    "short_candidate_col": "stc_roofing_short_candidate",
    "signal_col": "stc_roofing_signal",
    "candidate_col": "stc_roofing_signal_candidate",
    "hilbert_long_candidate_col": "stc_roofing_hilbert_long_candidate",
    "hilbert_short_candidate_col": "stc_roofing_hilbert_short_candidate",
    "hilbert_signal_col": "stc_roofing_hilbert_signal",
    "ema_bullish_col": "stc_roofing_ema_bullish",
    "ema_bearish_col": "stc_roofing_ema_bearish",
    "roofing_positive_col": "stc_roofing_roofing_positive",
    "roofing_negative_col": "stc_roofing_roofing_negative",
    "roofing_slope_positive_col": "stc_roofing_roofing_slope_positive",
    "roofing_slope_negative_col": "stc_roofing_roofing_slope_negative",
    "stc_cross_up_col": "stc_roofing_stc_cross_up",
    "stc_cross_down_col": "stc_roofing_stc_cross_down",
    "hilbert_pass_col": "stc_roofing_hilbert_pass",
    "zscore_long_pass_col": "stc_roofing_zscore_long_pass",
    "zscore_short_pass_col": "stc_roofing_zscore_short_pass",
    "adx_pass_col": "stc_roofing_adx_pass",
    "volatility_pass_col": "stc_roofing_volatility_pass",
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


def _finite_float(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number.")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{field} must be a finite number.")
    return out


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or int(value) <= 0:
        raise ValueError(f"{field} must be a positive integer.")
    return int(value)


def _non_negative_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or int(value) < 0:
        raise ValueError(f"{field} must be a non-negative integer.")
    return int(value)


def _string_value(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return value.strip()


def _allowed_regime_values(value: Any) -> set[float]:
    if isinstance(value, bool) or isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("allowed_volatility_regimes must be a non-empty sequence of finite numbers.")
    regimes: set[float] = set()
    for idx, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"allowed_volatility_regimes[{idx}] must be a finite number.")
        regime = float(item)
        if not math.isfinite(regime):
            raise ValueError(f"allowed_volatility_regimes[{idx}] must be a finite number.")
        regimes.add(regime)
    if not regimes:
        raise ValueError("allowed_volatility_regimes must not be empty.")
    return regimes


def _validate_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(cfg)
    mode = str(normalized.get("mode", "long_short"))
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of: {sorted(_ALLOWED_MODES)}.")
    normalized["mode"] = mode

    string_keys = (
        "ema_fast_col",
        "ema_slow_col",
        "roofing_col",
        "roofing_slope_col",
        "stc_col",
        "hilbert_cycle_ok_col",
        "hilbert_amplitude_rising_col",
        "zscore_momentum_col",
        "adx_col",
        "volatility_regime_col",
        "long_candidate_col",
        "short_candidate_col",
        "signal_col",
        "candidate_col",
        "hilbert_long_candidate_col",
        "hilbert_short_candidate_col",
        "hilbert_signal_col",
        "ema_bullish_col",
        "ema_bearish_col",
        "roofing_positive_col",
        "roofing_negative_col",
        "roofing_slope_positive_col",
        "roofing_slope_negative_col",
        "stc_cross_up_col",
        "stc_cross_down_col",
        "hilbert_pass_col",
        "zscore_long_pass_col",
        "zscore_short_pass_col",
        "adx_pass_col",
        "volatility_pass_col",
    )
    for key in string_keys:
        normalized[key] = _string_value(normalized.get(key), field=key)

    for key in (
        "use_ema_regime",
        "use_roofing_filter",
        "use_roofing_slope",
        "use_hilbert_filter",
        "use_zscore_filter",
        "use_adx_filter",
        "use_atr_vol_filter",
    ):
        if not isinstance(normalized.get(key), bool):
            raise TypeError(f"{key} must be boolean.")

    for key in ("stc_long_cross_level", "stc_short_cross_level", "adx_min"):
        normalized[key] = _finite_float(normalized.get(key), field=key)
    if not 0.0 <= normalized["stc_long_cross_level"] <= 100.0:
        raise ValueError("stc_long_cross_level must be in [0, 100].")
    if not 0.0 <= normalized["stc_short_cross_level"] <= 100.0:
        raise ValueError("stc_short_cross_level must be in [0, 100].")
    if normalized["stc_long_cross_level"] >= normalized["stc_short_cross_level"]:
        raise ValueError("stc_long_cross_level must be less than stc_short_cross_level.")
    if normalized["adx_min"] < 0.0:
        raise ValueError("adx_min must be >= 0.")

    normalized["roofing_slope_bars"] = _positive_int(
        normalized.get("roofing_slope_bars"),
        field="roofing_slope_bars",
    )
    normalized["entry_delay_bars"] = _non_negative_int(
        normalized.get("entry_delay_bars"),
        field="entry_delay_bars",
    )
    normalized["allowed_volatility_regimes"] = _allowed_regime_values(
        normalized.get("allowed_volatility_regimes")
    )
    return normalized


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for stc_roofing_hilbert_signal: {missing}")


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce").astype(float)


def _flag(frame: pd.DataFrame, column: str) -> pd.Series:
    return _numeric(frame, column).fillna(0.0).ne(0.0)


def _side_series(long_setup: pd.Series, short_setup: pd.Series) -> pd.Series:
    side = pd.Series(0, index=long_setup.index, dtype="int8")
    side.loc[long_setup & ~short_setup] = 1
    side.loc[short_setup & ~long_setup] = -1
    return side


def build_stc_roofing_hilbert_signal(
    df: pd.DataFrame,
    signal_cfg: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Build a diagnostic STC + Roofing Filter signal.

    Inputs are current-bar or trailing feature columns. Execution timing remains
    in the backtest layer; optional entry_delay_bars shifts only emitted signals.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    cfg = _validate_cfg(_merge_cfg(signal_cfg, overrides))
    required_cols = [str(cfg["ema_fast_col"]), str(cfg["ema_slow_col"]), str(cfg["stc_col"])]
    if bool(cfg["use_roofing_filter"]) or bool(cfg["use_roofing_slope"]):
        required_cols.append(str(cfg["roofing_col"]))
    if bool(cfg["use_roofing_slope"]) and str(cfg["roofing_slope_col"]) in df.columns:
        required_cols.append(str(cfg["roofing_slope_col"]))
    if bool(cfg["use_hilbert_filter"]):
        required_cols.extend([str(cfg["hilbert_cycle_ok_col"]), str(cfg["hilbert_amplitude_rising_col"])])
    if bool(cfg["use_zscore_filter"]):
        required_cols.append(str(cfg["zscore_momentum_col"]))
    if bool(cfg["use_adx_filter"]):
        required_cols.append(str(cfg["adx_col"]))
    if bool(cfg["use_atr_vol_filter"]):
        required_cols.append(str(cfg["volatility_regime_col"]))
    _require_columns(df, list(dict.fromkeys(required_cols)))

    out = df.copy()
    ema_fast = _numeric(out, str(cfg["ema_fast_col"]))
    ema_slow = _numeric(out, str(cfg["ema_slow_col"]))
    stc = _numeric(out, str(cfg["stc_col"]))
    roofing = (
        _numeric(out, str(cfg["roofing_col"]))
        if str(cfg["roofing_col"]) in out.columns
        else pd.Series(0.0, index=out.index, dtype=float)
    )
    roofing_slope = (
        _numeric(out, str(cfg["roofing_slope_col"]))
        if str(cfg["roofing_slope_col"]) in out.columns
        else roofing - roofing.shift(int(cfg["roofing_slope_bars"]))
    )

    ema_bullish = ema_fast.gt(ema_slow)
    ema_bearish = ema_fast.lt(ema_slow)
    roofing_positive = roofing.gt(0.0)
    roofing_negative = roofing.lt(0.0)
    roofing_slope_positive = roofing_slope.gt(0.0)
    roofing_slope_negative = roofing_slope.lt(0.0)
    stc_cross_up = stc.shift(1).le(float(cfg["stc_long_cross_level"])) & stc.gt(
        float(cfg["stc_long_cross_level"])
    )
    stc_cross_down = stc.shift(1).ge(float(cfg["stc_short_cross_level"])) & stc.lt(
        float(cfg["stc_short_cross_level"])
    )

    valid = ema_fast.notna() & ema_slow.notna() & stc.notna() & stc.shift(1).notna()
    long_filter = stc_cross_up.copy()
    short_filter = stc_cross_down.copy()
    if bool(cfg["use_ema_regime"]):
        long_filter &= ema_bullish
        short_filter &= ema_bearish
    if bool(cfg["use_roofing_filter"]):
        long_filter &= roofing_positive
        short_filter &= roofing_negative
        valid &= roofing.notna()
    if bool(cfg["use_roofing_slope"]):
        long_filter &= roofing_slope_positive
        short_filter &= roofing_slope_negative
        valid &= roofing_slope.notna()

    zscore_long_pass = pd.Series(True, index=out.index, dtype=bool)
    zscore_short_pass = pd.Series(True, index=out.index, dtype=bool)
    if bool(cfg["use_zscore_filter"]):
        zscore = _numeric(out, str(cfg["zscore_momentum_col"]))
        zscore_long_pass = zscore.gt(0.0)
        zscore_short_pass = zscore.lt(0.0)
        long_filter &= zscore_long_pass
        short_filter &= zscore_short_pass
        valid &= zscore.notna()

    adx_pass = pd.Series(True, index=out.index, dtype=bool)
    if bool(cfg["use_adx_filter"]):
        adx = _numeric(out, str(cfg["adx_col"]))
        adx_pass = adx.gt(float(cfg["adx_min"]))
        long_filter &= adx_pass
        short_filter &= adx_pass
        valid &= adx.notna()

    volatility_pass = pd.Series(True, index=out.index, dtype=bool)
    if bool(cfg["use_atr_vol_filter"]):
        volatility = _numeric(out, str(cfg["volatility_regime_col"]))
        volatility_pass = volatility.isin(set(cfg["allowed_volatility_regimes"]))
        long_filter &= volatility_pass
        short_filter &= volatility_pass
        valid &= volatility.notna()

    base_long_candidate = valid & long_filter
    base_short_candidate = valid & short_filter

    hilbert_pass = pd.Series(True, index=out.index, dtype=bool)
    final_long_candidate = base_long_candidate
    final_short_candidate = base_short_candidate
    if bool(cfg["use_hilbert_filter"]):
        hilbert_pass = _flag(out, str(cfg["hilbert_cycle_ok_col"])) & _flag(
            out,
            str(cfg["hilbert_amplitude_rising_col"]),
        )
        final_long_candidate = base_long_candidate & hilbert_pass
        final_short_candidate = base_short_candidate & hilbert_pass

    if str(cfg["mode"]) == "long_only":
        base_short_candidate = pd.Series(False, index=out.index)
        final_short_candidate = pd.Series(False, index=out.index)
    elif str(cfg["mode"]) == "short_only":
        base_long_candidate = pd.Series(False, index=out.index)
        final_long_candidate = pd.Series(False, index=out.index)

    side = _side_series(final_long_candidate.fillna(False), final_short_candidate.fillna(False))
    if int(cfg["entry_delay_bars"]) > 0:
        side = side.shift(int(cfg["entry_delay_bars"])).fillna(0).astype("int8")

    out[str(cfg["ema_bullish_col"])] = ema_bullish.fillna(False).astype("int8")
    out[str(cfg["ema_bearish_col"])] = ema_bearish.fillna(False).astype("int8")
    out[str(cfg["roofing_positive_col"])] = roofing_positive.fillna(False).astype("int8")
    out[str(cfg["roofing_negative_col"])] = roofing_negative.fillna(False).astype("int8")
    out[str(cfg["roofing_slope_positive_col"])] = roofing_slope_positive.fillna(False).astype("int8")
    out[str(cfg["roofing_slope_negative_col"])] = roofing_slope_negative.fillna(False).astype("int8")
    out[str(cfg["stc_cross_up_col"])] = stc_cross_up.fillna(False).astype("int8")
    out[str(cfg["stc_cross_down_col"])] = stc_cross_down.fillna(False).astype("int8")
    out[str(cfg["hilbert_pass_col"])] = hilbert_pass.fillna(False).astype("int8")
    out[str(cfg["zscore_long_pass_col"])] = zscore_long_pass.fillna(False).astype("int8")
    out[str(cfg["zscore_short_pass_col"])] = zscore_short_pass.fillna(False).astype("int8")
    out[str(cfg["adx_pass_col"])] = adx_pass.fillna(False).astype("int8")
    out[str(cfg["volatility_pass_col"])] = volatility_pass.fillna(False).astype("int8")
    out[str(cfg["long_candidate_col"])] = final_long_candidate.fillna(False).astype("int8")
    out[str(cfg["short_candidate_col"])] = final_short_candidate.fillna(False).astype("int8")
    if bool(cfg["use_hilbert_filter"]):
        out[str(cfg["hilbert_long_candidate_col"])] = final_long_candidate.fillna(False).astype("int8")
        out[str(cfg["hilbert_short_candidate_col"])] = final_short_candidate.fillna(False).astype("int8")
        out[str(cfg["hilbert_signal_col"])] = side
    out[str(cfg["signal_col"])] = side
    out[str(cfg["candidate_col"])] = side.ne(0).astype("int8")

    return out, {
        "kind": "stc_roofing_hilbert",
        "mode": str(cfg["mode"]),
        "stc_long_cross_level": float(cfg["stc_long_cross_level"]),
        "stc_short_cross_level": float(cfg["stc_short_cross_level"]),
        "use_ema_regime": bool(cfg["use_ema_regime"]),
        "use_roofing_filter": bool(cfg["use_roofing_filter"]),
        "use_roofing_slope": bool(cfg["use_roofing_slope"]),
        "use_hilbert_filter": bool(cfg["use_hilbert_filter"]),
        "use_zscore_filter": bool(cfg["use_zscore_filter"]),
        "use_adx_filter": bool(cfg["use_adx_filter"]),
        "use_atr_vol_filter": bool(cfg["use_atr_vol_filter"]),
        "entry_delay_bars": int(cfg["entry_delay_bars"]),
        "long_candidates": int(final_long_candidate.sum()),
        "short_candidates": int(final_short_candidate.sum()),
        "signal_col": str(cfg["signal_col"]),
        "candidate_col": str(cfg["candidate_col"]),
    }


def stc_roofing_hilbert_signal(df: pd.DataFrame, **params: Any) -> pd.DataFrame:
    """
    Apply the registered ``stc_roofing_hilbert`` signal transformation.
    
    This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        signals:
          kind: stc_roofing_hilbert
          params:
            mode: long_short
            ema_fast_col: ema_50
            ema_slow_col: ema_100
            roofing_col: roofing_filter
            roofing_slope_col: roofing_slope
            stc_col: stc
            hilbert_cycle_ok_col: hilbert_cycle_ok
            hilbert_amplitude_rising_col: hilbert_amplitude_rising
            zscore_momentum_col: zscore_momentum_20
            adx_col: adx_14
            volatility_regime_col: volatility_regime
            stc_long_cross_level: 25.0
            stc_short_cross_level: 75.0
            roofing_slope_bars: 3
            use_ema_regime: true
            use_roofing_filter: true
            use_roofing_slope: true
            use_hilbert_filter: false
            use_zscore_filter: false
            use_adx_filter: false
            adx_min: 18.0
            use_atr_vol_filter: false
            allowed_volatility_regimes: [0, 1]
            entry_delay_bars: 0
            long_candidate_col: stc_roofing_long_candidate
            short_candidate_col: stc_roofing_short_candidate
            signal_col: stc_roofing_signal
            candidate_col: stc_roofing_signal_candidate
            hilbert_long_candidate_col: stc_roofing_hilbert_long_candidate
            hilbert_short_candidate_col: stc_roofing_hilbert_short_candidate
            hilbert_signal_col: stc_roofing_hilbert_signal
            ema_bullish_col: stc_roofing_ema_bullish
            ema_bearish_col: stc_roofing_ema_bearish
            roofing_positive_col: stc_roofing_roofing_positive
            roofing_negative_col: stc_roofing_roofing_negative
            roofing_slope_positive_col: stc_roofing_roofing_slope_positive
            roofing_slope_negative_col: stc_roofing_roofing_slope_negative
            stc_cross_up_col: stc_roofing_stc_cross_up
            stc_cross_down_col: stc_roofing_stc_cross_down
            hilbert_pass_col: stc_roofing_hilbert_pass
            zscore_long_pass_col: stc_roofing_zscore_long_pass
            zscore_short_pass_col: stc_roofing_zscore_short_pass
            adx_pass_col: stc_roofing_adx_pass
            volatility_pass_col: stc_roofing_volatility_pass
            output_cols:
              - stc_roofing_long_candidate
              - stc_roofing_short_candidate
              - stc_roofing_signal
              - stc_roofing_signal_candidate
              - stc_roofing_hilbert_long_candidate
              - stc_roofing_hilbert_short_candidate
              - stc_roofing_hilbert_pass
              - stc_roofing_zscore_long_pass
              - stc_roofing_zscore_short_pass
              - stc_roofing_adx_pass
              - stc_roofing_volatility_pass
    
    Required input columns
    ----------------------
    ema_fast_col:
        Input dataframe column configured by ``ema_fast_col``. Default: ``ema_50``.
    ema_slow_col:
        Input dataframe column configured by ``ema_slow_col``. Default: ``ema_100``.
    roofing_col:
        Input dataframe column configured by ``roofing_col``. Default: ``roofing_filter``.
    roofing_slope_col:
        Input dataframe column configured by ``roofing_slope_col``. Default: ``roofing_slope``.
    stc_col:
        Input dataframe column configured by ``stc_col``. Default: ``stc``.
    hilbert_cycle_ok_col:
        Input dataframe column configured by ``hilbert_cycle_ok_col``. Default: ``hilbert_cycle_ok``.
    zscore_momentum_col:
        Input dataframe column configured by ``zscore_momentum_col``. Default: ``zscore_momentum_20``.
    adx_col:
        Input dataframe column configured by ``adx_col``. Default: ``adx_14``.
    volatility_regime_col:
        Input dataframe column configured by ``volatility_regime_col``. Default: ``volatility_regime``.
    roofing_positive_col:
        Input dataframe column configured by ``roofing_positive_col``. Default: ``stc_roofing_roofing_positive``.
    roofing_negative_col:
        Input dataframe column configured by ``roofing_negative_col``. Default: ``stc_roofing_roofing_negative``.
    roofing_slope_positive_col:
        Input dataframe column configured by ``roofing_slope_positive_col``. Default: ``stc_roofing_roofing_slope_positive``.
    roofing_slope_negative_col:
        Input dataframe column configured by ``roofing_slope_negative_col``. Default: ``stc_roofing_roofing_slope_negative``.
    stc_cross_up_col:
        Input dataframe column configured by ``stc_cross_up_col``. Default: ``stc_roofing_stc_cross_up``.
    stc_cross_down_col:
        Input dataframe column configured by ``stc_cross_down_col``. Default: ``stc_roofing_stc_cross_down``.
    
    Parameters
    ----------
    mode:
        Mode selector controlling how this signal is applied. Default: ``long_short``.
    ema_fast_col:
        Input dataframe column configured by ``ema_fast_col``. Default: ``ema_50``.
    ema_slow_col:
        Input dataframe column configured by ``ema_slow_col``. Default: ``ema_100``.
    roofing_col:
        Input dataframe column configured by ``roofing_col``. Default: ``roofing_filter``.
    roofing_slope_col:
        Input dataframe column configured by ``roofing_slope_col``. Default: ``roofing_slope``.
    stc_col:
        Input dataframe column configured by ``stc_col``. Default: ``stc``.
    hilbert_cycle_ok_col:
        Input dataframe column configured by ``hilbert_cycle_ok_col``. Default: ``hilbert_cycle_ok``.
    hilbert_amplitude_rising_col:
        Input dataframe column configured by ``hilbert_amplitude_rising_col``. Default: ``hilbert_amplitude_rising``.
    zscore_momentum_col:
        Input dataframe column configured by ``zscore_momentum_col``. Default: ``zscore_momentum_20``.
    adx_col:
        Input dataframe column configured by ``adx_col``. Default: ``adx_14``.
    volatility_regime_col:
        Input dataframe column configured by ``volatility_regime_col``. Default: ``volatility_regime``.
    stc_long_cross_level:
        Configuration parameter accepted by this signal. Default: ``25.0``.
    stc_short_cross_level:
        Configuration parameter accepted by this signal. Default: ``75.0``.
    roofing_slope_bars:
        Configuration parameter accepted by this signal. Default: ``3``.
    use_ema_regime:
        Boolean switch controlling optional signal behavior. Default: ``true``.
    use_roofing_filter:
        Boolean switch controlling optional signal behavior. Default: ``true``.
    use_roofing_slope:
        Boolean switch controlling optional signal behavior. Default: ``true``.
    use_hilbert_filter:
        Boolean switch controlling optional signal behavior. Default: ``false``.
    use_zscore_filter:
        Boolean switch controlling optional signal behavior. Default: ``false``.
    use_adx_filter:
        Boolean switch controlling optional signal behavior. Default: ``false``.
    adx_min:
        Numeric threshold used by this signal. Default: ``18.0``.
    use_atr_vol_filter:
        Boolean switch controlling optional signal behavior. Default: ``false``.
    allowed_volatility_regimes:
        Configuration parameter accepted by this signal. Default: ``[0, 1]``.
    entry_delay_bars:
        Configuration parameter accepted by this signal. Default: ``0``.
    long_candidate_col:
        Output dataframe column configured by ``long_candidate_col``. Default: ``stc_roofing_long_candidate``.
    short_candidate_col:
        Output dataframe column configured by ``short_candidate_col``. Default: ``stc_roofing_short_candidate``.
    signal_col:
        Output dataframe column configured by ``signal_col``. Default: ``stc_roofing_signal``.
    candidate_col:
        Output dataframe column configured by ``candidate_col``. Default: ``stc_roofing_signal_candidate``.
    hilbert_long_candidate_col:
        Output dataframe column configured by ``hilbert_long_candidate_col``. Default: ``stc_roofing_hilbert_long_candidate``.
    hilbert_short_candidate_col:
        Output dataframe column configured by ``hilbert_short_candidate_col``. Default: ``stc_roofing_hilbert_short_candidate``.
    hilbert_signal_col:
        Input dataframe column configured by ``hilbert_signal_col``. Default: ``stc_roofing_hilbert_signal``.
    ema_bullish_col:
        Input dataframe column configured by ``ema_bullish_col``. Default: ``stc_roofing_ema_bullish``.
    ema_bearish_col:
        Input dataframe column configured by ``ema_bearish_col``. Default: ``stc_roofing_ema_bearish``.
    roofing_positive_col:
        Input dataframe column configured by ``roofing_positive_col``. Default: ``stc_roofing_roofing_positive``.
    roofing_negative_col:
        Input dataframe column configured by ``roofing_negative_col``. Default: ``stc_roofing_roofing_negative``.
    roofing_slope_positive_col:
        Input dataframe column configured by ``roofing_slope_positive_col``. Default: ``stc_roofing_roofing_slope_positive``.
    roofing_slope_negative_col:
        Input dataframe column configured by ``roofing_slope_negative_col``. Default: ``stc_roofing_roofing_slope_negative``.
    stc_cross_up_col:
        Input dataframe column configured by ``stc_cross_up_col``. Default: ``stc_roofing_stc_cross_up``.
    stc_cross_down_col:
        Input dataframe column configured by ``stc_cross_down_col``. Default: ``stc_roofing_stc_cross_down``.
    hilbert_pass_col:
        Output dataframe column configured by ``hilbert_pass_col``. Default: ``stc_roofing_hilbert_pass``.
    zscore_long_pass_col:
        Output dataframe column configured by ``zscore_long_pass_col``. Default: ``stc_roofing_zscore_long_pass``.
    zscore_short_pass_col:
        Output dataframe column configured by ``zscore_short_pass_col``. Default: ``stc_roofing_zscore_short_pass``.
    adx_pass_col:
        Output dataframe column configured by ``adx_pass_col``. Default: ``stc_roofing_adx_pass``.
    volatility_pass_col:
        Output dataframe column configured by ``volatility_pass_col``. Default: ``stc_roofing_volatility_pass``.
    """
    out, _ = build_stc_roofing_hilbert_signal(df, params)
    return out


__all__ = ["build_stc_roofing_hilbert_signal", "stc_roofing_hilbert_signal"]
