from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from tests.optional_dependencies import (
    is_optional_dependency_runtime_failure,
    optional_dependency_stack_available,
)


RL_SUBPROCESS_ONLY = pytest.mark.skipif(
    not optional_dependency_stack_available(
        "torch",
        "stable_baselines3",
        "gymnasium",
        limit_native_threads=True,
    ),
    reason="torch / stable-baselines3 stack is unavailable in subprocess.",
)


@RL_SUBPROCESS_ONLY
def test_ppo_risk_yaml_end_to_end_smoke(tmp_path: Path) -> None:
    """Load YAML, build features/folds, train/save/load PPO, evaluate, and persist artifacts."""
    script = textwrap.dedent(
        """
        import json
        from pathlib import Path
        import sys

        import numpy as np
        import pandas as pd
        from stable_baselines3 import PPO

        from src.experiments.orchestration.feature_stage import apply_feature_steps
        from src.models.rl.risk_pipeline import train_ppo_risk_agent
        from src.utils.config import load_experiment_config

        config_path = Path(sys.argv[1])
        artifact_dir = Path(sys.argv[2])
        cfg = load_experiment_config(config_path)

        periods = 96
        index = pd.date_range("2025-01-01", periods=periods, freq="30min", tz="UTC")
        phase = np.arange(periods, dtype=float)
        close = 2000.0 + 0.08 * phase + 2.0 * np.sin(phase / 4.0)
        open_ = np.r_[close[0], close[:-1]]
        frame = pd.DataFrame(
            {
                "open": open_,
                "high": np.maximum(open_, close) + 0.8,
                "low": np.minimum(open_, close) - 0.8,
                "close": close,
                "volume": np.full(periods, 1000.0),
            },
            index=index,
        )
        featured = apply_feature_steps(frame, list(cfg["features"]), asset="XAUUSD")

        model_cfg = dict(cfg["model"])
        model_cfg["split"] = {
            "method": "walk_forward",
            "train_size": 32,
            "validation_size": 10,
            "test_size": 10,
            "train_tail_size": 10,
            "step_size": 10,
            "expanding": False,
            "max_folds": 1,
        }
        env_cfg = dict(model_cfg["env"])
        env_cfg.update(
            {
                "window_size": 4,
                "lookback_window": 4,
                "max_holding_bars": 5,
                "consistency_gate": {
                    "minimum_profitable_fold_ratio": 0.0,
                    "minimum_median_test_return": -1.0,
                },
            }
        )
        model_cfg["env"] = env_cfg
        params = dict(model_cfg["params"])
        params.update(
            {
                "total_timesteps": 4,
                "checkpoint_interval": 4,
                "n_steps": 4,
                "batch_size": 4,
                "artifact_dir": str(artifact_dir),
                "run_name": "smoke",
                "device": "cpu",
            }
        )
        model_cfg["params"] = params
        model_cfg["runtime"] = {
            "seed": 11,
            "repro_mode": "strict",
            "deterministic": True,
            "threads": 1,
            "seed_torch": True,
        }

        output, champion, meta = train_ppo_risk_agent(
            featured,
            model_cfg,
            returns_col="close_ret",
        )
        root = Path(meta["artifact_root"])
        selected_checkpoint = Path(meta["folds"][0]["selected_checkpoint"])
        reloaded = PPO.load(str(selected_checkpoint), device="cpu")
        payload = {
            "champion_loaded": champion is not None,
            "checkpoint_reloaded": reloaded is not None,
            "checkpoint_exists": selected_checkpoint.exists(),
            "fold_count": len(meta["folds"]),
            "oos_rows": int(output["pred_is_oos"].sum()),
            "environment_return_rows": int(output["rl_net_return"].notna().sum()),
            "validation_steps": int(meta["folds"][0]["validation_metrics"]["evaluation_steps"]),
            "test_steps": int(meta["folds"][0]["test_metrics"]["evaluation_steps"]),
            "run_summary_exists": (root / "run_summary.json").exists(),
            "gate_exists": (root / "consistency_gate.json").exists(),
            "fold_result_exists": (root / "fold_000" / "result.json").exists(),
            "trades_exists": (root / "fold_000" / "trades.json").exists(),
        }
        print(json.dumps(payload, sort_keys=True))
        """
    )
    env = dict(os.environ)
    env.update(
        {
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "VECLIB_MAXIMUM_THREADS": "1",
            "KMP_DUPLICATE_LIB_OK": "TRUE",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(tmp_path / "mplconfig"),
        }
    )
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            "config/experiments/rl/xauusd_30m_ppo_risk_walk_forward.yaml",
            str(tmp_path / "rl_artifacts"),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if proc.returncode != 0:
        if is_optional_dependency_runtime_failure(
            proc,
            modules=("torch", "stable_baselines3", "gymnasium"),
        ):
            pytest.skip("RL subprocess run is unstable in this environment.")
        raise AssertionError(proc.stderr or proc.stdout)
    payload = json.loads(proc.stdout)

    assert payload == {
        "champion_loaded": True,
        "checkpoint_reloaded": True,
        "checkpoint_exists": True,
        "fold_count": 1,
        "oos_rows": 10,
        "environment_return_rows": 10,
        "validation_steps": 10,
        "test_steps": 10,
        "run_summary_exists": True,
        "gate_exists": True,
        "fold_result_exists": True,
        "trades_exists": True,
    }
