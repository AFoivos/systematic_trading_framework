from __future__ import annotations

from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from src.experiments.orchestration import backtest_stage
from src.experiments.orchestration.reporting import build_fold_backtest_summaries
from src.models.rl.risk_env import (
    RiskRewardConfig,
    RiskTradeConfig,
    SingleAssetRiskTradingEnv,
    calculate_sl_tp,
    decode_trade_action,
)
from src.models.rl.walk_forward import (
    CheckpointEvaluation,
    PolicyEvaluation,
    PolicyMetrics,
    build_sliding_window_folds,
    evaluate_checkpoints_then_test,
    evaluate_consistency_gate,
    select_checkpoint_maximin,
    split_score,
)
from src.utils.config import load_experiment_config
from src.utils.config_validation import ConfigValidationError, validate_resolved_config


def _metrics(
    reward: float,
    *,
    drawdown: float = 0.0,
    total_return: float = 0.0,
    evaluation_steps: int = 1,
) -> PolicyMetrics:
    return PolicyMetrics(
        cumulative_reward=reward,
        max_drawdown=drawdown,
        total_return=total_return,
        final_equity=100_000.0 * (1.0 + total_return),
        trade_count=1,
        evaluation_steps=evaluation_steps,
    )


def _price_frame(*, highs: list[float], lows: list[float]) -> pd.DataFrame:
    periods = len(highs)
    return pd.DataFrame(
        {
            "open": np.full(periods, 100.0),
            "high": highs,
            "low": lows,
            "close": np.full(periods, 100.0),
            "atr_14": np.ones(periods),
            "feature_x": np.linspace(-1.0, 1.0, periods),
        },
        index=pd.date_range("2025-01-01", periods=periods, freq="h"),
    )


def test_action_decoding_covers_hold_long_short_and_risk_parameters() -> None:
    kwargs = {
        "atr_multipliers": [1.0, 2.0],
        "take_profit_r_multiples": [1.0, 3.0],
    }

    assert decode_trade_action(0, **kwargs).is_hold
    assert decode_trade_action(1, **kwargs) == decode_trade_action(np.array([1]), **kwargs)
    assert decode_trade_action(1, **kwargs).direction == 1
    assert decode_trade_action(1, **kwargs).stop_loss_atr_multiplier == 1.0
    assert decode_trade_action(1, **kwargs).take_profit_r_multiple == 1.0
    assert decode_trade_action(4, **kwargs).direction == 1
    assert decode_trade_action(4, **kwargs).stop_loss_atr_multiplier == 2.0
    assert decode_trade_action(4, **kwargs).take_profit_r_multiple == 3.0
    assert decode_trade_action(5, **kwargs).direction == -1
    assert decode_trade_action(8, **kwargs).direction == -1
    assert decode_trade_action(8, **kwargs).stop_loss_atr_multiplier == 2.0
    assert decode_trade_action(8, **kwargs).take_profit_r_multiple == 3.0


def test_directional_action_mode_has_exactly_three_actions() -> None:
    kwargs = {
        "atr_multipliers": [1.5],
        "take_profit_r_multiples": [2.0],
        "action_mode": "directional",
    }

    assert decode_trade_action(0, **kwargs).is_hold
    assert decode_trade_action(1, **kwargs).direction == 1
    assert decode_trade_action(2, **kwargs).direction == -1
    with pytest.raises(ValueError, match=r"\[0, 3\)"):
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
    long_stop, long_take_profit = calculate_sl_tp(
        entry_price=100.0,
        atr=2.0,
        direction=1,
        stop_loss_atr_multiplier=1.5,
        take_profit_r_multiple=2.0,
    )
    short_stop, short_take_profit = calculate_sl_tp(
        entry_price=100.0,
        atr=2.0,
        direction=-1,
        stop_loss_atr_multiplier=1.5,
        take_profit_r_multiple=2.0,
    )

    assert (long_stop, long_take_profit) == pytest.approx((97.0, 106.0))
    assert (short_stop, short_take_profit) == pytest.approx((103.0, 94.0))


def test_realized_reward_is_net_pnl_divided_by_initial_amount_at_risk() -> None:
    env = SingleAssetRiskTradingEnv(
        frame=_price_frame(
            highs=[100.2, 100.2, 102.5, 100.2],
            lows=[99.8, 99.8, 99.8, 99.8],
        ),
        feature_columns=["feature_x"],
        atr_column="atr_14",
        trade_config=RiskTradeConfig(
            atr_multipliers=(1.0,),
            take_profit_r_multiples=(2.0,),
            risk_fraction=0.01,
        ),
        reward_config=RiskRewardConfig(realized_pnl_r_multiple=1.0),
    )
    env.reset()

    _, opening_reward, _, _, _ = env.step(1)
    _, exit_reward, _, _, info = env.step(0)

    assert opening_reward == pytest.approx(0.0)
    assert info["realized_pnl_r_multiple"] == pytest.approx(2.0)
    assert exit_reward == pytest.approx(2.0)
    assert env.trades[0]["net_pnl"] / env.trades[0]["initial_risk"] == pytest.approx(2.0)


def test_holding_penalty_is_applied_once_per_carried_bar() -> None:
    env = SingleAssetRiskTradingEnv(
        frame=_price_frame(highs=[100.2] * 4, lows=[99.8] * 4),
        feature_columns=["feature_x"],
        atr_column="atr_14",
        trade_config=RiskTradeConfig(
            atr_multipliers=(1.0,),
            take_profit_r_multiples=(2.0,),
        ),
        reward_config=RiskRewardConfig(holding_penalty=0.05),
    )
    env.reset()

    _, opening_reward, _, _, opening_info = env.step(1)
    _, held_reward, _, _, held_info = env.step(0)

    assert opening_info["holding_penalty"] == pytest.approx(0.05)
    assert opening_reward == pytest.approx(-0.05)
    assert held_info["holding_penalty"] == pytest.approx(0.05)
    assert held_reward == pytest.approx(-0.05)


def test_actions_execute_next_open_and_reversal_uses_decision_bar_atr() -> None:
    index = pd.date_range("2025-01-01", periods=4, freq="h")
    frame = pd.DataFrame(
        {
            "open": [100.0, 110.0, 120.0, 130.0],
            "high": [100.4, 110.4, 120.4, 130.4],
            "low": [99.6, 109.6, 119.6, 129.6],
            "close": [100.0, 110.0, 120.0, 130.0],
            "atr_14": [1.0, 2.0, 3.0, 4.0],
            "feature_x": [0.0, 1.0, 2.0, 3.0],
        },
        index=index,
    )
    env = SingleAssetRiskTradingEnv(
        frame=frame,
        feature_columns=["feature_x"],
        atr_column="atr_14",
        trade_config=RiskTradeConfig(
            atr_multipliers=(1.0,),
            take_profit_r_multiples=(1.0,),
        ),
    )
    env.reset()

    _, _, terminated, _, first_info = env.step(1)

    assert terminated is False
    assert first_info["decision_timestamp"] == index[0]
    assert first_info["execution_timestamp"] == index[1]
    assert env.position is not None
    assert env.position.entry_price == pytest.approx(110.0)
    assert env.position.stop_price == pytest.approx(109.0)

    _, _, _, _, reversal_info = env.step(2)

    assert reversal_info["execution_timestamp"] == index[2]
    assert reversal_info["closed_trade"]["exit_reason"] == "opposite_signal"
    assert reversal_info["closed_trade"]["exit_price"] == pytest.approx(120.0)
    assert env.position is not None
    assert env.position.direction == -1
    assert env.position.entry_price == pytest.approx(120.0)
    assert env.position.stop_price == pytest.approx(122.0)


def test_final_execution_bar_rejects_new_entry() -> None:
    env = SingleAssetRiskTradingEnv(
        frame=_price_frame(highs=[100.2, 100.2], lows=[99.8, 99.8]),
        feature_columns=["feature_x"],
        atr_column="atr_14",
        trade_config=RiskTradeConfig(
            atr_multipliers=(1.0,),
            take_profit_r_multiples=(1.0,),
        ),
    )
    env.reset()

    _, reward, terminated, _, info = env.step(1)

    assert terminated is True
    assert reward == pytest.approx(0.0)
    assert info["entry_rejected_reason"] == "final_execution_bar"
    assert env.position is None
    assert env.trades == []


@pytest.mark.parametrize(
    ("max_leverage", "max_notional", "expected_notional", "expected_limit"),
    [
        (2.0, None, 200_000.0, "max_leverage"),
        (5.0, 50_000.0, 50_000.0, "max_notional"),
    ],
)
def test_position_sizing_is_capped_deterministically(
    max_leverage: float,
    max_notional: float | None,
    expected_notional: float,
    expected_limit: str,
) -> None:
    frame = _price_frame(highs=[100.0] * 3, lows=[100.0] * 3)
    frame["atr_14"] = 0.01
    env = SingleAssetRiskTradingEnv(
        frame=frame,
        feature_columns=["feature_x"],
        atr_column="atr_14",
        trade_config=RiskTradeConfig(
            atr_multipliers=(1.0,),
            take_profit_r_multiples=(2.0,),
            max_leverage=max_leverage,
            max_notional=max_notional,
        ),
    )
    env.reset()

    env.step(1)

    assert env.position is not None
    assert env.position.initial_notional == pytest.approx(expected_notional)
    assert env.position.initial_leverage == pytest.approx(expected_notional / 100_000.0)
    assert env.position.initial_risk == pytest.approx(env.position.quantity * 0.01)
    assert env.position.sizing_limit == expected_limit


def test_equity_charges_transaction_costs_only_when_entry_and_exit_occur() -> None:
    env = SingleAssetRiskTradingEnv(
        frame=_price_frame(highs=[100.2] * 3, lows=[99.8] * 3),
        feature_columns=["feature_x"],
        atr_column="atr_14",
        trade_config=RiskTradeConfig(
            atr_multipliers=(1.0,),
            take_profit_r_multiples=(2.0,),
            transaction_cost_bps=10.0,
        ),
    )
    env.reset()

    _, _, _, _, entry_info = env.step(1)
    entry_cost = env.position.entry_cost if env.position is not None else 0.0
    _, _, terminated, _, exit_info = env.step(0)

    assert entry_info["transaction_cost"] == pytest.approx(entry_cost)
    assert exit_info["transaction_cost"] == pytest.approx(env.trades[0]["exit_cost"])
    assert terminated is True
    assert env.equity == pytest.approx(
        env.trade_config.initial_equity + env.trades[0]["net_pnl"]
    )


def test_sliding_window_folds_are_disjoint_ordered_and_fixed_size() -> None:
    folds = build_sliding_window_folds(
        n_samples=40,
        train_size=10,
        validation_size=5,
        test_size=5,
        step_size=5,
        max_folds=3,
    )

    assert [fold.train_start for fold in folds] == [0, 5, 10]
    assert [len(fold.train_indices) for fold in folds] == [10, 10, 10]
    for fold in folds:
        assert fold.train_end == fold.validation_start
        assert fold.validation_end == fold.test_start
        assert fold.train_end <= fold.validation_start < fold.validation_end <= fold.test_start < fold.test_end
        assert set(fold.train_indices).isdisjoint(fold.validation_indices)
        assert set(fold.train_indices).isdisjoint(fold.test_indices)
        assert set(fold.validation_indices).isdisjoint(fold.test_indices)
    assert folds[1].train_indices.tolist() == list(range(5, 15))
    assert 0 not in folds[1].train_indices


def test_maximin_checkpoint_selection_uses_worst_train_tail_or_validation_score() -> None:
    selected = select_checkpoint_maximin(
        [
            CheckpointEvaluation(
                checkpoint="overfit.zip",
                step=100,
                train_tail=_metrics(10.0),
                validation=_metrics(1.0),
            ),
            CheckpointEvaluation(
                checkpoint="balanced.zip",
                step=200,
                train_tail=_metrics(4.0, drawdown=0.5),
                validation=_metrics(4.0),
            ),
        ],
        drawdown_penalty=2.0,
    )

    assert selected.checkpoint == "balanced.zip"
    assert selected.train_tail_score == pytest.approx(3.0)
    assert selected.validation_score == pytest.approx(4.0)
    assert selected.checkpoint_score == pytest.approx(3.0)


def test_checkpoint_score_normalizes_reward_by_evaluated_steps() -> None:
    ten_bar_metrics = _metrics(2.0, drawdown=0.1, evaluation_steps=10)
    twenty_bar_metrics = _metrics(4.0, drawdown=0.1, evaluation_steps=20)

    assert split_score(ten_bar_metrics, drawdown_penalty=0.5) == pytest.approx(0.15)
    assert split_score(twenty_bar_metrics, drawdown_penalty=0.5) == pytest.approx(0.15)


def test_consistency_gate_passes_and_fails_without_creating_failed_champion() -> None:
    passed = evaluate_consistency_gate(
        test_returns=[0.10, 0.20, -0.05],
        minimum_profitable_fold_ratio=0.60,
        minimum_median_test_return=0.05,
        last_fold_checkpoint="last.zip",
    )
    failed = evaluate_consistency_gate(
        test_returns=[0.10, 0.20, -0.05],
        minimum_profitable_fold_ratio=0.80,
        minimum_median_test_return=0.05,
        last_fold_checkpoint="last.zip",
    )

    assert passed.passed is True
    assert passed.profitable_fold_ratio == pytest.approx(2.0 / 3.0)
    assert passed.median_test_return == pytest.approx(0.10)
    assert passed.champion_checkpoint == "last.zip"
    assert failed.passed is False
    assert failed.champion_checkpoint is None


def test_test_split_is_evaluated_only_after_selection_and_only_for_selected_checkpoint() -> None:
    calls: list[tuple[str, str]] = []

    def evaluator(checkpoint: str, split_name: str) -> PolicyEvaluation:
        calls.append((checkpoint, split_name))
        reward_by_split = {
            ("a.zip", "train_tail"): 8.0,
            ("a.zip", "validation"): 1.0,
            ("b.zip", "train_tail"): 3.0,
            ("b.zip", "validation"): 3.0,
            ("b.zip", "test"): -100.0,
        }
        return PolicyEvaluation(metrics=_metrics(reward_by_split[(checkpoint, split_name)]))

    result = evaluate_checkpoints_then_test(
        checkpoints=[("a.zip", 100), ("b.zip", 200)],
        evaluator=evaluator,
        drawdown_penalty=0.0,
    )

    assert result.selection.checkpoint == "b.zip"
    assert calls == [
        ("a.zip", "train_tail"),
        ("a.zip", "validation"),
        ("b.zip", "train_tail"),
        ("b.zip", "validation"),
        ("b.zip", "test"),
    ]
    assert ("a.zip", "test") not in calls
    assert result.selection.checkpoint_score == pytest.approx(3.0)
    assert result.test.metrics.cumulative_reward == pytest.approx(-100.0)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("execution_lag_bars", 2, "execution_lag_bars=1"),
        ("max_leverage", 0.0, "max_leverage must be > 0"),
        ("max_notional", -1.0, "max_notional must be > 0"),
    ],
)
def test_invalid_rl_risk_execution_and_notional_configs_are_rejected(
    field: str,
    value: float,
    message: str,
) -> None:
    cfg = load_experiment_config(
        "config/experiments/rl/xauusd_30m_ppo_risk_walk_forward.yaml"
    )
    invalid = deepcopy(cfg)
    invalid["model"]["env"][field] = value

    with pytest.raises(ConfigValidationError, match=message):
        validate_resolved_config(invalid)


def test_rl_environment_results_bypass_generic_signal_backtest(monkeypatch: pytest.MonkeyPatch) -> None:
    index = pd.date_range("2025-01-01", periods=3, freq="h")
    frame = pd.DataFrame(
        {
            "pred_is_oos": [True, True, True],
            "rl_net_return": [0.01, -0.005, 0.002],
            "rl_position_leverage": [1.0, 0.5, 0.0],
            "rl_transaction_cost_return": [0.001, 0.001, 0.0],
            "signal_rl": [1.0, -1.0, 0.0],
        },
        index=index,
    )
    model_meta = {
        "performance_source": "rl_environment",
        "pred_is_oos_col": "pred_is_oos",
        "rl_environment_columns": {
            "net_return": "rl_net_return",
            "position_leverage": "rl_position_leverage",
            "transaction_cost_return": "rl_transaction_cost_return",
        },
        "folds": [
            {
                "fold": 0,
                "trades": [
                    {
                        "entry_timestamp": index[0],
                        "exit_timestamp": index[1],
                        "trade_r": 0.5,
                    }
                ],
            }
        ],
    }

    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("generic run_backtest must not be called for RL environment results")

    monkeypatch.setattr(backtest_stage, "run_backtest", fail_if_called)
    result = backtest_stage.run_single_asset_backtest(
        "XAUUSD",
        frame,
        cfg={"backtest": {"periods_per_year": 252}},
        model_meta=model_meta,
    )

    assert result.returns.tolist() == pytest.approx([0.01, -0.005, 0.002])
    assert result.gross_returns.tolist() == pytest.approx([0.011, -0.004, 0.002])
    assert result.trades is not None
    assert result.trades.loc[0, "asset"] == "XAUUSD"
    assert result.summary["cumulative_return"] == pytest.approx(
        (1.01 * 0.995 * 1.002) - 1.0
    )


def test_rl_environment_null_annualization_mode_defaults_to_fixed_periods() -> None:
    index = pd.date_range("2025-01-01", periods=2, freq="h")
    frame = pd.DataFrame(
        {
            "pred_is_oos": [True, True],
            "rl_net_return": [0.01, -0.005],
            "rl_position_leverage": [1.0, 0.0],
            "rl_transaction_cost_return": [0.001, 0.0],
        },
        index=index,
    )
    model_meta = {
        "performance_source": "rl_environment",
        "pred_is_oos_col": "pred_is_oos",
        "rl_environment_columns": {
            "net_return": "rl_net_return",
            "position_leverage": "rl_position_leverage",
            "transaction_cost_return": "rl_transaction_cost_return",
        },
    }

    result = backtest_stage.run_single_asset_backtest(
        "BTCUSD",
        frame,
        cfg={"backtest": {"periods_per_year": 252, "annualization_mode": None}},
        model_meta=model_meta,
    )

    assert result.summary["annualization_mode"] == "fixed_periods"


def test_rl_nested_split_boundaries_are_accepted_by_fold_reporting() -> None:
    source_index = pd.date_range("2025-01-01", periods=4, freq="h")
    net_returns = pd.Series([0.01, 0.02, -0.01], index=source_index[1:])
    zero_series = pd.Series(0.0, index=net_returns.index)

    summaries = build_fold_backtest_summaries(
        source_index=source_index,
        net_returns=net_returns,
        turnover=zero_series,
        costs=zero_series,
        gross_returns=net_returns,
        periods_per_year=252,
        folds=[
            {
                "fold": 0,
                "split_boundaries": {
                    "test_start": 2,
                    "test_end": 4,
                },
            }
        ],
    )

    assert summaries[0]["fold"] == 0
    assert summaries[0]["test_rows"] == 2
    assert summaries[0]["metrics"]["cumulative_return"] == pytest.approx(
        (1.02 * 0.99) - 1.0
    )
