from __future__ import annotations

import numpy as np
import pandas as pd


def _same_direction(left: float, right: float) -> bool:
    return bool(np.sign(left) == np.sign(right))


def btcusd_dual_trend_ensemble_signal(
    df: pd.DataFrame,
    *,
    ensemble_col: str = "dual_trend_score",
    volatility_col: str = "dual_volatility_ann_336",
    target_volatility: float = 0.22,
    max_leverage: float = 1.50,
    rebalance_bars: int = 48,
    allow_short: bool = True,
    signal_col: str = "signal_position",
) -> pd.DataFrame:
    """Apply the locked direction-change/48-exposed-bar rebalance state machine.

    YAML declaration::

        signals:
          kind: btcusd_dual_trend_ensemble
          params:
            ensemble_col: dual_trend_score
            volatility_col: dual_volatility_ann_336
            target_volatility: 0.22
            max_leverage: 1.50
            rebalance_bars: 48
            allow_short: true
            signal_col: signal_position

    Required input columns
    ----------------------
    ensemble_col:
        Causal 60/40 EMA and persistent-Donchian score available at close t.
    volatility_col:
        Causal annualized EWM volatility available at close t.

    Parameters
    ----------
    target_volatility, max_leverage:
        Locked volatility target and absolute leverage cap.
    rebalance_bars:
        Number of exposed bars retained before a same-direction scheduled resize.
    allow_short:
        Whether negative ensemble scores may create short exposure.
    signal_col:
        Output column containing the statefully applied position.
    """
    missing = sorted({ensemble_col, volatility_col}.difference(df.columns))
    if missing:
        raise KeyError(f"Missing BTCUSD signal inputs: {missing}.")
    if target_volatility <= 0.0:
        raise ValueError("target_volatility must be positive.")
    if max_leverage <= 0.0:
        raise ValueError("max_leverage must be positive.")
    if not isinstance(rebalance_bars, int) or isinstance(rebalance_bars, bool) or rebalance_bars <= 0:
        raise ValueError("rebalance_bars must be a positive integer.")

    ensemble = df[ensemble_col].astype(float)
    volatility = df[volatility_col].astype(float)
    if (~np.isfinite(ensemble.fillna(0.0).to_numpy(dtype=float))).any():
        raise ValueError("ensemble signal contains non-finite values.")
    if volatility.dropna().lt(0.0).any() or (~np.isfinite(volatility.dropna().to_numpy(dtype=float))).any():
        raise ValueError("volatility must be finite and non-negative when available.")
    if ensemble.dropna().abs().gt(1.0 + 1e-12).any():
        raise ValueError("ensemble signal must lie in [-1, 1].")

    with np.errstate(divide="ignore", invalid="ignore"):
        leverage = float(target_volatility) / volatility
    leverage = leverage.clip(upper=float(max_leverage))
    leverage = leverage.where(volatility.notna(), 0.0)
    desired = ensemble.fillna(0.0) * leverage
    if not allow_short:
        desired = desired.clip(lower=0.0)

    positions = np.zeros(len(df), dtype=float)
    rebalanced = np.zeros(len(df), dtype=bool)
    countdown_after = np.zeros(len(df), dtype=int)
    current = 0.0
    countdown = 0
    desired_values = desired.to_numpy(dtype=float)

    for offset, requested in enumerate(desired_values):
        if not np.isfinite(requested):
            requested = 0.0
        should_rebalance = False
        if requested == 0.0:
            should_rebalance = current != 0.0
        elif not _same_direction(requested, current):
            should_rebalance = True
        elif countdown == 0:
            should_rebalance = True

        if should_rebalance:
            current = float(requested)
            countdown = int(rebalance_bars)
            rebalanced[offset] = True

        positions[offset] = current
        if current != 0.0 and countdown > 0:
            countdown -= 1
        elif current == 0.0:
            countdown = 0
        countdown_after[offset] = countdown

    out = df.copy()
    out["desired_position"] = desired.astype(float)
    out[signal_col] = pd.Series(positions, index=df.index, dtype=float)
    out["position_rebalanced"] = pd.Series(rebalanced, index=df.index, dtype=bool)
    out["rebalance_countdown"] = pd.Series(countdown_after, index=df.index, dtype=int)
    return out


__all__ = ["btcusd_dual_trend_ensemble_signal"]
