from __future__ import annotations

from copy import deepcopy

import pytest

from src.utils.config import load_experiment_config
from src.experiments.optuna_search import load_optuna_spec_yaml
from src.utils.config_validation import (
    ConfigValidationError,
    validate_backtest_block,
    validate_diagnostics_block,
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
    validate_standalone_target_block,
)


def test_dukascopy_30m_tft_feature_config_loads() -> None:
    cfg = load_experiment_config("config/experiments/dukascopy_30m_xauusd_tft_feature_forecast_v1.yaml")

    assert cfg["data"]["source"] == "dukascopy_csv"
    assert cfg["data"]["interval"] == "30m"
    assert cfg["model"]["kind"] == "tft_forecaster"
    assert cfg["model"]["target"]["returns_type"] == "log"
    assert cfg["model"]["feature_selectors"]["strict"]["min_count"] >= 32
    assert cfg["backtest"]["periods_per_year"] == 12096


def test_dense_return_forecasting_v2_config_loads_and_validates() -> None:
    cfg = load_experiment_config("config/experiments/dense_return_forecasting_v2.yaml")

    assert cfg["strategy"]["name"] == "dense_return_forecasting_v2"
    assert cfg["model"]["kind"] == "lightgbm_regressor"
    assert cfg["model"]["target"]["kind"] == "future_return_regression"
    assert cfg["signals"]["kind"] == "dense_return_forecast"
    assert cfg["portfolio"]["selection"]["enabled"] is True
    assert cfg["execution"]["hysteresis"]["enabled"] is True
    validate_resolved_config(cfg)


def test_dense_return_forecasting_v2_optuna_spec_loads() -> None:
    spec = load_optuna_spec_yaml("config/optuna/dense_return_forecasting_v2_optuna.yaml")
    dimensions_by_name = {dimension.name: dimension for dimension in spec["search_space"]}

    assert spec["base_config"] == "config/experiments/dense_return_forecasting_v2.yaml"
    assert {"ema_fast", "horizon_bars", "top_k", "entry_threshold", "min_holding_bars"}.issubset(dimensions_by_name)
    horizon = dimensions_by_name["horizon_bars"]
    assert horizon.low == 8
    assert horizon.high == 16
    assert horizon.step == 4
    assert spec["objective"].constraints


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


def test_validate_stc_roofing_hilbert_feature_and_signal_params() -> None:
    validate_features_block(
        [
            {
                "step": "roofing_filter",
                "params": {
                    "price_col": "close",
                    "high_pass_period": 48,
                    "low_pass_period": 10,
                    "slope_bars": 3,
                    "output_col": "roofing_filter",
                },
            },
            {
                "step": "schaff_trend_cycle",
                "params": {
                    "price_col": "close",
                    "fast": 23,
                    "slow": 50,
                    "cycle": 10,
                    "smooth": 3,
                    "long_cross_level": 25.0,
                    "short_cross_level": 75.0,
                },
            },
            {
                "step": "hilbert_transform",
                "params": {
                    "price_col": "close",
                    "window": 64,
                    "amplitude_col": "hilbert_amplitude",
                    "phase_col": "hilbert_phase",
                    "instantaneous_frequency_col": "hilbert_instantaneous_frequency",
                    "min_cycle": 10,
                    "max_cycle": 48,
                    "amplitude_slope_bars": 3,
                },
                "transforms": {
                    "reciprocal": {
                        "params": {
                            "source_col": "hilbert_instantaneous_frequency",
                            "use_abs": True,
                            "output_col": "hilbert_dominant_cycle",
                        }
                    },
                    "between_flag": {
                        "params": {
                            "source_col": "hilbert_dominant_cycle",
                            "lower": 10.0,
                            "upper": 48.0,
                            "output_col": "hilbert_cycle_ok",
                        }
                    },
                    "rising_flag": {
                        "params": {
                            "source_col": "hilbert_amplitude",
                            "periods": 3,
                            "output_col": "hilbert_amplitude_rising",
                        }
                    },
                },
            },
        ]
    )
    validate_signals_block(
        {
            "kind": "stc_roofing_hilbert",
            "params": {
                "mode": "long_short",
                "stc_long_cross_level": 25.0,
                "stc_short_cross_level": 75.0,
                "use_hilbert_filter": False,
                "use_roofing_slope": True,
                "roofing_slope_bars": 3,
                "entry_delay_bars": 0,
            },
        }
    )


def test_validate_stc_roofing_hilbert_rejects_invalid_params() -> None:
    with pytest.raises(ConfigValidationError, match="long_cross_level"):
        validate_features_block(
            [
                {
                    "step": "schaff_trend_cycle",
                    "params": {
                        "fast": 23,
                        "slow": 50,
                        "long_cross_level": 80.0,
                        "short_cross_level": 75.0,
                    },
                }
            ]
        )

    with pytest.raises(ConfigValidationError, match="high_pass_period"):
        validate_features_block(
            [
                {
                    "step": "roofing_filter",
                    "params": {"high_pass_period": 8, "low_pass_period": 8},
                }
            ]
        )

    with pytest.raises(ConfigValidationError, match="entry_delay_bars"):
        validate_signals_block(
            {
                "kind": "stc_roofing_hilbert",
                "params": {"entry_delay_bars": -1},
            }
        )


def test_validate_model_outputs_reject_unknown_keys_and_signals_allow_column_mapping() -> None:
    with pytest.raises(ConfigValidationError, match="model.outputs.bad_key"):
        validate_model_block(
            {
                "kind": "logistic_regression_clf",
                "outputs": {"bad_key": "foo"},
                "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
                "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
            }
        )

    validate_signals_block(
        {
            "kind": "probability_threshold",
            "outputs": {"probability_threshold_signal": "signal_custom"},
            "params": {"prob_col": "pred_prob", "upper": 0.55, "lower": 0.45},
        }
    )

    with pytest.raises(ConfigValidationError, match="target.outputs.bad_key"):
        validate_standalone_target_block(
            {
                "kind": "forward_return",
                "price_col": "close",
                "horizon": 1,
                "outputs": {"bad_key": "custom_label"},
            }
        )


def test_validate_elastic_net_model_block() -> None:
    validate_model_block(
        {
            "kind": "elastic_net_clf",
            "params": {
                "penalty": "elasticnet",
                "solver": "saga",
                "l1_ratio": 0.5,
                "C": 0.5,
                "max_iter": 500,
            },
            "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
            "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
        }
    )

    with pytest.raises(ConfigValidationError, match="l1_ratio"):
        validate_model_block(
            {
                "kind": "elastic_net_clf",
                "params": {
                    "penalty": "elasticnet",
                    "solver": "saga",
                    "l1_ratio": 1.5,
                },
                "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
                "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
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

    with pytest.raises(ConfigValidationError, match="enforce_target_net_exposure"):
        validate_portfolio_block(
            {
                "enabled": True,
                "construction": "signal_weights",
                "constraints": {"enforce_target_net_exposure": "false"},
            }
        )

    validate_portfolio_block(
        {
            "enabled": True,
            "construction": "signal_weights",
            "constraints": {"target_net_exposure": 0.0, "enforce_target_net_exposure": False},
        }
    )


def test_validate_portfolio_barrier_bot_controls() -> None:
    validate_backtest_block(
        {
            "engine": "portfolio_barrier",
            "returns_col": "close_ret",
            "signal_col": "signal",
            "periods_per_year": 12096,
            "returns_type": "simple",
            "missing_return_policy": "raise_if_exposed",
            "min_holding_bars": 0,
            "open_col": "open",
            "high_col": "high",
            "low_col": "low",
            "close_col": "close",
            "volatility_col": "atr_14",
            "profit_barrier_r": 3.0,
            "stop_barrier_r": 2.0,
            "vertical_barrier_bars": None,
            "event_time_remap_policy": "skip",
            "max_cost_r": 0.25,
            "asset_params": {
                "AAA": {
                    "volatility_col": "atr_20",
                    "profit_barrier_r": 4.0,
                    "stop_barrier_r": 2.5,
                    "risk_per_trade": 0.006,
                    "max_cost_r": 0.2,
                    "vertical_barrier_bars": None,
                }
            },
        }
    )
    validate_risk_block(
        {
            "target_vol": None,
            "portfolio_guard": {
                "enabled": True,
                "max_open_trades": 3,
                "group_max_open_trades": {"equity_indices": 2},
                "kill_switch_max_drawdown": 0.08,
            },
        }
    )
    validate_diagnostics_block(
        {
            "enabled": True,
            "robustness": {
                "enabled": True,
                "cost_multipliers": [1.0, 2.0, 3.0],
                "entry_delay_bars": [1, 2],
                "walk_forward_frequency": "YE",
                "gap_loss_per_exposure": 0.001,
                "max_gap_multiple": 3.0,
                "strict_no_remap": True,
                "combined_cost_multipliers": [2.0, 3.0],
                "gross_cap_values": [1.0, 1.25, 1.5],
                "cost_filter_max_cost_r_values": [0.15, 0.2, 0.25],
            },
        }
    )

    with pytest.raises(ConfigValidationError, match="risk_per_trade"):
        validate_backtest_block(
            {
                "engine": "portfolio_barrier",
                "returns_col": "close_ret",
                "signal_col": "signal",
                "periods_per_year": 12096,
                "returns_type": "simple",
                "missing_return_policy": "raise_if_exposed",
                "volatility_col": "atr_14",
                "profit_barrier_r": 3.0,
                "stop_barrier_r": 2.0,
                "asset_params": {"AAA": {"risk_per_trade": 0.0}},
            }
        )

    with pytest.raises(ConfigValidationError, match="event_time_remap_policy"):
        validate_backtest_block(
            {
                "engine": "portfolio_barrier",
                "returns_col": "close_ret",
                "signal_col": "signal",
                "periods_per_year": 12096,
                "returns_type": "simple",
                "missing_return_policy": "raise_if_exposed",
                "volatility_col": "atr_14",
                "profit_barrier_r": 3.0,
                "stop_barrier_r": 2.0,
                "event_time_remap_policy": "bad",
            }
        )

    with pytest.raises(ConfigValidationError, match="max_cost_r"):
        validate_backtest_block(
            {
                "engine": "portfolio_barrier",
                "returns_col": "close_ret",
                "signal_col": "signal",
                "periods_per_year": 12096,
                "returns_type": "simple",
                "missing_return_policy": "raise_if_exposed",
                "volatility_col": "atr_14",
                "profit_barrier_r": 3.0,
                "stop_barrier_r": 2.0,
                "max_cost_r": 0.0,
            }
        )

    with pytest.raises(ConfigValidationError, match="strict_no_remap"):
        validate_diagnostics_block(
            {
                "enabled": True,
                "robustness": {
                    "enabled": True,
                    "strict_no_remap": "yes",
                },
            }
        )

    with pytest.raises(ConfigValidationError, match="cost_filter_max_cost_r_values"):
        validate_diagnostics_block(
            {
                "enabled": True,
                "robustness": {
                    "enabled": True,
                    "cost_filter_max_cost_r_values": [0.0],
                },
            }
        )

    with pytest.raises(ConfigValidationError, match="gross_cap_values"):
        validate_diagnostics_block(
            {
                "enabled": True,
                "robustness": {
                    "enabled": True,
                    "gross_cap_values": [0.0],
                },
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


def test_validate_model_block_accepts_feature_selector_profile_and_families() -> None:
    validate_model_block(
        {
            "kind": "xgboost_clf",
            "feature_selectors": {
                "profile": "ftmo_fx_intraday_balanced_v1",
                "families": {
                    "momentum": False,
                    "cross_asset": True,
                },
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


def test_validate_model_block_rejects_invalid_feature_selector_profile() -> None:
    model = {
        "kind": "xgboost_clf",
        "feature_selectors": {"profile": "unknown_profile_v1"},
        "target": {"kind": "forward_return", "horizon": 1},
        "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
    }

    with pytest.raises(ConfigValidationError, match="profile"):
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


def test_validate_risk_block_accepts_portfolio_guard() -> None:
    validate_risk_block(
        {
            "cost_per_turnover": 0.0,
            "slippage_per_turnover": 0.0,
            "target_vol": None,
            "max_leverage": 1.0,
            "dd_guard": {
                "enabled": True,
                "max_drawdown": 0.12,
                "rearm_drawdown": 0.08,
                "cooloff_bars": 48,
            },
            "portfolio_guard": {
                "enabled": True,
                "weekly_return_target": 0.015,
                "max_daily_loss": 0.025,
                "weekly_drawdown": 0.04,
                "max_total_loss": 0.08,
                "cooloff_bars": 24,
                "rearm_on_new_period": True,
                "weekly_anchor": "W-FRI",
            },
        }
    )


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


def test_validate_features_block_accepts_nested_feature_helpers() -> None:
    validate_features_block(
        [
            {
                "step": "bollinger",
                "enabled": True,
                "params": {"window": 24},
                "transforms": {
                    "rolling_clip": {
                        "enabled": True,
                        "params": {
                            "source_col": "volume_over_atr_24",
                            "output_col": "volume_over_atr_24_rollclip_2520_q01_q99",
                            "window": 2520,
                            "lower_q": 0.01,
                            "upper_q": 0.99,
                            "shift": 1,
                        },
                    },
                    "ratio": {
                        "enabled": True,
                        "params": {
                            "numerator_col": "lag_close_logret_1",
                            "denominator_col": "vol_rolling_24",
                            "output_col": "lag_close_logret_1_over_vol_rolling_24",
                        },
                    },
                    "rolling_zscore": {
                        "enabled": True,
                        "params": {
                            "source_col": "lag_close_logret_1",
                            "output_col": "lag_close_logret_1_z_24",
                            "window": 24,
                            "shift": 0,
                        },
                    },
                },
            },
        ]
    )


def test_validate_features_block_accepts_selector_based_feature_helpers() -> None:
    validate_features_block(
        [
            {
                "step": "returns",
                "params": {"log": True, "col_name": "close_logret"},
                "transforms": {
                    "rolling_clip": {
                        "enabled": True,
                        "params": {
                            "source_selector": {"regex": "^volume_over_atr_[0-9]+$"},
                            "output_col": "volume_over_atr_rollclip",
                        },
                    },
                    "ratio": {
                        "enabled": True,
                        "params": {
                            "numerator_selector": {"exact": "lag_close_logret_1"},
                            "denominator_selector": {"regex": "^vol_rolling_[0-9]+$"},
                            "output_col": "lag_close_logret_1_over_selected_vol",
                        },
                    },
                },
            },
        ]
    )


def test_validate_features_block_accepts_asset_specific_feature_helpers() -> None:
    validate_features_block(
        [
            {
                "step": "returns",
                "params": {"log": False, "col_name": "close_ret"},
                "transforms_by_asset": {
                    "AAA": {
                        "ratio": {
                            "enabled": True,
                            "params": {
                                "numerator_col": "close",
                                "denominator_col": "ema_asset",
                                "output_col": "close_over_ema_asset",
                                "subtract": 1.0,
                            },
                        }
                    }
                },
                "normalizations_by_asset": {
                    "AAA": {
                        "returns": {
                            "enabled": True,
                            "params": {
                                "close_col": "close",
                                "windows": [1, 4],
                                "log_returns": True,
                            },
                        }
                    }
                },
            },
        ]
    )


def test_validate_features_block_rejects_tsfresh_rolling_helper() -> None:
    with pytest.raises(ConfigValidationError, match="unsupported helpers"):
        validate_features_block(
            [
                {
                    "step": "returns",
                    "transforms": {
                        "tsfresh_rolling": {
                            "enabled": True,
                            "params": {"source_col": "close_logret", "window": 48},
                        }
                    },
                },
            ]
        )


def test_validate_features_block_accepts_rms_helper() -> None:
    validate_features_block(
        [
            {
                "step": "returns",
                "transforms": {
                    "rms": {
                        "enabled": True,
                        "params": {
                            "source_col": "close_logret",
                            "window": 48,
                            "shift": 0,
                        },
                    }
                },
            },
        ]
    )


def test_validate_features_block_accepts_stable_indicator_output_columns() -> None:
    validate_features_block(
        [
            {
                "step": "vwap",
                "params": {
                    "windows": [20],
                    "vwap_col": "selected_vwap",
                },
            },
            {
                "step": "ppo",
                "params": {
                    "fast": 12,
                    "slow": 26,
                    "signal": 9,
                    "ppo_col": "selected_ppo",
                    "ppo_signal_col": "selected_ppo_signal",
                    "ppo_hist_col": "selected_ppo_hist",
                },
            },
            {
                "step": "atr",
                "params": {
                    "windows": [14],
                    "atr_col": "selected_atr",
                },
            },
        ]
    )


def test_validate_features_block_rejects_legacy_derived_feature_outputs() -> None:
    with pytest.raises(ConfigValidationError, match="add_distance"):
        validate_features_block([{"step": "vwap", "params": {"add_distance": True}}])

    with pytest.raises(ConfigValidationError, match="distance_col"):
        validate_features_block([{"step": "vwap", "params": {"distance_col": "close_over_vwap_20"}}])

    with pytest.raises(ConfigValidationError, match="add_over_price"):
        validate_features_block([{"step": "atr", "params": {"add_over_price": True}}])

    with pytest.raises(ConfigValidationError, match="over_price_col"):
        validate_features_block([{"step": "atr", "params": {"over_price_col": "atr_over_price_14"}}])

    with pytest.raises(ConfigValidationError, match="add_ratios"):
        validate_features_block([{"step": "trend", "params": {"add_ratios": True}}])


def test_validate_features_block_rejects_stable_vwap_output_columns_for_multiple_windows() -> None:
    with pytest.raises(ConfigValidationError, match="stable VWAP output columns require exactly one window"):
        validate_features_block(
            [
                {
                    "step": "vwap",
                    "params": {"windows": [20, 48], "vwap_col": "selected_vwap"},
                },
            ]
        )


def test_validate_features_block_rejects_stable_atr_output_columns_for_multiple_windows() -> None:
    with pytest.raises(ConfigValidationError, match="stable ATR output columns require exactly one window"):
        validate_features_block(
            [
                {
                    "step": "atr",
                    "params": {"windows": [14, 28], "atr_col": "selected_atr"},
                },
            ]
        )


def test_validate_features_block_rejects_unknown_helper_name() -> None:
    with pytest.raises(ConfigValidationError, match="unsupported helpers"):
        validate_features_block(
            [
                {
                    "step": "returns",
                    "transforms": {
                        "not_a_helper": {
                            "enabled": True,
                            "params": {"source_col": "close_logret"},
                        }
                    },
                },
            ]
        )


def test_validate_features_block_rejects_legacy_rolling_stat_helper() -> None:
    with pytest.raises(ConfigValidationError, match="unsupported helpers"):
        validate_features_block(
            [
                {
                    "step": "returns",
                    "transforms": {
                        "rolling_stat": {
                            "enabled": True,
                            "params": {"source_col": "close_logret", "mode": "future_peek"},
                        }
                    },
                },
            ]
        )


def test_validate_features_block_rejects_ambiguous_feature_transform_selector() -> None:
    with pytest.raises(ConfigValidationError, match="source_col or source_selector"):
        validate_features_block(
            [
                {
                    "step": "returns",
                    "transforms": {
                        "rolling_clip": {
                            "enabled": True,
                            "params": {
                                "source_col": "volume_over_atr_24",
                                "source_selector": {"startswith": "volume_over_atr_"},
                                "output_col": "volume_over_atr_clip",
                            },
                        }
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


def test_validate_features_block_rejects_invalid_feature_helper_kind() -> None:
    with pytest.raises(ConfigValidationError, match="unsupported helpers"):
        validate_features_block(
            [
                {
                    "step": "returns",
                    "transforms": {
                        "bad_kind": {
                            "enabled": True,
                            "params": {
                                "source_col": "volume_over_atr_24",
                                "output_col": "volume_over_atr_24_clip",
                            },
                        }
                    },
                }
            ]
        )


def test_validate_features_block_rejects_invalid_ratio_transform_eps() -> None:
    with pytest.raises(ConfigValidationError, match="eps"):
        validate_features_block(
            [
                {
                    "step": "returns",
                    "transforms": {
                        "ratio": {
                            "enabled": True,
                            "params": {
                                "numerator_col": "lag_close_logret_1",
                                "denominator_col": "vol_rolling_24",
                                "output_col": "lag_close_logret_1_over_vol_rolling_24",
                                "eps": -1.0,
                            },
                        }
                    },
                }
            ]
        )


def test_validate_features_block_rejects_invalid_feature_transform_quantiles() -> None:
    with pytest.raises(ConfigValidationError, match="lower_q"):
        validate_features_block(
            [
                {
                    "step": "returns",
                    "transforms": {
                        "rolling_clip": {
                            "enabled": True,
                            "params": {
                                "source_col": "volume_over_atr_24",
                                "output_col": "volume_over_atr_24_clip",
                                "lower_q": 0.99,
                                "upper_q": 0.01,
                            },
                        }
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


def test_validate_features_block_accepts_superset_window_features() -> None:
    validate_features_block(
        [
            {"step": "atr", "params": {"window": 24, "windows": [14, 18, 24, 30]}},
            {"step": "adx", "params": {"window": 24, "windows": [14, 18, 24, 30]}},
            {
                "step": "regime_context",
                "params": {
                    "vol_short_window": 24,
                    "vol_long_window": 168,
                    "vol_window_pairs": [[12, 120], [24, 168], [36, 240]],
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


def test_validate_backtest_block_accepts_manual_barrier_without_time_exit() -> None:
    validate_backtest_block(
        {
            "engine": "manual_barrier",
            "returns_col": "close_ret",
            "signal_col": "signal",
            "periods_per_year": 12096,
            "returns_type": "simple",
            "missing_return_policy": "raise_if_exposed",
            "subset": "full",
            "stop_mode": "volatility_stop",
            "vol_col": "atr_over_price_14",
            "take_profit_r": 3.0,
            "stop_loss_r": 3.0,
            "risk_per_trade": 0.006,
            "max_holding_bars": None,
        }
    )


def test_validate_backtest_block_rejects_non_positive_manual_barrier_time_exit() -> None:
    with pytest.raises(ConfigValidationError, match="backtest.max_holding_bars"):
        validate_backtest_block(
            {
                "engine": "manual_barrier",
                "returns_col": "close_ret",
                "signal_col": "signal",
                "periods_per_year": 12096,
                "returns_type": "simple",
                "missing_return_policy": "raise_if_exposed",
                "subset": "full",
                "stop_mode": "volatility_stop",
                "vol_col": "atr_over_price_14",
                "take_profit_r": 3.0,
                "stop_loss_r": 3.0,
                "risk_per_trade": 0.006,
                "max_holding_bars": 0,
            }
        )


def test_validate_backtest_block_accepts_portfolio_barrier_engine() -> None:
    validate_backtest_block(
        {
            "engine": "portfolio_barrier",
            "returns_col": "close_ret",
            "signal_col": "signal",
            "periods_per_year": 12096,
            "returns_type": "simple",
            "missing_return_policy": "raise_if_exposed",
            "min_holding_bars": 0,
            "open_col": "open",
            "high_col": "high",
            "low_col": "low",
            "close_col": "close",
            "volatility_col": "atr_14",
            "entry_price_mode": "next_open",
            "profit_barrier_r": 1.4,
            "stop_barrier_r": 1.0,
            "vertical_barrier_bars": 4,
            "tie_break": "closest_to_open",
        }
    )


def test_validate_resolved_config_requires_portfolio_for_portfolio_barrier() -> None:
    cfg = load_experiment_config("config/experiments/indicator_model_adaptive_pullback_barrier.yaml")
    cfg["portfolio"] = dict(cfg["portfolio"])
    cfg["portfolio"]["enabled"] = False

    with pytest.raises(ConfigValidationError, match="portfolio.enabled=true"):
        validate_resolved_config(cfg)


def test_validate_resolved_config_rejects_portfolio_barrier_target_backtest_mismatch() -> None:
    cfg = deepcopy(load_experiment_config("config/experiments/indicator_model_adaptive_pullback_barrier.yaml"))
    cfg["backtest"]["profit_barrier_r"] = float(cfg["model"]["target"]["profit_barrier_r"]) + 0.1

    with pytest.raises(ConfigValidationError, match="portfolio_barrier parity mismatch"):
        validate_resolved_config(cfg)


def test_validate_resolved_config_rejects_portfolio_barrier_signal_ev_mismatch() -> None:
    cfg = deepcopy(load_experiment_config("config/experiments/indicator_model_adaptive_pullback_barrier.yaml"))
    cfg["signals"]["params"]["stop_barrier_r"] = float(cfg["model"]["target"]["stop_barrier_r"]) + 0.1

    with pytest.raises(ConfigValidationError, match="signals.params.stop_barrier_r"):
        validate_resolved_config(cfg)


def test_validate_resolved_config_requires_inner_alignment_for_portfolio_barrier() -> None:
    cfg = deepcopy(load_experiment_config("config/experiments/indicator_model_adaptive_pullback_barrier.yaml"))
    cfg["data"]["alignment"] = "outer"

    with pytest.raises(ConfigValidationError, match="data.alignment='inner'"):
        validate_resolved_config(cfg)


def test_validate_resolved_config_accepts_ftmo_sizing_for_portfolio_barrier() -> None:
    cfg = deepcopy(load_experiment_config("config/experiments/indicator_model_adaptive_pullback_barrier.yaml"))
    cfg["risk"]["sizing"] = {
        "kind": "ftmo_risk_per_trade",
        "output_col": "signal_ftmo_sized",
        "vol_col": "atr_pct",
        "risk_per_trade": 0.0025,
        "stop_mult": 1.0,
        "max_leverage": 0.25,
        "min_abs_signal": 0.5,
    }

    validated = validate_resolved_config(cfg)

    assert validated["risk"]["sizing"]["kind"] == "ftmo_risk_per_trade"


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


def test_validate_model_block_accepts_robust_preprocessing_scaler() -> None:
    model = {
        "kind": "logistic_regression_clf",
        "feature_cols": ["feat_1"],
        "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
        "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
        "preprocessing": {"scaler": "robust"},
    }

    validate_model_block(model)


def test_validate_model_block_rejects_unknown_preprocessing_scaler() -> None:
    model = {
        "kind": "logistic_regression_clf",
        "feature_cols": ["feat_1"],
        "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
        "split": {"method": "walk_forward", "train_size": 100, "test_size": 20},
        "preprocessing": {"scaler": "minmax"},
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


def test_validate_logging_block_rejects_invalid_execution_source_audit_enabled() -> None:
    with pytest.raises(ConfigValidationError, match="logging.execution_source_audit.enabled"):
        validate_logging_block(
            {
                "enabled": True,
                "run_name": "demo",
                "output_dir": "logs/experiments",
                "execution_source_audit": {"enabled": "yes"},
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


def test_validate_signals_block_rejects_non_numeric_vwap_rms_ema_cross_long_ppo_hist_min() -> None:
    with pytest.raises(ConfigValidationError, match="ppo_hist_min"):
        validate_signals_block(
            {
                "kind": "vwap_rms_ema_cross_long",
                "params": {"ppo_hist_min": "0.01"},
            }
        )


def test_validate_signals_block_validates_vwap_rms_ema_cross_long_optional_filters() -> None:
    validate_signals_block(
        {
            "kind": "vwap_rms_ema_cross_long",
            "params": {
                "use_ppo_confirmation": False,
                "use_ema_regime": True,
                "use_vwap_rms_cross": True,
                "use_mfi_confirmation": True,
                "mfi_col": "mfi_14",
                "mfi_lower": 35.0,
                "mfi_upper": 85.0,
                "entry_delay_bars": 2,
            },
        }
    )

    with pytest.raises(ConfigValidationError, match="use_mfi_confirmation"):
        validate_signals_block(
            {
                "kind": "vwap_rms_ema_cross_long",
                "params": {"use_mfi_confirmation": "true"},
            }
        )

    with pytest.raises(ConfigValidationError, match="mfi_lower"):
        validate_signals_block(
            {
                "kind": "vwap_rms_ema_cross_long",
                "params": {"mfi_lower": 90.0, "mfi_upper": 80.0},
            }
        )

    with pytest.raises(ConfigValidationError, match="entry_delay_bars"):
        validate_signals_block(
            {
                "kind": "vwap_rms_ema_cross_long",
                "params": {"entry_delay_bars": -1},
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


def test_validate_signals_block_accepts_manual_long_model_filter_gates() -> None:
    validate_signals_block(
        {
            "kind": "manual_long_model_filter",
            "params": {
                "prob_col": "pred_prob",
                "candidate_col": "manual_long_candidate",
                "base_signal_col": "manual_vol_adjusted_candidate",
                "gate_col": "session_spx_power",
                "gate_cols_any": ["session_spx_power", "session_spx_late"],
                "expected_value_col": None,
                "threshold": 0.42,
                "min_signal_abs": 0.75,
                "min_expected_value_r": 0.18,
                "profit_barrier_r": 1.8,
                "stop_barrier_r": 1.0,
            },
        }
    )


def test_validate_signals_block_rejects_invalid_manual_long_model_filter_gates() -> None:
    with pytest.raises(ConfigValidationError, match="min_signal_abs"):
        validate_signals_block(
            {
                "kind": "manual_long_model_filter",
                "params": {"threshold": 0.42, "min_signal_abs": -0.1},
            }
        )
    with pytest.raises(ConfigValidationError, match="stop_barrier_r"):
        validate_signals_block(
            {
                "kind": "manual_long_model_filter",
                "params": {"threshold": 0.42, "stop_barrier_r": 0.0},
            }
        )
    with pytest.raises(ConfigValidationError, match="gate_cols_any"):
        validate_signals_block(
            {
                "kind": "manual_long_model_filter",
                "params": {"threshold": 0.42, "gate_cols_any": "session_spx_power"},
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


def test_validate_data_block_accepts_dukascopy_csv_with_explicit_load_paths() -> None:
    validate_data_block(
        {
            "source": "dukascopy_csv",
            "symbols": ["EURUSD", "GBPUSD"],
            "interval": "1h",
            "storage": {
                "mode": "cached_only",
                "load_paths": {
                    "EURUSD": "data/raw/dukas_copy_bank/eurusd_h1.csv",
                    "GBPUSD": "data/raw/dukas_copy_bank/gbpusd_h1.csv",
                },
            },
        }
    )


def test_validate_data_block_rejects_dukascopy_csv_without_load_path() -> None:
    with pytest.raises(ConfigValidationError, match="data.storage.load_path or data.storage.load_paths is required"):
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
