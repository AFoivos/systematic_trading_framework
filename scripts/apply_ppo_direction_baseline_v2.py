from __future__ import annotations

import copy
import re
from pathlib import Path

import yaml

ROOT = Path.cwd()


def read_text(relative: str) -> tuple[Path, str]:
    path = ROOT / relative
    if not path.exists():
        raise FileNotFoundError(f"Expected repository file not found: {path}")
    return path, path.read_text(encoding="utf-8")


def replace_once(relative: str, old: str, new: str) -> None:
    path, text = read_text(relative)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{relative}: expected one literal match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def regex_replace_once(relative: str, pattern: str, replacement: str) -> None:
    path, text = read_text(relative)
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f"{relative}: expected one regex match, found {count}")
    path.write_text(updated, encoding="utf-8")


def patch_risk_env() -> None:
    relative = "src/models/rl/risk_env.py"

    replace_once(
        relative,
        '_RAW_OHLC_COLUMNS = frozenset({"open", "high", "low", "close"})\n',
        '_RAW_OHLC_COLUMNS = frozenset({"open", "high", "low", "close"})\n'
        '_ACTION_MODES = frozenset({"risk_templates", "directional"})\n'
        '_OPPOSITE_SIGNAL_MODES = frozenset({"reverse", "close"})\n',
    )

    replace_once(
        relative,
        '''class RiskTradeConfig:
    atr_multipliers: tuple[float, ...] = (1.0, 1.5, 2.0)
    take_profit_r_multiples: tuple[float, ...] = (1.0, 2.0, 3.0)
    initial_equity: float = 100_000.0
''',
        '''class RiskTradeConfig:
    atr_multipliers: tuple[float, ...] = (1.0, 1.5, 2.0)
    take_profit_r_multiples: tuple[float, ...] = (1.0, 2.0, 3.0)
    action_mode: str = "risk_templates"
    opposite_signal_mode: str = "reverse"
    minimum_holding_bars: int = 0
    stop_cooldown_bars: int = 0
    initial_equity: float = 100_000.0
''',
    )

    replace_once(
        relative,
        '''        if not self.take_profit_r_multiples or any(
            not np.isfinite(v) or v <= 0.0 for v in self.take_profit_r_multiples
        ):
            raise ValueError("take_profit_r_multiples must be a non-empty sequence of finite positive values.")
        if not np.isfinite(self.initial_equity) or self.initial_equity <= 0.0:
''',
        '''        if not self.take_profit_r_multiples or any(
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
''',
    )

    replace_once(
        relative,
        '''            take_profit_r_multiples=tuple(
                float(v) for v in cfg.get("take_profit_r_multiples", (1.0, 2.0, 3.0))
            ),
            initial_equity=float(cfg.get("initial_equity", 100_000.0)),
''',
        '''            take_profit_r_multiples=tuple(
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
''',
    )

    regex_replace_once(
        relative,
        r'def decode_trade_action\(.*?(?=def calculate_sl_tp\()',
        '''def decode_trade_action(
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


''',
    )

    replace_once(
        relative,
        '''        action_count = 1 + 2 * len(self.trade_config.atr_multipliers) * len(
            self.trade_config.take_profit_r_multiples
        )
        self.action_space = gym.spaces.Discrete(action_count)
        state_feature_count = 4
        self.observation_space = gym.spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.lookback_window, len(self.feature_columns) + state_feature_count),
''',
        '''        action_count = (
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
''',
    )

    replace_once(
        relative,
        '''        self.cumulative_reward = 0.0
        self.trades: list[dict[str, Any]] = []

    def _timestamp(self, step: int) -> Any:
''',
        '''        self.cumulative_reward = 0.0
        self.trades: list[dict[str, Any]] = []
        self._entry_cooldown_until_step = -1

    def _timestamp(self, step: int) -> Any:
''',
    )

    replace_once(
        relative,
        '''    def _bars_held(self) -> int:
        if self.position is None:
            return 0
        return max(int(self.current_step - self.position.entry_step + 1), 0)

    def _observation(self) -> np.ndarray:
''',
        '''    def _bars_held(self) -> int:
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
''',
    )

    replace_once(
        relative,
        '''        state = np.zeros((self.lookback_window, 4), dtype=np.float32)
        direction = float(self.position.direction) if self.position is not None else 0.0
        unrealized_r = self._unrealized_r(raw_exit_price=self._price(self.close_column))
        bars_held = float(self._bars_held())
        if self.trade_config.max_holding_bars is not None:
            bars_held /= float(self.trade_config.max_holding_bars)
        state[:, 0] = direction
        state[:, 1] = float(unrealized_r)
        state[:, 2] = bars_held
        state[:, 3] = float(self.drawdown)
''',
        '''        state = np.zeros(
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
''',
    )

    replace_once(
        relative,
        '''        self.trades.append(trade)
        self.position = None
        return trade
''',
        '''        self.trades.append(trade)
        if reason == "stop_loss" and self.trade_config.stop_cooldown_bars > 0:
            self._entry_cooldown_until_step = max(
                self._entry_cooldown_until_step,
                int(self.current_step + self.trade_config.stop_cooldown_bars),
            )
        self.position = None
        return trade
''',
    )

    replace_once(
        relative,
        '''        self.cumulative_reward = 0.0
        self.trades = []
        return self._observation(), {"timestamp": self._timestamp(self.current_step)}
''',
        '''        self.cumulative_reward = 0.0
        self.trades = []
        self._entry_cooldown_until_step = -1
        return self._observation(), {"timestamp": self._timestamp(self.current_step)}
''',
    )

    regex_replace_once(
        relative,
        r'    def step\(self, action: int \| np\.integer \| np\.ndarray\).*?(?=\n\n__all__ = \[)',
        '''    def step(self, action: int | np.integer | np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict]:
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
''',
    )


def patch_defaults_and_validation() -> None:
    replace_once(
        "src/utils/config_defaults.py",
        '''    if kind == "ppo_risk_agent":
        env.setdefault("action_space", "discrete")
        env.setdefault("lookback_window", env["window_size"])
''',
        '''    if kind == "ppo_risk_agent":
        env.setdefault("action_space", "discrete")
        env.setdefault("action_mode", "risk_templates")
        env.setdefault("opposite_signal_mode", "reverse")
        env.setdefault("minimum_holding_bars", env.get("min_holding_bars", 0))
        env.setdefault("stop_cooldown_bars", 0)
        env.setdefault("lookback_window", env["window_size"])
''',
    )

    replace_once(
        "src/utils/config_validation.py",
        '''            if model["kind"] in _RL_RISK_PPO_KINDS:
                if (action_space or "discrete") != "discrete":
                    raise ConfigValidationError("ppo_risk_agent requires model.env.action_space='discrete'.")
                _positive_int(
''',
        '''            if model["kind"] in _RL_RISK_PPO_KINDS:
                if (action_space or "discrete") != "discrete":
                    raise ConfigValidationError("ppo_risk_agent requires model.env.action_space='discrete'.")
                action_mode = str(env_cfg.get("action_mode", "risk_templates"))
                if action_mode not in {"risk_templates", "directional"}:
                    raise ConfigValidationError(
                        "model.env.action_mode must be 'risk_templates' or 'directional'."
                    )
                opposite_signal_mode = str(env_cfg.get("opposite_signal_mode", "reverse"))
                if opposite_signal_mode not in {"reverse", "close"}:
                    raise ConfigValidationError(
                        "model.env.opposite_signal_mode must be 'reverse' or 'close'."
                    )
                _non_negative_int(
                    env_cfg.get("minimum_holding_bars", env_cfg.get("min_holding_bars", 0)),
                    field="model.env.minimum_holding_bars",
                )
                _non_negative_int(
                    env_cfg.get("stop_cooldown_bars", 0),
                    field="model.env.stop_cooldown_bars",
                )
                _positive_int(
''',
    )

    replace_once(
        "src/utils/config_validation.py",
        '''                initial_equity = _finite_number(
                    env_cfg.get("initial_equity", 100_000.0),
''',
        '''                if action_mode == "directional":
                    for key, default_values in risk_parameter_defaults.items():
                        values = env_cfg.get(key, default_values)
                        if len(values) != 1:
                            raise ConfigValidationError(
                                f"model.env.{key} must contain exactly one value "
                                "when model.env.action_mode='directional'."
                            )
                initial_equity = _finite_number(
                    env_cfg.get("initial_equity", 100_000.0),
''',
    )


def patch_tests() -> None:
    replace_once(
        "tests/models/test_rl_risk_pipeline.py",
        '''def test_sl_tp_calculation_is_symmetric_for_long_and_short() -> None:
''',
        '''def test_directional_action_mode_has_exactly_three_actions() -> None:
    kwargs = {
        "atr_multipliers": [1.5],
        "take_profit_r_multiples": [2.0],
        "action_mode": "directional",
    }

    assert decode_trade_action(0, **kwargs).is_hold
    assert decode_trade_action(1, **kwargs).direction == 1
    assert decode_trade_action(2, **kwargs).direction == -1
    with pytest.raises(ValueError, match=r"\\[0, 3\\)"):
        decode_trade_action(3, **kwargs)


def test_directional_close_mode_closes_first_without_same_bar_reversal() -> None:
    env = SingleAssetRiskTradingEnv(
        frame=_price_frame(highs=[100.2] * 5, lows=[99.8] * 5),
        feature_columns=["feature_x"],
        atr_column="atr_14",
        trade_config=RiskTradeConfig(
            atr_multipliers=(1.5,),
            take_profit_r_multiples=(2.0,),
            action_mode="directional",
            opposite_signal_mode="close",
        ),
    )
    env.reset()
    env.step(1)
    assert env.position is not None and env.position.direction == 1

    _, _, _, _, close_info = env.step(2)
    assert close_info["closed_trade"]["exit_reason"] == "opposite_signal"
    assert close_info["reversal_opened"] is False
    assert env.position is None

    env.step(2)
    assert env.position is not None and env.position.direction == -1


def test_minimum_holding_bars_blocks_early_discretionary_exit() -> None:
    env = SingleAssetRiskTradingEnv(
        frame=_price_frame(highs=[100.2] * 6, lows=[99.8] * 6),
        feature_columns=["feature_x"],
        atr_column="atr_14",
        trade_config=RiskTradeConfig(
            atr_multipliers=(1.5,),
            take_profit_r_multiples=(2.0,),
            action_mode="directional",
            opposite_signal_mode="close",
            minimum_holding_bars=2,
        ),
    )
    env.reset()
    env.step(1)

    _, _, _, _, rejected = env.step(2)
    assert rejected["action_rejected_reason"] == "minimum_holding_bars"
    assert env.position is not None and env.position.direction == 1

    _, _, _, _, accepted = env.step(2)
    assert accepted["closed_trade"]["exit_reason"] == "opposite_signal"
    assert env.position is None


def test_stop_cooldown_blocks_new_entries_for_configured_bars() -> None:
    frame = _price_frame(
        highs=[100.2] * 7,
        lows=[99.8, 98.5, 99.8, 99.8, 99.8, 99.8, 99.8],
    )
    env = SingleAssetRiskTradingEnv(
        frame=frame,
        feature_columns=["feature_x"],
        atr_column="atr_14",
        trade_config=RiskTradeConfig(
            atr_multipliers=(1.0,),
            take_profit_r_multiples=(2.0,),
            action_mode="directional",
            opposite_signal_mode="close",
            stop_cooldown_bars=2,
        ),
    )
    env.reset()

    _, _, _, _, stopped = env.step(1)
    assert stopped["closed_trade"]["exit_reason"] == "stop_loss"
    assert stopped["cooldown_bars_remaining"] == 2
    assert env.position is None

    _, _, _, _, blocked_1 = env.step(1)
    _, _, _, _, blocked_2 = env.step(1)
    assert blocked_1["action_rejected_reason"] == "stop_cooldown"
    assert blocked_2["action_rejected_reason"] == "stop_cooldown"

    _, _, _, _, allowed = env.step(1)
    assert allowed["action_rejected_reason"] is None
    assert env.position is not None


def test_sl_tp_calculation_is_symmetric_for_long_and_short() -> None:
''',
    )


def build_configs() -> None:
    source_path = ROOT / "config/experiments/rl/btcusd_1m_ppo_risk_sanity.yaml"
    source = yaml.safe_load(source_path.read_text(encoding="utf-8"))

    gross = copy.deepcopy(source)
    gross["data"]["storage"]["dataset_id"] = "btcusd_1m_ppo_direction_baseline_v2"

    model = gross["model"]
    model["split"].update(
        {
            "train_size": 30000,
            "validation_size": 5000,
            "test_size": 5000,
            "train_tail_size": 5000,
            "step_size": 5000,
            "expanding": False,
            "max_folds": 5,
        }
    )
    env = model["env"]
    env.update(
        {
            "action_mode": "directional",
            "opposite_signal_mode": "close",
            "atr_multipliers": [1.5],
            "take_profit_r_multiples": [2.0],
            "minimum_holding_bars": 3,
            "stop_cooldown_bars": 5,
            "transaction_cost_bps": 0.0,
            "slippage_bps": 0.0,
        }
    )
    for ignored_reward_key in (
        "cost_per_turnover",
        "slippage_per_turnover",
        "inventory_penalty",
        "switching_penalty",
    ):
        env["reward"].pop(ignored_reward_key, None)

    params = model["params"]
    params.update(
        {
            "total_timesteps": 300000,
            "checkpoint_interval": 30000,
            "run_name": "btcusd_1m_ppo_direction_baseline_v2_gross",
        }
    )
    extractor = params.get("extractor", {})
    extractor.pop("features_dim", None)
    params["extractor"] = extractor

    gross["backtest"]["periods_per_year"] = 525600
    gross["logging"]["run_name"] = "btcusd_1m_ppo_direction_baseline_v2_gross"

    config_dir = source_path.parent
    gross_path = config_dir / "btcusd_1m_ppo_direction_baseline_v2_gross.yaml"
    net_path = config_dir / "btcusd_1m_ppo_direction_baseline_v2_net.yaml"
    gross_path.write_text(yaml.safe_dump(gross, sort_keys=False), encoding="utf-8")

    net = copy.deepcopy(gross)
    net["model"]["env"]["transaction_cost_bps"] = 1.0
    net["model"]["env"]["slippage_bps"] = 0.5
    net["model"]["params"]["run_name"] = "btcusd_1m_ppo_direction_baseline_v2_net"
    net["logging"]["run_name"] = "btcusd_1m_ppo_direction_baseline_v2_net"
    net_path.write_text(yaml.safe_dump(net, sort_keys=False), encoding="utf-8")


def main() -> None:
    markers = [
        ROOT / "src/models/rl/risk_env.py",
        ROOT / "src/utils/config_validation.py",
        ROOT / "config/experiments/rl/btcusd_1m_ppo_risk_sanity.yaml",
    ]
    if not all(path.exists() for path in markers):
        raise RuntimeError("Run this script from the systematic_trading_framework repository root.")

    patch_risk_env()
    patch_defaults_and_validation()
    patch_tests()
    build_configs()

    print("Applied PPO directional baseline v2 changes.")
    print("Created gross and net cost-ablation YAMLs under config/experiments/rl/.")
    print("Verify with: pytest -q tests/models/test_rl_risk_pipeline.py")
    print("Then run the gross YAML before the net YAML.")


if __name__ == "__main__":
    main()
