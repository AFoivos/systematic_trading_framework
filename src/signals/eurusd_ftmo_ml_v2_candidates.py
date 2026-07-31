from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from src.features.eurusd_ftmo_ml_v2 import add_candidate_indicators
from src.utils.eurusd_ftmo_ml_v2_contract import (
    PULLBACK_COMPONENTS,
    REQUIRED_MARKET_COLUMNS,
    REFERENCE_DATASET,
    PullbackComponent,
)



def validate_and_prepare_market_data(
    data: pd.DataFrame,
    *,
    enforce_reference_shape: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Validate the bid/ask M30 contract and add canonical causal columns."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame.")
    missing = [column for column in REQUIRED_MARKET_COLUMNS if column not in data.columns]
    if missing:
        raise KeyError(f"Missing required EURUSD columns: {missing}")

    out = data.copy()
    timestamps = pd.to_datetime(out["timestamp"], errors="raise", utc=True)
    out["timestamp"] = timestamps.dt.tz_convert(None)
    if out["timestamp"].duplicated().any():
        raise ValueError("EURUSD timestamps must be unique.")
    if not out["timestamp"].is_monotonic_increasing:
        raise ValueError("EURUSD timestamps must be strictly ascending.")
    out = out.set_index("timestamp", drop=False)

    numeric_columns = [column for column in REQUIRED_MARKET_COLUMNS if column != "timestamp"]
    for column in numeric_columns:
        out[column] = pd.to_numeric(out[column], errors="coerce").astype(float)
    price_columns = [
        column for column in numeric_columns
        if column not in {"volume", "spread_close", "spread_bps"}
    ]
    if not np.isfinite(out[numeric_columns].to_numpy(dtype=float)).all():
        raise ValueError("Prices, volume, and spread fields must be finite.")
    if (out[price_columns] <= 0.0).any().any():
        raise ValueError("All price and spread fields must be positive.")
    if (out["volume"] < 0.0).any():
        raise ValueError("Volume must be finite and non-negative.")

    for prefix in ("bid", "ask"):
        high = out[f"{prefix}_high"]
        low = out[f"{prefix}_low"]
        open_ = out[f"{prefix}_open"]
        close = out[f"{prefix}_close"]
        invalid = (high < low) | (high < open_) | (high < close) | (low > open_) | (low > close)
        if invalid.any():
            raise ValueError(f"Invalid {prefix} OHLC geometry.")
    for field in ("open", "high", "low", "close"):
        if (out[f"bid_{field}"] > out[f"ask_{field}"]).any():
            raise ValueError(f"bid_{field} must not exceed ask_{field}.")

    out["mid_open"] = (out["bid_open"] + out["ask_open"]) / 2.0
    out["mid_high"] = (out["bid_high"] + out["ask_high"]) / 2.0
    out["mid_low"] = (out["bid_low"] + out["ask_low"]) / 2.0
    out["mid_close"] = (out["bid_close"] + out["ask_close"]) / 2.0
    invalid_mid = (
        (out["mid_high"] < out["mid_low"])
        | (out["mid_high"] < out[["mid_open", "mid_close"]].max(axis=1))
        | (out["mid_low"] > out[["mid_open", "mid_close"]].min(axis=1))
    )
    if invalid_mid.any():
        raise ValueError("Invalid canonical mid OHLC geometry.")
    out["log_close"] = np.log(out["mid_close"])
    out["logret1"] = out["log_close"].diff()
    out["spread_open"] = out["ask_open"] - out["bid_open"]
    out["spread_close"] = out["spread_close"].where(out["spread_close"] > 0.0)

    deltas = out.index.to_series().diff().dropna()
    expected = pd.Timedelta(minutes=30)
    gaps = deltas[deltas != expected]
    report = {
        "rows": int(len(out)),
        "start": out.index.min().isoformat(sep=" ") if len(out) else None,
        "end": out.index.max().isoformat(sep=" ") if len(out) else None,
        "expected_cadence_minutes": 30,
        "timestamp_gap_count": int(len(gaps)),
        "timestamp_gaps": [
            {"timestamp": timestamp.isoformat(), "delta_seconds": float(delta.total_seconds())}
            for timestamp, delta in gaps.head(100).items()
        ],
        "timezone": "UTC-naive",
    }
    if enforce_reference_shape:
        if len(out) != int(REFERENCE_DATASET["rows"]):
            raise ValueError(f"Expected {REFERENCE_DATASET['rows']} rows, found {len(out)}.")
        if out.index.min() != pd.Timestamp(REFERENCE_DATASET["start"]):
            raise ValueError("Dataset start does not match the reference contract.")
        if out.index.max() != pd.Timestamp(REFERENCE_DATASET["end"]):
            raise ValueError("Dataset end does not match the reference contract.")
    return out, report


def _empty_candidates() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "candidate_id", "signal_timestamp", "entry_timestamp", "exit_signal_timestamp",
            "exit_timestamp", "strategy_family", "component_id", "direction", "is_session",
            "amplitude", "family_weight", "bars_planned",
        ]
    )


def generate_pullback_candidates(
    market: pd.DataFrame,
    *,
    components: Sequence[PullbackComponent] = PULLBACK_COMPONENTS,
) -> pd.DataFrame:
    """Run each pullback state machine independently and emit entry transitions."""
    frame = add_candidate_indicators(market)
    if not isinstance(frame.index, pd.DatetimeIndex) or not frame.index.is_monotonic_increasing:
        raise ValueError("market must use a sorted DatetimeIndex.")
    records: list[dict[str, Any]] = []
    index = frame.index

    for component in components:
        z_column = f"z_{component.component_id}"
        if z_column not in frame.columns:
            raise KeyError(f"Missing component z-score column: {z_column}")
        position = 0
        holding_bars = 0
        open_trade: dict[str, Any] | None = None
        for loc, timestamp in enumerate(index):
            hour_fraction = timestamp.hour + timestamp.minute / 60.0
            liquid = 6.0 <= hour_fraction <= 18.0
            z_value = float(frame.iloc[loc][z_column])
            if position == 0:
                if liquid and np.isfinite(z_value) and abs(z_value) >= component.entry_atr:
                    direction = -1 if z_value > 0.0 else 1
                    if direction == int(frame.iloc[loc]["slow_direction"]) and loc + 1 < len(frame):
                        position = direction
                        holding_bars = 0
                        open_trade = {
                            "candidate_id": f"PB-{component.component_id}-{timestamp.strftime('%Y%m%dT%H%M%S')}",
                            "signal_timestamp": timestamp,
                            "entry_timestamp": index[loc + 1],
                            "strategy_family": "pullback",
                            "component_id": component.component_id,
                            "direction": direction,
                            "is_session": 0,
                            "amplitude": 0.25,
                            "family_weight": 0.80,
                            "bars_planned": component.maximum_hold_bars,
                        }
                continue

            holding_bars += 1
            adverse = (
                (position == 1 and z_value <= -component.adverse_z_stop)
                or (position == -1 and z_value >= component.adverse_z_stop)
            )
            exit_trade = (
                (np.isfinite(z_value) and abs(z_value) <= component.exit_atr)
                or holding_bars >= component.maximum_hold_bars
                or not liquid
                or adverse
            )
            if exit_trade:
                if open_trade is not None and loc + 1 < len(frame):
                    records.append(
                        {
                            **open_trade,
                            "exit_signal_timestamp": timestamp,
                            "exit_timestamp": index[loc + 1],
                        }
                    )
                position = 0
                holding_bars = 0
                open_trade = None

    if not records:
        return _empty_candidates()
    return pd.DataFrame.from_records(records).sort_values(
        ["signal_timestamp", "component_id"], kind="stable"
    ).reset_index(drop=True)


def _previous_completed_daily_trend(market: pd.DataFrame) -> pd.Series:
    daily_close = market["mid_close"].groupby(market.index.normalize()).last().sort_index()
    daily_ema20 = daily_close.ewm(span=20, adjust=False).mean()
    previous = np.sign(daily_close.shift(1) - daily_ema20.shift(1))
    previous.name = "previous_daily_trend"
    return previous


def generate_session_fade_candidates(market: pd.DataFrame) -> pd.DataFrame:
    """Emit at most one causal 06:30 session-fade candidate per UTC date."""
    frame = add_candidate_indicators(market)
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise TypeError("market must use a DatetimeIndex.")
    previous_trend = _previous_completed_daily_trend(frame)
    records: list[dict[str, Any]] = []
    for day, day_frame in frame.groupby(frame.index.normalize(), sort=True):
        signal_timestamp = day + pd.Timedelta(hours=6, minutes=30)
        entry_timestamp = day + pd.Timedelta(hours=7)
        exit_timestamp = day + pd.Timedelta(hours=20)
        start_timestamp = day
        required = (start_timestamp, signal_timestamp, entry_timestamp, exit_timestamp)
        if any(timestamp not in day_frame.index for timestamp in required):
            continue
        overnight_move = float(day_frame.at[signal_timestamp, "mid_close"] - day_frame.at[start_timestamp, "mid_open"])
        atr48 = float(day_frame.at[signal_timestamp, "atr48"])
        trend = float(previous_trend.get(day, np.nan))
        if not np.isfinite(atr48) or atr48 <= 0.0 or not np.isfinite(trend) or trend == 0.0:
            continue
        if abs(overnight_move) < 2.0 * atr48 or overnight_move == 0.0:
            continue
        direction = int(-np.sign(overnight_move))
        if direction != int(-trend):
            continue
        records.append(
            {
                "candidate_id": f"SF-{day.strftime('%Y%m%d')}",
                "signal_timestamp": signal_timestamp,
                "entry_timestamp": entry_timestamp,
                "exit_signal_timestamp": signal_timestamp,
                "exit_timestamp": exit_timestamp,
                "strategy_family": "session_fade",
                "component_id": "session_fade",
                "direction": direction,
                "is_session": 1,
                "amplitude": 1.0,
                "family_weight": 0.20,
                "bars_planned": 26,
                "overnight_move": overnight_move,
                "previous_daily_trend": int(trend),
            }
        )
    return pd.DataFrame.from_records(records) if records else _empty_candidates()


def generate_candidates(market: pd.DataFrame) -> pd.DataFrame:
    pullback = generate_pullback_candidates(market)
    session = generate_session_fade_candidates(market)
    combined = pd.concat([pullback, session], ignore_index=True, sort=False)
    if combined.empty:
        return _empty_candidates()
    if combined["candidate_id"].duplicated().any():
        raise AssertionError("Candidate IDs must be unique.")
    return combined.sort_values(["signal_timestamp", "candidate_id"], kind="stable").reset_index(drop=True)


__all__ = [
    "add_candidate_indicators",
    "generate_candidates",
    "generate_pullback_candidates",
    "generate_session_fade_candidates",
    "validate_and_prepare_market_data",
]
