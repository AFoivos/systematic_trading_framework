from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import gymnasium as gym
import numpy as np
import pandas as pd


_RAW_OHLC_COLUMNS = frozenset({"open", "high", "low", "close"})
_ACTION_MODES = frozenset({"risk_templates", "directional"})
_OPPOSITE_SIGNAL_MODES = frozenset({"reverse", "close"})


@dataclass(frozen=True)
class TradeAction:
    direction: int
    stop_loss_atr_multiplier: float | None
    take_profit_r_multiple: float | None

    @property
    def is_hold(self) -> bool:
        return self.direction == 0


@dataclass(frozen=True)
class RiskTradeConfig:
    atr_multipliers: tuple[float, ...] = (1.0, 1.5, 2.0)
    take_profit_r_multiples: tuple[float, ...] = (1.0, 2.0, 3.0)
    action_mode: str = "risk_templates"
    opposite_signal_mode: str = "reverse"
    minimum_holding_bars: int = 0
    stop_cooldown_bars: int = 0
    initial_equity: float = 100_000.0
    risk_fraction: float = 0.01
    transaction_cost_bps: float = 0.0
    slippage_bps: float = 0.0
    max_holding_bars: int | None = None
    execution_lag_bars: int = 1
    max_leverage: float = 3.0
    max_notional: float | None = None

    def __post_init__(self) -> None:
        if not self.atr_multipliers or any(not np.isfinite(v) or v <= 0.0 for v in self.atr_multipliers):
            raise ValueError("atr_multipliers must be a non-empty sequence of finite positive values.")
        if not self.take_profit_r_multiples or any(
            not np.isfinite(v) or v <= 0.0 for v in self.take_profit_r_multiples
        ):
            raise ValueError("take_profit_r_multiples must be a non-empty sequence of finite positive values.")
        if self.action_mode not in _ACTION_MODES:
            raise ValueError(f"action_mode must be one of {sorted(_ACTION_MODES)}.")
        if self.opposite_signal_mode not in _OPPOSITE_SIGNAL_MODES:
            raise ValueError(
                f"opposite_signal_mode must be one of {sorted(_OPPOSITE_SIGNAL_MODES)}."
            )
        if self.action_mode == "directional" and (
            len(self.atr_multipliers) != 1 or len(self.take_profit_r_multiples) != 1
        ):
            raise ValueError(
                "directional action_mode requires exactly one ATR multiplier and one take-profit R multiple."
            )
        for field_name, value in (
            ("minimum_holding_bars", self.minimum_holding_bars),
            ("stop_cooldown_bars", self.stop_cooldown_bars),
        ):
            if (
                isinstance(value, (bool, np.bool_))
                or not isinstance(value, (int, np.integer))
                or int(value) < 0
            ):
                raise ValueError(f"{field_name} must be a non-negative integer.")
        if not np.isfinite(self.initial_equity) or self.initial_equity <= 0.0:
            raise ValueError("initial_equity must be finite and > 0.")
        if not np.isfinite(self.risk_fraction) or not 0.0 < self.risk_fraction <= 1.0:
            raise ValueError("risk_fraction must be in (0, 1].")
        for field_name, value in (
            ("transaction_cost_bps", self.transaction_cost_bps),
            ("slippage_bps", self.slippage_bps),
        ):
            if not np.isfinite(value) or value < 0.0:
                raise ValueError(f"{field_name} must be finite and >= 0.")
        if self.max_holding_bars is not None and self.max_holding_bars <= 0:
            raise ValueError("max_holding_bars must be > 0 when provided.")
        if (
            isinstance(self.execution_lag_bars, (bool, np.bool_))
            or not isinstance(self.execution_lag_bars, (int, np.integer))
            or int(self.execution_lag_bars) != 1
        ):
            raise ValueError("execution_lag_bars must be exactly 1.")
        if isinstance(self.max_leverage, (bool, np.bool_)) or (
            not np.isfinite(self.max_leverage) or self.max_leverage <= 0.0
        ):
            raise ValueError("max_leverage must be finite and > 0.")
        if self.max_notional is not None and (
            isinstance(self.max_notional, (bool, np.bool_))
            or not np.isfinite(self.max_notional)
            or self.max_notional <= 0.0
        ):
            raise ValueError("max_notional must be finite and > 0 when provided.")

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None) -> "RiskTradeConfig":
        cfg = dict(values or {})
        return cls(
            atr_multipliers=tuple(float(v) for v in cfg.get("atr_multipliers", (1.0, 1.5, 2.0))),
            take_profit_r_multiples=tuple(
                float(v) for v in cfg.get("take_profit_r_multiples", (1.0, 2.0, 3.0))
            ),
            action_mode=str(cfg.get("action_mode", "risk_templates")),
            opposite_signal_mode=str(cfg.get("opposite_signal_mode", "reverse")),
            minimum_holding_bars=cfg.get(
                "minimum_holding_bars",
                cfg.get("min_holding_bars", 0),
            ),
            stop_cooldown_bars=cfg.get("stop_cooldown_bars", 0),
            initial_equity=float(cfg.get("initial_equity", 100_000.0)),
            risk_fraction=float(cfg.get("risk_fraction", 0.01)),
            transaction_cost_bps=float(cfg.get("transaction_cost_bps", 0.0)),
            slippage_bps=float(cfg.get("slippage_bps", 0.0)),
            max_holding_bars=(
                int(cfg["max_holding_bars"])
                if cfg.get("max_holding_bars") is not None
                else None
            ),
            execution_lag_bars=cfg.get("execution_lag_bars", 1),
            max_leverage=float(cfg.get("max_leverage", 3.0)),
            max_notional=(
                float(cfg["max_notional"])
                if cfg.get("max_notional") is not None
                else None
            ),
        )


@dataclass(frozen=True)
class RiskRewardConfig:
    realized_pnl_r_multiple: float = 1.0
    unrealized_pnl_weight: float = 0.0
    holding_penalty: float = 0.0
    drawdown_penalty: float = 0.0

    def __post_init__(self) -> None:
        for field_name, value in asdict(self).items():
            if not np.isfinite(value) or value < 0.0:
                raise ValueError(f"{field_name} must be finite and >= 0.")

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None) -> "RiskRewardConfig":
        cfg = dict(values or {})
        return cls(
            realized_pnl_r_multiple=float(cfg.get("realized_pnl_r_multiple", 1.0)),
            unrealized_pnl_weight=float(cfg.get("unrealized_pnl_weight", 0.0)),
            holding_penalty=float(cfg.get("holding_penalty", 0.0)),
            drawdown_penalty=float(cfg.get("drawdown_penalty", 0.0)),
        )


@dataclass
class _OpenPosition:
    direction: int
    entry_step: int
    entry_time: Any
    entry_price: float
    stop_price: float
    take_profit_price: float
    quantity: float
    initial_risk: float
    target_risk: float
    initial_notional: float
    initial_leverage: float
    sizing_limit: str
    entry_cost: float
    stop_loss_atr_multiplier: float
    take_profit_r_multiple: float
    previous_unrealized_r: float = 0.0


def decode_trade_action(
    action: int | np.integer | np.ndarray,
    *,
    atr_multipliers: Sequence[float],
    take_profit_r_multiples: Sequence[float],
    action_mode: str = "risk_templates",
) -> TradeAction:
    """Decode the legacy risk-template space or the 3-action directional space."""
    atr_values = tuple(float(v) for v in atr_multipliers)
    tp_values = tuple(float(v) for v in take_profit_r_multiples)
    if not atr_values or not tp_values:
        raise ValueError("atr_multipliers and take_profit_r_multiples must be non-empty.")
    if action_mode not in _ACTION_MODES:
        raise ValueError(f"action_mode must be one of {sorted(_ACTION_MODES)}.")
    if action_mode == "directional" and (len(atr_values) != 1 or len(tp_values) != 1):
        raise ValueError(
            "directional action_mode requires exactly one ATR multiplier and one take-profit R multiple."
        )

    raw = np.asarray(action).reshape(-1)
    if raw.size != 1:
        raise ValueError("A risk-managed single-asset action must contain exactly one integer.")
    scalar = raw[0]
    if isinstance(scalar, (bool, np.bool_)):
        raise ValueError("A risk-managed single-asset action must be an integer, not boolean.")
    try:
        numeric_value = float(scalar)
    except (TypeError, ValueError) as exc:
        raise ValueError("A risk-managed single-asset action must be an integer.") from exc
    if not np.isfinite(numeric_value) or not numeric_value.is_integer():
        raise ValueError("A risk-managed single-asset action must be a finite integer.")
    value = int(numeric_value)

    if action_mode == "directional":
        if value < 0 or value >= 3:
            raise ValueError("Directional action must be in the discrete action space [0, 3).")
        if value == 0:
            return TradeAction(0, None, None)
        direction = 1 if value == 1 else -1
        return TradeAction(direction, atr_values[0], tp_values[0])

    combination_count = len(atr_values) * len(tp_values)
    action_count = 1 + 2 * combination_count
    if value < 0 or value >= action_count:
        raise ValueError(f"Action {value} is outside the discrete action space [0, {action_count}).")
    if value == 0:
        return TradeAction(0, None, None)

    zero_based = value - 1
    direction = 1 if zero_based < combination_count else -1
    combination = zero_based % combination_count
    atr_index, tp_index = divmod(combination, len(tp_values))
    return TradeAction(direction, atr_values[atr_index], tp_values[tp_index])


def calculate_sl_tp(
    *,
    entry_price: float,
    atr: float,
    direction: int,
    stop_loss_atr_multiplier: float,
    take_profit_r_multiple: float,
) -> tuple[float, float]:
    """Calculate price barriers from entry-time ATR and initial risk distance."""
    values = (entry_price, atr, stop_loss_atr_multiplier, take_profit_r_multiple)
    if any(not np.isfinite(value) for value in values):
        raise ValueError("SL/TP inputs must be finite.")
    if entry_price <= 0.0 or atr <= 0.0 or stop_loss_atr_multiplier <= 0.0 or take_profit_r_multiple <= 0.0:
        raise ValueError("SL/TP price, ATR, and multipliers must be > 0.")
    if direction not in {-1, 1}:
        raise ValueError("direction must be +1 for long or -1 for short.")

    risk_distance = float(atr * stop_loss_atr_multiplier)
    stop = float(entry_price - direction * risk_distance)
    take_profit = float(entry_price + direction * risk_distance * take_profit_r_multiple)
    if stop <= 0.0 or take_profit <= 0.0:
        raise ValueError("Configured SL/TP levels must remain positive.")
    return stop, take_profit


def realized_pnl_r_multiple(*, net_pnl: float, initial_amount_at_risk: float) -> float:
    if not np.isfinite(net_pnl):
        raise ValueError("net_pnl must be finite.")
    if not np.isfinite(initial_amount_at_risk) or initial_amount_at_risk <= 0.0:
        raise ValueError("initial_amount_at_risk must be finite and > 0.")
    return float(net_pnl / initial_amount_at_risk)


class SingleAssetRiskTradingEnv(gym.Env):
    """Causal single-asset ATR-risk environment with next-open execution.

    An observation contains features available at bar ``t`` close. The action passed to
    :meth:`step` is executed at bar ``t+1`` open, after which that bar's SL/TP range is
    evaluated. ATR-based barriers use the ATR observed at ``t`` rather than any value
    computed from the execution bar. Reward is emitted after the execution bar and includes
    all realized exits, potential-based unrealized shaping, one holding charge for exposure
    during that bar, and the increase in drawdown. Only ``execution_lag_bars=1`` is supported.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        *,
        frame: pd.DataFrame,
        feature_columns: Sequence[str],
        atr_column: str,
        lookback_window: int = 1,
        trade_config: RiskTradeConfig | None = None,
        reward_config: RiskRewardConfig | None = None,
        open_column: str = "open",
        high_column: str = "high",
        low_column: str = "low",
        close_column: str = "close",
        start_step: int | None = None,
        end_step: int | None = None,
        allow_raw_ohlc_features: bool = False,
    ) -> None:
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            raise ValueError("frame must be a non-empty pandas DataFrame.")
        if not frame.index.is_monotonic_increasing or not frame.index.is_unique:
            raise ValueError("frame index must be unique and monotonically increasing.")
        self.feature_columns = tuple(str(col) for col in feature_columns)
        if not self.feature_columns:
            raise ValueError("feature_columns must be non-empty and explicitly configured.")
        if len(set(self.feature_columns)) != len(self.feature_columns):
            raise ValueError("feature_columns must be unique.")
        raw_features = sorted(set(self.feature_columns) & _RAW_OHLC_COLUMNS)
        if raw_features and not allow_raw_ohlc_features:
            raise ValueError(
                "Raw OHLC columns are not accepted as default RL features; configure relative features instead: "
                f"{raw_features}"
            )
        if lookback_window <= 0:
            raise ValueError("lookback_window must be > 0.")

        self.open_column = str(open_column)
        self.high_column = str(high_column)
        self.low_column = str(low_column)
        self.close_column = str(close_column)
        self.atr_column = str(atr_column)
        required = list(self.feature_columns) + [
            self.open_column,
            self.high_column,
            self.low_column,
            self.close_column,
            self.atr_column,
        ]
        missing = sorted({col for col in required if col not in frame.columns})
        if missing:
            raise KeyError(f"Risk trading environment is missing required columns: {missing}")

        feature_values = frame.loc[:, self.feature_columns].to_numpy(dtype=np.float32, copy=True)
        if not bool(np.isfinite(feature_values).all()):
            bad_rows, bad_cols = np.where(~np.isfinite(feature_values))
            examples = [
                (str(frame.index[int(row)]), self.feature_columns[int(col)])
                for row, col in zip(bad_rows[:5], bad_cols[:5])
            ]
            raise ValueError(f"Configured RL features contain non-finite values; examples={examples}.")
        market_values = frame.loc[:, [self.open_column, self.high_column, self.low_column, self.close_column, self.atr_column]].to_numpy(
            dtype=float,
            copy=True,
        )
        if not bool(np.isfinite(market_values).all()):
            raise ValueError("OHLC/ATR execution columns must contain only finite values.")
        if bool((market_values[:, :4] <= 0.0).any()) or bool((market_values[:, 4] <= 0.0).any()):
            raise ValueError("OHLC prices and ATR must be strictly positive.")

        self.frame = frame
        self._features = feature_values
        self.lookback_window = int(lookback_window)
        self.trade_config = trade_config or RiskTradeConfig()
        self.reward_config = reward_config or RiskRewardConfig()
        minimum_start = self.lookback_window - 1
        self.start_step = int(minimum_start if start_step is None else start_step)
        self.end_step = int(len(frame) - 1 if end_step is None else end_step)
        if self.start_step < minimum_start:
            raise ValueError("start_step must leave enough causal history for lookback_window.")
        if self.end_step <= self.start_step or self.end_step >= len(frame):
            raise ValueError("end_step must be within frame and > start_step to leave an execution bar.")

        action_count = (
            3
            if self.trade_config.action_mode == "directional"
            else 1
            + 2
            * len(self.trade_config.atr_multipliers)
            * len(self.trade_config.take_profit_r_multiples)
        )
        self.action_space = gym.spaces.Discrete(action_count)
        self._include_cooldown_state = self.trade_config.stop_cooldown_bars > 0
        self._state_feature_count = 4 + int(self._include_cooldown_state)
        self.observation_space = gym.spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.lookback_window, len(self.feature_columns) + self._state_feature_count),
            dtype=np.float32,
        )

        self.current_step = self.start_step
        self.position: _OpenPosition | None = None
        self.cash_equity = float(self.trade_config.initial_equity)
        self.equity = float(self.trade_config.initial_equity)
        self.running_max_equity = float(self.trade_config.initial_equity)
        self.drawdown = 0.0
        self.cumulative_reward = 0.0
        self.trades: list[dict[str, Any]] = []
        self._entry_cooldown_until_step = -1

    def _timestamp(self, step: int) -> Any:
        return self.frame.index[int(step)]

    def _price(self, column: str, step: int | None = None) -> float:
        return float(self.frame.iloc[self.current_step if step is None else int(step)][column])

    def _slipped_fill(self, raw_price: float, *, direction: int, is_entry: bool) -> float:
        slippage = float(self.trade_config.slippage_bps) / 10_000.0
        adverse_sign = direction if is_entry else -direction
        return float(raw_price * (1.0 + adverse_sign * slippage))

    def _transaction_cost(self, *, price: float, quantity: float) -> float:
        return float(abs(price * quantity) * float(self.trade_config.transaction_cost_bps) / 10_000.0)

    def _unrealized_gross_pnl(self, *, raw_mark_price: float) -> float:
        if self.position is None:
            return 0.0
        position = self.position
        return float(
            position.direction
            * position.quantity
            * (float(raw_mark_price) - position.entry_price)
        )

    def _unrealized_net_pnl(self, *, raw_exit_price: float) -> float:
        if self.position is None:
            return 0.0
        # Entry costs have occurred; exit slippage/costs remain uncharged until an actual exit.
        return float(
            self._unrealized_gross_pnl(raw_mark_price=raw_exit_price)
            - self.position.entry_cost
        )

    def _unrealized_r(self, *, raw_exit_price: float) -> float:
        if self.position is None:
            return 0.0
        return realized_pnl_r_multiple(
            net_pnl=self._unrealized_net_pnl(raw_exit_price=raw_exit_price),
            initial_amount_at_risk=self.position.initial_risk,
        )

    def _bars_held(self) -> int:
        if self.position is None:
            return 0
        return max(int(self.current_step - self.position.entry_step + 1), 0)

    def _completed_holding_bars(self) -> int:
        if self.position is None:
            return 0
        return max(int(self.current_step - self.position.entry_step), 0)

    def _cooldown_bars_remaining(self) -> int:
        return max(int(self._entry_cooldown_until_step - self.current_step), 0)

    def _observation(self) -> np.ndarray:
        start = self.current_step - self.lookback_window + 1
        market_state = self._features[start : self.current_step + 1]
        state = np.zeros(
            (self.lookback_window, self._state_feature_count),
            dtype=np.float32,
        )
        direction = float(self.position.direction) if self.position is not None else 0.0
        unrealized_r = self._unrealized_r(raw_exit_price=self._price(self.close_column))
        bars_held = float(self._bars_held())
        if self.trade_config.max_holding_bars is not None:
            bars_held /= float(self.trade_config.max_holding_bars)
        state[:, 0] = direction
        state[:, 1] = float(unrealized_r)
        state[:, 2] = bars_held
        state[:, 3] = float(self.drawdown)
        if self._include_cooldown_state:
            state[:, 4] = float(
                self._cooldown_bars_remaining()
                / max(int(self.trade_config.stop_cooldown_bars), 1)
            )
        observation = np.concatenate([market_state, state], axis=1).astype(np.float32, copy=False)
        if not bool(np.isfinite(observation).all()):
            raise RuntimeError("Environment produced a non-finite observation.")
        return observation

    def _open_position(
        self,
        action: TradeAction,
        *,
        decision_step: int,
        execution_step: int,
    ) -> _OpenPosition | None:
        """Open at ``execution_step`` open using only ATR known at ``decision_step`` close."""
        if action.is_hold or action.stop_loss_atr_multiplier is None or action.take_profit_r_multiple is None:
            return None
        if self.cash_equity <= 0.0:
            return None
        raw_entry = self._price(self.open_column, execution_step)
        entry_fill = self._slipped_fill(raw_entry, direction=action.direction, is_entry=True)
        atr = self._price(self.atr_column, decision_step)
        stop_price, take_profit_price = calculate_sl_tp(
            entry_price=entry_fill,
            atr=atr,
            direction=action.direction,
            stop_loss_atr_multiplier=action.stop_loss_atr_multiplier,
            take_profit_r_multiple=action.take_profit_r_multiple,
        )
        target_risk = float(self.cash_equity * self.trade_config.risk_fraction)
        price_risk_per_unit = abs(entry_fill - stop_price)
        risk_sized_quantity = float(target_risk / price_risk_per_unit)
        leverage_notional_cap = float(self.cash_equity * self.trade_config.max_leverage)
        notional_cap = leverage_notional_cap
        notional_cap_source = "max_leverage"
        if self.trade_config.max_notional is not None:
            absolute_cap = float(self.trade_config.max_notional)
            if absolute_cap < notional_cap:
                notional_cap = absolute_cap
                notional_cap_source = "max_notional"
        leverage_quantity_cap = float(notional_cap / entry_fill)
        quantity = float(min(risk_sized_quantity, leverage_quantity_cap))
        if quantity <= 0.0 or not np.isfinite(quantity):
            return None
        sizing_limit = (
            notional_cap_source
            if quantity < risk_sized_quantity
            else "risk_fraction"
        )
        initial_notional = float(quantity * entry_fill)
        initial_risk = float(quantity * price_risk_per_unit)
        initial_leverage = float(initial_notional / self.cash_equity)
        entry_cost = self._transaction_cost(price=entry_fill, quantity=quantity)
        opened = _OpenPosition(
            direction=action.direction,
            entry_step=int(execution_step),
            entry_time=self._timestamp(execution_step),
            entry_price=entry_fill,
            stop_price=stop_price,
            take_profit_price=take_profit_price,
            quantity=quantity,
            initial_risk=initial_risk,
            target_risk=target_risk,
            initial_notional=initial_notional,
            initial_leverage=initial_leverage,
            sizing_limit=sizing_limit,
            entry_cost=entry_cost,
            stop_loss_atr_multiplier=float(action.stop_loss_atr_multiplier),
            take_profit_r_multiple=float(action.take_profit_r_multiple),
        )
        self.cash_equity -= entry_cost
        self.position = opened
        return opened

    def _close_position(self, *, raw_exit_price: float, reason: str) -> dict[str, Any]:
        if self.position is None:
            raise RuntimeError("Cannot close a flat position.")
        position = self.position
        exit_fill = self._slipped_fill(raw_exit_price, direction=position.direction, is_entry=False)
        gross_pnl = float(position.direction * position.quantity * (exit_fill - position.entry_price))
        exit_cost = self._transaction_cost(price=exit_fill, quantity=position.quantity)
        net_pnl = float(gross_pnl - position.entry_cost - exit_cost)
        realized_r = realized_pnl_r_multiple(
            net_pnl=net_pnl,
            initial_amount_at_risk=position.initial_risk,
        )
        # Entry cost was charged when the position opened; realize only price PnL and exit fee.
        self.cash_equity += gross_pnl - exit_cost
        trade = {
            "direction": int(position.direction),
            "entry_step": int(position.entry_step),
            "exit_step": int(self.current_step),
            "entry_time": position.entry_time,
            "entry_timestamp": position.entry_time,
            "exit_time": self._timestamp(self.current_step),
            "exit_timestamp": self._timestamp(self.current_step),
            "side": "long" if position.direction > 0 else "short",
            "entry_price": float(position.entry_price),
            "exit_price": float(exit_fill),
            "stop_price": float(position.stop_price),
            "take_profit_price": float(position.take_profit_price),
            "stop_loss_atr_multiplier": float(position.stop_loss_atr_multiplier),
            "take_profit_r_multiple": float(position.take_profit_r_multiple),
            "quantity": float(position.quantity),
            "initial_risk": float(position.initial_risk),
            "target_risk": float(position.target_risk),
            "initial_notional": float(position.initial_notional),
            "initial_leverage": float(position.initial_leverage),
            "sizing_limit": str(position.sizing_limit),
            "gross_pnl": gross_pnl,
            "entry_cost": float(position.entry_cost),
            "exit_cost": float(exit_cost),
            "transaction_cost": float(position.entry_cost + exit_cost),
            "net_pnl": net_pnl,
            "realized_r": realized_r,
            "trade_r": realized_r,
            "bars_held": int(self.current_step - position.entry_step + 1),
            "exit_reason": str(reason),
        }
        self.trades.append(trade)
        if reason == "stop_loss" and self.trade_config.stop_cooldown_bars > 0:
            self._entry_cooldown_until_step = max(
                self._entry_cooldown_until_step,
                int(self.current_step + self.trade_config.stop_cooldown_bars),
            )
        self.position = None
        return trade

    def _barrier_exit(self) -> tuple[float, str] | None:
        if self.position is None:
            return None
        position = self.position
        bar_open = self._price(self.open_column)
        high = self._price(self.high_column)
        low = self._price(self.low_column)
        if position.direction > 0:
            stop_hit = low <= position.stop_price
            take_profit_hit = high >= position.take_profit_price
        else:
            stop_hit = high >= position.stop_price
            take_profit_hit = low <= position.take_profit_price
        # With bar data the intrabar path is unknown. Stop-first is deliberately pessimistic.
        if stop_hit:
            gap_aware_stop = (
                min(position.stop_price, bar_open)
                if position.direction > 0
                else max(position.stop_price, bar_open)
            )
            return float(gap_aware_stop), "stop_loss"
        if take_profit_hit:
            return float(position.take_profit_price), "take_profit"
        return None

    def _mark_equity(self) -> None:
        unrealized_gross = self._unrealized_gross_pnl(
            raw_mark_price=self._price(self.close_column)
        )
        self.equity = float(self.cash_equity + unrealized_gross)
        self.running_max_equity = max(self.running_max_equity, self.equity)
        self.drawdown = (
            float(max(0.0, 1.0 - self.equity / self.running_max_equity))
            if self.running_max_equity > 0.0
            else 0.0
        )

    def reset(self, *, seed: int | None = None, options: dict | None = None) -> tuple[np.ndarray, dict]:
        """Reset to an observation at ``start_step`` close with no pending exposure."""
        super().reset(seed=seed)
        del options
        self.current_step = self.start_step
        self.position = None
        self.cash_equity = float(self.trade_config.initial_equity)
        self.equity = float(self.trade_config.initial_equity)
        self.running_max_equity = float(self.trade_config.initial_equity)
        self.drawdown = 0.0
        self.cumulative_reward = 0.0
        self.trades = []
        self._entry_cooldown_until_step = -1
        return self._observation(), {"timestamp": self._timestamp(self.current_step)}

    def step(self, action: int | np.integer | np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict]:
        """Execute a close-t decision at open t+1 and reward the resulting bar."""
        if self.current_step >= self.end_step:
            raise RuntimeError("step() called after the episode terminated; call reset().")
        decoded = decode_trade_action(
            action,
            atr_multipliers=self.trade_config.atr_multipliers,
            take_profit_r_multiples=self.trade_config.take_profit_r_multiples,
            action_mode=self.trade_config.action_mode,
        )
        raw_action = int(np.asarray(action).reshape(-1)[0])
        decision_step = int(self.current_step)
        execution_step = int(decision_step + self.trade_config.execution_lag_bars)
        if execution_step > self.end_step:
            raise RuntimeError("Execution step falls outside the configured episode.")
        decision_timestamp = self._timestamp(decision_step)
        previous_drawdown = float(self.drawdown)
        previous_position = self.position
        previous_unrealized_r = (
            float(previous_position.previous_unrealized_r)
            if previous_position is not None
            else 0.0
        )
        self.current_step = execution_step
        terminal_step = execution_step >= self.end_step
        allow_new_entry = not terminal_step
        entry_rejected_reason: str | None = None
        opened_position: _OpenPosition | None = None
        closed_trades: list[dict[str, Any]] = []
        reversal_opened = False

        if self.position is not None and decoded.direction == -self.position.direction:
            if self._completed_holding_bars() < int(self.trade_config.minimum_holding_bars):
                entry_rejected_reason = "minimum_holding_bars"
            else:
                closed_trades.append(
                    self._close_position(
                        raw_exit_price=self._price(self.open_column),
                        reason="opposite_signal",
                    )
                )
                if self.trade_config.opposite_signal_mode == "reverse":
                    if allow_new_entry:
                        opened_position = self._open_position(
                            decoded,
                            decision_step=decision_step,
                            execution_step=execution_step,
                        )
                        reversal_opened = opened_position is not None
                    else:
                        entry_rejected_reason = "final_execution_bar"
        elif self.position is None and not decoded.is_hold:
            if execution_step <= self._entry_cooldown_until_step:
                entry_rejected_reason = "stop_cooldown"
            elif allow_new_entry:
                opened_position = self._open_position(
                    decoded,
                    decision_step=decision_step,
                    execution_step=execution_step,
                )
            else:
                entry_rejected_reason = "final_execution_bar"

        exposed_during_bar = self.position is not None
        barrier_exit = self._barrier_exit()
        if barrier_exit is not None:
            closed_trades.append(
                self._close_position(raw_exit_price=barrier_exit[0], reason=barrier_exit[1])
            )
        elif self.position is not None:
            max_holding = self.trade_config.max_holding_bars
            if max_holding is not None and self._bars_held() >= max_holding:
                closed_trades.append(
                    self._close_position(
                        raw_exit_price=self._price(self.close_column),
                        reason="max_holding_bars",
                    )
                )

        if terminal_step and self.position is not None:
            closed_trades.append(
                self._close_position(
                    raw_exit_price=self._price(self.close_column),
                    reason="end_of_data",
                )
            )

        realized_r = float(sum(float(trade["realized_r"]) for trade in closed_trades))
        potential_after = 0.0
        if self.position is not None:
            potential_after = self._unrealized_r(raw_exit_price=self._price(self.close_column))
            self.position.previous_unrealized_r = potential_after
        unrealized_shaping = float(
            self.reward_config.unrealized_pnl_weight
            * (potential_after - previous_unrealized_r)
        )
        holding_penalty = float(
            self.reward_config.holding_penalty if exposed_during_bar else 0.0
        )
        self._mark_equity()
        drawdown_increase = max(0.0, float(self.drawdown - previous_drawdown))
        drawdown_penalty = float(self.reward_config.drawdown_penalty * drawdown_increase)
        realized_component = float(self.reward_config.realized_pnl_r_multiple * realized_r)
        reward = float(realized_component + unrealized_shaping - holding_penalty - drawdown_penalty)
        self.cumulative_reward += reward

        step_transaction_cost = float(
            (opened_position.entry_cost if opened_position is not None else 0.0)
            + sum(float(trade["exit_cost"]) for trade in closed_trades)
        )
        position_leverage = 0.0
        if self.position is not None and self.equity > 0.0:
            marked_notional = float(self.position.quantity * self._price(self.close_column))
            position_leverage = float(self.position.direction * marked_notional / self.equity)

        info = {
            "timestamp": self._timestamp(self.current_step),
            "decision_timestamp": decision_timestamp,
            "execution_timestamp": self._timestamp(self.current_step),
            "execution_lag_bars": int(self.trade_config.execution_lag_bars),
            "action": raw_action,
            "decoded_action": asdict(decoded),
            "action_mode": self.trade_config.action_mode,
            "opposite_signal_mode": self.trade_config.opposite_signal_mode,
            "position": int(self.position.direction) if self.position is not None else 0,
            "position_leverage": position_leverage,
            "equity": float(self.equity),
            "drawdown": float(self.drawdown),
            "realized_pnl_r_multiple": float(realized_r),
            "realized_reward": realized_component,
            "unrealized_pnl_shaping": unrealized_shaping,
            "holding_penalty": holding_penalty,
            "drawdown_penalty": drawdown_penalty,
            "transaction_cost": step_transaction_cost,
            "reward": reward,
            "entry_rejected_reason": entry_rejected_reason,
            "action_rejected_reason": entry_rejected_reason,
            "minimum_holding_bars": int(self.trade_config.minimum_holding_bars),
            "stop_cooldown_bars": int(self.trade_config.stop_cooldown_bars),
            "cooldown_bars_remaining": self._cooldown_bars_remaining(),
            "reversal_opened": bool(reversal_opened),
            "closed_trade": closed_trades[-1] if closed_trades else None,
            "closed_trades": tuple(closed_trades),
        }
        observation = self._observation()
        return observation, reward, bool(terminal_step), False, info


__all__ = [
    "RiskRewardConfig",
    "RiskTradeConfig",
    "SingleAssetRiskTradingEnv",
    "TradeAction",
    "calculate_sl_tp",
    "decode_trade_action",
    "realized_pnl_r_multiple",
]
