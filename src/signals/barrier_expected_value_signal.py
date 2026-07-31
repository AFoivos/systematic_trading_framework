from __future__ import annotations

import numpy as np
import pandas as pd


def barrier_expected_value_signal(
    df: pd.DataFrame,
    *,
    upper_probability_col: str = "pred_prob_upper",
    lower_probability_col: str = "pred_prob_lower",
    no_hit_probability_col: str = "pred_prob_no_hit",
    calibrated_col: str = "pred_probability_calibrated",
    pred_is_oos_col: str | None = "pred_is_oos",
    atr_col: str = "atr_14",
    price_col: str = "close",
    spread_col: str | None = "spread_bps",
    activity_col: str | None = None,
    no_hit_long_return_col: str | None = None,
    no_hit_short_return_col: str | None = None,
    upper_atr_multiplier: float = 1.0,
    lower_atr_multiplier: float = 1.0,
    minimum_expected_edge: float = 0.0,
    minimum_class_probability: float = 0.0,
    cost_safety_factor: float = 1.25,
    cost_per_turnover: float = 0.0,
    slippage_per_turnover: float = 0.0,
    maximum_no_hit_probability: float = 1.0,
    allow_long: bool = True,
    allow_short: bool = True,
    entry_delay_bars: int = 1,
    maximum_spread: float | None = None,
    minimum_activity: float | None = None,
    maximum_position: float = 1.0,
    signal_col: str = "barrier_ev_signal",
    long_ev_col: str = "barrier_ev_long",
    short_ev_col: str = "barrier_ev_short",
    selected_ev_col: str = "barrier_ev_selected",
    expected_edge_col: str = "barrier_expected_edge",
    round_trip_cost_col: str = "barrier_round_trip_cost",
) -> pd.DataFrame:
    """Convert calibrated barrier probabilities to a cost-aware causal position.

    YAML declaration::

        signals:
          kind: barrier_expected_value
          params:
            upper_probability_col: pred_prob_upper
            lower_probability_col: pred_prob_lower
            no_hit_probability_col: pred_prob_no_hit
            calibrated_col: pred_probability_calibrated
            pred_is_oos_col: pred_is_oos
            atr_col: atr_14
            price_col: close
            signal_col: barrier_ev_signal

    Required input columns
    ----------------------
    upper_probability_col, lower_probability_col, no_hit_probability_col:
        OOS class probabilities that sum to one on each eligible row.
    calibrated_col, pred_is_oos_col:
        Explicit calibration and held-out prediction gates.
    atr_col, price_col:
        Point-in-time payoff scale and decision price.

    Parameters
    ----------
    upper_atr_multiplier, lower_atr_multiplier:
        Gross first-passage payoffs in ATR units.
    minimum_expected_edge, minimum_class_probability, cost_safety_factor:
        Cost-aware decision gates applied before emitting a side.
    entry_delay_bars:
        Execution delay including the backtest engine's next-open fill.
    """
    required = [
        upper_probability_col,
        lower_probability_col,
        no_hit_probability_col,
        calibrated_col,
        atr_col,
        price_col,
    ]
    if pred_is_oos_col is not None:
        required.append(pred_is_oos_col)
    if spread_col is not None:
        required.append(spread_col)
    if activity_col is not None:
        required.append(activity_col)
    if no_hit_long_return_col is not None:
        required.append(no_hit_long_return_col)
    if no_hit_short_return_col is not None:
        required.append(no_hit_short_return_col)
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for barrier_expected_value signal: {missing}")

    for name, value in (
        ("upper_atr_multiplier", upper_atr_multiplier),
        ("lower_atr_multiplier", lower_atr_multiplier),
        ("cost_safety_factor", cost_safety_factor),
        ("maximum_position", maximum_position),
    ):
        if not np.isfinite(float(value)) or float(value) <= 0.0:
            raise ValueError(f"{name} must be finite and > 0.")
    for name, value in (
        ("minimum_expected_edge", minimum_expected_edge),
        ("cost_per_turnover", cost_per_turnover),
        ("slippage_per_turnover", slippage_per_turnover),
    ):
        if not np.isfinite(float(value)) or float(value) < 0.0:
            raise ValueError(f"{name} must be finite and >= 0.")
    for name, value in (
        ("minimum_class_probability", minimum_class_probability),
        ("maximum_no_hit_probability", maximum_no_hit_probability),
    ):
        if not np.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"{name} must be within [0, 1].")
    if isinstance(entry_delay_bars, bool) or int(entry_delay_bars) < 1:
        raise ValueError("entry_delay_bars must be an integer >= 1.")
    if maximum_spread is not None and (
        not np.isfinite(float(maximum_spread)) or float(maximum_spread) < 0.0
    ):
        raise ValueError("maximum_spread must be finite and >= 0 when provided.")
    if minimum_activity is not None and not np.isfinite(float(minimum_activity)):
        raise ValueError("minimum_activity must be finite when provided.")

    out = df.copy()
    p_upper = pd.to_numeric(out[upper_probability_col], errors="coerce").astype(float)
    p_lower = pd.to_numeric(out[lower_probability_col], errors="coerce").astype(float)
    p_no_hit = pd.to_numeric(out[no_hit_probability_col], errors="coerce").astype(float)
    probability_sum = p_upper + p_lower + p_no_hit
    probabilities_valid = (
        p_upper.between(0.0, 1.0)
        & p_lower.between(0.0, 1.0)
        & p_no_hit.between(0.0, 1.0)
        & probability_sum.sub(1.0).abs().le(1e-5)
    )

    atr = pd.to_numeric(out[atr_col], errors="coerce").astype(float)
    price = pd.to_numeric(out[price_col], errors="coerce").astype(float)
    upper_payoff = float(upper_atr_multiplier) * atr / price.where(price > 0.0)
    lower_payoff = float(lower_atr_multiplier) * atr / price.where(price > 0.0)
    no_hit_long = (
        pd.to_numeric(out[no_hit_long_return_col], errors="coerce").fillna(0.0).astype(float)
        if no_hit_long_return_col is not None
        else pd.Series(0.0, index=out.index, dtype=float)
    )
    no_hit_short = (
        pd.to_numeric(out[no_hit_short_return_col], errors="coerce").fillna(0.0).astype(float)
        if no_hit_short_return_col is not None
        else pd.Series(0.0, index=out.index, dtype=float)
    )
    round_trip_cost = 2.0 * (float(cost_per_turnover) + float(slippage_per_turnover))
    gross_long_ev = p_upper * upper_payoff - p_lower * lower_payoff + p_no_hit * no_hit_long
    gross_short_ev = p_lower * lower_payoff - p_upper * upper_payoff + p_no_hit * no_hit_short
    long_ev = gross_long_ev - round_trip_cost
    short_ev = gross_short_ev - round_trip_cost

    common_gate = probabilities_valid & out[calibrated_col].fillna(False).astype(bool)
    if pred_is_oos_col is not None:
        common_gate &= out[pred_is_oos_col].fillna(False).astype(bool)
    common_gate &= p_no_hit.le(float(maximum_no_hit_probability))
    if maximum_spread is not None and spread_col is not None:
        spread = pd.to_numeric(out[spread_col], errors="coerce").astype(float)
        common_gate &= spread.le(float(maximum_spread))
    if minimum_activity is not None and activity_col is not None:
        activity = pd.to_numeric(out[activity_col], errors="coerce").astype(float)
        common_gate &= activity.ge(float(minimum_activity))

    long_gate = (
        common_gate
        & bool(allow_long)
        & p_upper.ge(float(minimum_class_probability))
        & long_ev.gt(float(minimum_expected_edge))
        & gross_long_ev.gt(float(cost_safety_factor) * round_trip_cost)
    )
    short_gate = (
        common_gate
        & bool(allow_short)
        & p_lower.ge(float(minimum_class_probability))
        & short_ev.gt(float(minimum_expected_edge))
        & gross_short_ev.gt(float(cost_safety_factor) * round_trip_cost)
    )
    conflict = long_gate & short_gate
    long_gate &= ~conflict
    short_gate &= ~conflict

    signal = pd.Series(0.0, index=out.index, dtype=float)
    signal.loc[long_gate] = float(maximum_position)
    signal.loc[short_gate] = -float(maximum_position)
    selected_ev = pd.Series(np.nan, index=out.index, dtype=float)
    selected_ev.loc[long_gate] = long_ev.loc[long_gate]
    selected_ev.loc[short_gate] = short_ev.loc[short_gate]
    expected_edge = pd.concat([long_ev.rename("long"), short_ev.rename("short")], axis=1).max(axis=1)

    delay = int(entry_delay_bars) - 1
    if delay > 0:
        signal = signal.shift(delay).fillna(0.0)

    out[long_ev_col] = long_ev.astype("float32")
    out[short_ev_col] = short_ev.astype("float32")
    out[selected_ev_col] = selected_ev.astype("float32")
    out[expected_edge_col] = expected_edge.astype("float32")
    out[round_trip_cost_col] = float(round_trip_cost)
    out[signal_col] = signal.astype(float)
    return out


__all__ = ["barrier_expected_value_signal"]
