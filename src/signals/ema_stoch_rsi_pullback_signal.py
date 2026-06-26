from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd


_DEFAULT_CFG: dict[str, Any] = {
    "price_col": "close",
    "ema_fast_col": "ema_50",
    "ema_slow_col": "ema_150",
    "stoch_k_col": "stoch_rsi_k",
    "stoch_d_col": "stoch_rsi_d",
    "stoch_recover_col": "stoch_rsi_recover_from_oversold",
    "stoch_fall_col": "stoch_rsi_fall_from_overbought",
    "oversold": 0.20,
    "overbought": 0.80,
    "max_bars_after_cross": 30,
    "require_k_d_confirmation": True,
    "require_price_above_slow_ema_for_long": True,
    "require_price_below_slow_ema_for_short": True,
    "use_first_pullback_only": True,
    "prefix": "ema_stoch",
    "side_col": "signal_side",
    "candidate_col": "signal_candidate",
    "signal_col": None,
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
        raise KeyError(f"Missing columns for ema_stoch_rsi_pullback_signal: {missing}")


def _numeric(df: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(df[column], errors="coerce").astype(float)


def _bars_since_event(event: pd.Series) -> pd.Series:
    mask = event.fillna(False).astype(bool).to_numpy(dtype=bool)
    positions = np.arange(len(mask), dtype=float)
    last_event = pd.Series(
        np.where(mask, positions, np.nan),
        index=event.index,
        dtype=float,
    ).ffill()
    ages = pd.Series(positions, index=event.index, dtype=float) - last_event
    return ages.where(last_event.notna(), other=np.nan).astype("float32")


def _validate_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(cfg)
    string_keys = (
        "price_col",
        "ema_fast_col",
        "ema_slow_col",
        "stoch_k_col",
        "stoch_d_col",
        "stoch_recover_col",
        "stoch_fall_col",
        "prefix",
        "side_col",
        "candidate_col",
    )
    for key in string_keys:
        value = normalized.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string.")
        normalized[key] = value.strip()

    signal_col = normalized.get("signal_col")
    if signal_col is not None:
        if not isinstance(signal_col, str) or not signal_col.strip():
            raise ValueError("signal_col must be a non-empty string or None.")
        normalized["signal_col"] = signal_col.strip()

    oversold = float(normalized["oversold"])
    overbought = float(normalized["overbought"])
    if not 0.0 <= oversold <= 1.0:
        raise ValueError("oversold must be in [0, 1].")
    if not 0.0 <= overbought <= 1.0:
        raise ValueError("overbought must be in [0, 1].")
    if oversold >= overbought:
        raise ValueError("oversold must be less than overbought.")
    normalized["oversold"] = oversold
    normalized["overbought"] = overbought

    max_bars = normalized["max_bars_after_cross"]
    if isinstance(max_bars, bool) or int(max_bars) < 0:
        raise ValueError("max_bars_after_cross must be an integer >= 0.")
    normalized["max_bars_after_cross"] = int(max_bars)

    for key in (
        "require_k_d_confirmation",
        "require_price_above_slow_ema_for_long",
        "require_price_below_slow_ema_for_short",
        "use_first_pullback_only",
    ):
        if not isinstance(normalized.get(key), bool):
            raise TypeError(f"{key} must be boolean.")
    return normalized


def build_ema_stoch_rsi_signal(
    df: pd.DataFrame,
    signal_cfg: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Build causal EMA 50/150 trend-shift plus first StochRSI pullback signals.

    The signal is emitted at the current bar close and uses only current and previous bar values.
    Execution-time shifts, such as next-open entry, remain the target/backtest layer's job.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    cfg = _validate_cfg(_merge_cfg(signal_cfg, overrides))
    price_col = str(cfg["price_col"])
    ema_fast_col = str(cfg["ema_fast_col"])
    ema_slow_col = str(cfg["ema_slow_col"])
    stoch_k_col = str(cfg["stoch_k_col"])
    stoch_d_col = str(cfg["stoch_d_col"])
    stoch_recover_col = str(cfg["stoch_recover_col"])
    stoch_fall_col = str(cfg["stoch_fall_col"])
    prefix = str(cfg["prefix"])
    side_col = str(cfg["side_col"])
    candidate_col = str(cfg["candidate_col"])
    signal_col = cfg.get("signal_col")
    oversold = float(cfg["oversold"])
    overbought = float(cfg["overbought"])
    max_bars = int(cfg["max_bars_after_cross"])

    _require_columns(
        df,
        [
            price_col,
            ema_fast_col,
            ema_slow_col,
            stoch_k_col,
            stoch_d_col,
            stoch_recover_col,
            stoch_fall_col,
        ],
    )

    out = df.copy()
    price = _numeric(out, price_col)
    ema_fast = _numeric(out, ema_fast_col)
    ema_slow = _numeric(out, ema_slow_col)
    stoch_k = _numeric(out, stoch_k_col)
    stoch_d = _numeric(out, stoch_d_col)

    fast_above = ema_fast.gt(ema_slow)
    fast_below = ema_fast.lt(ema_slow)
    bull_cross = ema_fast.shift(1).le(ema_slow.shift(1)) & fast_above
    bear_cross = ema_fast.shift(1).ge(ema_slow.shift(1)) & fast_below
    bars_since_bull = _bars_since_event(bull_cross)
    bars_since_bear = _bars_since_event(bear_cross)

    fast_above_col = f"{prefix}_ema_fast_above_slow"
    fast_below_col = f"{prefix}_ema_fast_below_slow"
    bull_cross_col = f"{prefix}_bull_cross"
    bear_cross_col = f"{prefix}_bear_cross"
    bars_since_bull_col = f"{prefix}_bars_since_bull_cross"
    bars_since_bear_col = f"{prefix}_bars_since_bear_cross"
    fast_slope_col = f"{prefix}_ema_fast_slope"
    slow_slope_col = f"{prefix}_ema_slow_slope"
    distance_col = f"{prefix}_ema_distance"
    distance_pct_col = f"{prefix}_ema_distance_pct"
    oversold_after_col = f"{prefix}_oversold_after_bull_cross"
    overbought_after_col = f"{prefix}_overbought_after_bear_cross"
    first_oversold_col = f"{prefix}_first_oversold_after_bull_cross"
    first_overbought_col = f"{prefix}_first_overbought_after_bear_cross"
    long_entry_col = f"{prefix}_long_entry"
    short_entry_col = f"{prefix}_short_entry"

    recent_bull = bars_since_bull.notna() & bars_since_bull.le(float(max_bars))
    recent_bear = bars_since_bear.notna() & bars_since_bear.le(float(max_bars))

    oversold_after = recent_bull & fast_above & stoch_k.le(oversold)
    overbought_after = recent_bear & fast_below & stoch_k.ge(overbought)

    bull_group = bull_cross.fillna(False).astype("int64").cumsum()
    bear_group = bear_cross.fillna(False).astype("int64").cumsum()

    prev_oversold_in_group = (
        oversold_after.groupby(bull_group, sort=False).shift(fill_value=False).astype(bool)
    )
    oversold_episode_start = oversold_after & ~prev_oversold_in_group
    oversold_episode_count = (
        oversold_episode_start.astype("int16").groupby(bull_group, sort=False).cumsum()
    )
    first_oversold = oversold_episode_start & oversold_episode_count.eq(1)

    prev_overbought_in_group = (
        overbought_after.groupby(bear_group, sort=False).shift(fill_value=False).astype(bool)
    )
    overbought_episode_start = overbought_after & ~prev_overbought_in_group
    overbought_episode_count = (
        overbought_episode_start.astype("int16").groupby(bear_group, sort=False).cumsum()
    )
    first_overbought = overbought_episode_start & overbought_episode_count.eq(1)

    recover_from_oversold = stoch_k.shift(1).le(oversold) & stoch_k.gt(oversold)
    fall_from_overbought = stoch_k.shift(1).ge(overbought) & stoch_k.lt(overbought)

    long_pullback_ok = oversold_episode_count.eq(1) if cfg["use_first_pullback_only"] else oversold_episode_count.ge(1)
    short_pullback_ok = (
        overbought_episode_count.eq(1)
        if cfg["use_first_pullback_only"]
        else overbought_episode_count.ge(1)
    )

    long_entry = recent_bull & long_pullback_ok & recover_from_oversold & fast_above
    short_entry = recent_bear & short_pullback_ok & fall_from_overbought & fast_below
    if cfg["require_k_d_confirmation"]:
        long_entry &= stoch_k.gt(stoch_d)
        short_entry &= stoch_k.lt(stoch_d)
    if cfg["require_price_above_slow_ema_for_long"]:
        long_entry &= price.gt(ema_slow)
    if cfg["require_price_below_slow_ema_for_short"]:
        short_entry &= price.lt(ema_slow)
    if cfg["use_first_pullback_only"]:
        long_entry_count = long_entry.astype("int16").groupby(bull_group, sort=False).cumsum()
        short_entry_count = short_entry.astype("int16").groupby(bear_group, sort=False).cumsum()
        long_entry &= long_entry_count.eq(1)
        short_entry &= short_entry_count.eq(1)

    side = pd.Series(0, index=out.index, name=side_col, dtype="int8")
    side.loc[long_entry] = 1
    side.loc[short_entry & ~long_entry] = -1
    candidate = side.ne(0).astype("int8")

    out[fast_above_col] = fast_above.fillna(False).astype("int8")
    out[fast_below_col] = fast_below.fillna(False).astype("int8")
    out[bull_cross_col] = bull_cross.fillna(False).astype("int8")
    out[bear_cross_col] = bear_cross.fillna(False).astype("int8")
    out[bars_since_bull_col] = bars_since_bull.astype("float32")
    out[bars_since_bear_col] = bars_since_bear.astype("float32")
    out[fast_slope_col] = (ema_fast - ema_fast.shift(1)).astype("float32")
    out[slow_slope_col] = (ema_slow - ema_slow.shift(1)).astype("float32")
    out[distance_col] = (ema_fast - ema_slow).astype("float32")
    out[distance_pct_col] = ((ema_fast - ema_slow) / price.replace(0.0, np.nan)).astype("float32")
    out[oversold_after_col] = oversold_after.fillna(False).astype("int8")
    out[overbought_after_col] = overbought_after.fillna(False).astype("int8")
    out[first_oversold_col] = first_oversold.fillna(False).astype("int8")
    out[first_overbought_col] = first_overbought.fillna(False).astype("int8")
    out[long_entry_col] = long_entry.fillna(False).astype("int8")
    out[short_entry_col] = short_entry.fillna(False).astype("int8")
    out[side_col] = side.astype("int8")
    out[candidate_col] = candidate.astype("int8")
    if signal_col is not None and signal_col != side_col:
        out[str(signal_col)] = out[side_col].astype("int8")

    output_cols = [
        fast_above_col,
        fast_below_col,
        bull_cross_col,
        bear_cross_col,
        bars_since_bull_col,
        bars_since_bear_col,
        fast_slope_col,
        slow_slope_col,
        distance_col,
        distance_pct_col,
        oversold_after_col,
        overbought_after_col,
        first_oversold_col,
        first_overbought_col,
        long_entry_col,
        short_entry_col,
        side_col,
        candidate_col,
    ]
    if signal_col is not None and signal_col != side_col:
        output_cols.append(str(signal_col))

    meta = {
        "kind": "ema_stoch_rsi_pullback",
        "params": {key: cfg[key] for key in sorted(cfg)},
        "output_cols": output_cols,
        "long_entries": int(out[long_entry_col].sum()),
        "short_entries": int(out[short_entry_col].sum()),
        "candidate_rows": int(out[candidate_col].sum()),
    }
    return out, meta


def ema_stoch_rsi_pullback_signal(
    df: pd.DataFrame,
    **params: Any,
) -> pd.DataFrame:
    """
    Apply the registered ``ema_stoch_rsi_pullback`` signal transformation.
    
    This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        signals:
          kind: ema_stoch_rsi_pullback
          params:
            price_col: close
            ema_fast_col: ema_50
            ema_slow_col: ema_150
            stoch_k_col: stoch_rsi_k
            stoch_d_col: stoch_rsi_d
            stoch_recover_col: stoch_rsi_recover_from_oversold
            stoch_fall_col: stoch_rsi_fall_from_overbought
            oversold: 0.2
            overbought: 0.8
            max_bars_after_cross: 30
            require_k_d_confirmation: true
            require_price_above_slow_ema_for_long: true
            require_price_below_slow_ema_for_short: true
            use_first_pullback_only: true
            prefix: ema_stoch
            side_col: signal_side
            candidate_col: signal_candidate
            signal_col: null
          output_cols:
            - configured by signal_col
    
    Required input columns
    ----------------------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    ema_fast_col:
        Input dataframe column configured by ``ema_fast_col``. Default: ``ema_50``.
    ema_slow_col:
        Input dataframe column configured by ``ema_slow_col``. Default: ``ema_150``.
    stoch_k_col:
        Input dataframe column configured by ``stoch_k_col``. Default: ``stoch_rsi_k``.
    stoch_d_col:
        Input dataframe column configured by ``stoch_d_col``. Default: ``stoch_rsi_d``.
    stoch_recover_col:
        Input dataframe column configured by ``stoch_recover_col``. Default: ``stoch_rsi_recover_from_oversold``.
    stoch_fall_col:
        Input dataframe column configured by ``stoch_fall_col``. Default: ``stoch_rsi_fall_from_overbought``.
    side_col:
        Input dataframe column configured by ``side_col``. Default: ``signal_side``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    ema_fast_col:
        Input dataframe column configured by ``ema_fast_col``. Default: ``ema_50``.
    ema_slow_col:
        Input dataframe column configured by ``ema_slow_col``. Default: ``ema_150``.
    stoch_k_col:
        Input dataframe column configured by ``stoch_k_col``. Default: ``stoch_rsi_k``.
    stoch_d_col:
        Input dataframe column configured by ``stoch_d_col``. Default: ``stoch_rsi_d``.
    stoch_recover_col:
        Input dataframe column configured by ``stoch_recover_col``. Default: ``stoch_rsi_recover_from_oversold``.
    stoch_fall_col:
        Input dataframe column configured by ``stoch_fall_col``. Default: ``stoch_rsi_fall_from_overbought``.
    oversold:
        Configuration parameter accepted by this signal. Default: ``0.2``.
    overbought:
        Configuration parameter accepted by this signal. Default: ``0.8``.
    max_bars_after_cross:
        Configuration parameter accepted by this signal. Default: ``30``.
    require_k_d_confirmation:
        Configuration parameter accepted by this signal. Default: ``true``.
    require_price_above_slow_ema_for_long:
        Configuration parameter accepted by this signal. Default: ``true``.
    require_price_below_slow_ema_for_short:
        Configuration parameter accepted by this signal. Default: ``true``.
    use_first_pullback_only:
        Boolean switch controlling optional signal behavior. Default: ``true``.
    prefix:
        Configuration parameter accepted by this signal. Default: ``ema_stoch``.
    side_col:
        Input dataframe column configured by ``side_col``. Default: ``signal_side``.
    candidate_col:
        Input dataframe column configured by ``candidate_col``. Default: ``signal_candidate``.
    signal_col:
        Output dataframe column configured by ``signal_col``. Default: ``null``.
    """
    out, _ = build_ema_stoch_rsi_signal(df, params)
    return out


__all__ = ["build_ema_stoch_rsi_signal", "ema_stoch_rsi_pullback_signal"]
