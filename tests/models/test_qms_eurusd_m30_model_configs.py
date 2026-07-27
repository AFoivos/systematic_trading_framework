from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.evaluation.contracts import TargetContract, validate_feature_target_contract
from src.experiments.orchestration.feature_stage import apply_feature_steps
from src.models.rl.risk_env import RiskRewardConfig, RiskTradeConfig, SingleAssetRiskTradingEnv
from src.models.transforms.qms_candidate import apply_qms_candidate_transform
from src.models.transforms.qms_candidate_policy import apply_qms_candidate_policy_transform
from src.targets.registry import build_target
from src.utils.config import load_experiment_config


CONFIG_DIR = Path("config/experiments/qms_eurusd_m30_models")
EXPECTED_FILES = {
    "01_eurusd_30m_qms_future_volatility_lgbm_v1.yaml",
    "02_eurusd_30m_qms_multi_horizon_normalized_return_lgbm_v1.yaml",
    "03_eurusd_30m_qms_candidate_meta_logreg_v1.yaml",
    "04_eurusd_30m_qms_ppo_risk_sizing_exits_v1.yaml",
    "05_eurusd_30m_qms_trend_pullback_oos_baseline_v1.yaml",
    "06_eurusd_30m_qms_trend_pullback_atr_gate_v1.yaml",
    "07_eurusd_30m_qms_trend_pullback_forecast_vol_gate_v1.yaml",
    "08_eurusd_30m_qms_trend_pullback_forecast_vol_sized_v1.yaml",
    "09_eurusd_30m_qms_trend_pullback_forecast_vol_meta_v1.yaml",
    "10_eurusd_30m_qms_compression_breakout_session_forecast_v1.yaml",
}


@pytest.fixture(scope="module")
def configs() -> dict[str, dict]:
    paths = sorted(CONFIG_DIR.glob("*.yaml"))
    assert {path.name for path in paths} == EXPECTED_FILES
    return {path.name: load_experiment_config(path) for path in paths}


@pytest.fixture(scope="module")
def featured_frame(configs: dict[str, dict]) -> pd.DataFrame:
    periods = 1_800
    index = pd.date_range("2024-01-01", periods=periods, freq="30min", tz="UTC")
    rng = np.random.default_rng(7)
    phase = np.arange(periods, dtype=float)
    returns = (
        0.00006 * np.sin(phase / 31.0)
        + 0.00004 * np.sin(phase / 7.0)
        + rng.normal(0.0, 0.00018, size=periods)
    )
    close = 1.08 * np.exp(np.cumsum(returns))
    open_ = np.r_[close[0], close[:-1]]
    half_range = 0.00035 + 0.00008 * (1.0 + np.sin(phase / 13.0))
    raw = pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) + half_range,
            "low": np.minimum(open_, close) - half_range,
            "close": close,
            "volume": np.full(periods, 1_000.0),
        },
        index=index,
    )
    first = configs["01_eurusd_30m_qms_future_volatility_lgbm_v1.yaml"]
    return apply_feature_steps(raw, list(first["features"]), asset="EURUSD")


def test_ten_configs_are_causal_m30_research_specs(configs: dict[str, dict]) -> None:
    for cfg in configs.values():
        qms_step = next(step for step in cfg["features"] if step["step"] == "quant_market_state")
        load_path = Path(cfg["data"]["storage"]["load_path"])

        assert cfg["strategy"]["symbol"] == "EURUSD"
        assert cfg["strategy"]["timeframe"] == "M30"
        assert cfg["data"]["interval"] == "30m"
        assert qms_step["params"]["bar_minutes"] == 30.0
        assert load_path == Path("data/raw/dukascopy_30m_clean/eurusd_30m.csv").resolve()
        assert load_path.is_file()
        assert cfg["backtest"]["periods_per_year"] == 12_096
        assert cfg["evaluation"]["strict_oos_only"] is True

    volatility_cfg = configs["01_eurusd_30m_qms_future_volatility_lgbm_v1.yaml"]
    assert volatility_cfg["model"]["kind"] == "lightgbm_regressor"
    assert volatility_cfg["model"]["target"]["kind"] == "future_realized_volatility"
    assert volatility_cfg["signals"]["kind"] == "none"

    multi_cfg = configs["02_eurusd_30m_qms_multi_horizon_normalized_return_lgbm_v1.yaml"]
    assert [stage["target"]["horizon_bars"] for stage in multi_cfg["model_stages"]] == [8, 16, 48]
    assert len({stage["pred_ret_col"] for stage in multi_cfg["model_stages"]}) == 3
    assert all(stage["split"]["purge_bars"] >= 48 for stage in multi_cfg["model_stages"])

    meta_cfg = configs["03_eurusd_30m_qms_candidate_meta_logreg_v1.yaml"]
    assert [stage["kind"] for stage in meta_cfg["model_stages"]] == [
        "qms_candidate_transform",
        "logistic_regression_clf",
    ]
    assert meta_cfg["signals"]["params"]["pred_is_oos_col"] == "qms_meta_pred_is_oos"

    rl_cfg = configs["04_eurusd_30m_qms_ppo_risk_sizing_exits_v1.yaml"]
    assert rl_cfg["model"]["kind"] == "ppo_risk_agent"
    assert rl_cfg["model"]["env"]["execution_lag_bars"] == 1
    assert rl_cfg["risk"]["cost_per_turnover"] == 0.0
    assert rl_cfg["risk"]["slippage_per_turnover"] == 0.0


def test_five_alpha_ladder_configs_share_one_precommitted_oos_contract(
    configs: dict[str, dict],
) -> None:
    ladder_names = sorted(name for name in configs if name.startswith(("05_", "06_", "07_", "08_", "09_")))
    assert len(ladder_names) == 5

    for name in ladder_names:
        cfg = configs[name]
        stages = cfg["model_stages"]
        assert stages[0]["kind"] == "lightgbm_regressor"
        assert stages[0]["feature_cols"] == [
            "atr_over_price_48",
            "rlv_term_structure",
            "rlv_fast_slow_ratio",
            "rlv_shock_z",
            "rlv_vol_of_vol_ratio",
            "qms_post_gap_age",
        ]
        assert stages[0]["split"] == {
            "method": "purged",
            "train_size": 26_280,
            "test_size": 4_380,
            "step_size": 4_380,
            "expanding": True,
            "max_folds": 10,
            "purge_bars": 16,
            "embargo_bars": 16,
        }
        assert stages[1]["kind"] == "qms_candidate_transform"
        assert stages[1]["params"]["strategies"] == ["kds_pullback_continuation"]
        policy_stage = next(
            stage for stage in stages if stage["kind"] == "qms_candidate_policy_transform"
        )
        assert policy_stage["params"]["pred_is_oos_col"] == "pred_future_rv_16_is_oos"
        assert policy_stage["params"]["side_alignment_cols"] == ["kadx_signed"]
        assert cfg["backtest"]["max_holding_bars"] == 16
        assert cfg["backtest"]["take_profit_r"] == 1.75
        assert cfg["backtest"]["stop_loss_r"] == 1.25
        assert cfg["risk"]["max_leverage"] == 1.0
        assert cfg["risk"]["cost_per_turnover"] == 0.00004
        assert cfg["risk"]["slippage_per_turnover"] == 0.00002

    assert configs[ladder_names[0]]["model_stages"][2]["params"]["gate"]["kind"] == "none"
    assert configs[ladder_names[1]]["model_stages"][2]["params"]["gate"]["kind"] == "atr_regime"
    assert configs[ladder_names[2]]["model_stages"][2]["params"]["gate"]["kind"] == "forecast_expansion"
    assert configs[ladder_names[3]]["model_stages"][2]["params"]["sizing"]["kind"] == "inverse_forecast_vol"
    meta_stage = configs[ladder_names[4]]["model_stages"][-1]
    assert meta_stage["kind"] == "logistic_regression_clf"
    assert meta_stage["split"]["train_size"] > 26_280
    assert "qms_policy_expansion_ratio" in meta_stage["feature_cols"]
    assert not any(
        column.startswith(("target_", "label", "pred_"))
        for column in meta_stage["feature_cols"]
    )


def test_compression_breakout_config_is_precommitted_without_meta_model(
    configs: dict[str, dict],
) -> None:
    cfg = configs["10_eurusd_30m_qms_compression_breakout_session_forecast_v1.yaml"]
    stages = cfg["model_stages"]
    session_step = next(step for step in cfg["features"] if step["step"] == "session_context")
    candidate = stages[1]
    policy = stages[2]

    assert [stage["kind"] for stage in stages] == [
        "lightgbm_regressor",
        "qms_candidate_transform",
        "qms_candidate_policy_transform",
    ]
    assert session_step["params"] == {
        "timezone": "UTC",
        "add_cyclical_time": False,
        "include_weekend_flag": False,
        "sessions": {"london_ny_liquid": [7, 17]},
    }
    assert candidate["params"]["strategies"] == ["volatility_compression_breakout"]
    assert candidate["params"]["common_params"]["setup_lookback_bars"] == 8
    assert policy["params"]["side_alignment_cols"] == ["kadx_signed"]
    assert policy["params"]["positive_filter_cols"] == ["session_london_ny_liquid"]
    assert policy["params"]["gate"]["kind"] == "forecast_expansion"
    assert policy["params"]["gate"]["min_expansion"] == 1.10
    assert policy["params"]["sizing"]["kind"] == "fixed"
    assert cfg["research_metadata"]["meta_model"] == "disabled_until_base_edge_acceptance"
    assert cfg["research_metadata"]["precommitted_acceptance"] == {
        "min_oos_candidate_events": 500,
        "require_positive_gross_expectancy": True,
        "min_positive_oos_fold_fraction": 0.60,
        "min_gross_edge_to_round_trip_cost": 2.0,
        "require_positive_net_profit_factor": True,
    }


def test_compression_breakout_candidate_and_policy_smoke_without_model_fit(
    configs: dict[str, dict], featured_frame: pd.DataFrame
) -> None:
    cfg = configs["10_eurusd_30m_qms_compression_breakout_session_forecast_v1.yaml"]
    session_step = next(step for step in cfg["features"] if step["step"] == "session_context")
    frame = apply_feature_steps(featured_frame, [session_step], asset="EURUSD")
    candidate_frame, model, candidate_meta = apply_qms_candidate_transform(
        frame,
        cfg["model_stages"][1],
    )
    candidate_frame["pred_future_rv_16_is_oos"] = True
    candidate_frame["pred_future_rv_16"] = candidate_frame["rlv_sigma_slow"] * 1.20
    policy_frame, policy_model, policy_meta = apply_qms_candidate_policy_transform(
        candidate_frame,
        cfg["model_stages"][2],
    )

    expected_session = (
        (policy_frame.index.hour >= 7) & (policy_frame.index.hour < 17)
    ).astype("int8")
    np.testing.assert_array_equal(
        policy_frame["session_london_ny_liquid"].to_numpy(dtype="int8"),
        expected_session,
    )
    assert model is None and policy_model is None
    assert candidate_meta["strategies"] == ["volatility_compression_breakout"]
    assert policy_meta["anti_leakage"]["candidate_rows_require_pred_is_oos"] is True
    assert policy_meta["gate_kind"] == "forecast_expansion"
    outside_session = policy_frame["session_london_ny_liquid"].eq(0.0)
    assert policy_frame.loc[outside_session, "qms_breakout_policy_candidate"].eq(0).all()
    assert policy_frame["qms_breakout_policy_signal"].abs().le(1.0).all()


def test_forecast_gated_meta_features_satisfy_classifier_anti_leakage_contract(
    configs: dict[str, dict],
) -> None:
    cfg = configs["09_eurusd_30m_qms_trend_pullback_forecast_vol_meta_v1.yaml"]
    meta_stage = cfg["model_stages"][-1]
    feature_cols = list(meta_stage["feature_cols"])
    label_col = str(meta_stage["outputs"]["label_col"])
    contract_frame = pd.DataFrame(
        {
            **{column: [0.1, 0.2] for column in feature_cols},
            label_col: [0.0, 1.0],
        }
    )

    meta = validate_feature_target_contract(
        contract_frame,
        feature_cols=feature_cols,
        target=TargetContract(target_col=label_col, horizon=16),
    )

    assert meta["n_features"] == len(feature_cols)


def test_supervised_targets_build_without_fitting_models(
    configs: dict[str, dict], featured_frame: pd.DataFrame
) -> None:
    volatility_cfg = configs["01_eurusd_30m_qms_future_volatility_lgbm_v1.yaml"]
    vol_out, vol_label, vol_fwd, vol_meta = build_target(
        featured_frame,
        volatility_cfg["model"]["target"],
    )
    assert vol_label == vol_fwd == "target_future_rv_16"
    assert vol_meta["horizon_bars"] == 16
    assert vol_out[vol_fwd].iloc[-16:].isna().all()
    assert np.isfinite(vol_out[vol_fwd].dropna()).all()

    multi_cfg = configs["02_eurusd_30m_qms_multi_horizon_normalized_return_lgbm_v1.yaml"]
    for stage in multi_cfg["model_stages"]:
        horizon = int(stage["target"]["horizon_bars"])
        out, label_col, fwd_col, meta = build_target(featured_frame, stage["target"])
        assert label_col == fwd_col == f"target_vol_norm_return_{horizon}"
        assert meta["horizon_bars"] == horizon
        assert out[fwd_col].iloc[-horizon:].isna().all()
        assert np.isfinite(out[fwd_col].dropna()).all()


def test_qms_candidate_union_and_meta_target_smoke_without_classifier_fit(
    configs: dict[str, dict], featured_frame: pd.DataFrame
) -> None:
    cfg = configs["03_eurusd_30m_qms_candidate_meta_logreg_v1.yaml"]
    candidate_stage, meta_stage = cfg["model_stages"]
    candidate_frame, model, candidate_meta = apply_qms_candidate_transform(
        featured_frame,
        candidate_stage,
    )

    assert model is None
    assert candidate_meta["anti_leakage"]["fitted"] is False
    expected = {
        "qms_meta_candidate",
        "qms_meta_side",
        "qms_meta_source_count",
        "qms_meta_side_conflict",
        "qms_meta_origin_kds_pullback_continuation",
        "qms_meta_origin_lmds_exhaustion_reversal",
    }
    assert expected.issubset(candidate_frame.columns)
    conflict = candidate_frame["qms_meta_side_conflict"].eq(1)
    assert candidate_frame.loc[conflict, "qms_meta_candidate"].eq(0).all()
    assert candidate_frame.loc[conflict, "qms_meta_side"].eq(0).all()

    labeled, label_col, _, target_meta = build_target(candidate_frame, meta_stage["target"])
    assert label_col == "qms_meta_label"
    assert meta_stage["target"]["candidate_col"] == "qms_meta_candidate"
    assert target_meta["candidate_col"] == "qms_meta_labeled_candidate"
    assert "qms_meta_event_r" in labeled.columns
    assert "qms_meta_label_side" in labeled.columns


def test_ppo_risk_environment_reset_and_one_step_without_training(
    configs: dict[str, dict], featured_frame: pd.DataFrame
) -> None:
    cfg = configs["04_eurusd_30m_qms_ppo_risk_sizing_exits_v1.yaml"]
    model_cfg = cfg["model"]
    env_cfg = model_cfg["env"]
    feature_cols = list(model_cfg["feature_cols"])
    needed = feature_cols + ["open", "high", "low", "close", env_cfg["atr_column"]]
    clean = featured_frame.loc[:, needed].replace([np.inf, -np.inf], np.nan).dropna().tail(160)
    assert len(clean) >= 80

    env = SingleAssetRiskTradingEnv(
        frame=clean,
        feature_columns=feature_cols,
        atr_column=env_cfg["atr_column"],
        lookback_window=64,
        trade_config=RiskTradeConfig.from_mapping(env_cfg),
        reward_config=RiskRewardConfig.from_mapping(env_cfg["reward"]),
        open_column=env_cfg["open_column"],
        high_column=env_cfg["high_column"],
        low_column=env_cfg["low_column"],
        close_column=env_cfg["close_column"],
    )
    observation, reset_info = env.reset(seed=7)
    next_observation, reward, terminated, truncated, step_info = env.step(1)

    assert observation.shape == next_observation.shape == env.observation_space.shape
    assert np.isfinite(observation).all() and np.isfinite(next_observation).all()
    assert np.isfinite(reward)
    assert terminated is False and truncated is False
    assert step_info["decision_timestamp"] == reset_info["timestamp"]
    assert step_info["execution_timestamp"] > step_info["decision_timestamp"]
    assert step_info["execution_lag_bars"] == 1
    assert step_info["decoded_action"]["direction"] == 1
    assert step_info["decoded_action"]["stop_loss_atr_multiplier"] is not None
    assert step_info["decoded_action"]["take_profit_r_multiple"] is not None
