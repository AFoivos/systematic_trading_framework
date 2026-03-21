from __future__ import annotations

import pytest

from src.utils.config_validation import (
    ConfigValidationError,
    validate_execution_block,
    validate_model_block,
    validate_portfolio_block,
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
