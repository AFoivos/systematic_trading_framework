from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Sequence


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


@dataclass(frozen=True)
class RiskConfig:
    risk_per_trade: float = 0.0025
    max_daily_loss_pct: float | None = 0.02
    max_total_drawdown_pct: float | None = 0.05
    max_positions: int = 3
    max_positions_per_symbol: int = 1
    max_symbol_exposure: float | None = None
    max_spread_points: float | None = 50.0
    max_spread_points_by_symbol: dict[str, float] = field(default_factory=dict)
    allow_short: bool = False
    demo_only: bool = True
    trading_hours_utc: Any | None = None
    disable_weekend_trading: bool = True
    kill_switch_path: Path | None = Path("STOP_TRADING")
    state_path: Path | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "RiskConfig":
        cfg = dict(raw or {})
        return cls(
            risk_per_trade=float(cfg.get("risk_per_trade", 0.0025)),
            max_daily_loss_pct=_optional_float(cfg.get("max_daily_loss_pct", 0.02)),
            max_total_drawdown_pct=_optional_float(cfg.get("max_total_drawdown_pct", 0.05)),
            max_positions=int(cfg.get("max_positions", 3)),
            max_positions_per_symbol=int(cfg.get("max_positions_per_symbol", 1)),
            max_symbol_exposure=_optional_float(cfg.get("max_symbol_exposure")),
            max_spread_points=_optional_float(cfg.get("max_spread_points", 50.0)),
            max_spread_points_by_symbol=_spread_limits_by_symbol(
                cfg.get("max_spread_points_by_symbol")
            ),
            allow_short=bool(cfg.get("allow_short", False)),
            demo_only=bool(cfg.get("demo_only", True)),
            trading_hours_utc=cfg.get("trading_hours_utc"),
            disable_weekend_trading=bool(cfg.get("disable_weekend_trading", True)),
            kill_switch_path=Path(str(cfg.get("kill_switch_path", "STOP_TRADING")))
            if cfg.get("kill_switch_path", "STOP_TRADING") not in (None, "")
            else None,
            state_path=Path(str(cfg["state_path"]))
            if cfg.get("state_path") not in (None, "")
            else None,
        )


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def allow(cls, **details: Any) -> "RiskDecision":
        return cls(True, None, details)

    @classmethod
    def reject(cls, reason: str, **details: Any) -> "RiskDecision":
        return cls(False, reason, details)


@dataclass(frozen=True)
class PositionSizingResult:
    can_trade: bool
    volume: float | None
    reason: str | None = None
    risk_amount: float | None = None
    risk_per_lot: float | None = None
    raw_volume: float | None = None


def calculate_position_size(
    *,
    equity: float,
    risk_per_trade: float,
    stop_distance: float,
    symbol_info: Any,
) -> PositionSizingResult:
    equity = float(equity)
    risk_per_trade = float(risk_per_trade)
    stop_distance = float(stop_distance)
    if equity <= 0.0 or risk_per_trade <= 0.0:
        return PositionSizingResult(False, None, "invalid_equity_or_risk")
    if not math.isfinite(stop_distance) or stop_distance <= 0.0:
        return PositionSizingResult(False, None, "invalid_stop_distance")

    tick_value = _first_positive_attr(
        symbol_info,
        ("trade_tick_value_loss", "trade_tick_value", "trade_tick_value_profit"),
    )
    tick_size = _first_positive_attr(symbol_info, ("trade_tick_size", "point"))
    contract_size = _first_positive_attr(symbol_info, ("trade_contract_size", "contract_size"))
    if tick_value is not None and tick_size is not None:
        risk_per_lot = stop_distance / tick_size * tick_value
    elif contract_size is not None:
        risk_per_lot = stop_distance * contract_size
    else:
        return PositionSizingResult(False, None, "missing_tick_value_or_contract_size")

    if not math.isfinite(risk_per_lot) or risk_per_lot <= 0.0:
        return PositionSizingResult(False, None, "invalid_risk_per_lot")

    risk_amount = equity * risk_per_trade
    raw_volume = risk_amount / risk_per_lot
    volume_step = _first_positive_attr(symbol_info, ("volume_step",)) or 0.01
    volume_min = _first_positive_attr(symbol_info, ("volume_min",)) or volume_step
    volume_max = _first_positive_attr(symbol_info, ("volume_max",)) or raw_volume
    rounded = _floor_to_step(raw_volume, volume_step)
    if rounded < volume_min:
        return PositionSizingResult(
            False,
            None,
            "computed_volume_below_minimum",
            risk_amount=risk_amount,
            risk_per_lot=risk_per_lot,
            raw_volume=raw_volume,
        )
    volume = min(rounded, _floor_to_step(volume_max, volume_step))
    if volume <= 0.0:
        return PositionSizingResult(
            False,
            None,
            "invalid_rounded_volume",
            risk_amount=risk_amount,
            risk_per_lot=risk_per_lot,
            raw_volume=raw_volume,
        )
    return PositionSizingResult(
        True,
        round(volume, 8),
        None,
        risk_amount=risk_amount,
        risk_per_lot=risk_per_lot,
        raw_volume=raw_volume,
    )


class MT5RiskManager:
    """Stateful hard risk guards for the MT5 execution runner."""

    def __init__(
        self,
        config: RiskConfig,
        *,
        initial_equity: float | None = None,
        daily_start_equity: float | None = None,
        now_fn: Any | None = None,
    ) -> None:
        self.config = config
        self._now_fn = now_fn
        persisted = self._load_state()
        self.initial_equity = (
            float(initial_equity)
            if initial_equity is not None
            else persisted.get("initial_equity")
        )
        self.daily_start_equity = (
            float(daily_start_equity)
            if daily_start_equity is not None
            else persisted.get("daily_start_equity")
        )
        self.equity_peak = persisted.get("equity_peak", self.initial_equity)
        if initial_equity is not None and self.equity_peak is None:
            self.equity_peak = float(initial_equity)
        self._daily_date = persisted.get("daily_date")

    def update_equity_baselines(self, equity: float, *, now_utc: datetime | None = None) -> None:
        now = _coerce_utc(now_utc or self._now())
        equity = float(equity)
        if not math.isfinite(equity) or equity <= 0.0:
            raise ValueError("account equity must be a positive finite number.")
        changed = False
        if self.initial_equity is None:
            self.initial_equity = equity
            changed = True
        if self.equity_peak is None or equity > self.equity_peak:
            self.equity_peak = equity
            changed = True
        if self._daily_date is None:
            self._daily_date = now.date()
            if self.daily_start_equity is None:
                self.daily_start_equity = equity
            changed = True
        elif self._daily_date != now.date():
            self._daily_date = now.date()
            self.daily_start_equity = equity
            changed = True
        elif self.daily_start_equity is None:
            self.daily_start_equity = equity
            changed = True
        if changed:
            self._persist_state()

    def evaluate_entry(
        self,
        *,
        account_equity: float,
        positions: Sequence[Any],
        mt5_symbol: str,
        framework_symbol: str | None = None,
        side: str,
        spread_points: float | None,
        now_utc: datetime | None = None,
        proposed_volume: float | None = None,
        symbol_info: Any | None = None,
        entry_price: float | None = None,
    ) -> RiskDecision:
        now = _coerce_utc(now_utc or self._now())
        equity = float(account_equity)
        if not math.isfinite(equity) or equity <= 0.0:
            return RiskDecision.reject("invalid_account_equity", account_equity=account_equity)
        self.update_equity_baselines(equity, now_utc=now)

        if self.config.kill_switch_path is not None and self.config.kill_switch_path.exists():
            return RiskDecision.reject("kill_switch_active", path=str(self.config.kill_switch_path))
        if str(side).lower() in {"sell", "short"} and not self.config.allow_short:
            return RiskDecision.reject("short_trading_disabled")
        if self.config.disable_weekend_trading and now.weekday() >= 5:
            return RiskDecision.reject("weekend_trading_disabled", weekday=now.weekday())
        if not _within_trading_hours(now, self.config.trading_hours_utc):
            return RiskDecision.reject("outside_trading_hours_utc", now=now.isoformat())

        if self.config.max_daily_loss_pct is not None and self.daily_start_equity:
            daily_loss_pct = (self.daily_start_equity - equity) / self.daily_start_equity
            if daily_loss_pct >= self.config.max_daily_loss_pct:
                return RiskDecision.reject(
                    "max_daily_loss_exceeded",
                    daily_loss_pct=daily_loss_pct,
                    max_daily_loss_pct=self.config.max_daily_loss_pct,
                )
        if self.config.max_total_drawdown_pct is not None and self.equity_peak:
            total_drawdown_pct = (self.equity_peak - equity) / self.equity_peak
            if total_drawdown_pct >= self.config.max_total_drawdown_pct:
                return RiskDecision.reject(
                    "max_total_drawdown_exceeded",
                    total_drawdown_pct=total_drawdown_pct,
                    max_total_drawdown_pct=self.config.max_total_drawdown_pct,
                )

        if len(positions) >= self.config.max_positions:
            return RiskDecision.reject("max_positions_exceeded", open_positions=len(positions))
        symbol_positions = [position for position in positions if _attr(position, "symbol") == mt5_symbol]
        if len(symbol_positions) >= self.config.max_positions_per_symbol:
            return RiskDecision.reject(
                "max_positions_per_symbol_exceeded",
                symbol=mt5_symbol,
                open_positions=len(symbol_positions),
            )
        spread_limit = self.spread_limit_for_symbol(
            mt5_symbol=mt5_symbol,
            framework_symbol=framework_symbol,
        )
        if spread_limit is not None and spread_points is None:
            return RiskDecision.reject(
                "spread_unavailable",
                max_spread_points=spread_limit,
                framework_symbol=framework_symbol,
                mt5_symbol=mt5_symbol,
            )
        if spread_limit is not None and float(spread_points) > spread_limit:
            return RiskDecision.reject(
                "max_spread_exceeded",
                spread_points=float(spread_points),
                max_spread_points=spread_limit,
                framework_symbol=framework_symbol,
                mt5_symbol=mt5_symbol,
            )
        if self.config.max_symbol_exposure is not None:
            exposure = _symbol_exposure(
                symbol_positions,
                proposed_volume=proposed_volume,
                symbol_info=symbol_info,
                entry_price=entry_price,
            )
            if exposure is None:
                return RiskDecision.reject("cannot_compute_symbol_exposure", symbol=mt5_symbol)
            if exposure > self.config.max_symbol_exposure:
                return RiskDecision.reject(
                    "max_symbol_exposure_exceeded",
                    symbol=mt5_symbol,
                    exposure=exposure,
                    max_symbol_exposure=self.config.max_symbol_exposure,
                )
        return RiskDecision.allow(
            spread_points=spread_points,
            max_spread_points=spread_limit,
            open_positions=len(positions),
        )

    def spread_limit_for_symbol(
        self,
        *,
        mt5_symbol: str,
        framework_symbol: str | None = None,
    ) -> float | None:
        per_symbol = self.config.max_spread_points_by_symbol
        for symbol in (framework_symbol, mt5_symbol):
            if symbol and symbol in per_symbol:
                return per_symbol[symbol]
        return self.config.max_spread_points

    def _now(self) -> datetime:
        if self._now_fn is not None:
            return self._now_fn()
        return datetime.now(timezone.utc)

    def _load_state(self) -> dict[str, Any]:
        path = self.config.state_path
        if path is None or not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot load MT5 risk state from {path}: {exc}") from exc
        if not isinstance(payload, Mapping) or payload.get("version") != 1:
            raise ValueError(f"Invalid MT5 risk state format in {path}.")
        try:
            daily_date = date.fromisoformat(str(payload["daily_date"]))
            initial_equity = _required_positive_state_float(payload, "initial_equity")
            daily_start_equity = _required_positive_state_float(payload, "daily_start_equity")
            equity_peak = _required_positive_state_float(payload, "equity_peak")
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid MT5 risk state values in {path}: {exc}") from exc
        return {
            "initial_equity": initial_equity,
            "daily_start_equity": daily_start_equity,
            "equity_peak": equity_peak,
            "daily_date": daily_date,
        }

    def _persist_state(self) -> None:
        path = self.config.state_path
        if path is None:
            return
        if (
            self.initial_equity is None
            or self.daily_start_equity is None
            or self.equity_peak is None
            or self._daily_date is None
        ):
            raise ValueError("Cannot persist incomplete MT5 risk state.")
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "daily_date": self._daily_date.isoformat(),
            "initial_equity": self.initial_equity,
            "daily_start_equity": self.daily_start_equity,
            "equity_peak": self.equity_peak,
        }
        temp_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_name = handle.name
                json.dump(payload, handle, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            if temp_name is not None:
                try:
                    Path(temp_name).unlink()
                except FileNotFoundError:
                    pass


def _first_positive_attr(obj: Any, names: Sequence[str]) -> float | None:
    for name in names:
        value = _optional_float(_attr(obj, name))
        if value is not None and value > 0.0:
            return value
    return None


def _required_positive_state_float(payload: Mapping[str, Any], key: str) -> float:
    value = _optional_float(payload[key])
    if value is None or value <= 0.0:
        raise ValueError(f"{key} must be a positive finite number.")
    return value


def _spread_limits_by_symbol(value: Any) -> dict[str, float]:
    if value in (None, ""):
        return {}
    if not isinstance(value, Mapping):
        raise TypeError("max_spread_points_by_symbol must be a mapping.")
    limits: dict[str, float] = {}
    for raw_symbol, raw_limit in value.items():
        symbol = str(raw_symbol).strip()
        limit = _optional_float(raw_limit)
        if not symbol:
            raise ValueError("max_spread_points_by_symbol keys must be non-empty.")
        if limit is None or limit < 0.0:
            raise ValueError(
                f"max_spread_points_by_symbol[{symbol!r}] must be a non-negative finite number."
            )
        limits[symbol] = limit
    return limits


def _floor_to_step(value: float, step: float) -> float:
    if step <= 0.0:
        return float(value)
    return math.floor((float(value) + 1e-12) / step) * step


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _within_trading_hours(now: datetime, trading_hours_utc: Any | None) -> bool:
    if trading_hours_utc in (None, "", []):
        return True
    windows = trading_hours_utc if isinstance(trading_hours_utc, list) else [trading_hours_utc]
    return any(_window_contains(now.time(), window) for window in windows)


def _window_contains(current: time, raw_window: Any) -> bool:
    if isinstance(raw_window, Mapping):
        start_raw = raw_window.get("start")
        end_raw = raw_window.get("end")
    else:
        parts = str(raw_window).split("-", maxsplit=1)
        if len(parts) != 2:
            raise ValueError("trading_hours_utc windows must be 'HH:MM-HH:MM' or mappings.")
        start_raw, end_raw = parts
    start = _parse_hhmm(str(start_raw))
    end = _parse_hhmm(str(end_raw))
    current_minutes = current.hour * 60 + current.minute
    start_minutes = start.hour * 60 + start.minute
    end_minutes = end.hour * 60 + end.minute
    if start_minutes <= end_minutes:
        return start_minutes <= current_minutes <= end_minutes
    return current_minutes >= start_minutes or current_minutes <= end_minutes


def _parse_hhmm(value: str) -> time:
    hour_raw, minute_raw = value.strip().split(":", maxsplit=1)
    return time(hour=int(hour_raw), minute=int(minute_raw), tzinfo=timezone.utc)


def _symbol_exposure(
    positions: Sequence[Any],
    *,
    proposed_volume: float | None,
    symbol_info: Any | None,
    entry_price: float | None,
) -> float | None:
    contract_size = _first_positive_attr(symbol_info, ("trade_contract_size", "contract_size"))
    price = _optional_float(entry_price)
    if contract_size is None or price is None:
        return None
    current = 0.0
    for position in positions:
        volume = _optional_float(_attr(position, "volume")) or 0.0
        open_price = _optional_float(_attr(position, "price_open")) or price
        current += abs(volume) * contract_size * open_price
    current += abs(float(proposed_volume or 0.0)) * contract_size * price
    return current


__all__ = [
    "MT5RiskManager",
    "PositionSizingResult",
    "RiskConfig",
    "RiskDecision",
    "calculate_position_size",
]
