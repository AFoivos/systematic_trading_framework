from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd


_ALLOWED_MODES = frozenset({"long_only", "short_only", "long_short"})
_ALLOWED_STOCH_ENTRY_MODES = frozenset({"reset", "cross", "reset_or_cross"})

_DEFAULT_CFG: dict[str, Any] = {
    "close_col": "close",
    "high_col": "high",
    "low_col": "low",
    "ema_fast_col": "ema_50",
    "ema_slow_col": "ema_150",
    "ppo_col": "ppo",
    "ppo_signal_col": "ppo_signal",
    "adx_col": "adx",
    "plus_di_col": "plus_di",
    "minus_di_col": "minus_di",
    "atr_col": "atr",
    "stoch_k_col": "stochrsi_k",
    "stoch_d_col": "stochrsi_d",
    "mode": "long_short",
    "require_adx": True,
    "adx_threshold": 20.0,
    "ppo_slope_threshold": 0.0,
    "stoch_oversold": 0.20,
    "stoch_overbought": 0.80,
    "stoch_entry_mode": "reset_or_cross",
    "atr_stop_mult": 1.5,
    "atr_take_profit_mult": 2.0,
    "atr_trailing_mult": 1.0,
    "use_atr_trailing_stop": False,
    "signal_col": "signal",
    "position_col": "position",
    "entry_long_col": "entry_long",
    "entry_short_col": "entry_short",
    "exit_long_col": "exit_long",
    "exit_short_col": "exit_short",
    "long_setup_col": "long_setup",
    "short_setup_col": "short_setup",
    "exit_long_rule_col": "exit_long_rule",
    "exit_short_rule_col": "exit_short_rule",
    "ppo_slope_col": "ppo_slope",
    "ema_trend_state_col": "ema_trend_state",
    "directional_spread_col": "directional_spread",
    "stoch_bullish_reset_col": "stochrsi_bullish_reset",
    "stoch_bearish_reset_col": "stochrsi_bearish_reset",
    "stoch_bullish_cross_col": "stochrsi_bullish_cross",
    "stoch_bearish_cross_col": "stochrsi_bearish_cross",
    "atr_stop_distance_col": "atr_stop_distance",
    "atr_take_profit_distance_col": "atr_take_profit_distance",
    "atr_stop_long_col": "atr_stop_long",
    "atr_stop_short_col": "atr_stop_short",
    "atr_take_profit_long_col": "atr_take_profit_long",
    "atr_take_profit_short_col": "atr_take_profit_short",
    "atr_trailing_stop_long_col": "atr_trailing_stop_long",
    "atr_trailing_stop_short_col": "atr_trailing_stop_short",
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


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for ppo_adx_stochrsi_trend_signal: {missing}")


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce").astype(float)


def _finite_float(value: Any, *, field: str) -> float:
    out = float(value)
    if not np.isfinite(out):
        raise ValueError(f"{field} must be finite.")
    return out


def _validate_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(cfg)
    string_keys = (
        "close_col",
        "high_col",
        "low_col",
        "ema_fast_col",
        "ema_slow_col",
        "ppo_col",
        "ppo_signal_col",
        "adx_col",
        "plus_di_col",
        "minus_di_col",
        "atr_col",
        "stoch_k_col",
        "stoch_d_col",
        "signal_col",
        "position_col",
        "entry_long_col",
        "entry_short_col",
        "exit_long_col",
        "exit_short_col",
        "long_setup_col",
        "short_setup_col",
        "exit_long_rule_col",
        "exit_short_rule_col",
        "ppo_slope_col",
        "ema_trend_state_col",
        "directional_spread_col",
        "stoch_bullish_reset_col",
        "stoch_bearish_reset_col",
        "stoch_bullish_cross_col",
        "stoch_bearish_cross_col",
        "atr_stop_distance_col",
        "atr_take_profit_distance_col",
        "atr_stop_long_col",
        "atr_stop_short_col",
        "atr_take_profit_long_col",
        "atr_take_profit_short_col",
        "atr_trailing_stop_long_col",
        "atr_trailing_stop_short_col",
    )
    for key in string_keys:
        value = normalized.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string.")
        normalized[key] = value.strip()

    mode = str(normalized.get("mode", "long_short"))
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of: {sorted(_ALLOWED_MODES)}.")
    normalized["mode"] = mode

    stoch_entry_mode = str(normalized.get("stoch_entry_mode", "reset_or_cross"))
    if stoch_entry_mode not in _ALLOWED_STOCH_ENTRY_MODES:
        raise ValueError(
            f"stoch_entry_mode must be one of: {sorted(_ALLOWED_STOCH_ENTRY_MODES)}."
        )
    normalized["stoch_entry_mode"] = stoch_entry_mode

    for key in ("require_adx", "use_atr_trailing_stop"):
        if not isinstance(normalized.get(key), bool):
            raise TypeError(f"{key} must be boolean.")

    for key in (
        "adx_threshold",
        "ppo_slope_threshold",
        "stoch_oversold",
        "stoch_overbought",
        "atr_stop_mult",
        "atr_take_profit_mult",
        "atr_trailing_mult",
    ):
        normalized[key] = _finite_float(normalized.get(key), field=key)

    if normalized["adx_threshold"] < 0.0:
        raise ValueError("adx_threshold must be >= 0.")
    if normalized["ppo_slope_threshold"] < 0.0:
        raise ValueError("ppo_slope_threshold must be >= 0.")
    if not 0.0 <= normalized["stoch_oversold"] <= 1.0:
        raise ValueError("stoch_oversold must be in [0, 1].")
    if not 0.0 <= normalized["stoch_overbought"] <= 1.0:
        raise ValueError("stoch_overbought must be in [0, 1].")
    if normalized["stoch_oversold"] >= normalized["stoch_overbought"]:
        raise ValueError("stoch_oversold must be less than stoch_overbought.")
    for key in ("atr_stop_mult", "atr_take_profit_mult", "atr_trailing_mult"):
        if normalized[key] <= 0.0:
            raise ValueError(f"{key} must be > 0.")
    return normalized


def _entry_selector(
    *,
    reset: pd.Series,
    cross: pd.Series,
    mode: str,
) -> pd.Series:
    if mode == "reset":
        return reset
    if mode == "cross":
        return cross
    return reset | cross


def _direction_state(
    *,
    entry: pd.Series,
    exit_rule: pd.Series,
    opposite_entry: pd.Series,
    side: float,
) -> pd.Series:
    event = pd.Series(np.nan, index=entry.index, dtype=float)
    event.loc[(exit_rule | opposite_entry).fillna(False)] = 0.0
    event.loc[entry.fillna(False)] = float(side)
    return event.ffill().fillna(0.0).astype(float)


def _last_event_position(event: pd.Series) -> pd.Series:
    positions = np.arange(len(event), dtype=float)
    return pd.Series(
        np.where(event.fillna(False).astype(bool).to_numpy(dtype=bool), positions, np.nan),
        index=event.index,
        dtype=float,
    ).ffill()


def build_ppo_adx_stochrsi_trend_signal(
    df: pd.DataFrame,
    signal_cfg: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Build a causal PPO/ADX/StochRSI trend-continuation signal.

    The signal is generated from values known at the current bar close. Backtest execution
    remains responsible for applying the execution lag and pricing assumptions.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    cfg = _validate_cfg(_merge_cfg(signal_cfg, overrides))
    required_cols = [
        str(cfg["close_col"]),
        str(cfg["high_col"]),
        str(cfg["low_col"]),
        str(cfg["ema_fast_col"]),
        str(cfg["ema_slow_col"]),
        str(cfg["ppo_col"]),
        str(cfg["ppo_signal_col"]),
        str(cfg["adx_col"]),
        str(cfg["plus_di_col"]),
        str(cfg["minus_di_col"]),
        str(cfg["atr_col"]),
        str(cfg["stoch_k_col"]),
        str(cfg["stoch_d_col"]),
    ]
    _require_columns(df, required_cols)

    out = df.copy()
    close = _numeric(out, str(cfg["close_col"]))
    high = _numeric(out, str(cfg["high_col"]))
    low = _numeric(out, str(cfg["low_col"]))
    ema_fast = _numeric(out, str(cfg["ema_fast_col"]))
    ema_slow = _numeric(out, str(cfg["ema_slow_col"]))
    ppo = _numeric(out, str(cfg["ppo_col"]))
    ppo_signal = _numeric(out, str(cfg["ppo_signal_col"]))
    adx = _numeric(out, str(cfg["adx_col"]))
    plus_di = _numeric(out, str(cfg["plus_di_col"]))
    minus_di = _numeric(out, str(cfg["minus_di_col"]))
    atr = _numeric(out, str(cfg["atr_col"]))
    stoch_k = _numeric(out, str(cfg["stoch_k_col"]))
    stoch_d = _numeric(out, str(cfg["stoch_d_col"]))

    ppo_slope = ppo - ppo.shift(1)
    directional_spread = plus_di - minus_di
    ema_trend_state = pd.Series(0, index=out.index, dtype="int8")
    ema_trend_state.loc[ema_fast.gt(ema_slow)] = 1
    ema_trend_state.loc[ema_fast.lt(ema_slow)] = -1

    stoch_bullish_reset = (
        stoch_k.shift(1).le(float(cfg["stoch_oversold"]))
        & stoch_k.gt(float(cfg["stoch_oversold"]))
        & stoch_k.gt(stoch_d)
    )
    stoch_bearish_reset = (
        stoch_k.shift(1).ge(float(cfg["stoch_overbought"]))
        & stoch_k.lt(float(cfg["stoch_overbought"]))
        & stoch_k.lt(stoch_d)
    )
    stoch_bullish_cross = stoch_k.shift(1).le(stoch_d.shift(1)) & stoch_k.gt(stoch_d)
    stoch_bearish_cross = stoch_k.shift(1).ge(stoch_d.shift(1)) & stoch_k.lt(stoch_d)
    bullish_stoch_ok = _entry_selector(
        reset=stoch_bullish_reset,
        cross=stoch_bullish_cross,
        mode=str(cfg["stoch_entry_mode"]),
    )
    bearish_stoch_ok = _entry_selector(
        reset=stoch_bearish_reset,
        cross=stoch_bearish_cross,
        mode=str(cfg["stoch_entry_mode"]),
    )

    required_valid = (
        close.notna()
        & high.notna()
        & low.notna()
        & ema_fast.notna()
        & ema_slow.notna()
        & ppo.notna()
        & ppo_signal.notna()
        & plus_di.notna()
        & minus_di.notna()
        & atr.notna()
        & stoch_k.notna()
        & stoch_d.notna()
    )
    adx_ok = pd.Series(True, index=out.index, dtype=bool)
    if bool(cfg["require_adx"]):
        adx_ok = adx.gt(float(cfg["adx_threshold"])) & adx.notna()
        required_valid &= adx.notna()

    long_setup = (
        ema_fast.gt(ema_slow)
        & ppo.gt(0.0)
        & ppo_signal.gt(0.0)
        & plus_di.gt(minus_di)
        & bullish_stoch_ok
        & adx_ok
        & required_valid
    )
    short_setup = (
        ema_fast.lt(ema_slow)
        & ppo.lt(0.0)
        & ppo_signal.lt(0.0)
        & minus_di.gt(plus_di)
        & bearish_stoch_ok
        & adx_ok
        & required_valid
    )

    if str(cfg["mode"]) == "long_only":
        short_setup = pd.Series(False, index=out.index)
    elif str(cfg["mode"]) == "short_only":
        long_setup = pd.Series(False, index=out.index)

    slope_threshold = float(cfg["ppo_slope_threshold"])
    exit_long_rule = (
        minus_di.gt(plus_di)
        | ppo_slope.lt(-slope_threshold)
        | close.lt(ema_fast)
    ).fillna(False)
    exit_short_rule = (
        plus_di.gt(minus_di)
        | ppo_slope.gt(slope_threshold)
        | close.gt(ema_fast)
    ).fillna(False)

    long_state = _direction_state(
        entry=long_setup,
        exit_rule=exit_long_rule,
        opposite_entry=short_setup,
        side=1.0,
    )
    short_state = _direction_state(
        entry=short_setup,
        exit_rule=exit_short_rule,
        opposite_entry=long_setup,
        side=-1.0,
    )
    last_long_entry = _last_event_position(long_setup)
    last_short_entry = _last_event_position(short_setup)

    long_active = long_state.gt(0.0)
    short_active = short_state.lt(0.0)
    long_is_latest = last_long_entry.fillna(-1.0).ge(last_short_entry.fillna(-1.0))
    short_is_latest = last_short_entry.fillna(-1.0).gt(last_long_entry.fillna(-1.0))
    position = pd.Series(0.0, index=out.index, dtype=float)
    position.loc[long_active & (~short_active | long_is_latest)] = 1.0
    position.loc[short_active & (~long_active | short_is_latest)] = -1.0

    previous_position = position.shift(1).fillna(0.0)
    entry_long = position.gt(0.0) & previous_position.le(0.0)
    entry_short = position.lt(0.0) & previous_position.ge(0.0)
    exit_long = previous_position.gt(0.0) & position.le(0.0)
    exit_short = previous_position.lt(0.0) & position.ge(0.0)

    entry_event = entry_long | entry_short
    trade_group = entry_event.astype("int64").cumsum().where(position.ne(0.0))
    entry_close = close.where(entry_event).ffill().where(position.ne(0.0))
    entry_atr = atr.where(entry_event).ffill().where(position.ne(0.0))
    stop_distance = (entry_atr * float(cfg["atr_stop_mult"])).where(position.ne(0.0))
    take_profit_distance = (entry_atr * float(cfg["atr_take_profit_mult"])).where(position.ne(0.0))

    long_mask = position.gt(0.0)
    short_mask = position.lt(0.0)
    long_stop = (entry_close - stop_distance).where(long_mask)
    short_stop = (entry_close + stop_distance).where(short_mask)
    long_take_profit = (entry_close + take_profit_distance).where(long_mask)
    short_take_profit = (entry_close - take_profit_distance).where(short_mask)

    running_high = high.where(long_mask).groupby(trade_group).cummax()
    running_low = low.where(short_mask).groupby(trade_group).cummin()
    trailing_distance = (entry_atr * float(cfg["atr_trailing_mult"])).where(position.ne(0.0))
    long_trailing_stop = (running_high - trailing_distance).where(
        long_mask & bool(cfg["use_atr_trailing_stop"])
    )
    short_trailing_stop = (running_low + trailing_distance).where(
        short_mask & bool(cfg["use_atr_trailing_stop"])
    )

    out[str(cfg["ppo_slope_col"])] = ppo_slope.astype("float32")
    out[str(cfg["ema_trend_state_col"])] = ema_trend_state.astype("int8")
    out[str(cfg["directional_spread_col"])] = directional_spread.astype("float32")
    out[str(cfg["stoch_bullish_reset_col"])] = stoch_bullish_reset.fillna(False).astype("int8")
    out[str(cfg["stoch_bearish_reset_col"])] = stoch_bearish_reset.fillna(False).astype("int8")
    out[str(cfg["stoch_bullish_cross_col"])] = stoch_bullish_cross.fillna(False).astype("int8")
    out[str(cfg["stoch_bearish_cross_col"])] = stoch_bearish_cross.fillna(False).astype("int8")
    out[str(cfg["long_setup_col"])] = long_setup.fillna(False).astype("int8")
    out[str(cfg["short_setup_col"])] = short_setup.fillna(False).astype("int8")
    out[str(cfg["exit_long_rule_col"])] = exit_long_rule.fillna(False).astype("int8")
    out[str(cfg["exit_short_rule_col"])] = exit_short_rule.fillna(False).astype("int8")
    out[str(cfg["atr_stop_distance_col"])] = stop_distance.astype("float32")
    out[str(cfg["atr_take_profit_distance_col"])] = take_profit_distance.astype("float32")
    out[str(cfg["atr_stop_long_col"])] = long_stop.astype("float32")
    out[str(cfg["atr_stop_short_col"])] = short_stop.astype("float32")
    out[str(cfg["atr_take_profit_long_col"])] = long_take_profit.astype("float32")
    out[str(cfg["atr_take_profit_short_col"])] = short_take_profit.astype("float32")
    out[str(cfg["atr_trailing_stop_long_col"])] = long_trailing_stop.astype("float32")
    out[str(cfg["atr_trailing_stop_short_col"])] = short_trailing_stop.astype("float32")
    out[str(cfg["entry_long_col"])] = entry_long.fillna(False).astype("int8")
    out[str(cfg["entry_short_col"])] = entry_short.fillna(False).astype("int8")
    out[str(cfg["exit_long_col"])] = exit_long.fillna(False).astype("int8")
    out[str(cfg["exit_short_col"])] = exit_short.fillna(False).astype("int8")
    out[str(cfg["position_col"])] = position.astype("float32")
    out[str(cfg["signal_col"])] = position.astype("float32")

    output_cols = [
        str(cfg["ppo_slope_col"]),
        str(cfg["ema_trend_state_col"]),
        str(cfg["directional_spread_col"]),
        str(cfg["stoch_bullish_reset_col"]),
        str(cfg["stoch_bearish_reset_col"]),
        str(cfg["stoch_bullish_cross_col"]),
        str(cfg["stoch_bearish_cross_col"]),
        str(cfg["long_setup_col"]),
        str(cfg["short_setup_col"]),
        str(cfg["exit_long_rule_col"]),
        str(cfg["exit_short_rule_col"]),
        str(cfg["atr_stop_distance_col"]),
        str(cfg["atr_take_profit_distance_col"]),
        str(cfg["atr_stop_long_col"]),
        str(cfg["atr_stop_short_col"]),
        str(cfg["atr_take_profit_long_col"]),
        str(cfg["atr_take_profit_short_col"]),
        str(cfg["atr_trailing_stop_long_col"]),
        str(cfg["atr_trailing_stop_short_col"]),
        str(cfg["entry_long_col"]),
        str(cfg["entry_short_col"]),
        str(cfg["exit_long_col"]),
        str(cfg["exit_short_col"]),
        str(cfg["position_col"]),
        str(cfg["signal_col"]),
    ]
    meta = {
        "kind": "ppo_adx_stochrsi_trend",
        "params": {key: cfg[key] for key in sorted(cfg)},
        "output_cols": output_cols,
        "long_entries": int(out[str(cfg["entry_long_col"])].sum()),
        "short_entries": int(out[str(cfg["entry_short_col"])].sum()),
        "long_exits": int(out[str(cfg["exit_long_col"])].sum()),
        "short_exits": int(out[str(cfg["exit_short_col"])].sum()),
        "nonzero_position_rows": int(position.ne(0.0).sum()),
    }
    return out, meta


def ppo_adx_stochrsi_trend_signal(
    df: pd.DataFrame,
    **params: Any,
) -> pd.DataFrame:
    """
    Apply the registered ``ppo_adx_stochrsi_trend`` signal transformation.
    
    This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        signals:
          kind: ppo_adx_stochrsi_trend
          params:
            close_col: close
            high_col: high
            low_col: low
            ema_fast_col: ema_50
            ema_slow_col: ema_150
            ppo_col: ppo
            ppo_signal_col: ppo_signal
            adx_col: adx
            plus_di_col: plus_di
            minus_di_col: minus_di
            atr_col: atr
            stoch_k_col: stochrsi_k
            stoch_d_col: stochrsi_d
            mode: long_short
            require_adx: true
            adx_threshold: 20.0
            ppo_slope_threshold: 0.0
            stoch_oversold: 0.2
            stoch_overbought: 0.8
            stoch_entry_mode: reset_or_cross
            atr_stop_mult: 1.5
            atr_take_profit_mult: 2.0
            atr_trailing_mult: 1.0
            use_atr_trailing_stop: false
            signal_col: signal
            position_col: position
            entry_long_col: entry_long
            entry_short_col: entry_short
            exit_long_col: exit_long
            exit_short_col: exit_short
            long_setup_col: long_setup
            short_setup_col: short_setup
            exit_long_rule_col: exit_long_rule
            exit_short_rule_col: exit_short_rule
            ppo_slope_col: ppo_slope
            ema_trend_state_col: ema_trend_state
            directional_spread_col: directional_spread
            stoch_bullish_reset_col: stochrsi_bullish_reset
            stoch_bearish_reset_col: stochrsi_bearish_reset
            stoch_bullish_cross_col: stochrsi_bullish_cross
            stoch_bearish_cross_col: stochrsi_bearish_cross
            atr_stop_distance_col: atr_stop_distance
            atr_take_profit_distance_col: atr_take_profit_distance
            atr_stop_long_col: atr_stop_long
            atr_stop_short_col: atr_stop_short
            atr_take_profit_long_col: atr_take_profit_long
            atr_take_profit_short_col: atr_take_profit_short
            atr_trailing_stop_long_col: atr_trailing_stop_long
            atr_trailing_stop_short_col: atr_trailing_stop_short
            output_cols:
              - signal
    
    Required input columns
    ----------------------
    close_col:
        Input dataframe column configured by ``close_col``. Default: ``close``.
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    ema_fast_col:
        Input dataframe column configured by ``ema_fast_col``. Default: ``ema_50``.
    ema_slow_col:
        Input dataframe column configured by ``ema_slow_col``. Default: ``ema_150``.
    ppo_col:
        Input dataframe column configured by ``ppo_col``. Default: ``ppo``.
    adx_col:
        Input dataframe column configured by ``adx_col``. Default: ``adx``.
    plus_di_col:
        Input dataframe column configured by ``plus_di_col``. Default: ``plus_di``.
    minus_di_col:
        Input dataframe column configured by ``minus_di_col``. Default: ``minus_di``.
    atr_col:
        Input dataframe column configured by ``atr_col``. Default: ``atr``.
    stoch_k_col:
        Input dataframe column configured by ``stoch_k_col``. Default: ``stochrsi_k``.
    stoch_d_col:
        Input dataframe column configured by ``stoch_d_col``. Default: ``stochrsi_d``.
    position_col:
        Input dataframe column configured by ``position_col``. Default: ``position``.
    entry_long_col:
        Input dataframe column configured by ``entry_long_col``. Default: ``entry_long``.
    entry_short_col:
        Input dataframe column configured by ``entry_short_col``. Default: ``entry_short``.
    exit_long_col:
        Input dataframe column configured by ``exit_long_col``. Default: ``exit_long``.
    exit_short_col:
        Input dataframe column configured by ``exit_short_col``. Default: ``exit_short``.
    long_setup_col:
        Input dataframe column configured by ``long_setup_col``. Default: ``long_setup``.
    short_setup_col:
        Input dataframe column configured by ``short_setup_col``. Default: ``short_setup``.
    exit_long_rule_col:
        Input dataframe column configured by ``exit_long_rule_col``. Default: ``exit_long_rule``.
    exit_short_rule_col:
        Input dataframe column configured by ``exit_short_rule_col``. Default: ``exit_short_rule``.
    ppo_slope_col:
        Input dataframe column configured by ``ppo_slope_col``. Default: ``ppo_slope``.
    ema_trend_state_col:
        Input dataframe column configured by ``ema_trend_state_col``. Default: ``ema_trend_state``.
    directional_spread_col:
        Input dataframe column configured by ``directional_spread_col``. Default: ``directional_spread``.
    atr_stop_distance_col:
        Input dataframe column configured by ``atr_stop_distance_col``. Default: ``atr_stop_distance``.
    atr_take_profit_distance_col:
        Input dataframe column configured by ``atr_take_profit_distance_col``. Default: ``atr_take_profit_distance``.
    atr_stop_long_col:
        Input dataframe column configured by ``atr_stop_long_col``. Default: ``atr_stop_long``.
    atr_stop_short_col:
        Input dataframe column configured by ``atr_stop_short_col``. Default: ``atr_stop_short``.
    atr_take_profit_long_col:
        Input dataframe column configured by ``atr_take_profit_long_col``. Default: ``atr_take_profit_long``.
    atr_take_profit_short_col:
        Input dataframe column configured by ``atr_take_profit_short_col``. Default: ``atr_take_profit_short``.
    atr_trailing_stop_long_col:
        Input dataframe column configured by ``atr_trailing_stop_long_col``. Default: ``atr_trailing_stop_long``.
    atr_trailing_stop_short_col:
        Input dataframe column configured by ``atr_trailing_stop_short_col``. Default: ``atr_trailing_stop_short``.
    
    Parameters
    ----------
    close_col:
        Input dataframe column configured by ``close_col``. Default: ``close``.
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    ema_fast_col:
        Input dataframe column configured by ``ema_fast_col``. Default: ``ema_50``.
    ema_slow_col:
        Input dataframe column configured by ``ema_slow_col``. Default: ``ema_150``.
    ppo_col:
        Input dataframe column configured by ``ppo_col``. Default: ``ppo``.
    ppo_signal_col:
        Input dataframe column configured by ``ppo_signal_col``. Default: ``ppo_signal``.
    adx_col:
        Input dataframe column configured by ``adx_col``. Default: ``adx``.
    plus_di_col:
        Input dataframe column configured by ``plus_di_col``. Default: ``plus_di``.
    minus_di_col:
        Input dataframe column configured by ``minus_di_col``. Default: ``minus_di``.
    atr_col:
        Input dataframe column configured by ``atr_col``. Default: ``atr``.
    stoch_k_col:
        Input dataframe column configured by ``stoch_k_col``. Default: ``stochrsi_k``.
    stoch_d_col:
        Input dataframe column configured by ``stoch_d_col``. Default: ``stochrsi_d``.
    mode:
        Mode selector controlling how this signal is applied. Default: ``long_short``.
    require_adx:
        Configuration parameter accepted by this signal. Default: ``true``.
    adx_threshold:
        Numeric threshold used by this signal. Default: ``20.0``.
    ppo_slope_threshold:
        Numeric threshold used by this signal. Default: ``0.0``.
    stoch_oversold:
        Configuration parameter accepted by this signal. Default: ``0.2``.
    stoch_overbought:
        Configuration parameter accepted by this signal. Default: ``0.8``.
    stoch_entry_mode:
        Mode selector controlling how this signal is applied. Default: ``reset_or_cross``.
    atr_stop_mult:
        Configuration parameter accepted by this signal. Default: ``1.5``.
    atr_take_profit_mult:
        Configuration parameter accepted by this signal. Default: ``2.0``.
    atr_trailing_mult:
        Configuration parameter accepted by this signal. Default: ``1.0``.
    use_atr_trailing_stop:
        Boolean switch controlling optional signal behavior. Default: ``false``.
    signal_col:
        Output dataframe column configured by ``signal_col``. Default: ``signal``.
    position_col:
        Input dataframe column configured by ``position_col``. Default: ``position``.
    entry_long_col:
        Input dataframe column configured by ``entry_long_col``. Default: ``entry_long``.
    entry_short_col:
        Input dataframe column configured by ``entry_short_col``. Default: ``entry_short``.
    exit_long_col:
        Input dataframe column configured by ``exit_long_col``. Default: ``exit_long``.
    exit_short_col:
        Input dataframe column configured by ``exit_short_col``. Default: ``exit_short``.
    long_setup_col:
        Input dataframe column configured by ``long_setup_col``. Default: ``long_setup``.
    short_setup_col:
        Input dataframe column configured by ``short_setup_col``. Default: ``short_setup``.
    exit_long_rule_col:
        Input dataframe column configured by ``exit_long_rule_col``. Default: ``exit_long_rule``.
    exit_short_rule_col:
        Input dataframe column configured by ``exit_short_rule_col``. Default: ``exit_short_rule``.
    ppo_slope_col:
        Input dataframe column configured by ``ppo_slope_col``. Default: ``ppo_slope``.
    ema_trend_state_col:
        Input dataframe column configured by ``ema_trend_state_col``. Default: ``ema_trend_state``.
    directional_spread_col:
        Input dataframe column configured by ``directional_spread_col``. Default: ``directional_spread``.
    stoch_bullish_reset_col:
        Input dataframe column configured by ``stoch_bullish_reset_col``. Default: ``stochrsi_bullish_reset``.
    stoch_bearish_reset_col:
        Input dataframe column configured by ``stoch_bearish_reset_col``. Default: ``stochrsi_bearish_reset``.
    stoch_bullish_cross_col:
        Input dataframe column configured by ``stoch_bullish_cross_col``. Default: ``stochrsi_bullish_cross``.
    stoch_bearish_cross_col:
        Input dataframe column configured by ``stoch_bearish_cross_col``. Default: ``stochrsi_bearish_cross``.
    atr_stop_distance_col:
        Input dataframe column configured by ``atr_stop_distance_col``. Default: ``atr_stop_distance``.
    atr_take_profit_distance_col:
        Input dataframe column configured by ``atr_take_profit_distance_col``. Default: ``atr_take_profit_distance``.
    atr_stop_long_col:
        Input dataframe column configured by ``atr_stop_long_col``. Default: ``atr_stop_long``.
    atr_stop_short_col:
        Input dataframe column configured by ``atr_stop_short_col``. Default: ``atr_stop_short``.
    atr_take_profit_long_col:
        Input dataframe column configured by ``atr_take_profit_long_col``. Default: ``atr_take_profit_long``.
    atr_take_profit_short_col:
        Input dataframe column configured by ``atr_take_profit_short_col``. Default: ``atr_take_profit_short``.
    atr_trailing_stop_long_col:
        Input dataframe column configured by ``atr_trailing_stop_long_col``. Default: ``atr_trailing_stop_long``.
    atr_trailing_stop_short_col:
        Input dataframe column configured by ``atr_trailing_stop_short_col``. Default: ``atr_trailing_stop_short``.
    """
    out, _ = build_ppo_adx_stochrsi_trend_signal(df, params)
    return out


__all__ = [
    "build_ppo_adx_stochrsi_trend_signal",
    "ppo_adx_stochrsi_trend_signal",
]
