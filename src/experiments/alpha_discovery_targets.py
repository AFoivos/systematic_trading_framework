from __future__ import annotations

"""Future outcome construction for AR-0001 conditional-effect measurement."""

from typing import Final, Sequence

import numpy as np
import pandas as pd

ALPHA_DISCOVERY_HORIZONS: Final[tuple[int, ...]] = (1, 2, 4, 8, 16, 32)


class AlphaDiscoveryTargetError(ValueError):
    """Raised when future outcomes cannot honor the frozen quote contract."""


def _forward_extreme(series: pd.Series, horizon: int, *, kind: str) -> pd.Series:
    reversed_series = series.iloc[::-1]
    rolling = reversed_series.rolling(horizon, min_periods=horizon)
    if kind == "max":
        including_current = rolling.max().iloc[::-1]
    elif kind == "min":
        including_current = rolling.min().iloc[::-1]
    else:
        raise ValueError(f"Unsupported forward extreme: {kind}.")
    return including_current.shift(-1)


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    values = pd.to_numeric(frame[column], errors="coerce")
    if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
        raise AlphaDiscoveryTargetError(f"{column} must be finite and non-missing.")
    return values.astype(float)


def build_alpha_discovery_targets(
    frame: pd.DataFrame,
    *,
    horizons: Sequence[int] = ALPHA_DISCOVERY_HORIZONS,
) -> pd.DataFrame:
    """Build future-only outcomes aligned to a state observed at ``close[t]``.

    For an ``h``-bar executable outcome, entry is at ``open[t+1]`` and exit is
    at ``open[t+h+1]``.  Longs cross ASK on entry and BID on exit; shorts cross
    BID on entry and ASK on cover.  MFE/MAE use executable quote sides over
    bars ``t+1`` through ``t+h``.  No commission, slippage, or swap is invented;
    these targets are quote-side net of spread only.
    """

    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame.")
    required = {
        "timestamp",
        "mid_open",
        "mid_close",
        "bid_open",
        "bid_high",
        "bid_low",
        "ask_open",
        "ask_high",
        "ask_low",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise AlphaDiscoveryTargetError(f"Missing target inputs: {missing}.")
    timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    if timestamps.isna().any() or timestamps.duplicated().any():
        raise AlphaDiscoveryTargetError("Target timestamps must be valid and unique.")
    if not timestamps.is_monotonic_increasing:
        raise AlphaDiscoveryTargetError("Target timestamps must be sorted.")

    mid_open = _numeric(frame, "mid_open")
    mid_close = _numeric(frame, "mid_close")
    bid_open = _numeric(frame, "bid_open")
    bid_high = _numeric(frame, "bid_high")
    bid_low = _numeric(frame, "bid_low")
    ask_open = _numeric(frame, "ask_open")
    ask_high = _numeric(frame, "ask_high")
    ask_low = _numeric(frame, "ask_low")
    if (
        (mid_open <= 0.0).any()
        or (mid_close <= 0.0).any()
        or (bid_open <= 0.0).any()
        or (ask_open <= 0.0).any()
    ):
        raise AlphaDiscoveryTargetError("Target prices must be strictly positive.")
    if (
        (ask_open < bid_open).any()
        or (ask_high < bid_high).any()
        or (ask_low < bid_low).any()
    ):
        raise AlphaDiscoveryTargetError(
            "Executable target inputs contain crossed quotes."
        )

    output = pd.DataFrame({"timestamp": timestamps})
    one_bar_log_return = np.log(mid_close).diff()
    resolved_horizons: list[int] = []
    for raw_horizon in horizons:
        if isinstance(raw_horizon, bool) or int(raw_horizon) != raw_horizon:
            raise AlphaDiscoveryTargetError("Horizons must be positive integers.")
        horizon = int(raw_horizon)
        if horizon <= 0 or horizon in resolved_horizons:
            raise AlphaDiscoveryTargetError(
                "Horizons must be unique positive integers."
            )
        resolved_horizons.append(horizon)

        future_close = mid_close.shift(-horizon)
        next_mid_open = mid_open.shift(-1)
        future_mid_open = mid_open.shift(-(horizon + 1))
        next_ask_open = ask_open.shift(-1)
        next_bid_open = bid_open.shift(-1)
        future_bid_open = bid_open.shift(-(horizon + 1))
        future_ask_open = ask_open.shift(-(horizon + 1))

        output[f"mid_close_to_close_h{horizon}"] = future_close / mid_close - 1.0
        output[f"next_open_to_future_open_h{horizon}"] = (
            future_mid_open / next_mid_open - 1.0
        )
        output[f"executable_long_h{horizon}"] = future_bid_open / next_ask_open - 1.0
        output[f"executable_short_h{horizon}"] = (
            next_bid_open - future_ask_open
        ) / next_bid_open
        output[f"future_realized_volatility_h{horizon}"] = np.sqrt(
            one_bar_log_return.pow(2)
            .rolling(horizon, min_periods=horizon)
            .sum()
            .shift(-horizon)
        )

        future_bid_high = _forward_extreme(bid_high, horizon, kind="max")
        future_bid_low = _forward_extreme(bid_low, horizon, kind="min")
        future_ask_low = _forward_extreme(ask_low, horizon, kind="min")
        future_ask_high = _forward_extreme(ask_high, horizon, kind="max")
        output[f"long_mfe_h{horizon}"] = future_bid_high / next_ask_open - 1.0
        output[f"long_mae_h{horizon}"] = future_bid_low / next_ask_open - 1.0
        output[f"short_mfe_h{horizon}"] = (
            next_bid_open - future_ask_low
        ) / next_bid_open
        output[f"short_mae_h{horizon}"] = (
            next_bid_open - future_ask_high
        ) / next_bid_open

    return output


def target_columns_for_horizon(horizon: int) -> tuple[str, ...]:
    resolved = int(horizon)
    return (
        f"mid_close_to_close_h{resolved}",
        f"next_open_to_future_open_h{resolved}",
        f"executable_long_h{resolved}",
        f"executable_short_h{resolved}",
        f"future_realized_volatility_h{resolved}",
        f"long_mfe_h{resolved}",
        f"long_mae_h{resolved}",
        f"short_mfe_h{resolved}",
        f"short_mae_h{resolved}",
    )


__all__ = [
    "ALPHA_DISCOVERY_HORIZONS",
    "AlphaDiscoveryTargetError",
    "build_alpha_discovery_targets",
    "target_columns_for_horizon",
]
