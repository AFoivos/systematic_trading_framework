from __future__ import annotations

import pytest

from src.utils.config_validation import (
    ConfigValidationError,
    validate_backtest_block,
    validate_execution_block,
    validate_data_block,
    validate_logging_block,
    validate_model_block,
    validate_portfolio_block,
    validate_signals_block,
)


@pytest.mark.parametrize(
    "field_overrides",
    [
        {"target": {"kind": "forward_return", "horizon": 1.9}},
        {"split": {"method": "walk_forward", "train_size": 100, "test_size": "20"}},
        {
            "split": {
                "method": "purged",
                "train_size": 100,
                "test_size": 20,
                "purge_bars": True,
                "embargo_bars": 0,
            }
        },
    ],
)
def test_validate_model_block_rejects_silent_integer_coercions(field_overrides: dict[str, object]) -> None:
    """
    Model validation should reject numeric-like values that would silently change integer semantics.
    """
    model = {
        "kind": "logistic_regression_clf",
        "target": {"kind": "forward_return", "horizon": 1},
        "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
    }
    model.update(field_overrides)

    with pytest.raises(ConfigValidationError):
        validate_model_block(model)


def test_validate_portfolio_block_rejects_invalid_nested_constraints() -> None:
    """
    Portfolio validation should fail early on malformed or infeasible nested constraint values.
    """
    with pytest.raises(ConfigValidationError):
        validate_portfolio_block(
            {
                "enabled": True,
                "construction": "signal_weights",
                "constraints": {
                    "min_weight": 0.5,
                    "max_weight": -0.5,
                    "max_gross_leverage": 1.0,
                },
            }
        )

    with pytest.raises(ConfigValidationError):
        validate_portfolio_block(
            {
                "enabled": True,
                "construction": "mean_variance",
                "constraints": {"group_max_exposure": {"fx": "bad"}},
            }
        )


def test_validate_execution_block_rejects_invalid_current_weight_and_price_values() -> None:
    """
    Execution validation should reject non-numeric weights and non-positive supplemental prices.
    """
    with pytest.raises(ConfigValidationError):
        validate_execution_block(
            {
                "enabled": True,
                "capital": 100_000.0,
                "current_weights": {"AAA": "bad"},
            }
        )

    with pytest.raises(ConfigValidationError):
        validate_execution_block(
            {
                "enabled": True,
                "capital": 100_000.0,
                "current_prices": {"AAA": 0.0},
            }
        )


def test_validate_model_block_rejects_ppo_only_params_for_dqn() -> None:
    model = {
        "kind": "dqn_agent",
        "feature_cols": ["close_ret"],
        "target": {"kind": "forward_return", "horizon": 1},
        "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
        "env": {"action_space": "discrete", "window_size": 8, "execution_lag_bars": 1},
        "params": {"total_timesteps": 128, "n_steps": 16},
    }

    with pytest.raises(ConfigValidationError, match="PPO-only"):
        validate_model_block(model)


def test_validate_model_block_rejects_triple_barrier_for_forecasters() -> None:
    model = {
        "kind": "sarimax_forecaster",
        "feature_cols": ["feat_1"],
        "target": {
            "kind": "triple_barrier",
            "price_col": "close",
            "open_col": "open",
            "high_col": "high",
            "low_col": "low",
            "max_holding": 12,
        },
        "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
    }

    with pytest.raises(ConfigValidationError, match="triple_barrier"):
        validate_model_block(model)


def test_validate_model_block_rejects_invalid_overlay_configuration() -> None:
    model = {
        "kind": "garch_forecaster",
        "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
        "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
        "overlay": {"kind": "garch", "params": {"mean_model": "zero"}},
    }

    with pytest.raises(ConfigValidationError, match="model.overlay"):
        validate_model_block(model)


def test_validate_backtest_block_accepts_min_holding_bars() -> None:
    validate_backtest_block(
        {
            "returns_col": "close_logret",
            "signal_col": "signal",
            "periods_per_year": 8760,
            "returns_type": "log",
            "missing_return_policy": "raise_if_exposed",
            "min_holding_bars": 2,
        }
    )


def test_validate_backtest_block_rejects_negative_min_holding_bars() -> None:
    with pytest.raises(ConfigValidationError, match="backtest.min_holding_bars"):
        validate_backtest_block(
            {
                "returns_col": "close_logret",
                "signal_col": "signal",
                "periods_per_year": 8760,
                "returns_type": "log",
                "missing_return_policy": "raise_if_exposed",
                "min_holding_bars": -1,
            }
        )


def test_validate_model_block_rejects_lightgbm_only_params_for_xgboost() -> None:
    model = {
        "kind": "xgboost_clf",
        "feature_cols": ["feat_1"],
        "target": {"kind": "triple_barrier", "price_col": "close", "open_col": "open", "high_col": "high", "low_col": "low", "max_holding": 12},
        "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
        "params": {"n_estimators": 10, "num_leaves": 31, "min_child_samples": 20},
    }

    with pytest.raises(ConfigValidationError, match="LightGBM-only params"):
        validate_model_block(model)


def test_validate_model_block_accepts_lstm_forecaster_with_garch_overlay() -> None:
    model = {
        "kind": "lstm_forecaster",
        "feature_cols": ["feat_1", "feat_2"],
        "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
        "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
        "params": {
            "lookback": 24,
            "hidden_dim": 16,
            "num_layers": 1,
            "epochs": 2,
            "batch_size": 16,
            "learning_rate": 1e-3,
            "scale_target": True,
        },
        "overlay": {"kind": "garch", "params": {"returns_input_col": "close_ret", "mean_model": "zero"}},
    }

    validate_model_block(model)


def test_validate_model_block_rejects_invalid_patchtst_quantiles() -> None:
    model = {
        "kind": "patchtst_forecaster",
        "feature_cols": ["feat_1", "feat_2"],
        "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
        "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
        "params": {
            "lookback": 32,
            "patch_len": 8,
            "patch_stride": 4,
            "hidden_dim": 32,
            "num_heads": 4,
            "num_layers": 1,
            "quantiles": [0.5],
        },
    }

    with pytest.raises(ConfigValidationError, match="quantiles"):
        validate_model_block(model)


def test_validate_logging_block_rejects_invalid_stage_tail_values() -> None:
    with pytest.raises(ConfigValidationError, match="stage_tails.limit"):
        validate_logging_block(
            {
                "enabled": True,
                "run_name": "demo",
                "output_dir": "logs/experiments",
                "stage_tails": {"limit": 0},
            }
        )

    with pytest.raises(ConfigValidationError, match="stage_tails.stdout"):
        validate_logging_block(
            {
                "enabled": True,
                "run_name": "demo",
                "output_dir": "logs/experiments",
                "stage_tails": {"stdout": "yes"},
            }
        )


def test_validate_signals_block_rejects_invalid_probability_vol_adjusted_dead_zone() -> None:
    from src.utils.config_validation import validate_signals_block

    with pytest.raises(ConfigValidationError, match="lower < prob_center < upper"):
        validate_signals_block(
            {
                "kind": "probability_vol_adjusted",
                "params": {
                    "prob_col": "pred_prob",
                    "vol_col": "pred_vol",
                    "prob_center": 0.5,
                    "upper": 0.45,
                    "lower": 0.40,
                    "vol_target": 0.001,
                    "clip": 0.5,
                },
            }
        )

    with pytest.raises(ConfigValidationError, match="min_signal_abs"):
        validate_signals_block(
            {
                "kind": "probability_vol_adjusted",
                "params": {
                    "prob_col": "pred_prob",
                    "vol_col": "pred_vol",
                    "upper": 0.55,
                    "lower": 0.45,
                    "vol_target": 0.001,
                    "clip": 0.5,
                    "min_signal_abs": 0.6,
                },
            }
        )

    with pytest.raises(ConfigValidationError, match="activation_filters\\[0\\]\\.op"):
        validate_signals_block(
            {
                "kind": "probability_vol_adjusted",
                "params": {
                    "prob_col": "pred_prob",
                    "vol_col": "pred_vol",
                    "upper": 0.55,
                    "lower": 0.45,
                    "vol_target": 0.001,
                    "clip": 0.5,
                    "activation_filters": [
                        {"col": "adx_24", "op": "neq", "value": 20.0},
                    ],
                },
            }
        )


def test_validate_data_block_accepts_dukascopy_csv_with_explicit_load_path() -> None:
    validate_data_block(
        {
            "source": "dukascopy_csv",
            "symbol": "BTCUSD",
            "interval": "1h",
            "storage": {
                "mode": "cached_only",
                "load_path": "data/raw/dukas_copy_bank/btcusd_h1.csv",
            },
        }
    )


def test_validate_data_block_rejects_dukascopy_csv_without_load_path() -> None:
    with pytest.raises(ConfigValidationError, match="data.storage.load_path is required"):
        validate_data_block(
            {
                "source": "dukascopy_csv",
                "symbol": "BTCUSD",
                "interval": "1h",
                "storage": {"mode": "cached_only"},
            }
        )

    with pytest.raises(ConfigValidationError, match="activation_filters\\[0\\]\\.use_abs"):
        validate_signals_block(
            {
                "kind": "probability_vol_adjusted",
                "params": {
                    "prob_col": "pred_prob",
                    "vol_col": "pred_vol",
                    "upper": 0.55,
                    "lower": 0.45,
                    "vol_target": 0.001,
                    "clip": 0.5,
                    "activation_filters": [
                        {"col": "adx_24", "op": "ge", "value": 20.0, "use_abs": "yes"},
                    ],
                },
            }
        )
