from __future__ import annotations

"""Quote-aware, rules-only research harness for the fresh FTMO alpha pass.

This module is intentionally kept under :mod:`src.experiments.support`: it is a
research harness, not a production signal or a runner extension.  It consumes
the fresh YAML files under ``config/experiments/fresh_alpha_discovery`` and
uses only raw quote data.

Causality contract
------------------
Every signal is calculated from values known by the close of bar ``t``.  The
simulator enters at the next available bar open (or a deliberately stressed
later open), never at the signal bar.  ATR, EMA, RSI, and breakout levels are
all trailing calculations.  No labels, future returns, barrier diagnostics,
or realised-trade fields are ever passed into a signal.

The raw source has market closures and a few irregular gaps.  A trade may not
open through, or remain open across, a gap larger than the configured maximum;
an existing trade is closed at the final quote before that gap.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping

import numpy as np
import pandas as pd
import yaml

from src.evaluation.metrics import compute_backtest_metrics
from src.src_data.storage import load_ohlcv_csv
from src.src_data.validation import validate_ohlcv


_REQUIRED_QUOTE_COLUMNS = (
    "bid_open",
    "bid_high",
    "bid_low",
    "bid_close",
    "ask_open",
    "ask_high",
    "ask_low",
    "ask_close",
)
_SIGNAL_KINDS = {
    "eurusd_london_reversal_short",
    "eurusd_session_trend_pullback",
    "usoil_structural_pullback_long",
    "usoil_donchian_breakout_long",
    "ethusd_donchian_breakout_long",
    "ethusd_structural_weekly_long",
    "ethusd_structural_pullback_long",
}


@dataclass(frozen=True)
class RiskSpec:
    risk_per_trade: float
    max_leverage: float


@dataclass(frozen=True)
class ExecutionSpec:
    entry_delay_bars: int
    max_contiguous_minutes: int
    extra_slippage_bps_per_side: float
    conservative_cost_multiplier: float


@dataclass(frozen=True)
class BarrierSpec:
    take_profit_atr: float
    stop_loss_atr: float
    max_holding_bars: int
    periods_per_year: int


@dataclass(frozen=True)
class ResearchSpec:
    development_end: pd.Timestamp
    validation_start: pd.Timestamp
    development_folds: int
    validation_folds: int
    timezone: str
    expected_timeframe_minutes: int
    random_seed: int


@dataclass(frozen=True)
class FreshStrategyConfig:
    strategy_id: str
    asset: str
    data_path: Path
    expected_file_sha256: str
    signal_kind: str
    signal_params: dict[str, Any]
    risk: RiskSpec
    execution: ExecutionSpec
    barrier: BarrierSpec
    research: ResearchSpec
    hypothesis: str
    notes: str


@dataclass
class QuoteBacktestResult:
    returns: pd.Series
    mark_to_market_equity: pd.Series
    mark_to_market_returns: pd.Series
    trades: pd.DataFrame
    summary: dict[str, float]
    ftmo: dict[str, float]


@dataclass(frozen=True)
class OuterFold:
    fold: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int


def _as_timestamp(value: Any, *, field: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC").tz_localize(None)
    if pd.isna(timestamp):
        raise ValueError(f"{field} must be a valid timestamp.")
    return timestamp


def _require_mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a mapping.")
    return value


def _require_positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a positive integer.")
    result = int(value)
    if result <= 0 or result != float(value):
        raise ValueError(f"{field} must be a positive integer.")
    return result


def _require_nonnegative_float(value: Any, *, field: str) -> float:
    result = float(value)
    if not np.isfinite(result) or result < 0.0:
        raise ValueError(f"{field} must be a finite value >= 0.")
    return result


def _require_positive_float(value: Any, *, field: str) -> float:
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"{field} must be a finite value > 0.")
    return result


def load_fresh_strategy_config(path: str | Path) -> FreshStrategyConfig:
    """Load and validate the isolated fresh-alpha YAML contract.

    This deliberately does *not* extend the framework's public experiment
    schema.  The core runner cannot combine its strict OOS subset with the
    manual barrier engine, whereas this rules-only harness enforces outer
    chronological folds itself.
    """
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    root = _require_mapping(raw, field="root")
    if int(root.get("version", 0)) != 1:
        raise ValueError("version must equal 1.")

    strategy = _require_mapping(root.get("strategy"), field="strategy")
    data = _require_mapping(root.get("data"), field="data")
    signal = _require_mapping(root.get("signal"), field="signal")
    risk = _require_mapping(root.get("risk"), field="risk")
    execution = _require_mapping(root.get("execution"), field="execution")
    barrier = _require_mapping(root.get("barrier"), field="barrier")
    research = _require_mapping(root.get("research"), field="research")

    strategy_id = str(strategy.get("id", "")).strip()
    asset = str(data.get("asset", "")).strip().upper()
    signal_kind = str(signal.get("kind", "")).strip()
    if not strategy_id:
        raise ValueError("strategy.id must be non-empty.")
    if asset not in {"EURUSD", "USOIL", "ETHUSD"}:
        raise ValueError("data.asset must be EURUSD, USOIL, or ETHUSD.")
    if signal_kind not in _SIGNAL_KINDS:
        raise ValueError(f"Unsupported fresh signal kind: {signal_kind!r}.")

    configured_path = Path(str(data.get("csv_path", "")))
    if not configured_path.parts:
        raise ValueError("data.csv_path must be non-empty.")
    repo_root = Path(__file__).resolve().parents[3]
    data_path = configured_path if configured_path.is_absolute() else repo_root / configured_path
    expected_hash = str(data.get("expected_file_sha256", "")).strip().lower()
    if len(expected_hash) != 64 or any(char not in "0123456789abcdef" for char in expected_hash):
        raise ValueError("data.expected_file_sha256 must be a 64-character lowercase SHA-256 value.")

    development_end = _as_timestamp(research.get("development_end"), field="research.development_end")
    validation_start = _as_timestamp(research.get("validation_start"), field="research.validation_start")
    if validation_start < development_end:
        raise ValueError("research.validation_start must not precede research.development_end.")
    expected_minutes = _require_positive_int(
        research.get("expected_timeframe_minutes"),
        field="research.expected_timeframe_minutes",
    )
    if expected_minutes != 30:
        raise ValueError("This fresh-alpha harness accepts the audited 30-minute inputs only.")
    timezone = str(research.get("timezone", "")).strip()
    if timezone != "UTC":
        raise ValueError("research.timezone must be UTC for the audited source contract.")

    signal_params = dict(_require_mapping(signal.get("params", {}), field="signal.params"))
    result = FreshStrategyConfig(
        strategy_id=strategy_id,
        asset=asset,
        data_path=data_path.resolve(),
        expected_file_sha256=expected_hash,
        signal_kind=signal_kind,
        signal_params=signal_params,
        risk=RiskSpec(
            risk_per_trade=_require_positive_float(risk.get("risk_per_trade"), field="risk.risk_per_trade"),
            max_leverage=_require_positive_float(risk.get("max_leverage"), field="risk.max_leverage"),
        ),
        execution=ExecutionSpec(
            entry_delay_bars=_require_positive_int(execution.get("entry_delay_bars"), field="execution.entry_delay_bars"),
            max_contiguous_minutes=_require_positive_int(
                execution.get("max_contiguous_minutes"),
                field="execution.max_contiguous_minutes",
            ),
            extra_slippage_bps_per_side=_require_nonnegative_float(
                execution.get("extra_slippage_bps_per_side"),
                field="execution.extra_slippage_bps_per_side",
            ),
            conservative_cost_multiplier=_require_positive_float(
                execution.get("conservative_cost_multiplier"),
                field="execution.conservative_cost_multiplier",
            ),
        ),
        barrier=BarrierSpec(
            take_profit_atr=_require_positive_float(barrier.get("take_profit_atr"), field="barrier.take_profit_atr"),
            stop_loss_atr=_require_positive_float(barrier.get("stop_loss_atr"), field="barrier.stop_loss_atr"),
            max_holding_bars=_require_positive_int(barrier.get("max_holding_bars"), field="barrier.max_holding_bars"),
            periods_per_year=_require_positive_int(barrier.get("periods_per_year"), field="barrier.periods_per_year"),
        ),
        research=ResearchSpec(
            development_end=development_end,
            validation_start=validation_start,
            development_folds=_require_positive_int(research.get("development_folds"), field="research.development_folds"),
            validation_folds=_require_positive_int(research.get("validation_folds"), field="research.validation_folds"),
            timezone=timezone,
            expected_timeframe_minutes=expected_minutes,
            random_seed=_require_positive_int(research.get("random_seed"), field="research.random_seed"),
        ),
        hypothesis=str(strategy.get("hypothesis", "")).strip(),
        notes=str(strategy.get("notes", "")).strip(),
    )
    if not result.hypothesis:
        raise ValueError("strategy.hypothesis must be non-empty.")
    return result


def verified_raw_frame(config: FreshStrategyConfig) -> pd.DataFrame:
    """Load the raw file through the public loader and pin its fingerprint."""
    if not config.data_path.is_file():
        raise FileNotFoundError(f"Configured raw data does not exist: {config.data_path}")
    digest = sha256(config.data_path.read_bytes()).hexdigest()
    if digest != config.expected_file_sha256:
        raise ValueError(
            f"Raw-data fingerprint mismatch for {config.data_path}: expected "
            f"{config.expected_file_sha256}, got {digest}."
        )
    frame = load_ohlcv_csv(config.data_path, symbol=config.asset)
    validate_ohlcv(frame, allow_missing_volume=False)
    missing = [name for name in _REQUIRED_QUOTE_COLUMNS if name not in frame.columns]
    if missing:
        raise ValueError(f"Quote-aware research requires columns: {missing}")
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError("Raw timestamps must be unique and monotonic.")
    return frame.copy()


def _wilder_rsi(close: pd.Series, window: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    average_gain = gain.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    average_loss = loss.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    rs = average_gain / average_loss.replace(0.0, np.nan)
    return 100.0 - 100.0 / (1.0 + rs)


def add_causal_research_features(frame: pd.DataFrame, *, timeframe_minutes: int = 30) -> pd.DataFrame:
    """Add only point-in-time trailing features used by the fresh rules.

    A previous close is intentionally ignored after a gap.  That avoids
    treating a closure as an artificial intrabar move in ATR while preserving
    the historical state of trailing EMA/RSI calculations.
    """
    out = frame.copy().sort_index()
    gap = out.index.to_series().diff().gt(pd.Timedelta(minutes=timeframe_minutes))
    prior_close = out["close"].shift(1).where(~gap)
    true_range = pd.concat(
        [
            out["high"] - out["low"],
            (out["high"] - prior_close).abs(),
            (out["low"] - prior_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out["research_atr_pct_24"] = (
        true_range.ewm(alpha=1.0 / 24.0, adjust=False, min_periods=24).mean() / out["close"]
    )
    for span in (24, 48, 96, 192, 384):
        out[f"research_ema_{span}"] = out["close"].ewm(
            span=span,
            adjust=False,
            min_periods=span,
        ).mean()
    out["research_rsi_7"] = _wilder_rsi(out["close"], 7)
    out["research_prior_high_96"] = out["high"].shift(1).rolling(96, min_periods=96).max()
    out["research_prior_low_96"] = out["low"].shift(1).rolling(96, min_periods=96).min()
    out["research_gap_before"] = gap.astype(bool)
    return out


def _session_trend_pullback_signal(frame: pd.DataFrame, *, session_start_hour: int, session_end_hour: int) -> pd.Series:
    ema24 = frame["research_ema_24"]
    ema48 = frame["research_ema_48"]
    ema96 = frame["research_ema_96"]
    ema384 = frame["research_ema_384"]
    rsi7 = frame["research_rsi_7"]
    hours = frame.index.hour
    weekdays = frame.index.dayofweek < 5
    in_session = (hours >= session_start_hour) & (hours < session_end_hour) & weekdays
    long_signal = (
        in_session
        & (ema96 > ema384)
        & (frame["close"] > ema48)
        & (frame["close"].shift(1) <= ema24.shift(1))
        & (frame["close"] > ema24)
        & rsi7.between(42.0, 72.0)
    )
    short_signal = (
        in_session
        & (ema96 < ema384)
        & (frame["close"] < ema48)
        & (frame["close"].shift(1) >= ema24.shift(1))
        & (frame["close"] < ema24)
        & rsi7.between(28.0, 58.0)
    )
    return long_signal.astype(float) - short_signal.astype(float)


def _structural_pullback_long_signal(frame: pd.DataFrame) -> pd.Series:
    ema24 = frame["research_ema_24"]
    return (
        (frame["research_ema_96"] > frame["research_ema_384"])
        & (frame["close"] > frame["research_ema_48"])
        & (frame["close"].shift(1) <= ema24.shift(1))
        & (frame["close"] > ema24)
        & frame["research_rsi_7"].between(42.0, 72.0)
    ).astype(float)


def _donchian_long_signal(frame: pd.DataFrame) -> pd.Series:
    return (
        (frame["research_ema_96"] > frame["research_ema_384"])
        & (frame["close"] > frame["research_prior_high_96"])
    ).astype(float)


def _weekly_structural_long_signal(frame: pd.DataFrame) -> pd.Series:
    # W-SUN makes Monday the start of the week.  This is a calendar rule, not
    # a fitted timestamp feature, and the next-bar entry remains causal.
    week = pd.Series(frame.index.to_period("W-SUN"), index=frame.index)
    first_bar_of_week = week.ne(week.shift(1))
    return (
        first_bar_of_week
        & (frame["research_ema_96"] > frame["research_ema_384"])
    ).astype(float)


def build_fresh_signal(frame: pd.DataFrame, config: FreshStrategyConfig) -> pd.Series:
    """Build one registered research signal from causal feature columns only."""
    kind = config.signal_kind
    params = config.signal_params
    if kind == "eurusd_london_reversal_short":
        hour = _require_positive_int(params.get("signal_hour_utc", 9), field="signal.params.signal_hour_utc")
        if hour > 23:
            raise ValueError("signal.params.signal_hour_utc must be in [0, 23].")
        signal = pd.Series(
            np.where(
                (frame.index.hour == hour)
                & (frame.index.minute == 0)
                & (frame.index.dayofweek < 5),
                -1.0,
                0.0,
            ),
            index=frame.index,
            dtype=float,
        )
    elif kind == "eurusd_session_trend_pullback":
        signal = _session_trend_pullback_signal(
            frame,
            session_start_hour=_require_positive_int(params.get("session_start_hour", 7), field="signal.params.session_start_hour"),
            session_end_hour=_require_positive_int(params.get("session_end_hour", 17), field="signal.params.session_end_hour"),
        )
    elif kind in {"usoil_structural_pullback_long", "ethusd_structural_pullback_long"}:
        signal = _structural_pullback_long_signal(frame)
    elif kind in {"usoil_donchian_breakout_long", "ethusd_donchian_breakout_long"}:
        signal = _donchian_long_signal(frame)
    elif kind == "ethusd_structural_weekly_long":
        signal = _weekly_structural_long_signal(frame)
    else:  # guarded by YAML validation, retained for type-checker exhaustiveness.
        raise ValueError(f"Unsupported fresh signal kind: {kind!r}.")

    required = ["research_atr_pct_24"]
    valid = frame[required].notna().all(axis=1) & ~frame["research_gap_before"]
    return signal.where(valid, 0.0).replace([np.inf, -np.inf], np.nan).fillna(0.0).astype(float)


def _mid_and_half_spread(frame: pd.DataFrame, idx: int, suffix: str) -> tuple[float, float]:
    bid = float(frame.iloc[idx][f"bid_{suffix}"])
    ask = float(frame.iloc[idx][f"ask_{suffix}"])
    return (bid + ask) / 2.0, (ask - bid) / 2.0


def _effective_quote(
    frame: pd.DataFrame,
    *,
    idx: int,
    suffix: Literal["open", "close"],
    side: int,
    is_entry: bool,
    cost_multiplier: float,
    extra_slippage_bps_per_side: float,
) -> float:
    """Return a side-aware price with raw spread plus a stress multiplier.

    ``cost_multiplier=1`` uses the supplied bid/ask quote.  At two, execution
    is moved a second half-spread away from the midpoint.  Extra slippage is
    then applied on each side of the trade.  This makes the cost stress
    interpretable even though raw quote data already embeds a spread.
    """
    midpoint, half_spread = _mid_and_half_spread(frame, idx, suffix)
    adverse_direction = side if is_entry else -side
    price = midpoint + adverse_direction * float(cost_multiplier) * half_spread
    slippage = float(extra_slippage_bps_per_side) * float(cost_multiplier) / 10_000.0
    price *= 1.0 + adverse_direction * slippage
    if not np.isfinite(price) or price <= 0.0:
        raise ValueError("Non-finite effective execution quote.")
    return float(price)


def _stress_barrier_fill(
    frame: pd.DataFrame,
    *,
    idx: int,
    barrier_price: float,
    side: int,
    cost_multiplier: float,
    extra_slippage_bps_per_side: float,
) -> float:
    """Apply only the incremental stressed half-spread to a barrier fill."""
    midpoint, half_spread = _mid_and_half_spread(frame, idx, "close")
    del midpoint  # The raw barrier itself is already in price space.
    adverse_direction = -side
    extra_spread = max(float(cost_multiplier) - 1.0, 0.0) * half_spread
    price = float(barrier_price) + adverse_direction * extra_spread
    slippage = float(extra_slippage_bps_per_side) * float(cost_multiplier) / 10_000.0
    price *= 1.0 + adverse_direction * slippage
    if not np.isfinite(price) or price <= 0.0:
        raise ValueError("Non-finite stressed barrier fill.")
    return float(price)


def _trade_return(*, side: int, size: float, entry_price: float, exit_price: float) -> float:
    if side > 0:
        return float(size * (exit_price / entry_price - 1.0))
    return float(size * (1.0 - exit_price / entry_price))


def _is_contiguous(index: pd.DatetimeIndex, start: int, end: int, max_gap: pd.Timedelta) -> bool:
    if end <= start:
        return True
    differences = index[start + 1 : end + 1] - index[start:end]
    return bool((differences <= max_gap).all())


def _resolve_quote_exit(
    frame: pd.DataFrame,
    *,
    idx: int,
    side: int,
    stop_price: float,
    target_price: float,
    cost_multiplier: float,
    extra_slippage_bps_per_side: float,
) -> tuple[float | None, str | None]:
    """Resolve a quote-aware stop/target event with conservative double-touch.

    The side-specific bid/ask path is inspected.  If both barriers are touched
    within an OHLC bar, the stop is used.  Open gaps are filled at the opening
    quote, never at an unavailable stop level.
    """
    if side > 0:
        bid_open = float(frame.iloc[idx]["bid_open"])
        bid_high = float(frame.iloc[idx]["bid_high"])
        bid_low = float(frame.iloc[idx]["bid_low"])
        if bid_open <= stop_price:
            return _effective_quote(
                frame,
                idx=idx,
                suffix="open",
                side=side,
                is_entry=False,
                cost_multiplier=cost_multiplier,
                extra_slippage_bps_per_side=extra_slippage_bps_per_side,
            ), "stop_gap"
        if bid_open >= target_price:
            return _stress_barrier_fill(
                frame,
                idx=idx,
                barrier_price=target_price,
                side=side,
                cost_multiplier=cost_multiplier,
                extra_slippage_bps_per_side=extra_slippage_bps_per_side,
            ), "target_gap"
        stop_hit = bid_low <= stop_price
        target_hit = bid_high >= target_price
    else:
        ask_open = float(frame.iloc[idx]["ask_open"])
        ask_high = float(frame.iloc[idx]["ask_high"])
        ask_low = float(frame.iloc[idx]["ask_low"])
        if ask_open >= stop_price:
            return _effective_quote(
                frame,
                idx=idx,
                suffix="open",
                side=side,
                is_entry=False,
                cost_multiplier=cost_multiplier,
                extra_slippage_bps_per_side=extra_slippage_bps_per_side,
            ), "stop_gap"
        if ask_open <= target_price:
            return _stress_barrier_fill(
                frame,
                idx=idx,
                barrier_price=target_price,
                side=side,
                cost_multiplier=cost_multiplier,
                extra_slippage_bps_per_side=extra_slippage_bps_per_side,
            ), "target_gap"
        stop_hit = ask_high >= stop_price
        target_hit = ask_low <= target_price

    if stop_hit:  # Deliberately conservative when target_hit is also true.
        return _stress_barrier_fill(
            frame,
            idx=idx,
            barrier_price=stop_price,
            side=side,
            cost_multiplier=cost_multiplier,
            extra_slippage_bps_per_side=extra_slippage_bps_per_side,
        ), "stop"
    if target_hit:
        return _stress_barrier_fill(
            frame,
            idx=idx,
            barrier_price=target_price,
            side=side,
            cost_multiplier=cost_multiplier,
            extra_slippage_bps_per_side=extra_slippage_bps_per_side,
        ), "target"
    return None, None


def _ftmo_metrics_from_equity(equity: pd.Series) -> dict[str, float]:
    """Compute conservative UTC-day loss estimates from close mark-to-market."""
    if equity.empty:
        return {
            "max_daily_loss_estimate": 0.0,
            "daily_loss_breach_count_5pct": 0.0,
            "max_total_drawdown": 0.0,
            "total_loss_breach_10pct": 0.0,
            "active_trading_days": 0.0,
        }
    values = equity.astype(float).ffill().fillna(1.0)
    drawdown = values / values.cummax() - 1.0
    previous = values.shift(1).fillna(1.0)
    day_key = values.index.normalize()
    base_by_day = previous.groupby(day_key).first()
    daily_min = values.groupby(day_key).min()
    daily_loss = daily_min / base_by_day - 1.0
    return {
        "max_daily_loss_estimate": float(max(0.0, -daily_loss.min())),
        "daily_loss_breach_count_5pct": float((daily_loss <= -0.05).sum()),
        "max_total_drawdown": float(drawdown.min()),
        "total_loss_breach_10pct": float((values <= 0.90).any()),
        "active_trading_days": float((values.groupby(day_key).max() != values.groupby(day_key).min()).sum()),
    }


def quote_aware_barrier_backtest(
    frame: pd.DataFrame,
    signal: pd.Series,
    *,
    risk: RiskSpec,
    execution: ExecutionSpec,
    barrier: BarrierSpec,
    cost_multiplier: float = 1.0,
    entry_delay_bars: int | None = None,
) -> QuoteBacktestResult:
    """Run sequential next-open, quote-aware barrier trades on one OOS slice.

    The simulator does not pyramid, average down, grid, or martingale.  Risk
    sizing is based on the point-in-time ATR stop distance and capped by
    ``max_leverage``.  Every trade is closed before a market-data gap.
    """
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise TypeError("frame must have a DatetimeIndex.")
    if not frame.index.equals(signal.index):
        raise ValueError("signal index must exactly match the frame index.")
    if cost_multiplier <= 0.0:
        raise ValueError("cost_multiplier must be > 0.")
    delay = execution.entry_delay_bars if entry_delay_bars is None else int(entry_delay_bars)
    if delay <= 0:
        raise ValueError("entry_delay_bars must be >= 1 for next-bar execution.")

    data = frame.copy()
    signals = signal.astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    n_rows = len(data)
    max_gap = pd.Timedelta(minutes=execution.max_contiguous_minutes)
    realised = pd.Series(0.0, index=data.index, dtype=float, name="returns")
    mtm_equity = pd.Series(np.nan, index=data.index, dtype=float, name="mark_to_market_equity")
    trades: list[dict[str, Any]] = []
    current_equity = 1.0
    last_filled = -1
    signal_idx = 0

    while signal_idx < n_rows - delay:
        raw_signal = float(np.sign(signals.iat[signal_idx]))
        if raw_signal == 0.0:
            signal_idx += 1
            continue
        entry_idx = signal_idx + delay
        if not _is_contiguous(data.index, signal_idx, entry_idx, max_gap):
            signal_idx += 1
            continue
        atr_pct = float(data["research_atr_pct_24"].iat[signal_idx])
        if not np.isfinite(atr_pct) or atr_pct <= 0.0:
            signal_idx += 1
            continue
        side = 1 if raw_signal > 0.0 else -1
        entry_price = _effective_quote(
            data,
            idx=entry_idx,
            suffix="open",
            side=side,
            is_entry=True,
            cost_multiplier=cost_multiplier,
            extra_slippage_bps_per_side=execution.extra_slippage_bps_per_side,
        )
        stop_distance_pct = max(atr_pct * barrier.stop_loss_atr, 1e-8)
        target_distance_pct = max(atr_pct * barrier.take_profit_atr, 1e-8)
        size = min(risk.max_leverage, risk.risk_per_trade / stop_distance_pct)
        if size <= 0.0:
            signal_idx += 1
            continue
        if side > 0:
            stop_price = entry_price * (1.0 - stop_distance_pct)
            target_price = entry_price * (1.0 + target_distance_pct)
        else:
            stop_price = entry_price * (1.0 + stop_distance_pct)
            target_price = entry_price * (1.0 - target_distance_pct)

        max_exit_idx = min(n_rows - 1, entry_idx + barrier.max_holding_bars - 1)
        exit_idx = max_exit_idx
        exit_price: float | None = None
        exit_reason = "time_stop"
        for candidate_idx in range(entry_idx, max_exit_idx + 1):
            if candidate_idx > entry_idx and data.index[candidate_idx] - data.index[candidate_idx - 1] > max_gap:
                exit_idx = candidate_idx - 1
                exit_price = _effective_quote(
                    data,
                    idx=exit_idx,
                    suffix="close",
                    side=side,
                    is_entry=False,
                    cost_multiplier=cost_multiplier,
                    extra_slippage_bps_per_side=execution.extra_slippage_bps_per_side,
                )
                exit_reason = "gap_exit"
                break
            resolved_price, resolved_reason = _resolve_quote_exit(
                data,
                idx=candidate_idx,
                side=side,
                stop_price=stop_price,
                target_price=target_price,
                cost_multiplier=cost_multiplier,
                extra_slippage_bps_per_side=execution.extra_slippage_bps_per_side,
            )
            if resolved_price is not None:
                exit_idx = candidate_idx
                exit_price = resolved_price
                exit_reason = str(resolved_reason)
                break
        if exit_price is None:
            exit_price = _effective_quote(
                data,
                idx=exit_idx,
                suffix="close",
                side=side,
                is_entry=False,
                cost_multiplier=cost_multiplier,
                extra_slippage_bps_per_side=execution.extra_slippage_bps_per_side,
            )

        trade_return = _trade_return(
            side=side,
            size=size,
            entry_price=entry_price,
            exit_price=exit_price,
        )
        realised.iat[exit_idx] += trade_return
        if entry_idx > last_filled + 1:
            mtm_equity.iloc[last_filled + 1 : entry_idx] = current_equity
        entry_equity = current_equity
        for mark_idx in range(entry_idx, exit_idx + 1):
            mark_price = (
                exit_price
                if mark_idx == exit_idx
                else _effective_quote(
                    data,
                    idx=mark_idx,
                    suffix="close",
                    side=side,
                    is_entry=False,
                    cost_multiplier=cost_multiplier,
                    extra_slippage_bps_per_side=execution.extra_slippage_bps_per_side,
                )
            )
            mtm_equity.iat[mark_idx] = entry_equity * (
                1.0 + _trade_return(
                    side=side,
                    size=size,
                    entry_price=entry_price,
                    exit_price=mark_price,
                )
            )
        current_equity = entry_equity * (1.0 + trade_return)
        last_filled = exit_idx
        trades.append(
            {
                "signal_timestamp": data.index[signal_idx],
                "entry_timestamp": data.index[entry_idx],
                "exit_timestamp": data.index[exit_idx],
                "side": "long" if side > 0 else "short",
                "position_size": float(size),
                "entry_price": float(entry_price),
                "exit_price": float(exit_price),
                "stop_price": float(stop_price),
                "target_price": float(target_price),
                "net_return": float(trade_return),
                "trade_r": float(trade_return / max(size * stop_distance_pct, 1e-12)),
                "bars_held": int(exit_idx - entry_idx + 1),
                "exit_reason": exit_reason,
            }
        )
        signal_idx = exit_idx + 1

    if last_filled + 1 < n_rows:
        mtm_equity.iloc[last_filled + 1 :] = current_equity
    mtm_equity = mtm_equity.ffill().fillna(1.0)
    mtm_returns = mtm_equity.pct_change().fillna(0.0)
    summary = compute_backtest_metrics(
        net_returns=realised,
        periods_per_year=barrier.periods_per_year,
    )
    trade_frame = pd.DataFrame(trades)
    if not trade_frame.empty:
        gross_profit = float(trade_frame.loc[trade_frame["net_return"] > 0.0, "net_return"].sum())
        gross_loss = float(-trade_frame.loc[trade_frame["net_return"] < 0.0, "net_return"].sum())
        summary["trade_win_rate"] = float((trade_frame["net_return"] > 0.0).mean())
        summary["trade_profit_factor"] = gross_profit / gross_loss if gross_loss > 0.0 else 0.0
        summary["trade_count"] = float(len(trade_frame))
    else:
        summary.update({"trade_win_rate": 0.0, "trade_profit_factor": 0.0, "trade_count": 0.0})
    return QuoteBacktestResult(
        returns=realised,
        mark_to_market_equity=mtm_equity,
        mark_to_market_returns=mtm_returns,
        trades=trade_frame,
        summary=summary,
        ftmo=_ftmo_metrics_from_equity(mtm_equity),
    )


def outer_walk_forward_folds(
    frame: pd.DataFrame,
    *,
    start: pd.Timestamp,
    fold_count: int,
) -> list[OuterFold]:
    """Make contiguous outer chronological folds with strictly prior training.

    Rules are not fitted, so train rows are used only to establish the
    information boundary.  Features remain causal and are precomputed from
    the original chronology; a test slice never contains a trade started
    before the slice.
    """
    if fold_count < 2:
        raise ValueError("fold_count must be >= 2.")
    test_start = int(frame.index.searchsorted(start, side="left"))
    if test_start <= 0 or test_start >= len(frame):
        raise ValueError("Walk-forward start must leave both development and test rows.")
    available = len(frame) - test_start
    base_size, remainder = divmod(available, fold_count)
    if base_size < 2:
        raise ValueError("Not enough validation rows for the requested number of folds.")
    folds: list[OuterFold] = []
    cursor = test_start
    for fold in range(fold_count):
        size = base_size + (1 if fold < remainder else 0)
        end = cursor + size
        folds.append(
            OuterFold(
                fold=fold,
                train_start=0,
                train_end=cursor,
                test_start=cursor,
                test_end=end,
            )
        )
        cursor = end
    if cursor != len(frame):  # Defensive: divmod distribution should consume every row.
        raise AssertionError("Outer fold construction did not consume all rows.")
    return folds


def _combine_fold_results(
    fold_results: Iterable[tuple[OuterFold, QuoteBacktestResult]],
    *,
    periods_per_year: int,
) -> dict[str, Any]:
    rows = list(fold_results)
    if not rows:
        raise ValueError("At least one fold result is required.")
    returns = pd.concat([result.returns for _, result in rows]).sort_index()
    mark_to_market_returns = pd.concat([result.mark_to_market_returns for _, result in rows]).sort_index()
    equity = (1.0 + mark_to_market_returns).cumprod()
    summary = compute_backtest_metrics(net_returns=returns, periods_per_year=periods_per_year)
    ftmo = _ftmo_metrics_from_equity(equity)
    # Realised-only PnL can understate an open-trade drawdown.  Publish the
    # close mark-to-market number as the strategy drawdown throughout this
    # research harness.
    summary["max_drawdown"] = float(ftmo["max_total_drawdown"])
    all_trades = pd.concat(
        [result.trades for _, result in rows if not result.trades.empty],
        axis=0,
        ignore_index=True,
    ) if any(not result.trades.empty for _, result in rows) else pd.DataFrame()
    if not all_trades.empty:
        gross_profit = float(all_trades.loc[all_trades["net_return"] > 0.0, "net_return"].sum())
        gross_loss = float(-all_trades.loc[all_trades["net_return"] < 0.0, "net_return"].sum())
        summary.update(
            {
                "trade_count": float(len(all_trades)),
                "trade_win_rate": float((all_trades["net_return"] > 0.0).mean()),
                "trade_profit_factor": gross_profit / gross_loss if gross_loss > 0.0 else 0.0,
            }
        )
    else:
        summary.update({"trade_count": 0.0, "trade_win_rate": 0.0, "trade_profit_factor": 0.0})

    fold_metrics: list[dict[str, Any]] = []
    for fold, result in rows:
        fold_metrics.append(
            {
                "fold": fold.fold + 1,
                "train_start": str(returns.index.min()) if fold.train_end == 0 else None,
                "test_start": str(result.returns.index.min()),
                "test_end": str(result.returns.index.max()),
                "trade_count": int(len(result.trades)),
                "annualized_return": float(result.summary["annualized_return"]),
                "sharpe": float(result.summary["sharpe"]),
                "sortino": float(result.summary["sortino"]),
                "calmar": float(result.summary["calmar"]),
                "max_drawdown": float(result.ftmo["max_total_drawdown"]),
                "profit_factor": float(result.summary["trade_profit_factor"]),
                "win_rate": float(result.summary["trade_win_rate"]),
                "max_daily_loss_estimate": float(result.ftmo["max_daily_loss_estimate"]),
            }
        )
    profitable_folds = sum(metric["annualized_return"] > 0.0 for metric in fold_metrics)
    active_days = float((equity.groupby(equity.index.normalize()).max() != equity.groupby(equity.index.normalize()).min()).sum())
    years = max((equity.index.max() - equity.index.min()).total_seconds() / (365.25 * 24.0 * 3600.0), 1e-9)
    summary["profitable_folds"] = float(profitable_folds)
    summary["fold_count"] = float(len(fold_metrics))
    summary["active_trading_days"] = active_days
    summary["trades_per_year"] = float(summary["trade_count"] / years)
    return {
        "summary": {key: float(value) for key, value in summary.items()},
        "ftmo": {key: float(value) for key, value in ftmo.items()},
        "folds": fold_metrics,
        "trades": all_trades,
        "returns": returns,
        "mark_to_market_returns": mark_to_market_returns,
        "equity": equity,
    }


def evaluate_walk_forward(
    frame: pd.DataFrame,
    signal: pd.Series,
    config: FreshStrategyConfig,
    *,
    start: pd.Timestamp,
    fold_count: int,
    cost_multiplier: float = 1.0,
    entry_delay_bars: int | None = None,
) -> dict[str, Any]:
    """Evaluate only outer-fold test slices; no prior-fold trade leaks forward."""
    folds = outer_walk_forward_folds(frame, start=start, fold_count=fold_count)
    results: list[tuple[OuterFold, QuoteBacktestResult]] = []
    for fold in folds:
        test_frame = frame.iloc[fold.test_start : fold.test_end]
        test_signal = signal.iloc[fold.test_start : fold.test_end]
        result = quote_aware_barrier_backtest(
            test_frame,
            test_signal,
            risk=config.risk,
            execution=config.execution,
            barrier=config.barrier,
            cost_multiplier=cost_multiplier,
            entry_delay_bars=entry_delay_bars,
        )
        results.append((fold, result))
    return _combine_fold_results(results, periods_per_year=config.barrier.periods_per_year)


def _passive_quote_returns(
    frame: pd.DataFrame,
    *,
    side: int,
    periods_per_year: int,
    cost_multiplier: float,
    extra_slippage_bps_per_side: float,
) -> pd.Series:
    """One-times leverage passive exposure used only as a baseline."""
    if len(frame) < 2:
        return pd.Series(0.0, index=frame.index, dtype=float)
    entry = _effective_quote(
        frame,
        idx=1,
        suffix="open",
        side=side,
        is_entry=True,
        cost_multiplier=cost_multiplier,
        extra_slippage_bps_per_side=extra_slippage_bps_per_side,
    )
    exits = pd.Series(
        [
            _effective_quote(
                frame,
                idx=index,
                suffix="close",
                side=side,
                is_entry=False,
                cost_multiplier=cost_multiplier,
                extra_slippage_bps_per_side=extra_slippage_bps_per_side,
            )
            for index in range(len(frame))
        ],
        index=frame.index,
        dtype=float,
    )
    position_equity = 1.0 + (exits / entry - 1.0 if side > 0 else 1.0 - exits / entry)
    position_equity.iloc[0] = 1.0
    return position_equity.pct_change().fillna(0.0)


def _generic_trend_signal(frame: pd.DataFrame, *, asset: str) -> pd.Series:
    long = frame["research_ema_96"] > frame["research_ema_384"]
    if asset == "EURUSD":
        short = frame["research_ema_96"] < frame["research_ema_384"]
        return long.astype(float) - short.astype(float)
    return long.astype(float)


def _random_signal(
    index: pd.DatetimeIndex,
    *,
    rate: float,
    long_only: bool,
    seed: int,
) -> pd.Series:
    rng = np.random.default_rng(seed)
    active = rng.random(len(index)) < float(np.clip(rate, 0.0, 1.0))
    if long_only:
        signs = np.ones(len(index), dtype=float)
    else:
        signs = rng.choice(np.array([-1.0, 1.0]), size=len(index))
    return pd.Series(np.where(active, signs, 0.0), index=index, dtype=float)


def _summarize_random_baseline(
    frame: pd.DataFrame,
    config: FreshStrategyConfig,
    *,
    start: pd.Timestamp,
    fold_count: int,
    observed_trade_rate: float,
    repeats: int = 32,
) -> dict[str, float]:
    long_only = config.signal_kind not in {
        "eurusd_london_reversal_short",
        "eurusd_session_trend_pullback",
    }
    summaries: list[dict[str, float]] = []
    for repeat in range(repeats):
        random_signal = _random_signal(
            frame.index,
            rate=observed_trade_rate,
            long_only=long_only,
            seed=config.research.random_seed + repeat,
        )
        result = evaluate_walk_forward(
            frame,
            random_signal,
            config,
            start=start,
            fold_count=fold_count,
        )
        summaries.append(result["summary"])
    summary_frame = pd.DataFrame(summaries)
    return {
        "annualized_return_median": float(summary_frame["annualized_return"].median()),
        "sharpe_median": float(summary_frame["sharpe"].median()),
        "calmar_median": float(summary_frame["calmar"].median()),
        "max_drawdown_median": float(summary_frame["max_drawdown"].median()),
        "trade_count_median": float(summary_frame["trade_count"].median()),
        "annualized_return_p95": float(summary_frame["annualized_return"].quantile(0.95)),
        "sharpe_p95": float(summary_frame["sharpe"].quantile(0.95)),
        "repeats": float(repeats),
    }


def evaluate_baselines(
    frame: pd.DataFrame,
    signal: pd.Series,
    config: FreshStrategyConfig,
    *,
    start: pd.Timestamp,
    fold_count: int,
    selected_result: dict[str, Any],
) -> dict[str, Any]:
    """Run passive, random, generic-trend, no-trade, and cost-stress baselines."""
    folds = outer_walk_forward_folds(frame, start=start, fold_count=fold_count)
    passive_side = 1
    passive_parts: list[pd.Series] = []
    for fold in folds:
        passive_parts.append(
            _passive_quote_returns(
                frame.iloc[fold.test_start : fold.test_end],
                side=passive_side,
                periods_per_year=config.barrier.periods_per_year,
                cost_multiplier=1.0,
                extra_slippage_bps_per_side=config.execution.extra_slippage_bps_per_side,
            )
        )
    passive_returns = pd.concat(passive_parts).sort_index()
    passive_metrics = compute_backtest_metrics(
        net_returns=passive_returns,
        periods_per_year=config.barrier.periods_per_year,
    )
    trend_result = evaluate_walk_forward(
        frame,
        _generic_trend_signal(frame, asset=config.asset),
        config,
        start=start,
        fold_count=fold_count,
    )
    observed_rate = float(selected_result["summary"]["trade_count"] / max(len(selected_result["returns"]), 1))
    random_metrics = _summarize_random_baseline(
        frame,
        config,
        start=start,
        fold_count=fold_count,
        observed_trade_rate=observed_rate,
    )
    stressed = evaluate_walk_forward(
        frame,
        signal,
        config,
        start=start,
        fold_count=fold_count,
        cost_multiplier=config.execution.conservative_cost_multiplier,
    )
    delayed = evaluate_walk_forward(
        frame,
        signal,
        config,
        start=start,
        fold_count=fold_count,
        entry_delay_bars=config.execution.entry_delay_bars + 1,
    )
    return {
        "buy_and_hold_long": {key: float(value) for key, value in passive_metrics.items()},
        "generic_trend": {key: float(value) for key, value in trend_result["summary"].items()},
        "no_trade": {
            "annualized_return": 0.0,
            "sharpe": 0.0,
            "sortino": 0.0,
            "calmar": 0.0,
            "max_drawdown": 0.0,
        },
        "random_sign_same_trade_rate": random_metrics,
        "double_quoted_cost": {key: float(value) for key, value in stressed["summary"].items()},
        "two_bar_entry_delay": {key: float(value) for key, value in delayed["summary"].items()},
    }


def _public_result(result: dict[str, Any]) -> dict[str, Any]:
    """Convert result objects to stable JSON-ready values without full trade paths."""
    return {
        "summary": result["summary"],
        "ftmo": result["ftmo"],
        "folds": result["folds"],
        "equity_start": str(result["equity"].index.min()),
        "equity_end": str(result["equity"].index.max()),
        "equity_final": float(result["equity"].iloc[-1]),
    }


def run_fresh_strategy(
    config: FreshStrategyConfig,
    *,
    phase: Literal["development", "validation", "all"] = "all",
    include_baselines: bool = True,
) -> dict[str, Any]:
    """Run a frozen development screen and/or sealed final OOS validation."""
    raw = verified_raw_frame(config)
    frame = add_causal_research_features(raw, timeframe_minutes=config.research.expected_timeframe_minutes)
    signal = build_fresh_signal(frame, config)
    outputs: dict[str, Any] = {
        "strategy_id": config.strategy_id,
        "asset": config.asset,
        "signal_kind": config.signal_kind,
        "model_type": "rules_only",
        "config": {
            "risk": asdict(config.risk),
            "execution": asdict(config.execution),
            "barrier": asdict(config.barrier),
            "research": {
                **asdict(config.research),
                "development_end": str(config.research.development_end),
                "validation_start": str(config.research.validation_start),
            },
        },
    }
    if phase in {"development", "all"}:
        # Slice first: the development screen must not even execute on sealed
        # final-validation rows.
        development_frame = frame.loc[frame.index < config.research.development_end]
        development_signal = signal.reindex(development_frame.index)
        development = evaluate_walk_forward(
            development_frame,
            development_signal,
            config,
            start=development_frame.index.min() + pd.Timedelta(days=90),
            fold_count=config.research.development_folds,
        )
        outputs["development"] = _public_result(development)
    if phase in {"validation", "all"}:
        validation = evaluate_walk_forward(
            frame,
            signal,
            config,
            start=config.research.validation_start,
            fold_count=config.research.validation_folds,
        )
        outputs["validation"] = _public_result(validation)
        if include_baselines:
            outputs["baselines"] = evaluate_baselines(
                frame,
                signal,
                config,
                start=config.research.validation_start,
                fold_count=config.research.validation_folds,
                selected_result=validation,
            )
    return outputs


__all__ = [
    "BarrierSpec",
    "ExecutionSpec",
    "FreshStrategyConfig",
    "OuterFold",
    "QuoteBacktestResult",
    "RiskSpec",
    "add_causal_research_features",
    "build_fresh_signal",
    "evaluate_baselines",
    "evaluate_walk_forward",
    "load_fresh_strategy_config",
    "outer_walk_forward_folds",
    "quote_aware_barrier_backtest",
    "run_fresh_strategy",
    "verified_raw_frame",
]
