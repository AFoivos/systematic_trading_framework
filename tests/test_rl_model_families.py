from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap

import pytest
import numpy as np

from src.experiments.registry import MODEL_REGISTRY
from src.utils.config_validation import ConfigValidationError, validate_model_block, validate_resolved_config
from src.models.rl.envs import RLExecutionConfig, RLRewardConfig, SingleAssetTradingEnv


def _base_rl_model_cfg(*, signal_col: str = "signal_rl") -> dict[str, object]:
    return {
        "feature_cols": ["lag_close_ret_1", "lag_close_ret_2", "vol_rolling_8"],
        "signal_col": signal_col,
        "action_col": "action_rl",
        "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
        "split": {
            "method": "walk_forward",
            "train_size": 72,
            "test_size": 24,
            "step_size": 24,
            "expanding": False,
            "max_folds": 1,
        },
        "runtime": {"seed": 7, "deterministic": True, "threads": 1, "repro_mode": "strict"},
        "backtest": {"returns_col": "close_ret", "returns_type": "simple"},
        "env": {
            "window_size": 8,
            "execution_lag_bars": 1,
            "max_signal_abs": 1.0,
            "reward": {
                "cost_per_turnover": 0.0001,
                "slippage_per_turnover": 0.0,
                "inventory_penalty": 0.0,
                "drawdown_penalty": 0.0,
            },
        },
    }


def _ppo_params() -> dict[str, object]:
    return {
        "total_timesteps": 64,
        "n_steps": 16,
        "batch_size": 16,
        "learning_rate": 3e-4,
        "gamma": 0.99,
        "device": "cpu",
        "extractor": {"kind": "flatten", "features_dim": 16},
    }


def _dqn_params() -> dict[str, object]:
    return {
        "total_timesteps": 64,
        "learning_starts": 0,
        "buffer_size": 256,
        "batch_size": 16,
        "train_freq": 1,
        "gradient_steps": 1,
        "target_update_interval": 32,
        "learning_rate": 1e-3,
        "gamma": 0.99,
        "device": "cpu",
        "extractor": {"kind": "flatten", "features_dim": 16},
    }


def _portfolio_cfg() -> dict[str, object]:
    return {
        "enabled": True,
        "construction": "signal_weights",
        "gross_target": 1.0,
        "long_short": True,
        "constraints": {
            "min_weight": -0.75,
            "max_weight": 0.75,
            "max_gross_leverage": 1.0,
            "target_net_exposure": 0.0,
            "turnover_limit": 0.75,
        },
    }


def _resolved_rl_config(
    *,
    model_kind: str,
    signals_kind: str = "none",
    backtest_signal_col: str = "signal_rl",
) -> dict[str, object]:
    return {
        "data": {
            "symbol": "AAA",
            "source": "yahoo",
            "interval": "1h",
            "start": "2024-01-01",
            "end": None,
            "alignment": "inner",
            "pit": {},
            "storage": {"mode": "live"},
        },
        "features": [
            {"step": "returns", "params": {"log": False, "col_name": "close_ret"}},
            {"step": "lags", "params": {"cols": ["close_ret"], "lags": [1, 2]}},
        ],
        "model": {
            "kind": model_kind,
            **_base_rl_model_cfg(),
            "params": _ppo_params(),
        },
        "signals": {"kind": signals_kind, "params": {}},
        "risk": {
            "cost_per_turnover": 0.0001,
            "slippage_per_turnover": 0.0,
            "target_vol": None,
            "max_leverage": 1.0,
            "dd_guard": {"enabled": False, "max_drawdown": 0.2, "cooloff_bars": 5},
        },
        "backtest": {
            "returns_col": "close_ret",
            "signal_col": backtest_signal_col,
            "periods_per_year": 6048,
            "returns_type": "simple",
            "missing_return_policy": "raise_if_exposed",
        },
        "portfolio": {
            "enabled": False,
            "construction": "signal_weights",
            "gross_target": 1.0,
            "long_short": True,
            "constraints": {},
            "asset_groups": {},
        },
        "monitoring": {"enabled": False, "psi_threshold": 0.1, "n_bins": 8},
        "execution": {"enabled": False, "mode": "paper", "capital": 100_000.0, "price_col": "close"},
        "logging": {"enabled": False, "run_name": "rl_cfg", "output_dir": "logs/experiments"},
        "runtime": {"seed": 7, "repro_mode": "strict", "deterministic": True, "threads": 1, "seed_torch": False},
    }


def _torch_stack_available_in_subprocess() -> bool:
    proc = subprocess.run(
        [sys.executable, "-c", "import torch, stable_baselines3, gymnasium; print('ok')"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def _run_python_json(script: str, *args: str) -> dict[str, object]:
    env = dict(os.environ)
    env["OMP_NUM_THREADS"] = "1"
    env["MKL_NUM_THREADS"] = "1"
    env["OPENBLAS_NUM_THREADS"] = "1"
    env["NUMEXPR_NUM_THREADS"] = "1"
    env["VECLIB_MAXIMUM_THREADS"] = "1"
    env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    env["MPLBACKEND"] = "Agg"
    env["MPLCONFIGDIR"] = env.get("TMPDIR", "/tmp")
    proc = subprocess.run(
        [sys.executable, "-c", script, *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if proc.returncode != 0:
        if "Fatal Python error: Aborted" in proc.stderr or "OMP: Error #179" in proc.stderr:
            pytest.skip("RL subprocess run is unstable in this environment.")
        raise AssertionError(proc.stderr or proc.stdout)
    return json.loads(proc.stdout)


def _script_prelude() -> str:
    return textwrap.dedent(
        """
        import json
        import numpy as np
        import pandas as pd

        def synthetic_hourly_ohlcv(periods=120, seed=7, amplitude=0.003):
            rng = np.random.default_rng(seed)
            base = np.where(np.arange(periods) % 3 == 0, amplitude, -amplitude / 2.0)
            returns = base + rng.normal(0.0, amplitude / 4.0, size=periods)
            close = 100.0 * np.exp(np.cumsum(returns))
            idx = pd.date_range("2024-01-01", periods=periods, freq="h")
            df = pd.DataFrame(index=idx)
            df["close"] = close
            df["open"] = df["close"].shift(1).fillna(df["close"].iloc[0] * 0.999)
            df["high"] = np.maximum(df["open"], df["close"]) * 1.0015
            df["low"] = np.minimum(df["open"], df["close"]) * 0.9985
            df["volume"] = 100_000 + rng.integers(0, 2_500, size=periods)
            df["close_ret"] = df["close"].pct_change()
            df["lag_close_ret_1"] = df["close_ret"].shift(1)
            df["lag_close_ret_2"] = df["close_ret"].shift(2)
            df["vol_rolling_8"] = df["close_ret"].rolling(8, min_periods=3).std()
            return df

        def asset_panel():
            return {
                "AAA": synthetic_hourly_ohlcv(seed=11, amplitude=0.0032),
                "BBB": synthetic_hourly_ohlcv(seed=19, amplitude=0.0026),
            }
        """
    )


RL_SUBPROCESS_ONLY = pytest.mark.skipif(
    not _torch_stack_available_in_subprocess(),
    reason="torch / stable-baselines3 stack is unavailable in subprocess.",
)


def test_registry_contains_rl_model_kinds() -> None:
    for model_kind in ("ppo_agent", "dqn_agent", "ppo_portfolio_agent", "dqn_portfolio_agent"):
        assert model_kind in MODEL_REGISTRY


def test_validate_model_block_rejects_continuous_dqn_action_space() -> None:
    model = {
        "kind": "dqn_agent",
        **_base_rl_model_cfg(),
        "params": _dqn_params(),
        "env": {
            **dict(_base_rl_model_cfg()["env"]),
            "action_space": "continuous",
        },
    }

    with pytest.raises(ConfigValidationError, match="DQN agents require"):
        validate_model_block(model)


def test_single_asset_env_enforces_min_holding_bars_and_switching_penalty() -> None:
    env = SingleAssetTradingEnv(
        features=np.zeros((6, 1), dtype=np.float32),
        simple_returns=np.zeros(6, dtype=np.float32),
        window_size=2,
        continuous_actions=False,
        max_signal_abs=1.0,
        discrete_action_values=[-1.0, 0.0, 1.0],
        reward_config=RLRewardConfig(switching_penalty=0.1),
        execution_config=RLExecutionConfig(min_holding_bars=2),
    )
    env.reset()

    _, reward_1, _, _, info_1 = env.step(2)
    _, reward_2, _, _, info_2 = env.step(0)
    _, reward_3, _, _, info_3 = env.step(0)
    _, reward_4, _, _, info_4 = env.step(0)

    assert np.isclose(info_1["position"], 1.0)
    assert np.isclose(reward_1, -0.1)
    assert np.isclose(info_2["position"], 1.0)
    assert np.isclose(reward_2, 0.0)
    assert np.isclose(info_3["position"], 1.0)
    assert np.isclose(reward_3, 0.0)
    assert np.isclose(info_4["position"], -1.0)
    assert np.isclose(reward_4, -0.1)


def test_single_asset_env_dd_guard_forces_future_flat_cooloff() -> None:
    env = SingleAssetTradingEnv(
        features=np.zeros((6, 1), dtype=np.float32),
        simple_returns=np.array([0.0, -0.3, 0.05, 0.05, 0.05, 0.05], dtype=np.float32),
        window_size=2,
        continuous_actions=False,
        max_signal_abs=1.0,
        discrete_action_values=[0.0, 1.0],
        reward_config=RLRewardConfig(),
        execution_config=RLExecutionConfig(
            dd_guard_enabled=True,
            max_drawdown=0.1,
            cooloff_bars=1,
            rearm_drawdown=0.05,
        ),
    )
    env.reset()

    _, _, _, _, info_1 = env.step(1)
    _, _, _, _, info_2 = env.step(1)
    _, _, _, _, info_3 = env.step(1)

    assert info_1["position"] == 1.0
    assert info_2["position"] == 0.0
    assert info_3["position"] == 1.0


def test_validate_resolved_config_rejects_rl_signal_pipeline_mismatch() -> None:
    cfg = _resolved_rl_config(
        model_kind="ppo_agent",
        signals_kind="probability_threshold",
        backtest_signal_col="signal_wrong",
    )

    with pytest.raises(ConfigValidationError, match="signals.kind='none'"):
        validate_resolved_config(cfg)


@RL_SUBPROCESS_ONLY
def test_ppo_agent_emits_oos_signals() -> None:
    model_cfg = {
        "kind": "ppo_agent",
        **_base_rl_model_cfg(),
        "params": _ppo_params(),
        "env": {
            **dict(_base_rl_model_cfg()["env"]),
            "action_space": "continuous",
        },
    }
    script = _script_prelude() + textwrap.dedent(
        f"""
        from src.experiments.models import train_ppo_agent

        df = synthetic_hourly_ohlcv()
        model_cfg = json.loads({json.dumps(model_cfg)!r})
        out, _, meta = train_ppo_agent(df, model_cfg, returns_col="close_ret")
        payload = {{
            "model_kind": meta["model_kind"],
            "oos_rows": int(out["pred_is_oos"].sum()),
            "signal_non_null": bool(out.loc[out["pred_is_oos"], "signal_rl"].notna().all()),
            "action_non_null": bool(out.loc[out["pred_is_oos"], "action_rl"].notna().all()),
            "max_abs_signal": float(out.loc[out["pred_is_oos"], "signal_rl"].abs().max()),
            "signal_rows": int(meta["oos_policy_summary"]["signal_rows"]),
        }}
        print(json.dumps(payload, sort_keys=True))
        """
    )

    payload = _run_python_json(script)

    assert payload["model_kind"] == "ppo_agent"
    assert payload["oos_rows"] == 24
    assert payload["signal_non_null"] is True
    assert payload["action_non_null"] is True
    assert float(payload["max_abs_signal"]) <= 1.0 + 1e-6
    assert payload["signal_rows"] > 0


@RL_SUBPROCESS_ONLY
def test_dqn_agent_respects_discrete_position_grid() -> None:
    model_cfg = {
        "kind": "dqn_agent",
        **_base_rl_model_cfg(),
        "params": _dqn_params(),
        "env": {
            **dict(_base_rl_model_cfg()["env"]),
            "action_space": "discrete",
            "position_grid": [-1.0, 0.0, 1.0],
        },
    }
    script = _script_prelude() + textwrap.dedent(
        f"""
        from src.experiments.models import train_dqn_agent

        df = synthetic_hourly_ohlcv(seed=13)
        model_cfg = json.loads({json.dumps(model_cfg)!r})
        out, _, meta = train_dqn_agent(df, model_cfg, returns_col="close_ret")
        observed = sorted(set(out.loc[out["pred_is_oos"], "signal_rl"].dropna().round(6).tolist()))
        payload = {{
            "model_kind": meta["model_kind"],
            "observed": observed,
            "signal_rows": int(meta["oos_policy_summary"]["signal_rows"]),
        }}
        print(json.dumps(payload, sort_keys=True))
        """
    )

    payload = _run_python_json(script)

    assert payload["model_kind"] == "dqn_agent"
    assert set(payload["observed"]) <= {-1.0, 0.0, 1.0}
    assert payload["signal_rows"] > 0


@RL_SUBPROCESS_ONLY
def test_apply_model_to_assets_supports_per_asset_ppo_panel() -> None:
    model_cfg = {
        "kind": "ppo_agent",
        **_base_rl_model_cfg(),
        "params": _ppo_params(),
        "portfolio": _portfolio_cfg(),
        "env": {
            **dict(_base_rl_model_cfg()["env"]),
            "action_space": "continuous",
        },
    }
    script = _script_prelude() + textwrap.dedent(
        f"""
        from src.experiments.orchestration.model_stage import apply_model_to_assets

        asset_frames = asset_panel()
        model_cfg = json.loads({json.dumps(model_cfg)!r})
        out, models, meta = apply_model_to_assets(asset_frames, model_cfg=model_cfg, returns_col="close_ret")
        payload = {{
            "assets": sorted(out),
            "models_is_dict": isinstance(models, dict),
            "model_kind": meta["model_kind"],
            "per_asset": sorted(meta["per_asset"]),
            "signal_rows": int(meta["oos_policy_summary"]["signal_rows"]),
            "all_signals_present": bool(all(frame.loc[frame["pred_is_oos"], "signal_rl"].notna().all() for frame in out.values())),
        }}
        print(json.dumps(payload, sort_keys=True))
        """
    )

    payload = _run_python_json(script)

    assert payload["assets"] == ["AAA", "BBB"]
    assert payload["models_is_dict"] is True
    assert payload["model_kind"] == "ppo_agent"
    assert payload["per_asset"] == ["AAA", "BBB"]
    assert payload["signal_rows"] > 0
    assert payload["all_signals_present"] is True


@RL_SUBPROCESS_ONLY
def test_dqn_portfolio_agent_emits_discrete_template_signals() -> None:
    model_cfg = {
        "kind": "dqn_portfolio_agent",
        **_base_rl_model_cfg(),
        "params": _dqn_params(),
        "portfolio": _portfolio_cfg(),
        "data_alignment": "inner",
        "env": {
            **dict(_base_rl_model_cfg()["env"]),
            "action_space": "discrete",
            "action_templates": [[0.0, 0.0], [1.0, -1.0], [-1.0, 1.0]],
        },
    }
    script = _script_prelude() + textwrap.dedent(
        f"""
        from src.experiments.models import train_dqn_portfolio_agent

        asset_frames = asset_panel()
        model_cfg = json.loads({json.dumps(model_cfg)!r})
        out, _, meta = train_dqn_portfolio_agent(asset_frames, model_cfg, returns_col="close_ret")
        observed = {{
            asset: sorted(set(frame.loc[frame["pred_is_oos"], "signal_rl"].dropna().round(6).tolist()))
            for asset, frame in out.items()
        }}
        payload = {{
            "model_kind": meta["model_kind"],
            "scope": meta["scope"],
            "evaluation_rows": int(meta["oos_policy_summary"]["evaluation_rows"]),
            "signal_rows": int(meta["aggregated_per_asset_policy_summary"]["signal_rows"]),
            "observed": observed,
        }}
        print(json.dumps(payload, sort_keys=True))
        """
    )

    payload = _run_python_json(script)

    assert payload["model_kind"] == "dqn_portfolio_agent"
    assert payload["scope"] == "portfolio"
    assert payload["evaluation_rows"] > 0
    assert payload["signal_rows"] > 0
    for observed in payload["observed"].values():
        assert set(observed) <= {-1.0, 0.0, 1.0}


@RL_SUBPROCESS_ONLY
def test_run_experiment_supports_ppo_portfolio_agent(tmp_path) -> None:
    config = {
        "data": {
            "symbols": ["AAA", "BBB"],
            "source": "yahoo",
            "interval": "1h",
            "start": "2024-01-01",
            "end": None,
            "alignment": "inner",
            "storage": {"mode": "live"},
        },
        "features": [
            {"step": "returns", "params": {"log": False, "col_name": "close_ret"}},
            {"step": "lags", "params": {"cols": ["close_ret"], "lags": [1, 2]}},
            {"step": "volatility", "params": {"returns_col": "close_ret", "rolling_windows": [8], "ewma_spans": []}},
        ],
        "model": {
            "kind": "ppo_portfolio_agent",
            **_base_rl_model_cfg(),
            "params": _ppo_params(),
            "env": {
                **dict(_base_rl_model_cfg()["env"]),
                "action_space": "continuous",
            },
        },
        "signals": {"kind": "none", "params": {}},
        "portfolio": _portfolio_cfg(),
        "risk": {
            "cost_per_turnover": 0.0001,
            "slippage_per_turnover": 0.0,
            "target_vol": None,
            "max_leverage": 1.0,
            "dd_guard": {"enabled": False, "max_drawdown": 0.2, "cooloff_bars": 5},
        },
        "backtest": {
            "returns_col": "close_ret",
            "signal_col": "signal_rl",
            "periods_per_year": 6048,
            "returns_type": "simple",
            "missing_return_policy": "raise_if_exposed",
        },
        "monitoring": {"enabled": False, "psi_threshold": 0.1, "n_bins": 8},
        "execution": {"enabled": False, "mode": "paper", "capital": 100_000.0, "price_col": "close"},
        "logging": {"enabled": False, "run_name": "ppo_portfolio_agent", "output_dir": "logs/experiments"},
        "runtime": {"seed": 7, "repro_mode": "strict", "deterministic": True, "threads": 1, "seed_torch": False},
    }
    config_path = tmp_path / "ppo_portfolio_agent.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    script = _script_prelude() + textwrap.dedent(
        """
        import sys

        import src.experiments.runner as runner_mod

        panel = asset_panel()

        def mock_load_panel(**kwargs):
            requested = kwargs["symbols"]
            return {symbol: panel[symbol].copy() for symbol in requested}

        runner_mod.load_ohlcv_panel = mock_load_panel
        result = runner_mod.run_experiment(sys.argv[1])
        payload = {
            "model_kind": result.model_meta["model_kind"],
            "scope": result.model_meta["scope"],
            "evaluation_scope": result.evaluation["scope"],
            "has_portfolio_weights": result.portfolio_weights is not None,
            "is_dict_data": isinstance(result.data, dict),
            "all_signals_present": bool(all(frame.loc[frame["pred_is_oos"], "signal_rl"].notna().all() for frame in result.data.values())),
        }
        print(json.dumps(payload, sort_keys=True))
        """
    )

    payload = _run_python_json(script, str(config_path))

    assert payload["model_kind"] == "ppo_portfolio_agent"
    assert payload["scope"] == "portfolio"
    assert payload["evaluation_scope"] == "strict_oos_only"
    assert payload["has_portfolio_weights"] is True
    assert payload["is_dict_data"] is True
    assert payload["all_signals_present"] is True
