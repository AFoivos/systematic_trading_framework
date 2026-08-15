from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from src.experiments.support.ethusd_broker_alpha import STRESS_GRID, TickStressSpec
from src.experiments.support.ethusd_custom_indicator_alpha import trade_metrics
from src.src_data.ctrader_export import load_ctrader_bar_export, load_ctrader_tick_export
from src.utils.paths import PROJECT_ROOT, enforce_safe_absolute_path
from src.utils.run_metadata import collect_git_metadata, file_sha256


CTRADER_ROOT = PROJECT_ROOT / "data/ETHUSD"

DISCOVERY_END = pd.Timestamp("2022-12-31 23:59:59")
VALIDATION_2023_START = pd.Timestamp("2023-01-01 00:00:00")
VALIDATION_2023_END = pd.Timestamp("2023-12-31 23:59:59")
VALIDATION_2024_START = pd.Timestamp("2024-01-01 00:00:00")
VALIDATION_2024_END = pd.Timestamp("2024-12-31 23:59:59")
CONFIRMATION_2025H1_START = pd.Timestamp("2025-01-01 00:00:00")
CONFIRMATION_2025H1_END = pd.Timestamp("2025-06-30 23:59:59")
HISTORICAL_DIAGNOSTIC_START = pd.Timestamp("2025-07-01 00:00:00")

BASE_COMMISSION_BPS_PER_SIDE = 0.5
EXPECTED_BAR_MINUTES = 30
MAX_CONTIGUOUS_MINUTES = 90


SELECTION_SPLITS = (
    ("discovery", None, DISCOVERY_END),
    ("validation_2023", VALIDATION_2023_START, VALIDATION_2023_END),
    ("validation_2024", VALIDATION_2024_START, VALIDATION_2024_END),
    ("confirmation_2025h1", CONFIRMATION_2025H1_START, CONFIRMATION_2025H1_END),
)


@dataclass(frozen=True)
class PatternSpec:
    family: str
    primary_threshold: float
    secondary_threshold: float
    release_threshold: float
    holding_bars: int
    session_start_hour: int
    session_end_hour: int

    @property
    def candidate_id(self) -> str:
        return (
            f"{self.family}__p_{self.primary_threshold:.2f}__"
            f"s_{self.secondary_threshold:.2f}__r_{self.release_threshold:.2f}__"
            f"hold_{self.holding_bars}__session_{self.session_start_hour:02d}_"
            f"{self.session_end_hour:02d}"
        )


def _stage1_candidate_grid() -> tuple[PatternSpec, ...]:
    specs: list[PatternSpec] = []
    for primary, secondary, release, holding, session in itertools.product(
        (0.25, 0.40, 0.55),
        (0.10, 0.20),
        (0.80, 1.20),
        (4, 8, 16, 32),
        ((0, 24), (12, 20)),
    ):
        specs.append(
            PatternSpec(
                family="efficient_continuation",
                primary_threshold=primary,
                secondary_threshold=secondary,
                release_threshold=release,
                holding_bars=holding,
                session_start_hour=session[0],
                session_end_hour=session[1],
            )
        )
    for primary, secondary, release, holding in itertools.product(
        (0.30, 0.45, 0.60),
        (0.10, 0.20),
        (0.80, 1.20),
        (4, 8, 16),
    ):
        specs.append(
            PatternSpec(
                family="efficiency_acceleration",
                primary_threshold=primary,
                secondary_threshold=secondary,
                release_threshold=release,
                holding_bars=holding,
                session_start_hour=0,
                session_end_hour=24,
            )
        )
    for primary, secondary, release, holding in itertools.product(
        (0.30, 0.45, 0.60),
        (0.30, 0.45),
        (0.00, 0.80),
        (4, 8, 16),
    ):
        specs.append(
            PatternSpec(
                family="efficient_pullback_recovery",
                primary_threshold=primary,
                secondary_threshold=secondary,
                release_threshold=release,
                holding_bars=holding,
                session_start_hour=0,
                session_end_hour=24,
            )
        )
    for primary, secondary, release, holding in itertools.product(
        (0.35, 0.50),
        (0.50, 1.00),
        (0.25, 0.40),
        (4, 8, 16),
    ):
        specs.append(
            PatternSpec(
                family="absorption_reversal",
                primary_threshold=primary,
                secondary_threshold=secondary,
                release_threshold=release,
                holding_bars=holding,
                session_start_hour=0,
                session_end_hour=24,
            )
        )
    for primary, secondary, holding in itertools.product(
        (0.35, 0.50),
        (0.25, 0.40),
        (4, 8, 16),
    ):
        specs.append(
            PatternSpec(
                family="failed_breakout_reversal",
                primary_threshold=primary,
                secondary_threshold=secondary,
                release_threshold=0.0,
                holding_bars=holding,
                session_start_hour=0,
                session_end_hour=24,
            )
        )
    for primary, secondary, holding in itertools.product(
        (0.70, 0.85),
        (1.50, 2.00),
        (4, 8, 16),
    ):
        specs.append(
            PatternSpec(
                family="compression_release",
                primary_threshold=primary,
                secondary_threshold=secondary,
                release_threshold=0.50,
                holding_bars=holding,
                session_start_hour=0,
                session_end_hour=24,
            )
        )
    for primary, secondary, release, holding in itertools.product(
        (1.50, 2.00, 2.50),
        (0.15, 0.25),
        (0.25, 0.40),
        (4, 8, 16),
    ):
        specs.append(
            PatternSpec(
                family="inefficient_extreme_reversal",
                primary_threshold=primary,
                secondary_threshold=secondary,
                release_threshold=release,
                holding_bars=holding,
                session_start_hour=0,
                session_end_hour=24,
            )
        )
    return tuple(specs)


def _stage2_candidate_grid() -> tuple[PatternSpec, ...]:
    """Selection-only follow-up hypotheses derived from the stage-1 atlas."""

    specs: list[PatternSpec] = []
    families = (
        (
            "efficient_state_continuation",
            (0.25, 0.31, 0.40),
            (0.05, 0.10, 0.20),
            (0.00, 0.20),
            (4, 8, 16),
            ((0, 24), (12, 22)),
        ),
        (
            "efficiency_acceleration_state",
            (0.30, 0.43, 0.55),
            (0.30, 0.45),
            (0.00, 0.20),
            (4, 8, 16),
            ((0, 24),),
        ),
        (
            "efficient_anti_persistence",
            (0.31, 0.40),
            (-0.12, -0.08),
            (0.00, 0.20),
            (8, 16),
            ((0, 24),),
        ),
        (
            "compression_acceptance_impulse",
            (0.70, 0.775, 0.85),
            (1.00, 1.50),
            (0.40, 0.60),
            (4, 8, 16),
            ((0, 24),),
        ),
        (
            "volume_wick_fade",
            (0.35, 0.50),
            (1.00, 2.00),
            (0.25, 0.40),
            (4, 8, 16),
            ((0, 24),),
        ),
        (
            "pullback_resume_cross",
            (0.25, 0.31, 0.40),
            (0.15, 0.30),
            (0.20, 0.40),
            (4, 8, 16),
            ((0, 24),),
        ),
    )
    for family, primary_values, secondary_values, release_values, holdings, sessions in families:
        for primary, secondary, release, holding, session in itertools.product(
            primary_values,
            secondary_values,
            release_values,
            holdings,
            sessions,
        ):
            specs.append(
                PatternSpec(
                    family=family,
                    primary_threshold=float(primary),
                    secondary_threshold=float(secondary),
                    release_threshold=float(release),
                    holding_bars=int(holding),
                    session_start_hour=int(session[0]),
                    session_end_hour=int(session[1]),
                )
            )
    return tuple(specs)


def candidate_grid(research_round: str = "stage1") -> tuple[PatternSpec, ...]:
    if research_round == "stage1":
        return _stage1_candidate_grid()
    if research_round == "stage2":
        return _stage2_candidate_grid()
    raise ValueError(f"Unknown research round: {research_round}")


def build_pattern_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Build a causal M30 state map plus separately named future outcomes."""

    required = ("open", "high", "low", "close", "volume")
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise KeyError(f"Pattern atlas requires columns: {missing}")
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise TypeError("Pattern atlas requires a DatetimeIndex.")
    if not frame.index.is_monotonic_increasing or frame.index.has_duplicates:
        raise ValueError("Pattern atlas index must be unique and monotonic.")

    out = frame.copy()
    close = pd.to_numeric(out["close"], errors="coerce").astype(float)
    open_ = pd.to_numeric(out["open"], errors="coerce").astype(float)
    high = pd.to_numeric(out["high"], errors="coerce").astype(float)
    low = pd.to_numeric(out["low"], errors="coerce").astype(float)
    volume = pd.to_numeric(out["volume"], errors="coerce").astype(float)
    log_close = np.log(close.where(close > 0.0))
    log_return = log_close.diff()
    gaps = out.index.to_series().diff().dt.total_seconds().div(60.0)
    gap_flag = gaps.gt(MAX_CONTIGUOUS_MINUTES)
    segment = gap_flag.fillna(False).cumsum()
    contiguous = segment.groupby(segment).cumcount() + 1

    absolute_range = high - low
    safe_range = absolute_range.where(absolute_range > 0.0)
    range_fraction = absolute_range / close
    close_location = ((2.0 * close - high - low) / safe_range).clip(-1.0, 1.0)
    body_fraction = ((close - open_).abs() / safe_range).clip(0.0, 1.0)
    body_direction = ((close - open_) / safe_range).clip(-1.0, 1.0)
    acceptance = (0.65 * close_location + 0.35 * body_direction).clip(-1.0, 1.0)
    upper_wick = (high - pd.concat([open_, close], axis=1).max(axis=1)).clip(lower=0.0)
    lower_wick = (pd.concat([open_, close], axis=1).min(axis=1) - low).clip(lower=0.0)
    wick_imbalance = ((lower_wick - upper_wick) / safe_range).clip(-1.0, 1.0)

    out["atlas_gap_flag"] = gap_flag.fillna(False)
    out["atlas_contiguous_bars"] = contiguous.astype("int32")
    out["atlas_log_return_1"] = log_return.where(~gap_flag)
    out["atlas_range_fraction"] = range_fraction
    out["atlas_close_location"] = close_location.fillna(0.0)
    out["atlas_body_fraction"] = body_fraction.fillna(0.0)
    out["atlas_acceptance"] = acceptance.fillna(0.0)
    out["atlas_wick_imbalance"] = wick_imbalance.fillna(0.0)

    path_step = log_return.abs().where(~gap_flag)
    signed_efficiencies: dict[int, pd.Series] = {}
    for window in (4, 8, 16, 32, 64, 128):
        displacement = log_close - log_close.shift(window)
        path = path_step.rolling(window, min_periods=window).sum()
        signed = (displacement / path.where(path > 0.0)).clip(-1.0, 1.0)
        signed = signed.where(contiguous > window)
        signed_efficiencies[window] = signed
        out[f"atlas_signed_efficiency_{window}"] = signed.astype("float32")
        out[f"atlas_efficiency_{window}"] = signed.abs().astype("float32")

    direction = np.sign(signed_efficiencies[32])
    agreement = (
        pd.concat(
            [signed_efficiencies[8], signed_efficiencies[32], signed_efficiencies[64]],
            axis=1,
        )
        .apply(np.sign)
        .eq(direction, axis=0)
        .mean(axis=1)
        .where(signed_efficiencies[32].notna())
    )
    out["atlas_efficiency_agreement"] = agreement.astype("float32")
    out["atlas_efficiency_acceleration"] = (
        signed_efficiencies[8].abs() - signed_efficiencies[64].abs()
    ).astype("float32")

    prior_range_8 = range_fraction.rolling(8, min_periods=8).median().shift(1)
    prior_range_96 = range_fraction.rolling(96, min_periods=96).median().shift(1)
    prior_range_24 = range_fraction.rolling(24, min_periods=24).median().shift(1)
    out["atlas_compression"] = prior_range_8 / prior_range_96.where(prior_range_96 > 0.0)
    out["atlas_release"] = range_fraction / prior_range_24.where(prior_range_24 > 0.0)
    out["atlas_range_energy"] = range_fraction.rolling(48, min_periods=48).median().shift(1)

    log_volume = np.log1p(volume.clip(lower=0.0))
    volume_median = log_volume.rolling(336, min_periods=168).median().shift(1)
    volume_mad = (log_volume - volume_median).abs().rolling(
        336, min_periods=168
    ).median().shift(1)
    out["atlas_volume_surprise"] = (
        (log_volume - volume_median) / (1.4826 * volume_mad + 1.0e-12)
    ).clip(-5.0, 5.0)

    out["atlas_realized_vol_16"] = log_return.rolling(16, min_periods=16).std()
    out["atlas_realized_vol_64"] = log_return.rolling(64, min_periods=64).std()
    out["atlas_volatility_ratio"] = out["atlas_realized_vol_16"] / out[
        "atlas_realized_vol_64"
    ].where(out["atlas_realized_vol_64"] > 0.0)
    out["atlas_autocorrelation_32"] = log_return.rolling(32, min_periods=32).corr(
        log_return.shift(1)
    )

    prior_median = log_close.rolling(96, min_periods=96).median().shift(1)
    prior_deviation = (log_close - prior_median).abs()
    prior_mad = prior_deviation.rolling(96, min_periods=96).median().shift(1)
    out["atlas_price_robust_z"] = (
        (log_close - prior_median) / (1.4826 * prior_mad + 1.0e-12)
    ).clip(-8.0, 8.0)
    out["atlas_prior_high_48"] = high.shift(1).rolling(48, min_periods=48).max()
    out["atlas_prior_low_48"] = low.shift(1).rolling(48, min_periods=48).min()
    out["atlas_recovery_up"] = close / high.shift(1).rolling(3, min_periods=3).max() - 1.0
    out["atlas_recovery_down"] = close / low.shift(1).rolling(3, min_periods=3).min() - 1.0
    out["atlas_entry_hour_utc"] = ((out.index + pd.Timedelta(minutes=30)).hour).astype(
        "int8"
    )
    out["atlas_weekday_utc"] = out.index.dayofweek.astype("int8")

    for holding in (1, 4, 8, 16, 32):
        entry_open = open_.shift(-1)
        exit_open = open_.shift(-(holding + 1))
        out[f"future_open_return_{holding}"] = exit_open / entry_open - 1.0
        out[f"future_continuation_return_{holding}"] = (
            np.sign(signed_efficiencies[32]) * out[f"future_open_return_{holding}"]
        )
    return out


def candidate_triggers(frame: pd.DataFrame, spec: PatternSpec) -> pd.Series:
    """Return sparse, symmetric transition pulses for one causal hypothesis."""

    se8 = pd.to_numeric(frame["atlas_signed_efficiency_8"], errors="coerce")
    se16 = pd.to_numeric(frame["atlas_signed_efficiency_16"], errors="coerce")
    se32 = pd.to_numeric(frame["atlas_signed_efficiency_32"], errors="coerce")
    se64 = pd.to_numeric(frame["atlas_signed_efficiency_64"], errors="coerce")
    release = pd.to_numeric(frame["atlas_release"], errors="coerce")
    acceptance = pd.to_numeric(frame["atlas_acceptance"], errors="coerce")
    agreement = pd.to_numeric(frame["atlas_efficiency_agreement"], errors="coerce")
    direction = pd.Series(0.0, index=frame.index)
    active = pd.Series(False, index=frame.index)

    if spec.family == "efficient_continuation":
        direction = np.sign(se64)
        active = (
            se64.abs().ge(spec.primary_threshold)
            & se16.abs().ge(spec.secondary_threshold)
            & np.sign(se16).eq(direction)
            & agreement.ge(2.0 / 3.0)
            & release.ge(spec.release_threshold)
            & (acceptance * direction).ge(0.20)
        )
    elif spec.family == "efficiency_acceleration":
        direction = np.sign(se8)
        acceleration = se8.abs() - se64.abs()
        active = (
            se8.abs().ge(spec.primary_threshold)
            & acceleration.ge(spec.secondary_threshold)
            & np.sign(se32).eq(direction)
            & release.ge(spec.release_threshold)
            & (acceptance * direction).ge(0.20)
        )
    elif spec.family == "efficient_pullback_recovery":
        direction = np.sign(se64)
        recovery = pd.Series(
            np.where(direction > 0.0, frame["atlas_recovery_up"], -frame["atlas_recovery_down"]),
            index=frame.index,
        )
        active = (
            se64.abs().ge(spec.primary_threshold)
            & se8.abs().le(spec.secondary_threshold)
            & recovery.gt(0.0)
            & (acceptance * direction).ge(spec.secondary_threshold)
            & release.ge(spec.release_threshold)
        )
    elif spec.family == "absorption_reversal":
        wick = pd.to_numeric(frame["atlas_wick_imbalance"], errors="coerce")
        direction = np.sign(wick)
        active = (
            wick.abs().ge(spec.primary_threshold)
            & pd.to_numeric(frame["atlas_volume_surprise"], errors="coerce").ge(
                spec.secondary_threshold
            )
            & pd.to_numeric(frame["atlas_body_fraction"], errors="coerce").le(
                spec.release_threshold
            )
            & (se8 * direction).le(-0.10)
        )
    elif spec.family == "failed_breakout_reversal":
        wick = pd.to_numeric(frame["atlas_wick_imbalance"], errors="coerce")
        failed_low = (frame["low"] < frame["atlas_prior_low_48"]) & (
            frame["close"] > frame["atlas_prior_low_48"]
        )
        failed_high = (frame["high"] > frame["atlas_prior_high_48"]) & (
            frame["close"] < frame["atlas_prior_high_48"]
        )
        direction = pd.Series(np.where(failed_low, 1.0, np.where(failed_high, -1.0, 0.0)), index=frame.index)
        active = (
            direction.ne(0.0)
            & (wick * direction).ge(spec.primary_threshold)
            & se64.abs().le(spec.secondary_threshold)
        )
    elif spec.family == "compression_release":
        direction = np.sign(acceptance)
        active = (
            pd.to_numeric(frame["atlas_compression"], errors="coerce").le(
                spec.primary_threshold
            )
            & release.ge(spec.secondary_threshold)
            & acceptance.abs().ge(spec.release_threshold)
            & np.sign(se16).eq(direction)
        )
    elif spec.family == "inefficient_extreme_reversal":
        price_z = pd.to_numeric(frame["atlas_price_robust_z"], errors="coerce")
        direction = -np.sign(price_z)
        active = (
            price_z.abs().ge(spec.primary_threshold)
            & se32.abs().le(spec.secondary_threshold)
            & (acceptance * direction).ge(spec.release_threshold)
        )
    elif spec.family == "efficient_state_continuation":
        direction = np.sign(se32)
        active = (
            se32.abs().ge(spec.primary_threshold)
            & (se8 * direction).ge(spec.secondary_threshold)
            & agreement.ge(2.0 / 3.0)
            & (acceptance * direction).ge(spec.release_threshold)
        )
    elif spec.family == "efficiency_acceleration_state":
        direction = np.sign(se8)
        acceleration = se8.abs() - se64.abs()
        active = (
            acceleration.ge(spec.primary_threshold)
            & se8.abs().ge(spec.secondary_threshold)
            & np.sign(se32).eq(direction)
            & (acceptance * direction).ge(spec.release_threshold)
        )
    elif spec.family == "efficient_anti_persistence":
        autocorrelation = pd.to_numeric(
            frame["atlas_autocorrelation_32"], errors="coerce"
        )
        direction = np.sign(se32)
        active = (
            se32.abs().ge(spec.primary_threshold)
            & autocorrelation.ge(spec.secondary_threshold)
            & autocorrelation.lt(0.0)
            & (acceptance * direction).ge(spec.release_threshold)
        )
    elif spec.family == "compression_acceptance_impulse":
        direction = np.sign(acceptance)
        active = (
            pd.to_numeric(frame["atlas_compression"], errors="coerce").le(
                spec.primary_threshold
            )
            & release.ge(spec.secondary_threshold)
            & acceptance.abs().ge(spec.release_threshold)
        )
    elif spec.family == "volume_wick_fade":
        wick = pd.to_numeric(frame["atlas_wick_imbalance"], errors="coerce")
        direction = -np.sign(wick)
        active = (
            wick.abs().ge(spec.primary_threshold)
            & pd.to_numeric(frame["atlas_volume_surprise"], errors="coerce").ge(
                spec.secondary_threshold
            )
            & pd.to_numeric(frame["atlas_body_fraction"], errors="coerce").le(
                spec.release_threshold
            )
        )
    elif spec.family == "pullback_resume_cross":
        direction = np.sign(se32)
        prior_short_state = se8.shift(1) * direction
        current_short_state = se8 * direction
        active = (
            se32.abs().ge(spec.primary_threshold)
            & prior_short_state.le(0.0)
            & current_short_state.gt(0.0)
            & current_short_state.le(spec.secondary_threshold)
            & (acceptance * direction).ge(spec.release_threshold)
        )
    else:
        raise ValueError(f"Unknown pattern family: {spec.family}")

    entry_hour = pd.to_numeric(frame["atlas_entry_hour_utc"], errors="coerce")
    if spec.session_end_hour == 24:
        session = entry_hour.ge(spec.session_start_hour) & entry_hour.lt(24)
    else:
        session = entry_hour.ge(spec.session_start_hour) & entry_hour.lt(
            spec.session_end_hour
        )
    valid = (
        active
        & direction.ne(0.0)
        & session
        & pd.to_numeric(frame["atlas_contiguous_bars"], errors="coerce").ge(129)
    )
    state = pd.Series(np.where(valid, direction, 0.0), index=frame.index, dtype=float)
    pulse = state.where(state.ne(0.0) & state.ne(state.shift(1).fillna(0.0)), 0.0)
    return pulse.astype("int8").rename("pattern_signal")


def fixed_holding_ledger(
    frame: pd.DataFrame,
    spec: PatternSpec,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    round_trip_cost_bps: float,
) -> pd.DataFrame:
    """Replay non-overlapping next-open entries with a fixed time exit."""

    if start > end:
        raise ValueError("start must not be after end.")
    if not np.isfinite(round_trip_cost_bps) or round_trip_cost_bps < 0.0:
        raise ValueError("round_trip_cost_bps must be finite and non-negative.")
    triggers = candidate_triggers(frame, spec)
    index = frame.index
    positions = np.flatnonzero(
        triggers.ne(0.0).to_numpy()
        & (index >= pd.Timestamp(start))
        & (index <= pd.Timestamp(end))
    )
    rows: list[dict[str, Any]] = []
    last_exit_position = -1
    cost_return = float(round_trip_cost_bps) / 10_000.0
    for signal_position in positions:
        entry_position = int(signal_position + 1)
        exit_position = int(entry_position + spec.holding_bars)
        if signal_position <= last_exit_position or exit_position >= len(frame):
            continue
        if index[entry_position] < start or index[exit_position] > end:
            continue
        expected = pd.Timedelta(minutes=EXPECTED_BAR_MINUTES * spec.holding_bars)
        observed = index[exit_position] - index[entry_position]
        if observed > expected + pd.Timedelta(minutes=MAX_CONTIGUOUS_MINUTES):
            continue
        if bool(frame["atlas_gap_flag"].iloc[entry_position : exit_position + 1].any()):
            continue
        side = int(triggers.iloc[signal_position])
        entry_price = float(frame["open"].iloc[entry_position])
        exit_price = float(frame["open"].iloc[exit_position])
        if not np.isfinite(entry_price) or not np.isfinite(exit_price) or entry_price <= 0.0:
            continue
        gross_return = side * (exit_price / entry_price - 1.0)
        net_return = gross_return - cost_return
        path = frame.iloc[entry_position:exit_position]
        if side > 0:
            favorable = float(path["high"].max() / entry_price - 1.0)
            adverse = float(path["low"].min() / entry_price - 1.0)
        else:
            favorable = float(1.0 - path["low"].min() / entry_price)
            adverse = float(1.0 - path["high"].max() / entry_price)
        rows.append(
            {
                "candidate_id": spec.candidate_id,
                "family": spec.family,
                "signal_timestamp": index[signal_position],
                "entry_timestamp": index[entry_position],
                "exit_timestamp": index[exit_position],
                "side": "long" if side > 0 else "short",
                "side_numeric": side,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "holding_bars": spec.holding_bars,
                "gross_return": gross_return,
                "estimated_cost_return": cost_return,
                "net_return": net_return,
                "maximum_favorable_excursion": favorable,
                "maximum_adverse_excursion": adverse,
            }
        )
        last_exit_position = exit_position
    return pd.DataFrame(rows)


def exact_tick_fixed_holding_ledger(
    frame: pd.DataFrame,
    ticks: pd.DataFrame,
    spec: PatternSpec,
    *,
    stress: TickStressSpec,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Execute one frozen fixed-holding rule on side-aware cTrader ticks."""

    triggers = candidate_triggers(frame, spec)
    tick_ns = ticks.index.asi8
    first_tick = ticks.index.min()
    last_tick = ticks.index.max()
    rows: list[dict[str, Any]] = []
    excluded_outside = 0
    excluded_overlap = 0
    unfilled = 0
    last_exit = pd.Timestamp.min
    for signal_position in np.flatnonzero(triggers.ne(0.0).to_numpy()):
        signal_timestamp = pd.Timestamp(frame.index[signal_position])
        decision_timestamp = signal_timestamp + pd.Timedelta(minutes=30)
        exit_decision = decision_timestamp + pd.Timedelta(
            minutes=30 * spec.holding_bars
        )
        if decision_timestamp < first_tick or exit_decision > last_tick:
            excluded_outside += 1
            continue
        if decision_timestamp <= last_exit:
            excluded_overlap += 1
            continue
        entry_desired = decision_timestamp + pd.Timedelta(seconds=stress.delay_seconds)
        exit_desired = exit_decision + pd.Timedelta(seconds=stress.delay_seconds)
        entry_idx, entry_wait = _tick_index_at_or_after(
            tick_ns,
            entry_desired,
            maximum_wait_seconds=stress.maximum_quote_wait_seconds,
        )
        exit_idx, exit_wait = _tick_index_at_or_after(
            tick_ns,
            exit_desired,
            maximum_wait_seconds=stress.maximum_quote_wait_seconds,
        )
        if entry_idx is None or exit_idx is None or exit_idx <= entry_idx:
            unfilled += 1
            continue
        side = int(triggers.iloc[signal_position])
        entry_tick = ticks.iloc[entry_idx]
        exit_tick = ticks.iloc[exit_idx]
        slippage = stress.slippage_bps_per_side / 10_000.0
        entry_price = float(entry_tick["mid"]) + side * stress.spread_multiplier * float(
            entry_tick["spread"]
        ) / 2.0
        entry_price *= 1.0 + side * slippage
        exit_price = float(exit_tick["mid"]) - side * stress.spread_multiplier * float(
            exit_tick["spread"]
        ) / 2.0
        exit_price *= 1.0 - side * slippage
        reference_mid_return = side * (
            float(exit_tick["mid"]) / float(entry_tick["mid"]) - 1.0
        )
        gross_return = side * (exit_price / entry_price - 1.0)
        commission_return = 2.0 * stress.commission_bps_per_side / 10_000.0
        net_return = gross_return - commission_return
        rows.append(
            {
                "scenario_id": stress.scenario_id,
                "candidate_id": spec.candidate_id,
                "family": spec.family,
                "signal_timestamp": signal_timestamp,
                "entry_timestamp": ticks.index[entry_idx],
                "exit_timestamp": ticks.index[exit_idx],
                "side": "long" if side > 0 else "short",
                "side_numeric": side,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "entry_spread_bps": float(entry_tick["spread_bps"]),
                "exit_spread_bps": float(exit_tick["spread_bps"]),
                "reference_mid_return": reference_mid_return,
                "gross_return": gross_return,
                "commission_return": commission_return,
                "net_return": net_return,
                "execution_cost_return": reference_mid_return - net_return,
                "entry_quote_wait_seconds": float(entry_wait or 0.0),
                "exit_quote_wait_seconds": float(exit_wait or 0.0),
            }
        )
        last_exit = pd.Timestamp(ticks.index[exit_idx])
    ledger = pd.DataFrame(rows)
    diagnostics = {
        "scenario_id": stress.scenario_id,
        "signal_pulses": int(triggers.ne(0.0).sum()),
        "excluded_outside_tick_coverage": int(excluded_outside),
        "excluded_due_to_open_position": int(excluded_overlap),
        "unfilled": int(unfilled),
        "executed_closed_trades": int(len(ledger)),
        "tick_coverage_start": first_tick.isoformat(),
        "tick_coverage_end": last_tick.isoformat(),
    }
    return ledger, diagnostics


def _tick_index_at_or_after(
    index_ns: np.ndarray,
    desired: pd.Timestamp,
    *,
    maximum_wait_seconds: int,
) -> tuple[int | None, float | None]:
    position = int(np.searchsorted(index_ns, int(pd.Timestamp(desired).value), side="left"))
    if position >= len(index_ns):
        return None, None
    wait = float((int(index_ns[position]) - int(pd.Timestamp(desired).value)) / 1e9)
    if wait > maximum_wait_seconds:
        return None, wait
    return position, wait


def profile_sources() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Profile cTrader coverage, gaps, caps, and cross-timeframe consistency."""

    timeframes = {
        "M1": ("bars_M1.csv", 1),
        "M5": ("bars_M5.csv", 5),
        "M15": ("bars_M15.csv", 15),
        "M30": ("bars_M30.csv", 30),
        "H1": ("bars_H1.csv", 60),
    }
    rows: list[dict[str, Any]] = []
    frames: dict[str, pd.DataFrame] = {}
    for timeframe, (name, minutes) in timeframes.items():
        export = load_ctrader_bar_export(
            CTRADER_ROOT / name,
            timeframe=timeframe,
            source_timezone="UTC",
            timestamp_convention="bar_open",
            drop_incomplete_tail=True,
        )
        frame = export.frame
        deltas = frame.index.to_series().diff().dt.total_seconds().div(60.0)
        large_gaps = deltas[deltas > minutes]
        rows.append(
            {
                "source": name,
                "kind": "bar",
                "timeframe": timeframe,
                "raw_rows": export.metadata["raw_rows"],
                "canonical_rows": export.metadata["canonical_rows"],
                "timestamp_start": export.metadata["timestamp_start"],
                "timestamp_end": export.metadata["timestamp_end"],
                "expected_interval_minutes": minutes,
                "gap_count": int(len(large_gaps)),
                "largest_gap_minutes": float(large_gaps.max()) if len(large_gaps) else 0.0,
                "zero_volume_rows": int(frame["volume"].eq(0.0).sum()),
                "median_tick_volume": float(frame["volume"].median()),
                "row_cap_suspected": bool(export.metadata["raw_rows"] in {2_000_000, 2_000_001}),
                "file_sha256": export.metadata["file_sha256"],
            }
        )
        if timeframe in {"M5", "M15", "M30", "H1"}:
            frames[timeframe] = frame

    tick_export = load_ctrader_tick_export(
        CTRADER_ROOT / "historical_ticks.csv",
        source_timezone="UTC",
    )
    tick_frame = tick_export.frame
    tick_deltas = tick_frame.index.to_series().diff().dt.total_seconds()
    rows.append(
        {
            "source": "historical_ticks.csv",
            "kind": "tick",
            "timeframe": "event",
            "raw_rows": tick_export.metadata["raw_rows"],
            "canonical_rows": tick_export.metadata["canonical_rows"],
            "timestamp_start": tick_export.metadata["timestamp_start"],
            "timestamp_end": tick_export.metadata["timestamp_end"],
            "expected_interval_minutes": None,
            "gap_count": int(tick_deltas.gt(120.0).sum()),
            "largest_gap_minutes": float(tick_deltas.max() / 60.0),
            "zero_volume_rows": None,
            "median_tick_volume": None,
            "row_cap_suspected": bool(tick_export.metadata["raw_rows"] in {2_000_000, 2_000_001}),
            "file_sha256": tick_export.metadata["file_sha256"],
        }
    )

    auxiliary_sources = (
        "account.csv",
        "collector_log.csv",
        "dom_events.csv",
        "dom_snapshot.csv",
        "quotes.csv",
        "symbol_info.csv",
        "ticks.csv",
    )
    for name in auxiliary_sources:
        path = CTRADER_ROOT / name
        auxiliary = pd.read_csv(path)
        timestamp_column = "time" if "time" in auxiliary.columns else "export_time"
        timestamps = pd.to_datetime(
            auxiliary[timestamp_column], errors="coerce", utc=True
        )
        rows.append(
            {
                "source": name,
                "kind": "microstructure_auxiliary",
                "timeframe": "event",
                "raw_rows": int(len(auxiliary)),
                "canonical_rows": int(timestamps.notna().sum()),
                "timestamp_start": (
                    timestamps.min().isoformat() if timestamps.notna().any() else None
                ),
                "timestamp_end": (
                    timestamps.max().isoformat() if timestamps.notna().any() else None
                ),
                "expected_interval_minutes": None,
                "gap_count": None,
                "largest_gap_minutes": None,
                "zero_volume_rows": None,
                "median_tick_volume": None,
                "row_cap_suspected": False,
                "file_sha256": file_sha256(path),
            }
        )

    consistency_rows = [
        _timeframe_consistency(frames["M5"], frames["M30"], rule="30min", expected_children=6, label="M5_to_M30"),
        _timeframe_consistency(frames["M15"], frames["M30"], rule="30min", expected_children=2, label="M15_to_M30"),
        _timeframe_consistency(frames["M30"], frames["H1"], rule="1h", expected_children=2, label="M30_to_H1"),
    ]
    tick_stats = {
        "median_spread_bps": float(tick_frame["spread_bps"].median()),
        "spread_bps_p95": float(tick_frame["spread_bps"].quantile(0.95)),
        "spread_bps_p99": float(tick_frame["spread_bps"].quantile(0.99)),
        "spread_bps_max": float(tick_frame["spread_bps"].max()),
        "ticks_per_second_median": float(
            tick_frame.groupby(tick_frame.index.floor("s")).size().median()
        ),
    }
    return pd.DataFrame(rows), pd.DataFrame(consistency_rows), tick_stats


def _timeframe_consistency(
    child: pd.DataFrame,
    parent: pd.DataFrame,
    *,
    rule: str,
    expected_children: int,
    label: str,
) -> dict[str, Any]:
    grouped = child.resample(rule, label="left", closed="left")
    aggregate = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    counts = grouped["close"].count()
    complete = aggregate.loc[counts.eq(expected_children)]
    common = complete.index.intersection(parent.index)
    left = complete.loc[common]
    right = parent.loc[common]
    price_match = pd.DataFrame(
        {
            column: np.isclose(left[column], right[column], rtol=0.0, atol=0.011)
            for column in ("open", "high", "low", "close")
        }
    )
    volume_match = np.isclose(left["volume"], right["volume"], rtol=0.0, atol=0.5)
    return {
        "comparison": label,
        "common_complete_rows": int(len(common)),
        "ohlc_all_match_rate": float(price_match.all(axis=1).mean()) if len(common) else None,
        "open_match_rate": float(price_match["open"].mean()) if len(common) else None,
        "high_match_rate": float(price_match["high"].mean()) if len(common) else None,
        "low_match_rate": float(price_match["low"].mean()) if len(common) else None,
        "close_match_rate": float(price_match["close"].mean()) if len(common) else None,
        "volume_match_rate": float(volume_match.mean()) if len(common) else None,
    }


def build_pattern_atlas(frame: pd.DataFrame) -> pd.DataFrame:
    """Summarize non-overlapping conditional outcomes across predefined views."""

    discovery = frame.loc[frame.index <= DISCOVERY_END]
    split_ranges = (
        ("discovery", frame.index.min(), DISCOVERY_END),
        ("validation_2023", VALIDATION_2023_START, VALIDATION_2023_END),
        ("validation_2024", VALIDATION_2024_START, VALIDATION_2024_END),
        ("confirmation_2025h1", CONFIRMATION_2025H1_START, CONFIRMATION_2025H1_END),
        ("historical_diagnostic", HISTORICAL_DIAGNOSTIC_START, frame.index.max()),
    )

    efficiency_bins = _quantile_edges(discovery["atlas_efficiency_32"], 5)
    acceleration_bins = _quantile_edges(discovery["atlas_efficiency_acceleration"], 5)
    autocorrelation_bins = _quantile_edges(discovery["atlas_autocorrelation_32"], 5)
    compression_bins = _quantile_edges(discovery["atlas_compression"], 5)
    volatility_bins = _quantile_edges(discovery["atlas_realized_vol_64"], 5)

    views: dict[str, tuple[pd.Series, str]] = {
        "efficiency_32_quintile": (
            _cut_labels(frame["atlas_efficiency_32"], efficiency_bins),
            "continuation_32",
        ),
        "efficiency_acceleration_quintile": (
            _cut_labels(
                frame["atlas_efficiency_acceleration"],
                acceleration_bins,
            ),
            "continuation_8",
        ),
        "autocorrelation_32_quintile": (
            _cut_labels(
                frame["atlas_autocorrelation_32"],
                autocorrelation_bins,
            ),
            "continuation_32",
        ),
        "compression_quintile": (
            _cut_labels(frame["atlas_compression"], compression_bins),
            "acceptance_direction",
        ),
        "volatility_64_quintile": (
            _cut_labels(
                frame["atlas_realized_vol_64"],
                volatility_bins,
            ),
            "raw",
        ),
        "entry_hour_utc": (frame["atlas_entry_hour_utc"].astype(str), "raw"),
        "weekday_utc": (frame["atlas_weekday_utc"].astype(str), "raw"),
        "price_robust_z_band": (
            _cut_labels(
                frame["atlas_price_robust_z"],
                [-np.inf, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, np.inf],
            ),
            "extreme_reversal",
        ),
        "volume_surprise_band": (
            _cut_labels(
                frame["atlas_volume_surprise"],
                [-np.inf, -1.0, 0.0, 1.0, 2.0, np.inf],
            ),
            "wick_direction",
        ),
    }

    rows: list[dict[str, Any]] = []
    for split_name, split_start, split_end in split_ranges:
        split_mask = (frame.index >= split_start) & (frame.index <= split_end)
        for view_name, (groups, outcome_kind) in views.items():
            for horizon in (4, 8, 16):
                raw = pd.to_numeric(
                    frame[f"future_open_return_{horizon}"], errors="coerce"
                )
                if outcome_kind == "continuation_32":
                    outcome = np.sign(frame["atlas_signed_efficiency_32"]) * raw
                elif outcome_kind == "continuation_8":
                    outcome = np.sign(frame["atlas_signed_efficiency_8"]) * raw
                elif outcome_kind == "acceptance_direction":
                    outcome = np.sign(frame["atlas_acceptance"]) * raw
                elif outcome_kind == "extreme_reversal":
                    outcome = -np.sign(frame["atlas_price_robust_z"]) * raw
                elif outcome_kind == "wick_direction":
                    outcome = np.sign(frame["atlas_wick_imbalance"]) * raw
                else:
                    outcome = raw
                for group in sorted(groups.loc[split_mask].dropna().unique().tolist()):
                    group_mask = split_mask & groups.eq(group) & outcome.notna()
                    sampled = _non_overlapping_values(outcome, group_mask, horizon=horizon)
                    if sampled.empty:
                        continue
                    std = float(sampled.std(ddof=1))
                    t_stat = (
                        float(sampled.mean() / (std / np.sqrt(len(sampled))))
                        if len(sampled) > 1 and std > 0.0
                        else 0.0
                    )
                    rows.append(
                        {
                            "split": split_name,
                            "view": view_name,
                            "group": str(group),
                            "outcome_kind": outcome_kind,
                            "horizon_bars": horizon,
                            "event_count": int(len(sampled)),
                            "mean_return_bps": float(sampled.mean() * 10_000.0),
                            "median_return_bps": float(sampled.median() * 10_000.0),
                            "hit_rate": float((sampled > 0.0).mean()),
                            "t_stat": t_stat,
                        }
                    )
    return pd.DataFrame(rows)


def _cut_labels(series: pd.Series, bins: list[float] | np.ndarray) -> pd.Series:
    """Keep missing observations missing instead of converting them to the string 'nan'."""

    return pd.cut(series, bins, include_lowest=True).astype("string")


def _quantile_edges(series: pd.Series, quantiles: int) -> np.ndarray:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        raise ValueError("Cannot build atlas quantiles from an empty discovery series.")
    edges = np.unique(values.quantile(np.linspace(0.0, 1.0, quantiles + 1)).to_numpy())
    if len(edges) < 3:
        raise ValueError("Discovery feature does not have enough unique values for quantiles.")
    edges[0] = -np.inf
    edges[-1] = np.inf
    return edges


def _non_overlapping_values(
    outcome: pd.Series,
    mask: pd.Series,
    *,
    horizon: int,
) -> pd.Series:
    positions = np.flatnonzero(mask.fillna(False).to_numpy(dtype=bool))
    kept: list[int] = []
    last = -horizon - 1
    for position in positions:
        if position > last + horizon:
            kept.append(int(position))
            last = int(position)
    return outcome.iloc[kept].astype(float)


def select_pattern_candidate(
    frame: pd.DataFrame,
    *,
    round_trip_cost_bps: float,
    specs: tuple[PatternSpec, ...] | None = None,
) -> tuple[PatternSpec | None, pd.DataFrame, dict[str, Any]]:
    """Select only from discovery and three chronological confirmation splits."""

    selection_frame = frame.loc[frame.index <= CONFIRMATION_2025H1_END]
    records: list[dict[str, Any]] = []
    search_specs = candidate_grid() if specs is None else specs
    for spec in search_specs:
        record: dict[str, Any] = {"candidate_id": spec.candidate_id, **asdict(spec)}
        split_metrics: list[dict[str, Any]] = []
        all_ledgers: list[pd.DataFrame] = []
        for split_name, configured_start, split_end in SELECTION_SPLITS:
            split_start = (
                selection_frame.index.min()
                if configured_start is None
                else pd.Timestamp(configured_start)
            )
            ledger = fixed_holding_ledger(
                selection_frame,
                spec,
                start=split_start,
                end=min(pd.Timestamp(split_end), selection_frame.index.max()),
                round_trip_cost_bps=round_trip_cost_bps,
            )
            metrics = trade_metrics(
                ledger,
                evidence_scope=f"{split_name} cTrader M30 fixed-holding replay",
            )
            split_metrics.append(metrics)
            if not ledger.empty:
                all_ledgers.append(ledger)
            record.update({f"{split_name}_{key}": value for key, value in metrics.items()})

        combined = pd.concat(all_ledgers, ignore_index=True) if all_ledgers else pd.DataFrame()
        combined_metrics = trade_metrics(
            combined,
            evidence_scope="combined selection splits",
        )
        double_cost = _restress_ledger(
            combined,
            base_cost_bps=round_trip_cost_bps,
            stressed_cost_bps=2.0 * round_trip_cost_bps,
        )
        double_cost_metrics = trade_metrics(
            double_cost,
            evidence_scope="combined selection splits at 2x transaction cost",
        )
        worst_return = min(float(item["cumulative_return"]) for item in split_metrics)
        worst_pf = min(float(item["trade_profit_factor"]) for item in split_metrics)
        worst_sharpe = min(float(item["conventional_sharpe"]) for item in split_metrics)
        minimum_trades = min(int(item["trade_count"]) for item in split_metrics)
        positive_splits = sum(float(item["cumulative_return"]) > 0.0 for item in split_metrics)
        eligible = (
            minimum_trades >= 15
            and positive_splits == len(SELECTION_SPLITS)
            and worst_return > 0.0
            and worst_pf > 1.0
            and float(double_cost_metrics["cumulative_return"]) > 0.0
            and int(combined_metrics["long_trade_count"]) > 0
            and int(combined_metrics["short_trade_count"]) > 0
        )
        selection_score = (
            0.60 * float(np.clip(worst_sharpe, -3.0, 3.0))
            + np.log(float(np.clip(worst_pf, 1.0e-6, 100.0)))
            + 2.0 * worst_return
            + 0.20 * float(combined_metrics["win_rate"])
        )
        record.update(
            {
                "eligible": bool(eligible),
                "selection_score": float(selection_score),
                "positive_selection_splits": int(positive_splits),
                "worst_split_cumulative_return": worst_return,
                "worst_split_profit_factor": worst_pf,
                "worst_split_conventional_sharpe": worst_sharpe,
                "minimum_split_trade_count": minimum_trades,
                **{f"combined_{key}": value for key, value in combined_metrics.items()},
                **{
                    f"double_cost_{key}": value
                    for key, value in double_cost_metrics.items()
                },
            }
        )
        records.append(record)

    table = pd.DataFrame(records).sort_values(
        ["eligible", "positive_selection_splits", "selection_score"],
        ascending=[False, False, False],
    )
    eligible_rows = table.loc[table["eligible"]]
    diagnostic_leader_id = str(table.iloc[0]["candidate_id"])
    if eligible_rows.empty:
        return None, table, {
            "status": "no_candidate_passed_four_split_gate",
            "candidate_count": int(len(table)),
            "eligible_candidate_count": 0,
            "selected_candidate_id": None,
            "diagnostic_leader_id": diagnostic_leader_id,
            "historical_diagnostic_authorized": False,
        }
    row = eligible_rows.iloc[0]
    selected = PatternSpec(
        family=str(row["family"]),
        primary_threshold=float(row["primary_threshold"]),
        secondary_threshold=float(row["secondary_threshold"]),
        release_threshold=float(row["release_threshold"]),
        holding_bars=int(row["holding_bars"]),
        session_start_hour=int(row["session_start_hour"]),
        session_end_hour=int(row["session_end_hour"]),
    )
    return selected, table, {
        "status": "selected_from_four_split_eligible_set",
        "candidate_count": int(len(table)),
        "eligible_candidate_count": int(len(eligible_rows)),
        "selected_candidate_id": selected.candidate_id,
        "diagnostic_leader_id": diagnostic_leader_id,
        "historical_diagnostic_authorized": True,
    }


def _restress_ledger(
    ledger: pd.DataFrame,
    *,
    base_cost_bps: float,
    stressed_cost_bps: float,
) -> pd.DataFrame:
    if ledger.empty:
        return ledger.copy()
    out = ledger.copy()
    extra = (stressed_cost_bps - base_cost_bps) / 10_000.0
    out["estimated_cost_return"] = out["estimated_cost_return"] + extra
    out["net_return"] = out["gross_return"] - out["estimated_cost_return"]
    return out


def stable_pattern_ranking(atlas: pd.DataFrame) -> pd.DataFrame:
    """Rank descriptive patterns using selection splits only.

    The sign is fixed from discovery. Later selection splits test whether that
    discovery direction persists; the historical diagnostic column is attached
    only after ranking and never changes the rank.
    """

    selection_names = [name for name, _, _ in SELECTION_SPLITS]
    rows: list[dict[str, Any]] = []
    keys = ["view", "group", "outcome_kind", "horizon_bars"]
    for values, group in atlas.groupby(keys, dropna=False):
        indexed = group.set_index("split")
        if not set(selection_names).issubset(indexed.index):
            continue
        discovery_mean = float(indexed.loc["discovery", "mean_return_bps"])
        direction = int(np.sign(discovery_mean))
        if direction == 0:
            continue
        signed_means = {
            name: direction * float(indexed.loc[name, "mean_return_bps"])
            for name in selection_names
        }
        event_counts = {
            name: int(indexed.loc[name, "event_count"]) for name in selection_names
        }
        stable = (
            event_counts["discovery"] >= 100
            and min(event_counts[name] for name in selection_names[1:]) >= 30
            and min(signed_means.values()) > 0.0
        )
        historical = indexed.loc["historical_diagnostic"] if "historical_diagnostic" in indexed.index else None
        rows.append(
            {
                "view": values[0],
                "group": values[1],
                "outcome_kind": values[2],
                "horizon_bars": int(values[3]),
                "discovery_direction": "positive" if direction > 0 else "negative",
                "stable_across_selection_splits": bool(stable),
                "worst_selection_signed_mean_bps": float(min(signed_means.values())),
                "mean_selection_signed_mean_bps": float(np.mean(list(signed_means.values()))),
                "minimum_selection_event_count": int(min(event_counts.values())),
                **{f"{name}_signed_mean_bps": value for name, value in signed_means.items()},
                "historical_diagnostic_signed_mean_bps": (
                    direction * float(historical["mean_return_bps"])
                    if historical is not None
                    else None
                ),
                "historical_diagnostic_event_count": (
                    int(historical["event_count"]) if historical is not None else 0
                ),
                "historical_direction_persisted": (
                    bool(direction * float(historical["mean_return_bps"]) > 0.0)
                    if historical is not None
                    else None
                ),
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        [
            "stable_across_selection_splits",
            "worst_selection_signed_mean_bps",
            "mean_selection_signed_mean_bps",
        ],
        ascending=[False, False, False],
    )


def ledger_stability(ledger: pd.DataFrame, *, scope: str) -> pd.DataFrame:
    if ledger.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    working = ledger.copy()
    working["entry_year"] = pd.to_datetime(working["entry_timestamp"]).dt.year
    for dimension, groups in (
        ("year", working.groupby("entry_year")),
        ("side", working.groupby("side")),
    ):
        for value, group in groups:
            rows.append(
                {
                    "scope": scope,
                    "dimension": dimension,
                    "value": str(value),
                    **trade_metrics(
                        group,
                        evidence_scope=f"{scope}: {dimension}={value}",
                    ),
                }
            )
    return pd.DataFrame(rows)


def run_suite(
    *,
    output_dir: str | Path | None = None,
    research_round: str = "stage1",
) -> dict[str, Any]:
    """Run the causal dataset map, strategy search, and gated tick validation."""

    run_dir = _resolve_output_dir(output_dir)
    inventory, consistency, tick_stats = profile_sources()
    inventory.to_csv(run_dir / "source_inventory.csv", index=False)
    consistency.to_csv(run_dir / "timeframe_consistency.csv", index=False)
    _write_json(run_dir / "tick_statistics.json", tick_stats)

    export = load_ctrader_bar_export(
        CTRADER_ROOT / "bars_M30.csv",
        timeframe="M30",
        source_timezone="UTC",
        timestamp_convention="bar_open",
        drop_incomplete_tail=True,
    )
    frame = build_pattern_frame(export.frame)
    atlas = build_pattern_atlas(frame)
    atlas.to_csv(run_dir / "pattern_atlas.csv", index=False)
    stable_patterns = stable_pattern_ranking(atlas)
    stable_patterns.to_csv(run_dir / "stable_pattern_ranking.csv", index=False)

    base_round_trip_cost_bps = float(tick_stats["median_spread_bps"]) + (
        2.0 * BASE_COMMISSION_BPS_PER_SIDE
    )
    search_specs = candidate_grid(research_round)
    selected, search_table, selection_status = select_pattern_candidate(
        frame,
        round_trip_cost_bps=base_round_trip_cost_bps,
        specs=search_specs,
    )
    search_table.to_csv(run_dir / "candidate_search.csv", index=False)

    selection_ledgers: list[pd.DataFrame] = []
    selection_metrics: dict[str, Any] = {}
    historical_metrics: dict[str, Any] = {}
    historical_gate: dict[str, Any] = {"evaluated": False, "passed": False}
    exact_base_metrics: dict[str, Any] = {}
    exact_gate: dict[str, Any] = {"evaluated": False, "passed": False}
    stress_rows: list[dict[str, Any]] = []
    exact_ledgers: list[pd.DataFrame] = []
    stability_frames: list[pd.DataFrame] = []

    if selected is not None:
        for split_name, configured_start, split_end in SELECTION_SPLITS:
            start = frame.index.min() if configured_start is None else pd.Timestamp(configured_start)
            ledger = fixed_holding_ledger(
                frame.loc[frame.index <= CONFIRMATION_2025H1_END],
                selected,
                start=start,
                end=pd.Timestamp(split_end),
                round_trip_cost_bps=base_round_trip_cost_bps,
            )
            if not ledger.empty:
                ledger = ledger.assign(evidence_split=split_name)
                selection_ledgers.append(ledger)
            selection_metrics[split_name] = trade_metrics(
                ledger,
                evidence_scope=f"{split_name} fixed candidate",
            )

        combined_selection = (
            pd.concat(selection_ledgers, ignore_index=True)
            if selection_ledgers
            else pd.DataFrame()
        )
        combined_selection.to_csv(run_dir / "selected_candidate_selection_ledger.csv", index=False)
        selection_metrics["combined"] = trade_metrics(
            combined_selection,
            evidence_scope="combined selection splits with frozen candidate",
        )
        stability_frames.append(
            ledger_stability(combined_selection, scope="selection")
        )

        historical_ledger = fixed_holding_ledger(
            frame,
            selected,
            start=HISTORICAL_DIAGNOSTIC_START,
            end=frame.index.max(),
            round_trip_cost_bps=base_round_trip_cost_bps,
        )
        historical_ledger.to_csv(run_dir / "historical_diagnostic_ledger.csv", index=False)
        historical_metrics = trade_metrics(
            historical_ledger,
            evidence_scope=(
                "single-use historical diagnostic after four-split selection; "
                "not prospective"
            ),
        )
        stability_frames.append(
            ledger_stability(historical_ledger, scope="historical_diagnostic")
        )
        historical_conditions = {
            "minimum_20_trades": int(historical_metrics["trade_count"]) >= 20,
            "win_rate_at_least_70pct": float(historical_metrics["win_rate"]) >= 0.70,
            "positive_net_return": float(historical_metrics["cumulative_return"]) > 0.0,
            "profit_factor_at_least_1_20": float(historical_metrics["trade_profit_factor"]) >= 1.20,
            "conventional_sharpe_at_least_1": float(historical_metrics["conventional_sharpe"]) >= 1.0,
            "both_sides_present": (
                int(historical_metrics["long_trade_count"]) > 0
                and int(historical_metrics["short_trade_count"]) > 0
            ),
        }
        historical_gate = {
            "evaluated": True,
            "passed": bool(all(historical_conditions.values())),
            "conditions": historical_conditions,
        }

        tick_export = load_ctrader_tick_export(
            CTRADER_ROOT / "historical_ticks.csv",
            source_timezone="UTC",
        )
        for stress in STRESS_GRID:
            ledger, diagnostics = exact_tick_fixed_holding_ledger(
                frame,
                tick_export.frame,
                selected,
                stress=stress,
            )
            metrics = trade_metrics(
                ledger,
                evidence_scope=f"exact cTrader tick replay: {stress.scenario_id}",
            )
            stress_rows.append(
                {
                    **asdict(stress),
                    "scenario_id": stress.scenario_id,
                    **diagnostics,
                    **metrics,
                }
            )
            if not ledger.empty:
                exact_ledgers.append(ledger)
            if stress.delay_seconds == 0 and stress.spread_multiplier == 1.0 and stress.slippage_bps_per_side == 0.0:
                exact_base_metrics = metrics
                stability_frames.append(ledger_stability(ledger, scope="exact_tick_base"))

        exact_combined = (
            pd.concat(exact_ledgers, ignore_index=True)
            if exact_ledgers
            else pd.DataFrame()
        )
        exact_combined.to_csv(run_dir / "exact_tick_ledgers.csv", index=False)
        stress_table = pd.DataFrame(stress_rows)
        stress_table.to_csv(run_dir / "exact_tick_stress.csv", index=False)
        exact_conditions = {
            "minimum_10_base_trades": int(exact_base_metrics.get("trade_count", 0)) >= 10,
            "base_win_rate_at_least_70pct": float(exact_base_metrics.get("win_rate", 0.0)) >= 0.70,
            "base_positive_net_return": float(exact_base_metrics.get("cumulative_return", 0.0)) > 0.0,
            "base_profit_factor_at_least_1_20": float(exact_base_metrics.get("trade_profit_factor", 0.0)) >= 1.20,
            "all_stress_scenarios_positive": bool(
                len(stress_table) > 0 and stress_table["cumulative_return"].gt(0.0).all()
            ),
        }
        exact_gate = {
            "evaluated": True,
            "passed": bool(all(exact_conditions.values())),
            "conditions": exact_conditions,
        }
    else:
        pd.DataFrame().to_csv(run_dir / "selected_candidate_selection_ledger.csv", index=False)
        pd.DataFrame().to_csv(run_dir / "historical_diagnostic_ledger.csv", index=False)
        pd.DataFrame().to_csv(run_dir / "exact_tick_ledgers.csv", index=False)
        pd.DataFrame().to_csv(run_dir / "exact_tick_stress.csv", index=False)

    stability = (
        pd.concat([item for item in stability_frames if not item.empty], ignore_index=True)
        if any(not item.empty for item in stability_frames)
        else pd.DataFrame()
    )
    stability.to_csv(run_dir / "selected_candidate_stability.csv", index=False)

    stable_selection_count = int(
        stable_patterns.get("stable_across_selection_splits", pd.Series(dtype=bool)).sum()
    )
    stable_historical_count = int(
        (
            stable_patterns.get("stable_across_selection_splits", pd.Series(dtype=bool))
            & stable_patterns.get("historical_direction_persisted", pd.Series(dtype=bool)).fillna(False)
        ).sum()
    )
    if selected is None:
        verdict = (
            "NO ROBUST STRATEGY CANDIDATE: no causal rule passed all four "
            "chronological selection gates; historical/tick strategy evaluation was denied."
        )
    elif historical_gate["passed"] and exact_gate["passed"]:
        verdict = (
            "HISTORICAL CANDIDATE PASSED THE 70% AND EXECUTION GATES, but real alpha "
            "still requires a frozen prospective cTrader confirmation period."
        )
    else:
        verdict = (
            "A FOUR-SPLIT HISTORICAL CANDIDATE EXISTS, but it failed at least one "
            "70%/historical/exact-execution gate and is not deployable."
        )

    source_paths = sorted(path for path in CTRADER_ROOT.iterdir() if path.is_file())
    provenance = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git": collect_git_metadata(),
        "source_hashes": {path.name: file_sha256(path) for path in source_paths},
        "m30_loader_metadata": export.metadata,
        "selection_policy": (
            "Grid and thresholds use discovery through 2025H1 only. Historical data "
            "from 2025-07 onward is descriptive for the atlas and may be opened for "
            "strategy diagnostics only after a four-split candidate passes."
        ),
        "execution_contract": (
            "Signals use completed M30 bars; bar replay enters next M30 open and exits "
            "after fixed holding bars. Exact replay uses first cTrader quote at/after "
            "the decision plus scenario delay, side-aware bid/ask, commission, and slippage."
        ),
    }
    _write_json(run_dir / "provenance.json", provenance)

    summary: dict[str, Any] = {
        "run_dir": str(run_dir),
        "research_round": research_round,
        "verdict": verdict,
        "source_inventory_rows": int(len(inventory)),
        "m30_rows": int(len(frame)),
        "m30_start": frame.index.min(),
        "m30_end": frame.index.max(),
        "base_round_trip_cost_bps": base_round_trip_cost_bps,
        "candidate_grid_count": int(len(search_table)),
        "selection_status": selection_status,
        "selected_candidate": asdict(selected) if selected is not None else None,
        "selection_metrics": selection_metrics,
        "historical_diagnostic_metrics": historical_metrics,
        "historical_gate": historical_gate,
        "exact_tick_base_metrics": exact_base_metrics,
        "exact_tick_gate": exact_gate,
        "stable_pattern_count_selection": stable_selection_count,
        "stable_pattern_count_persisting_historical": stable_historical_count,
        "pattern_cells_tested": int(len(stable_patterns)),
        "tick_statistics": tick_stats,
    }
    _write_json(run_dir / "summary.json", summary)
    (run_dir / "report.md").write_text(
        _report_markdown(summary, inventory=inventory, consistency=consistency),
        encoding="utf-8",
    )
    return _jsonable(summary)


def _report_markdown(
    summary: Mapping[str, Any],
    *,
    inventory: pd.DataFrame,
    consistency: pd.DataFrame,
) -> str:
    selected = dict(summary.get("selected_candidate") or {})
    selection = dict(summary.get("selection_metrics") or {})
    combined = dict(selection.get("combined") or {})
    historical = dict(summary.get("historical_diagnostic_metrics") or {})
    exact = dict(summary.get("exact_tick_base_metrics") or {})
    source_table = _markdown_table(
        inventory[
            [
                "source",
                "kind",
                "canonical_rows",
                "timestamp_start",
                "timestamp_end",
                "row_cap_suspected",
            ]
        ]
    )
    consistency_table = _markdown_table(consistency)
    selected_text = (
        f"`{PatternSpec(**selected).candidate_id}`" if selected else "none"
    )
    return f"""# ETHUSD cTrader dataset pattern atlas and causal alpha search

## Technical summary

**{summary.get('verdict')}**

The canonical research surface is cTrader ETHUSD M30. M5/M15/H1 are used for consistency checks, M1 is profiled for coverage, and historical cTrader bid/ask ticks are reserved for exact execution replay. The atlas evaluates efficiency across several scales, efficiency acceleration, compression/release, short-lag autocorrelation, robust price displacement, volume surprise, candle acceptance, wick imbalance, UTC hour, and weekday.

- Candidate rules searched: {summary.get('candidate_grid_count')}
- Four-split eligible candidates: {dict(summary.get('selection_status') or {{}}).get('eligible_candidate_count')}
- Frozen selected candidate: {selected_text}
- Stable descriptive cells across discovery, 2023, 2024, and 2025H1: {summary.get('stable_pattern_count_selection')} / {summary.get('pattern_cells_tested')}
- Of those, sign also persisted in the historical diagnostic period: {summary.get('stable_pattern_count_persisting_historical')}
- Bar cost proxy: {float(summary.get('base_round_trip_cost_bps', 0.0)):.3f} bps round trip, equal to the exact-tick median spread plus 0.5 bps commission per side.

## Strategy evidence

| Evidence layer | Trades | Win rate | Net return | Profit factor | Conventional Sharpe |
|---|---:|---:|---:|---:|---:|
| Four selection splits combined | {combined.get('trade_count', 0)} | {100.0 * float(combined.get('win_rate', 0.0)):.2f}% | {100.0 * float(combined.get('cumulative_return', 0.0)):.2f}% | {float(combined.get('trade_profit_factor', 0.0)):.3f} | {float(combined.get('conventional_sharpe', 0.0)):.3f} |
| Historical diagnostic, not prospective | {historical.get('trade_count', 0)} | {100.0 * float(historical.get('win_rate', 0.0)):.2f}% | {100.0 * float(historical.get('cumulative_return', 0.0)):.2f}% | {float(historical.get('trade_profit_factor', 0.0)):.3f} | {float(historical.get('conventional_sharpe', 0.0)):.3f} |
| Exact cTrader ticks, base execution | {exact.get('trade_count', 0)} | {100.0 * float(exact.get('win_rate', 0.0)):.2f}% | {100.0 * float(exact.get('cumulative_return', 0.0)):.2f}% | {float(exact.get('trade_profit_factor', 0.0)):.3f} | {float(exact.get('conventional_sharpe', 0.0)):.3f} |

The 70% objective is a gate, not an optimization target in the candidate score. A high hit rate without positive net return, profit factor, temporal consistency, both trade directions, and cost survival is rejected.

## Scope and data quality

{source_table}

### Cross-timeframe reconciliation

{consistency_table}

The M1 and historical tick exports are flagged when their row counts equal a round collector cap. DOM, live quotes, live ticks, account, and collector files cover only a short live session and therefore support case-study diagnostics, not general market claims.

## Methods and causality

All indicator values at timestamp *t* use information available by the close of the M30 bar at *t*. Entry is the next M30 open. Rolling medians, MADs, highs, lows, and range baselines are shifted where the current observation would otherwise contaminate a reference distribution. Future returns are stored only in explicitly named `future_*` columns and never enter the signal functions.

Candidate selection uses discovery through 2022, validation 2023, validation 2024, and confirmation 2025H1. A candidate needs at least 15 trades in every split, positive return and profit factor above one in every split, positive combined return at twice the base cost, and both long and short trades. Only after passing may it access the 2025H2+ strategy diagnostic and exact ticks.

## Limitations and uncertainty

- This is a multiple-hypothesis research exercise. Stable atlas cells are descriptive and are not independent statistical tests; their t-statistics are diagnostics, not corrected p-values.
- The period from 2025-07 onward is a historical pseudo-holdout, not prospective, because this dataset and earlier research have already been inspected.
- Exact bid/ask validation is limited to the tick export's short 2026 coverage. A small number of executed trades cannot validate a production execution model.
- Tick volume is broker/event activity, not centralized ETH market volume. DOM is broker-specific and very short.
- Bar replay omits swap, order rejection, market impact, partial fills, financing, and account-level FTMO constraints.
- UTC and cTrader bar-open timestamp conventions are explicit software assumptions and should also be confirmed at the terminal/exporter configuration.

## Next steps

Freeze only a candidate that passes every gate, then collect append-only cTrader M30 and bid/ask ticks prospectively without changing thresholds, sessions, holding periods, or costs. A genuine alpha claim requires that new prospective sample plus adequate trade count and execution coverage.

## Further questions

The durable open questions are whether the stable efficiency-related cells survive a multiplicity-aware prospective test, whether performance is symmetric by side and year, and whether the broker's spread/latency distribution changes outside the short tick sample. See `stable_pattern_ranking.csv`, `candidate_search.csv`, `selected_candidate_stability.csv`, and `exact_tick_stress.csv` for the complete evidence.
"""


def _markdown_table(frame: pd.DataFrame) -> str:
    """Render a compact Markdown table without an optional tabulate dependency."""

    columns = [str(column) for column in frame.columns]
    header = "| " + " | ".join(columns) + " |"
    separator = "|" + "|".join("---" for _ in columns) + "|"
    body = []
    for row in frame.itertuples(index=False, name=None):
        body.append(
            "| "
            + " | ".join(
                str(value).replace("|", "\\|") if pd.notna(value) else ""
                for value in row
            )
            + " |"
        )
    return "\n".join([header, separator, *body])


def _resolve_output_dir(path: str | Path | None) -> Path:
    if path is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        candidate = PROJECT_ROOT / "logs/experiments" / f"ethusd_pattern_atlas_{stamp}"
    else:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
    candidate = enforce_safe_absolute_path(candidate.resolve())
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(dict(payload)), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Map the cTrader ETHUSD dataset and search causal efficiency patterns."
    )
    parser.add_argument("--output-dir", default=None)
    parser.add_argument(
        "--research-round",
        choices=("stage1", "stage2"),
        default="stage1",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            run_suite(
                output_dir=args.output_dir,
                research_round=args.research_round,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()


__all__ = [
    "PatternSpec",
    "build_pattern_atlas",
    "build_pattern_frame",
    "candidate_grid",
    "candidate_triggers",
    "exact_tick_fixed_holding_ledger",
    "fixed_holding_ledger",
    "ledger_stability",
    "profile_sources",
    "run_suite",
    "select_pattern_candidate",
    "stable_pattern_ranking",
]
