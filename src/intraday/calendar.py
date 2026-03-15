from __future__ import annotations

from dataclasses import dataclass
import re


_INTERVAL_RE = re.compile(r"^\s*(\d+)\s*([A-Za-z]+)\s*$")
_MINUTE_UNITS = {"m", "min", "mins", "minute", "minutes"}
_HOUR_UNITS = {"h", "hr", "hrs", "hour", "hours"}
_DAY_UNITS = {"d", "day", "days"}
_WEEK_UNITS = {"wk", "w", "week", "weeks"}
_MONTH_UNITS = {"mo", "mon", "month", "months"}


@dataclass(frozen=True)
class IntervalSpec:
    """
    Describe a configured bar interval in a normalized, typed form so intraday-sensitive logic
    does not have to keep reparsing raw strings.
    """
    raw: str
    value: int
    unit: str

    @property
    def minutes(self) -> int | None:
        if self.unit in _MINUTE_UNITS:
            return self.value
        if self.unit in _HOUR_UNITS:
            return self.value * 60
        return None

    @property
    def is_intraday(self) -> bool:
        minutes = self.minutes
        return minutes is not None and minutes < 24 * 60


def parse_interval(interval: str) -> IntervalSpec:
    """
    Parse interval strings such as `1d`, `1h`, or `30m` into a normalized specification.
    """
    value = str(interval).strip().lower()
    match = _INTERVAL_RE.match(value)
    if not match:
        raise ValueError(f"Unsupported interval format: {interval!r}")
    count = int(match.group(1))
    unit = match.group(2).lower()
    if count <= 0:
        raise ValueError("Interval multiplier must be positive.")
    if unit not in (_MINUTE_UNITS | _HOUR_UNITS | _DAY_UNITS | _WEEK_UNITS | _MONTH_UNITS):
        raise ValueError(f"Unsupported interval unit: {unit!r}")
    return IntervalSpec(raw=value, value=count, unit=unit)


def is_intraday_interval(interval: str) -> bool:
    """
    Return whether an interval represents bars inside the same trading session.
    """
    return parse_interval(interval).is_intraday


def default_normalize_daily(interval: str) -> bool:
    """
    Daily-or-slower bars can be normalized safely; intraday bars must retain timestamps.
    """
    return not is_intraday_interval(interval)


def infer_bars_per_session(
    interval: str,
    *,
    trading_hours_per_day: float = 6.5,
) -> float | None:
    """
    Infer the expected number of bars inside a regular cash session for intraday intervals.
    """
    spec = parse_interval(interval)
    minutes = spec.minutes
    if minutes is None or minutes <= 0:
        return None
    return float(trading_hours_per_day * 60.0 / minutes)


def infer_periods_per_year(
    interval: str,
    *,
    trading_days_per_year: int = 252,
    trading_hours_per_day: float = 6.5,
) -> int:
    """
    Infer a reasonable annualization count for backtest metrics under the project's default
    market-hours assumptions.
    """
    spec = parse_interval(interval)
    if spec.is_intraday:
        bars_per_session = infer_bars_per_session(
            interval,
            trading_hours_per_day=trading_hours_per_day,
        )
        assert bars_per_session is not None
        return max(int(round(float(trading_days_per_year) * bars_per_session)), 1)
    if spec.unit in _DAY_UNITS:
        return max(int(round(trading_days_per_year / spec.value)), 1)
    if spec.unit in _WEEK_UNITS:
        return max(int(round(52 / spec.value)), 1)
    if spec.unit in _MONTH_UNITS:
        return max(int(round(12 / spec.value)), 1)
    return max(trading_days_per_year, 1)


def infer_volatility_annualization_factor(
    interval: str,
    *,
    trading_days_per_year: int = 252,
    trading_hours_per_day: float = 6.5,
) -> float:
    """
    Infer a volatility annualization factor that matches the configured bar frequency.
    """
    return float(
        infer_periods_per_year(
            interval,
            trading_days_per_year=trading_days_per_year,
            trading_hours_per_day=trading_hours_per_day,
        )
    )


def validate_intraday_normalization_policy(interval: str, *, normalize_daily: bool) -> None:
    """
    Guard against collapsing intraday bars down to one timestamp per day.
    """
    if is_intraday_interval(interval) and normalize_daily:
        raise ValueError(
            "Intraday intervals must set data.pit.timestamp_alignment.normalize_daily=false."
        )


__all__ = [
    "IntervalSpec",
    "default_normalize_daily",
    "infer_bars_per_session",
    "infer_periods_per_year",
    "infer_volatility_annualization_factor",
    "is_intraday_interval",
    "parse_interval",
    "validate_intraday_normalization_policy",
]
