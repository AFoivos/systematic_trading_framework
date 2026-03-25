from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import gymnasium as gym
import numpy as np
import pandas as pd

from src.portfolio import PortfolioConstraints, apply_constraints, signal_to_raw_weights


@dataclass(frozen=True)
class RLRewardConfig:
    cost_per_turnover: float = 0.0
    slippage_per_turnover: float = 0.0
    inventory_penalty: float = 0.0
    drawdown_penalty: float = 0.0
    switching_penalty: float = 0.0


@dataclass(frozen=True)
class RLExecutionConfig:
    min_holding_bars: int = 0
    action_hysteresis: float = 0.0
    dd_guard_enabled: bool = False
    max_drawdown: float = 0.2
    cooloff_bars: int = 20
    rearm_drawdown: float | None = None


def _update_drawdown_guard_state(
    *,
    drawdown: float,
    execution_config: RLExecutionConfig,
    cooloff_remaining: int,
    guard_armed: bool,
) -> tuple[int, bool]:
    if not execution_config.dd_guard_enabled or int(execution_config.cooloff_bars) <= 0:
        return 0, True

    max_drawdown = abs(float(execution_config.max_drawdown))
    rearm_drawdown = execution_config.rearm_drawdown
    if rearm_drawdown is None:
        rearm_drawdown = max_drawdown
    rearm_drawdown = abs(float(rearm_drawdown))

    next_guard_armed = bool(guard_armed)
    if not next_guard_armed and drawdown >= -rearm_drawdown:
        next_guard_armed = True

    if cooloff_remaining > 0:
        return int(cooloff_remaining - 1), next_guard_armed

    if next_guard_armed and drawdown <= -max_drawdown:
        return int(execution_config.cooloff_bars), False

    return 0, next_guard_armed


def _safe_window(
    values: np.ndarray,
    *,
    end_index: int,
    window_size: int,
) -> np.ndarray:
    """
    Return a fixed-length rolling window, left-padding with the first available row.
    """
    if values.ndim < 2:
        raise ValueError("values must have at least 2 dimensions.")
    if window_size <= 0:
        raise ValueError("window_size must be > 0.")

    end = int(max(end_index, 0)) + 1
    start = max(end - int(window_size), 0)
    window = values[start:end]
    if len(window) >= window_size:
        return window[-window_size:].copy()

    pad_count = int(window_size - len(window))
    pad_source = window[0] if len(window) > 0 else np.zeros(values.shape[1:], dtype=np.float32)
    pad = np.repeat(np.expand_dims(pad_source, axis=0), pad_count, axis=0)
    return np.concatenate([pad, window], axis=0).astype(np.float32, copy=False)


def _nan_to_zero(values: np.ndarray) -> np.ndarray:
    return np.nan_to_num(values.astype(np.float32, copy=False), nan=0.0, posinf=0.0, neginf=0.0)


class SingleAssetTradingEnv(gym.Env):
    """
    Single-asset trading environment aligned with the framework's backtest semantics.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        *,
        features: np.ndarray,
        simple_returns: np.ndarray,
        window_size: int,
        continuous_actions: bool,
        max_signal_abs: float,
        discrete_action_values: Sequence[float] | None,
        reward_config: RLRewardConfig,
        execution_config: RLExecutionConfig,
        start_step: int = 0,
        end_step: int | None = None,
    ) -> None:
        if features.ndim != 2:
            raise ValueError("SingleAssetTradingEnv expects features with shape=(time, feature_dim).")
        if len(features) != len(simple_returns):
            raise ValueError("features and simple_returns must have matching length.")
        if len(features) < 2:
            raise ValueError("SingleAssetTradingEnv requires at least 2 rows.")
        if max_signal_abs <= 0:
            raise ValueError("max_signal_abs must be > 0.")

        self.features = _nan_to_zero(features)
        self.simple_returns = np.nan_to_num(
            np.asarray(simple_returns, dtype=np.float32),
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )
        self.window_size = int(window_size)
        self.continuous_actions = bool(continuous_actions)
        self.max_signal_abs = float(max_signal_abs)
        self.discrete_action_values = (
            np.asarray(list(discrete_action_values), dtype=np.float32)
            if discrete_action_values is not None
            else None
        )
        if not self.continuous_actions and (
            self.discrete_action_values is None or len(self.discrete_action_values) == 0
        ):
            raise ValueError("Discrete single-asset RL requires non-empty discrete_action_values.")

        self.reward_config = reward_config
        self.execution_config = execution_config
        self.start_step = int(max(start_step, 0))
        max_reward_step = len(self.features) - 2
        self.end_step = int(max_reward_step if end_step is None else min(end_step, max_reward_step))
        if self.end_step < self.start_step:
            raise ValueError("end_step must be >= start_step and allow at least one reward transition.")

        obs_dim = int(self.features.shape[1]) + 2
        self.observation_space = gym.spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.window_size, obs_dim),
            dtype=np.float32,
        )
        if self.continuous_actions:
            self.action_space = gym.spaces.Box(
                low=-self.max_signal_abs,
                high=self.max_signal_abs,
                shape=(1,),
                dtype=np.float32,
            )
        else:
            self.action_space = gym.spaces.Discrete(int(len(self.discrete_action_values)))

        self.current_step = self.start_step
        self.position = 0.0
        self.equity = 1.0
        self.running_max = 1.0
        self.drawdown = 0.0
        self.bars_since_switch = int(self.execution_config.min_holding_bars)
        self.cooloff_remaining = 0
        self.dd_guard_armed = True

    def _map_action(self, action: np.ndarray | int) -> float:
        if self.continuous_actions:
            value = float(np.asarray(action, dtype=np.float32).reshape(-1)[0])
            return float(np.clip(value, -self.max_signal_abs, self.max_signal_abs))
        idx = int(action)
        if idx < 0 or idx >= int(len(self.discrete_action_values)):
            raise ValueError("Discrete action index is out of bounds.")
        return float(self.discrete_action_values[idx])

    def _build_observation(self, *, step: int, position: float, drawdown: float) -> np.ndarray:
        window = _safe_window(self.features, end_index=step, window_size=self.window_size)
        state_cols = np.zeros((self.window_size, 2), dtype=np.float32)
        state_cols[:, 0] = float(position)
        state_cols[:, 1] = float(drawdown)
        return np.concatenate([window, state_cols], axis=1).astype(np.float32, copy=False)

    def _apply_execution_controls(self, action_value: float) -> float:
        controlled = float(action_value)
        if self.cooloff_remaining > 0:
            return 0.0
        if abs(controlled - float(self.position)) <= float(self.execution_config.action_hysteresis):
            controlled = float(self.position)
        if (
            abs(controlled - float(self.position)) > 1e-12
            and self.bars_since_switch < int(self.execution_config.min_holding_bars)
        ):
            controlled = float(self.position)
        return controlled

    def _transition(self, *, action_value: float) -> tuple[float, dict[str, float]]:
        forced_cooloff = self.cooloff_remaining > 0
        actual_action_value = self._apply_execution_controls(action_value)
        next_return = float(self.simple_returns[self.current_step + 1])
        turnover = abs(float(actual_action_value) - float(self.position))
        costs = float(self.reward_config.cost_per_turnover + self.reward_config.slippage_per_turnover) * turnover
        gross_return = float(actual_action_value) * next_return
        inventory_penalty = float(self.reward_config.inventory_penalty) * abs(float(actual_action_value))
        switching_penalty = float(self.reward_config.switching_penalty) * float(turnover > 1e-12 and not forced_cooloff)

        tentative_equity = float(self.equity * (1.0 + gross_return - costs))
        running_max = max(float(self.running_max), tentative_equity)
        drawdown = float(tentative_equity / running_max - 1.0) if running_max > 0 else 0.0
        drawdown_penalty = float(self.reward_config.drawdown_penalty) * abs(min(drawdown, 0.0))
        reward = gross_return - costs - inventory_penalty - drawdown_penalty - switching_penalty

        return reward, {
            "next_return": next_return,
            "gross_return": gross_return,
            "costs": costs,
            "turnover": turnover,
            "inventory_penalty": inventory_penalty,
            "drawdown_penalty": drawdown_penalty,
            "switching_penalty": switching_penalty,
            "reward": float(reward),
            "position": float(actual_action_value),
            "drawdown": drawdown,
            "equity": tentative_equity,
            "running_max": running_max,
        }

    def reset(self, *, seed: int | None = None, options: dict | None = None) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        self.current_step = self.start_step
        self.position = 0.0
        self.equity = 1.0
        self.running_max = 1.0
        self.drawdown = 0.0
        self.bars_since_switch = int(self.execution_config.min_holding_bars)
        self.cooloff_remaining = 0
        self.dd_guard_armed = True
        return self._build_observation(step=self.current_step, position=self.position, drawdown=self.drawdown), {}

    def step(self, action: np.ndarray | int) -> tuple[np.ndarray, float, bool, bool, dict]:
        prev_position = float(self.position)
        action_value = self._map_action(action)
        reward, info = self._transition(action_value=action_value)

        self.position = float(info["position"])
        self.equity = float(info["equity"])
        self.running_max = float(info["running_max"])
        self.drawdown = float(info["drawdown"])
        if abs(self.position - prev_position) > 1e-12:
            self.bars_since_switch = 0
        else:
            self.bars_since_switch += 1
        self.cooloff_remaining, self.dd_guard_armed = _update_drawdown_guard_state(
            drawdown=self.drawdown,
            execution_config=self.execution_config,
            cooloff_remaining=self.cooloff_remaining,
            guard_armed=self.dd_guard_armed,
        )
        self.current_step += 1

        terminated = bool(self.current_step > self.end_step)
        obs = self._build_observation(
            step=min(self.current_step, len(self.features) - 1),
            position=self.position,
            drawdown=self.drawdown,
        )
        return obs, float(reward), terminated, False, info


class PortfolioTradingEnv(gym.Env):
    """
    Portfolio-level trading environment that maps agent signals through the existing constraint layer.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        *,
        features: np.ndarray,
        simple_returns: np.ndarray,
        asset_names: Sequence[str],
        window_size: int,
        continuous_actions: bool,
        max_signal_abs: float,
        discrete_action_templates: np.ndarray | None,
        reward_config: RLRewardConfig,
        execution_config: RLExecutionConfig,
        constraints: PortfolioConstraints,
        asset_to_group: Mapping[str, str] | None,
        long_short: bool,
        gross_target: float,
        start_step: int = 0,
        end_step: int | None = None,
    ) -> None:
        if features.ndim != 3:
            raise ValueError("PortfolioTradingEnv expects features with shape=(time, assets, feature_dim).")
        if simple_returns.ndim != 2:
            raise ValueError("PortfolioTradingEnv expects returns with shape=(time, assets).")
        if features.shape[0] != simple_returns.shape[0] or features.shape[1] != simple_returns.shape[1]:
            raise ValueError("Portfolio features and returns must align on time and asset dimensions.")
        if features.shape[1] != len(asset_names):
            raise ValueError("asset_names length must match the asset dimension of features.")
        if len(features) < 2:
            raise ValueError("PortfolioTradingEnv requires at least 2 rows.")
        if max_signal_abs <= 0:
            raise ValueError("max_signal_abs must be > 0.")

        self.features = _nan_to_zero(features)
        self.simple_returns = np.nan_to_num(
            np.asarray(simple_returns, dtype=np.float32),
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )
        self.asset_names = tuple(str(asset) for asset in asset_names)
        self.window_size = int(window_size)
        self.continuous_actions = bool(continuous_actions)
        self.max_signal_abs = float(max_signal_abs)
        self.discrete_action_templates = (
            np.asarray(discrete_action_templates, dtype=np.float32)
            if discrete_action_templates is not None
            else None
        )
        if not self.continuous_actions and (
            self.discrete_action_templates is None or len(self.discrete_action_templates) == 0
        ):
            raise ValueError("Discrete portfolio RL requires non-empty action templates.")

        self.reward_config = reward_config
        self.execution_config = execution_config
        self.constraints = constraints
        self.asset_to_group = {str(k): str(v) for k, v in dict(asset_to_group or {}).items()}
        self.long_short = bool(long_short)
        self.gross_target = float(gross_target)
        self.start_step = int(max(start_step, 0))
        max_reward_step = len(self.features) - 2
        self.end_step = int(max_reward_step if end_step is None else min(end_step, max_reward_step))
        if self.end_step < self.start_step:
            raise ValueError("end_step must be >= start_step and allow at least one reward transition.")

        flattened_feature_dim = int(self.features.shape[1] * self.features.shape[2])
        obs_dim = flattened_feature_dim + len(self.asset_names) + 1
        self.observation_space = gym.spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.window_size, obs_dim),
            dtype=np.float32,
        )
        if self.continuous_actions:
            self.action_space = gym.spaces.Box(
                low=-self.max_signal_abs,
                high=self.max_signal_abs,
                shape=(len(self.asset_names),),
                dtype=np.float32,
            )
        else:
            self.action_space = gym.spaces.Discrete(int(len(self.discrete_action_templates)))

        self.current_step = self.start_step
        self.weights = pd.Series(0.0, index=self.asset_names, dtype=float)
        self.signal_state = pd.Series(0.0, index=self.asset_names, dtype=float)
        self.equity = 1.0
        self.running_max = 1.0
        self.drawdown = 0.0
        self.bars_since_switch = int(self.execution_config.min_holding_bars)
        self.cooloff_remaining = 0
        self.dd_guard_armed = True

    def _map_action(self, action: np.ndarray | int) -> np.ndarray:
        if self.continuous_actions:
            out = np.asarray(action, dtype=np.float32).reshape(-1)
            if len(out) != len(self.asset_names):
                raise ValueError("Continuous portfolio action has incompatible dimensionality.")
            return np.clip(out, -self.max_signal_abs, self.max_signal_abs).astype(np.float32, copy=False)
        idx = int(action)
        if idx < 0 or idx >= int(len(self.discrete_action_templates)):
            raise ValueError("Discrete portfolio action index is out of bounds.")
        return self.discrete_action_templates[idx].astype(np.float32, copy=False)

    def _build_observation(self, *, step: int, weights: pd.Series, drawdown: float) -> np.ndarray:
        window = _safe_window(self.features, end_index=step, window_size=self.window_size)
        flattened_window = window.reshape(self.window_size, -1)
        state_cols = np.zeros((self.window_size, len(self.asset_names) + 1), dtype=np.float32)
        state_cols[:, : len(self.asset_names)] = weights.to_numpy(dtype=np.float32)
        state_cols[:, -1] = float(drawdown)
        return np.concatenate([flattened_window, state_cols], axis=1).astype(np.float32, copy=False)

    def _apply_execution_controls(self, signal_values: np.ndarray) -> np.ndarray:
        controlled = np.asarray(signal_values, dtype=np.float32).copy()
        prev_signals = self.signal_state.to_numpy(dtype=np.float32)
        if self.cooloff_remaining > 0:
            return np.zeros_like(controlled, dtype=np.float32)
        hysteresis = float(self.execution_config.action_hysteresis)
        if hysteresis > 0.0:
            hold_mask = np.abs(controlled - prev_signals) <= hysteresis
            controlled = np.where(hold_mask, prev_signals, controlled)
        if (
            np.any(np.abs(controlled - prev_signals) > 1e-12)
            and self.bars_since_switch < int(self.execution_config.min_holding_bars)
        ):
            controlled = prev_signals.copy()
        return controlled.astype(np.float32, copy=False)

    def _signals_to_weights(self, signal_values: np.ndarray) -> tuple[pd.Series, dict[str, float | dict[str, float]]]:
        signal_series = pd.Series(signal_values.astype(float), index=self.asset_names, dtype=float)
        raw_weights = signal_to_raw_weights(
            signal_series,
            long_short=self.long_short,
            gross_target=min(float(self.gross_target), float(self.constraints.max_gross_leverage)),
        )
        return apply_constraints(
            raw_weights,
            constraints=self.constraints,
            prev_weights=self.weights,
            asset_to_group=self.asset_to_group or None,
        )

    def _transition(self, *, signal_values: np.ndarray) -> tuple[float, dict[str, float | dict[str, float]]]:
        forced_cooloff = self.cooloff_remaining > 0
        actual_signal_values = self._apply_execution_controls(signal_values)
        target_weights, diagnostics = self._signals_to_weights(actual_signal_values)
        next_returns = pd.Series(
            self.simple_returns[self.current_step + 1].astype(float),
            index=self.asset_names,
            dtype=float,
        )
        gross_return = float(target_weights.dot(next_returns))
        turnover = float((target_weights - self.weights).abs().sum())
        costs = float(self.reward_config.cost_per_turnover + self.reward_config.slippage_per_turnover) * turnover
        inventory_penalty = float(self.reward_config.inventory_penalty) * float(target_weights.abs().sum())
        switch_fraction = float(
            np.mean(np.abs(actual_signal_values - self.signal_state.to_numpy(dtype=np.float32)) > 1e-12)
        )
        switching_penalty = float(self.reward_config.switching_penalty) * switch_fraction * float(not forced_cooloff)

        tentative_equity = float(self.equity * (1.0 + gross_return - costs))
        running_max = max(float(self.running_max), tentative_equity)
        drawdown = float(tentative_equity / running_max - 1.0) if running_max > 0 else 0.0
        drawdown_penalty = float(self.reward_config.drawdown_penalty) * abs(min(drawdown, 0.0))
        reward = gross_return - costs - inventory_penalty - drawdown_penalty - switching_penalty

        return reward, {
            "gross_return": gross_return,
            "costs": costs,
            "turnover": turnover,
            "inventory_penalty": inventory_penalty,
            "drawdown_penalty": drawdown_penalty,
            "switching_penalty": switching_penalty,
            "reward": float(reward),
            "drawdown": drawdown,
            "equity": tentative_equity,
            "running_max": running_max,
            "weights": target_weights.to_dict(),
            "signals": {asset: float(value) for asset, value in zip(self.asset_names, actual_signal_values)},
            "diagnostics": diagnostics,
        }

    def reset(self, *, seed: int | None = None, options: dict | None = None) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        self.current_step = self.start_step
        self.weights = pd.Series(0.0, index=self.asset_names, dtype=float)
        self.signal_state = pd.Series(0.0, index=self.asset_names, dtype=float)
        self.equity = 1.0
        self.running_max = 1.0
        self.drawdown = 0.0
        self.bars_since_switch = int(self.execution_config.min_holding_bars)
        self.cooloff_remaining = 0
        self.dd_guard_armed = True
        return self._build_observation(step=self.current_step, weights=self.weights, drawdown=self.drawdown), {}

    def step(self, action: np.ndarray | int) -> tuple[np.ndarray, float, bool, bool, dict]:
        prev_signals = self.signal_state.copy()
        signal_values = self._map_action(action)
        reward, info = self._transition(signal_values=signal_values)

        self.weights = pd.Series(info["weights"], dtype=float).reindex(self.asset_names).fillna(0.0)
        self.signal_state = pd.Series(info["signals"], dtype=float).reindex(self.asset_names).fillna(0.0)
        self.equity = float(info["equity"])
        self.running_max = float(info["running_max"])
        self.drawdown = float(info["drawdown"])
        if bool((self.signal_state - prev_signals).abs().gt(1e-12).any()):
            self.bars_since_switch = 0
        else:
            self.bars_since_switch += 1
        self.cooloff_remaining, self.dd_guard_armed = _update_drawdown_guard_state(
            drawdown=self.drawdown,
            execution_config=self.execution_config,
            cooloff_remaining=self.cooloff_remaining,
            guard_armed=self.dd_guard_armed,
        )
        self.current_step += 1

        terminated = bool(self.current_step > self.end_step)
        obs = self._build_observation(
            step=min(self.current_step, len(self.features) - 1),
            weights=self.weights,
            drawdown=self.drawdown,
        )
        return obs, float(reward), terminated, False, info


__all__ = [
    "PortfolioTradingEnv",
    "RLExecutionConfig",
    "RLRewardConfig",
    "SingleAssetTradingEnv",
]
