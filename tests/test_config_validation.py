from __future__ import annotations

import pytest

from src.utils.config_validation import (
    ConfigValidationError,
    validate_backtest_block,
    validate_execution_block,
    validate_data_block,
    validate_features_block,
    validate_logging_block,
    validate_model_block,
    validate_model_stages_block,
    validate_portfolio_block,
    validate_risk_block,
    validate_resolved_config,
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


def test_validate_features_block_accepts_outputs_and_support_resistance() -> None:
    validate_features_block(
        [
            {
                "step": "support_resistance",
                "outputs": {
                    "support_24": "btc_support_24",
                    "resistance_24": "btc_resistance_24",
                },
                "params": {
                    "price_col": "close",
                    "high_col": "high",
                    "low_col": "low",
                    "windows": [24],
                    "include_pct_distance": True,
                    "include_atr_distance": False,
                },
            }
        ]
    )


def test_validate_features_block_accepts_support_resistance_v2() -> None:
    validate_features_block(
        [
            {
                "step": "support_resistance_v2",
                "params": {
                    "price_col": "close",
                    "high_col": "high",
                    "low_col": "low",
                    "pivot_left_window": 24,
                    "pivot_confirm_bars": 6,
                    "touch_tolerance_atr": 0.25,
                    "breakout_tolerance_atr": 0.05,
                },
            }
        ]
    )


def test_validate_model_and_signals_outputs_reject_unknown_keys() -> None:
    with pytest.raises(ConfigValidationError, match="model.outputs.bad_key"):
        validate_model_block(
            {
                "kind": "logistic_regression_clf",
                "outputs": {"bad_key": "foo"},
                "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
                "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
            }
        )

    with pytest.raises(ConfigValidationError, match="signals.outputs.bad_key"):
        validate_signals_block(
            {
                "kind": "probability_threshold",
                "outputs": {"bad_key": "signal_custom"},
                "params": {"prob_col": "pred_prob", "upper": 0.55, "lower": 0.45},
            }
        )


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


def test_validate_model_block_accepts_feature_selectors() -> None:
    validate_model_block(
        {
            "kind": "xgboost_clf",
            "feature_selectors": {
                "exact": ["shock_strength"],
                "include": [
                    {"startswith": "close_rsi_"},
                    {"regex": "^bb_percent_b_"},
                ],
                "exclude": [{"startswith": "target_"}],
                "strict": {"min_count": 3},
            },
            "target": {"kind": "forward_return", "horizon": 1},
            "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
        }
    )


def test_validate_model_block_rejects_invalid_feature_selectors() -> None:
    model = {
        "kind": "xgboost_clf",
        "feature_selectors": {"include": [{"prefix": "close_rsi_"}]},
        "target": {"kind": "forward_return", "horizon": 1},
        "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
    }

    with pytest.raises(ConfigValidationError, match="feature_selectors"):
        validate_model_block(model)


def test_validate_model_block_accepts_event_transformer_encoder_with_candidate_target() -> None:
    validate_model_block(
        {
            "kind": "event_transformer_encoder",
            "feature_cols": ["shock_strength", "shock_ret_z_1h"],
            "target": {
                "kind": "triple_barrier",
                "price_col": "close",
                "open_col": "open",
                "high_col": "high",
                "low_col": "low",
                "max_holding": 12,
                "side_col": "shock_side_contrarian",
                "candidate_col": "shock_candidate",
            },
            "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
            "params": {
                "lookback": 24,
                "hidden_dim": 16,
                "num_heads": 4,
                "num_layers": 1,
                "embedding_dim": 8,
                "embedding_prefix": "extrema_emb",
                "min_train_samples": 16,
            },
        }
    )


def test_validate_model_block_rejects_event_transformer_without_candidate_col() -> None:
    with pytest.raises(ConfigValidationError, match="candidate_col"):
        validate_model_block(
            {
                "kind": "event_transformer_encoder",
                "feature_cols": ["shock_strength", "shock_ret_z_1h"],
                "target": {
                    "kind": "triple_barrier",
                    "price_col": "close",
                    "open_col": "open",
                    "high_col": "high",
                    "low_col": "low",
                    "max_holding": 12,
                    "side_col": "shock_side_contrarian",
                },
                "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
            }
        )


def test_validate_model_block_rejects_invalid_overlay_configuration() -> None:
    model = {
        "kind": "garch_forecaster",
        "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
        "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
        "overlay": {"kind": "garch", "params": {"mean_model": "zero"}},
    }

    with pytest.raises(ConfigValidationError, match="model.overlay"):
        validate_model_block(model)


def test_validate_model_block_accepts_forward_return_log_target_from_returns_col() -> None:
    model = {
        "kind": "tft_forecaster",
        "feature_cols": ["feat_1", "feat_2"],
        "target": {
            "kind": "forward_return",
            "price_col": "close",
            "returns_col": "close_logret",
            "returns_type": "log",
            "horizon": 1,
        },
        "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
    }

    validate_model_block(model)


def test_validate_model_block_rejects_invalid_forward_return_returns_type() -> None:
    model = {
        "kind": "tft_forecaster",
        "feature_cols": ["feat_1", "feat_2"],
        "target": {
            "kind": "forward_return",
            "price_col": "close",
            "returns_col": "close_logret",
            "returns_type": "compound",
            "horizon": 1,
        },
        "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
    }

    with pytest.raises(ConfigValidationError, match="returns_type"):
        validate_model_block(model)


@pytest.mark.parametrize("rearm_drawdown", [0.0, 0.13])
def test_validate_risk_block_rejects_invalid_rearm_drawdown(rearm_drawdown: float) -> None:
    risk = {
        "cost_per_turnover": 0.0,
        "slippage_per_turnover": 0.0,
        "target_vol": None,
        "max_leverage": 1.0,
        "dd_guard": {
            "enabled": True,
            "max_drawdown": 0.12,
            "rearm_drawdown": rearm_drawdown,
            "cooloff_bars": 48,
        },
    }

    with pytest.raises(ConfigValidationError, match="rearm_drawdown"):
        validate_risk_block(risk)


def test_validate_model_block_rejects_log_forward_return_without_returns_col() -> None:
    model = {
        "kind": "tft_forecaster",
        "feature_cols": ["feat_1", "feat_2"],
        "target": {
            "kind": "forward_return",
            "price_col": "close",
            "returns_type": "log",
            "horizon": 1,
        },
        "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
    }

    with pytest.raises(ConfigValidationError, match="returns_col"):
        validate_model_block(model)


def test_validate_model_stages_block_rejects_duplicate_output_columns() -> None:
    with pytest.raises(ConfigValidationError, match="duplicate emitted column"):
        validate_model_stages_block(
            [
                {
                    "name": "forecast_a",
                    "kind": "sarimax_forecaster",
                    "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
                    "split": {"method": "time", "train_frac": 0.6},
                    "pred_ret_col": "shared_pred_ret",
                },
                {
                    "name": "forecast_b",
                    "kind": "sarimax_forecaster",
                    "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
                    "split": {"method": "time", "train_frac": 0.7},
                    "pred_ret_col": "shared_pred_ret",
                },
            ]
        )


def test_validate_model_stages_block_rejects_duplicate_embedding_columns() -> None:
    with pytest.raises(ConfigValidationError, match="duplicate emitted column"):
        validate_model_stages_block(
            [
                {
                    "name": "encoder_a",
                    "kind": "event_transformer_encoder",
                    "feature_cols": ["shock_strength"],
                    "target": {
                        "kind": "triple_barrier",
                        "price_col": "close",
                        "open_col": "open",
                        "high_col": "high",
                        "low_col": "low",
                        "max_holding": 12,
                        "side_col": "shock_side_contrarian",
                        "candidate_col": "shock_candidate",
                    },
                    "split": {"method": "time", "train_frac": 0.6},
                    "params": {"embedding_dim": 2, "embedding_prefix": "shared_emb"},
                },
                {
                    "name": "encoder_b",
                    "kind": "event_transformer_encoder",
                    "feature_cols": ["shock_strength"],
                    "target": {
                        "kind": "triple_barrier",
                        "price_col": "close",
                        "open_col": "open",
                        "high_col": "high",
                        "low_col": "low",
                        "max_holding": 12,
                        "side_col": "shock_side_contrarian",
                        "candidate_col": "shock_candidate",
                    },
                    "split": {"method": "time", "train_frac": 0.7},
                    "params": {"embedding_dim": 2, "embedding_prefix": "shared_emb"},
                },
            ]
        )


def test_validate_resolved_config_accepts_multi_stage_model_chain() -> None:
    cfg = {
        "data": {"symbol": "SPY", "source": "yahoo", "interval": "1d", "alignment": "inner"},
        "features": [],
        "model": {
            "kind": "logistic_regression_clf",
            "feature_cols": ["forecast_pred_ret"],
            "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
            "split": {"method": "time", "train_frac": 0.75},
            "pred_prob_col": "pred_prob",
        },
        "model_stages": [
            {
                "name": "forecast",
                "enabled": True,
                "stage": 1,
                "kind": "sarimax_forecaster",
                "feature_cols": ["feat_1"],
                "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
                "split": {"method": "time", "train_frac": 0.6},
                "pred_ret_col": "forecast_pred_ret",
                "pred_prob_col": "forecast_pred_prob",
            },
            {
                "name": "filter",
                "enabled": True,
                "stage": 2,
                "kind": "logistic_regression_clf",
                "feature_cols": ["forecast_pred_ret"],
                "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
                "split": {"method": "time", "train_frac": 0.75},
                "pred_prob_col": "pred_prob",
            },
        ],
        "signals": {"kind": "probability_threshold", "params": {"prob_col": "pred_prob", "signal_col": "signal"}},
        "runtime": {"seed": 7, "repro_mode": "strict", "deterministic": True, "threads": 1, "seed_torch": False},
        "risk": {"cost_per_turnover": 0.0, "slippage_per_turnover": 0.0, "target_vol": None, "max_leverage": 1.0},
        "backtest": {
            "returns_col": "close_ret",
            "signal_col": "signal",
            "periods_per_year": 252,
            "returns_type": "simple",
            "missing_return_policy": "raise_if_exposed",
        },
        "portfolio": {"enabled": False, "construction": "signal_weights", "gross_target": 1.0, "long_short": True},
        "monitoring": {"enabled": True, "psi_threshold": 0.2, "n_bins": 10},
        "execution": {"enabled": False, "mode": "paper", "capital": 100000.0, "price_col": "close", "min_trade_notional": 0.0},
        "logging": {"enabled": True, "run_name": "multi_stage_test", "output_dir": "logs/experiments"},
    }

    validate_resolved_config(cfg)


def test_validate_model_stages_block_rejects_all_disabled_stages() -> None:
    with pytest.raises(ConfigValidationError, match="enabled=true"):
        validate_model_stages_block(
            [
                {
                    "name": "forecast",
                    "enabled": False,
                    "stage": 1,
                    "kind": "sarimax_forecaster",
                },
                {
                    "name": "filter",
                    "enabled": False,
                    "stage": 2,
                    "kind": "logistic_regression_clf",
                },
            ]
        )


def test_validate_features_block_accepts_feature_transforms_step() -> None:
    validate_features_block(
        [
            {"step": "bollinger", "enabled": True, "params": {"window": 24}},
            {
                "step": "feature_transforms",
                "params": {
                    "transforms": [
                        {
                            "source_col": "volume_over_atr_24",
                            "kind": "rolling_clip",
                            "output_col": "volume_over_atr_24_rollclip_2520_q01_q99",
                            "window": 2520,
                            "lower_q": 0.01,
                            "upper_q": 0.99,
                            "shift": 1,
                        },
                        {
                            "numerator_col": "lag_close_logret_1",
                            "denominator_col": "vol_rolling_24",
                            "kind": "ratio",
                            "output_col": "lag_close_logret_1_over_vol_rolling_24",
                        },
                        {
                            "source_col": "lag_close_logret_1",
                            "kind": "rolling_zscore",
                            "output_col": "lag_close_logret_1_z_24",
                            "window": 24,
                            "shift": 0,
                        }
                    ]
                },
            },
        ]
        )


def test_validate_features_block_accepts_selector_based_feature_transforms() -> None:
    validate_features_block(
        [
            {
                "step": "feature_transforms",
                "params": {
                    "transforms": [
                        {
                            "source_selector": {"regex": "^volume_over_atr_[0-9]+$"},
                            "kind": "rolling_clip",
                            "output_col": "volume_over_atr_rollclip",
                        },
                        {
                            "numerator_selector": {"exact": "lag_close_logret_1"},
                            "denominator_selector": {"regex": "^vol_rolling_[0-9]+$"},
                            "kind": "ratio",
                            "output_col": "lag_close_logret_1_over_selected_vol",
                        },
                    ]
                },
            },
        ]
    )


def test_validate_features_block_rejects_ambiguous_feature_transform_selector() -> None:
    with pytest.raises(ConfigValidationError, match="source_col or source_selector"):
        validate_features_block(
            [
                {
                    "step": "feature_transforms",
                    "params": {
                        "transforms": [
                            {
                                "source_col": "volume_over_atr_24",
                                "source_selector": {"startswith": "volume_over_atr_"},
                                "kind": "rolling_clip",
                                "output_col": "volume_over_atr_clip",
                            }
                        ]
                    },
                }
            ]
        )


def test_validate_features_block_accepts_boolean_enabled_flag() -> None:
    validate_features_block(
        [
            {"step": "returns", "enabled": False, "params": {"log": True, "col_name": "close_logret"}},
            {"step": "rsi", "enabled": True, "params": {"price_col": "close", "windows": [14]}},
        ]
    )


def test_validate_features_block_rejects_non_boolean_enabled_flag() -> None:
    with pytest.raises(ConfigValidationError, match="features\\[\\]\\.enabled"):
        validate_features_block(
            [
                {"step": "returns", "enabled": "yes", "params": {"log": True, "col_name": "close_logret"}},
            ]
        )


def test_validate_features_block_rejects_invalid_feature_transform_kind() -> None:
    with pytest.raises(ConfigValidationError, match="rolling_clip, ratio, rolling_zscore"):
        validate_features_block(
            [
                {
                    "step": "feature_transforms",
                    "params": {
                        "transforms": [
                            {
                                "source_col": "volume_over_atr_24",
                                "kind": "bad_kind",
                                "output_col": "volume_over_atr_24_clip",
                            }
                        ]
                    },
                }
            ]
        )


def test_validate_features_block_rejects_invalid_ratio_transform_eps() -> None:
    with pytest.raises(ConfigValidationError, match="eps"):
        validate_features_block(
            [
                {
                    "step": "feature_transforms",
                    "params": {
                        "transforms": [
                            {
                                "numerator_col": "lag_close_logret_1",
                                "denominator_col": "vol_rolling_24",
                                "kind": "ratio",
                                "output_col": "lag_close_logret_1_over_vol_rolling_24",
                                "eps": -1.0,
                            }
                        ]
                    },
                }
            ]
        )


def test_validate_features_block_rejects_invalid_feature_transform_quantiles() -> None:
    with pytest.raises(ConfigValidationError, match="lower_q"):
        validate_features_block(
            [
                {
                    "step": "feature_transforms",
                    "params": {
                        "transforms": [
                            {
                                "source_col": "volume_over_atr_24",
                                "kind": "rolling_clip",
                                "output_col": "volume_over_atr_24_clip",
                                "lower_q": 0.99,
                                "upper_q": 0.01,
                            }
                        ]
                    },
                }
            ]
        )


def test_validate_features_block_accepts_vol_normalized_momentum_vol_window() -> None:
    validate_features_block(
        [
            {
                "step": "vol_normalized_momentum",
                "params": {
                    "returns_col": "close_logret",
                    "vol_col": None,
                    "vol_window": 36,
                    "windows": [6, 24],
                },
            },
        ]
    )


def test_validate_features_block_accepts_shock_context() -> None:
    validate_features_block(
        [
            {"step": "returns", "enabled": True, "params": {"log": True, "col_name": "close_logret"}},
            {
                "step": "shock_context",
                "enabled": True,
                "params": {
                    "price_col": "close",
                    "high_col": "high",
                    "low_col": "low",
                    "returns_col": "close_logret",
                    "ema_col": "close_ema_24",
                    "atr_col": "atr_24",
                    "short_horizon": 1,
                    "medium_horizon": 4,
                    "vol_window": 24,
                    "ret_z_threshold": 2.0,
                    "atr_mult_threshold": 1.5,
                    "distance_from_mean_threshold": 1.0,
                    "post_shock_active_bars": 4,
                    "use_log_returns": True,
                },
            },
        ]
    )


def test_validate_features_block_rejects_invalid_shock_context_params() -> None:
    with pytest.raises(ConfigValidationError, match="medium_horizon"):
        validate_features_block(
            [
                {
                    "step": "shock_context",
                    "enabled": True,
                    "params": {"short_horizon": 4, "medium_horizon": 1},
                }
            ]
        )

    with pytest.raises(ConfigValidationError, match="ret_z_threshold"):
        validate_features_block(
            [
                {
                    "step": "shock_context",
                    "enabled": True,
                    "params": {"ret_z_threshold": 0.0},
                }
            ]
        )

    with pytest.raises(ConfigValidationError, match="post_shock_active_bars"):
        validate_features_block(
            [
                {
                    "step": "shock_context",
                    "enabled": True,
                    "params": {"post_shock_active_bars": 0},
                }
            ]
        )


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


def test_validate_model_block_accepts_standard_preprocessing_scaler() -> None:
    model = {
        "kind": "logistic_regression_clf",
        "feature_cols": ["feat_1"],
        "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
        "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
        "preprocessing": {"scaler": "standard"},
    }

    validate_model_block(model)


def test_validate_model_block_rejects_unknown_preprocessing_scaler() -> None:
    model = {
        "kind": "logistic_regression_clf",
        "feature_cols": ["feat_1"],
        "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
        "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
        "preprocessing": {"scaler": "robust"},
    }

    with pytest.raises(ConfigValidationError, match="model.preprocessing.scaler"):
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


def test_validate_signals_block_rejects_invalid_probability_threshold_hysteresis() -> None:
    with pytest.raises(ConfigValidationError, match="lower <= lower_exit <= upper_exit <= upper"):
        validate_signals_block(
            {
                "kind": "probability_threshold",
                "params": {
                    "prob_col": "pred_prob",
                    "upper": 0.55,
                    "upper_exit": 0.56,
                    "lower": 0.45,
                    "lower_exit": 0.46,
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


def test_validate_signals_block_accepts_activation_filter_selectors() -> None:
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
                    {"selector": {"regex": "^regime_vol_ratio_[0-9]+_[0-9]+$"}, "op": "ge", "value": 1.0},
                    {"selector": {"startswith": "adx_"}, "op": "ge", "value": 20.0},
                ],
            },
        }
    )


def test_validate_signals_block_rejects_ambiguous_activation_filter_selector() -> None:
    with pytest.raises(ConfigValidationError, match="col or selector"):
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
                        {
                            "col": "adx_24",
                            "selector": {"startswith": "adx_"},
                            "op": "ge",
                            "value": 20.0,
                        },
                    ],
                },
            }
        )


def test_validate_signals_block_rejects_legacy_signal_name() -> None:
    with pytest.raises(ConfigValidationError, match="signal_name is no longer supported"):
        validate_signals_block(
            {
                "kind": "forecast_threshold",
                "params": {
                    "forecast_col": "pred_ret",
                    "signal_name": "signal_a",
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


def test_validate_resolved_config_rejects_test_subset_without_model() -> None:
    cfg = {
        "data": {
            "source": "dukascopy_csv",
            "interval": "1h",
            "start": "2024-01-01 00:00:00",
            "end": None,
            "alignment": "inner",
            "symbol": "BTCUSD",
            "pit": {},
            "storage": {
                "mode": "cached_only",
                "load_path": "data/raw/dukas_copy_bank/btcusd_h1.csv",
            },
        },
        "features": [],
        "model": {"kind": "none"},
        "signals": {"kind": "none"},
        "risk": {},
        "backtest": {
            "returns_col": "close_logret",
            "signal_col": "signal",
            "periods_per_year": 8760,
            "returns_type": "log",
            "subset": "test",
        },
        "portfolio": {"enabled": False},
        "monitoring": {"enabled": False},
        "execution": {"enabled": False, "capital": 100000.0, "price_col": "close"},
        "logging": {"enabled": False, "run_name": "demo", "output_dir": "logs/experiments"},
        "runtime": {
            "seed": 7,
            "deterministic": True,
            "threads": 1,
            "repro_mode": "strict",
            "seed_torch": False,
        },
    }

    with pytest.raises(ConfigValidationError, match="requires a model that emits an OOS boundary"):
        validate_resolved_config(cfg)
