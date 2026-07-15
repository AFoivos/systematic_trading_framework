"""Generate the standalone US100 M30 Trend-VWAP expected-R YAML ladder."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config/experiments/foundation_alpha/trend_vwap_expected_r_us100_m30"

FILENAMES = [
    "00_us100_m30_trend_vwap_expected_r_yaml0.yaml",
    "01_us100_m30_trend_vwap_expected_r_yaml1.yaml",
    "02_us100_m30_trend_vwap_expected_r_yaml2.yaml",
    "03_us100_m30_trend_vwap_expected_r_yaml3.yaml",
    "04_us100_m30_trend_vwap_expected_r_yaml4.yaml",
    "05_us100_m30_trend_vwap_expected_r_yaml5.yaml",
    "06_us100_m30_trend_vwap_expected_r_yaml6.yaml",
    "07_us100_m30_trend_vwap_expected_r_yaml7.yaml",
    "08_us100_m30_trend_vwap_expected_r_yaml8.yaml",
    "09_us100_m30_trend_vwap_expected_r_yaml9.yaml",
    "10_us100_m30_trend_vwap_expected_r_yaml10_FINAL.yaml",
]

STAGE_LABELS = [
    "Minimal viable expected-R strategy",
    "Normalized return and momentum history",
    "Trend structure and temporary 3-of-4 trend score",
    "Complete session/rolling VWAP normalization block",
    "Explicit expansion and pullback path",
    "Momentum reacceleration",
    "Ehlers market structure and final 4-of-5 trend score",
    "Volatility, volume, range, and New York session context",
    "Hard shock, resistance, and extreme-volatility rejections",
    "Expected-R threshold raised from 0.00R to 0.25R",
    "Next-open gap, cooldown, and portfolio-risk controls",
]

BASE_FEATURES = [
    "atr_over_price_20",
    "d_vwap_atr",
    "d_vwap_pct",
    "d_ema50_atr",
    "ema50_ema100_spread_atr",
    "return_1",
    "return_4",
    "return_4_atr",
    "vwap_reclaim_cross",
]

STAGE_ADDITIONS: dict[int, list[str]] = {
    1: [
        "log_return_1",
        "return_2",
        "return_8",
        "return_16",
        "return_1_atr",
        "return_2_atr",
        "return_8_atr",
        "return_16_atr",
        "return_1_vol96",
        "return_2_vol96",
        "return_4_vol96",
        "return_8_vol96",
        "return_16_vol96",
        "return_1_robust_z96",
        "return_4_robust_z96",
        "return_8_robust_z96",
    ],
    2: [
        "d_ema20_atr",
        "ema20_slope_5_atr",
        "ema50_slope_5_atr",
        "ema50_slope_10_atr",
        "rolling_log_price_slope_96",
        "rolling_log_price_r2_96",
        "trend_vwap_trend_score",
    ],
    3: [
        "session_vwap_slope_5_atr",
        "d_rolling_vwap40_atr",
        "d_vwap_atr_robust_z96",
        "d_vwap_atr_percent_rank_252",
        "d_vwap_atr_lag_1",
        "d_vwap_atr_lag_2",
        "d_vwap_atr_lag_3",
        "d_vwap_atr_lag_4",
        "vwap_loss_cross",
    ],
    4: [
        "prior_8_max_d_vwap_atr",
        "prior_4_min_d_vwap_atr",
        "pullback_depth_atr",
        "bars_since_d_vwap_expansion_080",
    ],
    5: [
        "ppo_12_26",
        "ppo_signal_9",
        "ppo_hist_12_26_9",
        "ppo_hist_diff_1",
        "ppo_hist_diff_2",
        "ppo_hist_zero_cross",
        "stoch_rsi_14_k",
        "stoch_rsi_14_d",
        "stoch_rsi_bullish_cross",
        "stoch_rsi_bearish_cross",
        "mfi_14",
        "mfi_14_centered",
    ],
    6: [
        "mama_fama_spread_atr",
        "mama_fama_bullish_cross",
        "decycler_oscillator_30_60_atr",
        "roofing_filter_48_10_robust_z96",
        "roofing_filter_slope_atr",
        "roofing_filter_zero_cross",
        "acp_dominant_period_10_48",
        "acp_power_10_48",
        "acp_period_std_24",
        "hilbert_amplitude_64_atr",
        "hilbert_phase_sin_64",
        "hilbert_phase_cos_64",
        "hilbert_period_64",
    ],
    7: [
        "atr_percent_rank_252",
        "atr_over_price_z96",
        "atr_short_long_ratio_10_40",
        "rolling_volatility_24",
        "rolling_volatility_96",
        "volatility_ratio_24_96",
        "volatility_of_volatility_24",
        "relative_volume_96",
        "volume_z96",
        "range_position_96",
        "bar_range_atr",
        "close_location_value",
        "hour_sin_24",
        "hour_cos_24",
        "day_of_week_sin_7",
        "day_of_week_cos_7",
        "minutes_since_ny_cash_open",
    ],
    8: [
        "shock_active",
        "resistance_distance_atr",
    ],
}


def _stage_one_lags() -> list[str]:
    normalized = [f"return_{horizon}_atr" for horizon in (1, 2, 4, 8, 16)]
    normalized += [f"return_{horizon}_vol96" for horizon in (1, 2, 4, 8, 16)]
    normalized += [f"return_{horizon}_robust_z96" for horizon in (1, 4, 8)]
    return [f"{column}_lag_{lag}" for column in normalized for lag in (1, 2, 3)]


STAGE_ADDITIONS[1].extend(_stage_one_lags())


def model_features_for_stage(stage: int) -> list[str]:
    """Return the explicit cumulative model feature list for one ladder stage."""
    feature_stage = min(stage, 8)
    columns = list(BASE_FEATURES)
    for current in range(1, feature_stage + 1):
        columns.extend(STAGE_ADDITIONS.get(current, []))
    if len(columns) != len(set(columns)):
        raise AssertionError(f"Duplicate model feature in stage {stage}.")
    return columns


def build_config(stage: int) -> dict[str, object]:
    """Build one fully self-contained ladder configuration."""
    feature_stage = min(stage, 8)
    threshold = 0.25 if stage >= 9 else 0.0
    run_name = f"us100_m30_trend_vwap_expected_r_yaml{stage}"
    config: dict[str, object] = {
        "strategy": {
            "name": "Causal Trend-VWAP Pullback Continuation with Path-Dependent Expected-R",
            "version": f"yaml{stage}",
            "stage": STAGE_LABELS[stage],
            "symbol": "US100",
            "timeframe": "M30",
            "direction": "long_only",
        },
        "data": {
            "source": "dukascopy_csv",
            "interval": "30m",
            "start": None,
            "end": None,
            "alignment": "inner",
            "symbol": "US100",
            "pit": {
                "timestamp_alignment": {
                    "source_timezone": "UTC",
                    "output_timezone": "UTC",
                    "normalize_daily": False,
                    "duplicate_policy": "last",
                },
                "corporate_actions": {"policy": "none", "adj_close_col": "adj_close"},
                "universe_snapshot": {"inactive_policy": "raise"},
            },
            "storage": {
                "mode": "cached_only",
                "dataset_id": run_name,
                "save_raw": False,
                "save_processed": True,
                "load_path": "data/raw/dukascopy_30m_clean/us100_30m.csv",
                "raw_dir": "data/raw",
                "processed_dir": "data/processed/trend_vwap_expected_r_us100_m30",
            },
        },
        "features": [
            {
                "step": "trend_vwap_pullback_candidate",
                "params": {"stage": feature_stage, "timezone": "America/New_York"},
                "enabled": True,
            }
        ],
        "model": {
            "kind": "lightgbm_regressor",
            "params": {
                "n_estimators": 400,
                "learning_rate": 0.025,
                "num_leaves": 15,
                "max_depth": 5,
                "min_child_samples": 120,
                "subsample": 0.80,
                "colsample_bytree": 0.75,
                "reg_alpha": 0.25,
                "reg_lambda": 2.0,
                "random_state": 7,
                "n_jobs": 1,
                "verbosity": -1,
            },
            "preprocessing": {"scaler": "none"},
            "calibration": {},
            "feature_cols": model_features_for_stage(stage),
            "target": {
                "kind": "triple_barrier",
                "label_mode": "meta",
                "candidate_col": "trend_vwap_base_candidate",
                "side_col": "trend_vwap_candidate_side",
                "candidate_mode": "all_nonzero",
                "entry_price_mode": "next_open",
                "price_col": "close",
                "open_col": "open",
                "high_col": "high",
                "low_col": "low",
                "volatility_col": "atr_over_price_20",
                "lower_mult": 1.5,
                "upper_mult": 3.0,
                "max_holding": 16,
                "add_r_multiple": True,
                "target_col": "tb_oriented_r",
                "oriented_r_col": "tb_oriented_r",
                "r_col": "tb_event_r",
                "r_clip": [-1.25, 2.25],
                "tie_break": "lower",
                "neutral_label": "lower",
                "label_col": "tb_label",
                "event_ret_col": "tb_event_ret",
                "candidate_out_col": "tb_candidate",
            },
            "split": {
                "method": "purged",
                "train_size": 35040,
                "test_size": 4380,
                "step_size": 4380,
                "expanding": True,
                "max_folds": 17,
                "purge_bars": 24,
                "embargo_bars": 24,
            },
            "runtime": {},
            "env": {},
            "use_features": True,
            "pred_ret_col": "pred_tb_oriented_r",
            "pred_prob_col": "pred_tb_positive_prob",
            "pred_is_oos_col": "pred_is_oos",
            "returns_input_col": None,
            "signal_col": None,
            "action_col": None,
        },
        "signals": {
            "kind": "forecast_threshold_candidate",
            "params": {
                "forecast_col": "pred_tb_oriented_r",
                "pred_is_oos_col": "pred_is_oos",
                "signal_col": "signal_trend_vwap_expected_r",
                "upper": threshold,
                "lower": -999.0,
                "inclusive": True,
                "mode": "long_only",
                "activation_filters": [
                    {"col": "trend_vwap_base_candidate", "op": "ge", "value": 1.0},
                    {"col": "pred_is_oos", "op": "ge", "value": 1.0},
                ],
                "candidate_col": "accepted_trend_vwap_candidate",
                "side_col": "accepted_trend_vwap_side",
                "strength_col": "accepted_predicted_r",
                "threshold_distance_col": "accepted_predicted_r_margin",
            },
        },
        "runtime": {
            "seed": 7,
            "repro_mode": "strict",
            "deterministic": True,
            "threads": 1,
            "seed_torch": False,
        },
        "risk": {
            "cost_per_turnover": 0.00015,
            "slippage_per_turnover": 0.00010,
            "target_vol": None,
            "max_leverage": 1.0,
            "sizing": {},
            "dd_guard": {
                "enabled": False,
                "max_drawdown": 0.08,
                "rearm_drawdown": 0.04,
                "cooloff_bars": 48,
            },
            "portfolio_guard": {},
            "drawdown_sizing": {},
            "vol_col": None,
        },
        "backtest": {
            "engine": "manual_barrier",
            "signal_col": "signal_trend_vwap_expected_r",
            "returns_col": "return_1",
            "returns_type": "simple",
            "subset": "full",
            "periods_per_year": 12096,
            "missing_return_policy": "raise_if_exposed",
            "allow_short": False,
            "stop_mode": "volatility_stop",
            "vol_col": "atr_over_price_20",
            "open_col": "open",
            "high_col": "high",
            "low_col": "low",
            "close_col": "close",
            "take_profit_r": 3.0,
            "stop_loss_r": 1.5,
            "risk_per_trade": 0.003,
            "max_holding_bars": 16,
            "dynamic_exits": {"enabled": False},
            "partial_exits": {"enabled": False},
        },
        "portfolio": {
            "enabled": False,
            "construction": "signal_weights",
            "long_short": False,
            "gross_target": 1.0,
        },
        "monitoring": {"enabled": False, "psi_threshold": 0.2, "n_bins": 10},
        "diagnostics": {
            "enabled": True,
            "model": {"enabled": False},
            "trade_path": {"enabled": False},
            "robustness": {
                "enabled": True,
                "cost_multipliers": [1.0, 2.0, 3.0, 5.0],
                "entry_delay_bars": [1, 2],
                "walk_forward_frequency": "YE",
            },
        },
        "execution": {"enabled": False, "mode": "paper", "capital": 100000.0, "price_col": "close"},
        "logging": {
            "enabled": True,
            "run_name": run_name,
            "output_dir": "logs/experiments/trend_vwap_expected_r_us100_m30",
            "save_model": False,
            "stage_tails": {"enabled": False},
            "execution_source_audit": {"enabled": True},
        },
        "validation": {"method": "purged_walk_forward", "purge_bars": 24, "embargo_bars": 24},
        "evaluation": {"strict_oos_only": True},
        "research_metadata": {
            "ladder": "trend_vwap_expected_r_us100_m30",
            "yaml_stage": stage,
            "feature_stage": feature_stage,
            "forecast_threshold_r": threshold,
            "random_search_used": False,
        },
    }

    if stage == 10:
        risk = deepcopy(config["risk"])
        risk["max_correlated_us_index_risk"] = 0.0045
        risk["portfolio_guard"] = {
            "enabled": True,
            "timezone": "America/New_York",
            "daily_soft_stop": 0.012,
            "daily_soft_stop_risk_multiplier": 0.5,
            "daily_hard_stop": 0.015,
            "weekly_drawdown": 0.030,
            "weekly_anchor": "W-FRI",
        }
        config["risk"] = risk
        backtest = deepcopy(config["backtest"])
        backtest.update(
            {
                "max_entry_gap_atr": 0.35,
                "entry_gap_atr_col": "atr_20",
                "stop_cooldown_bars": 8,
            }
        )
        config["backtest"] = backtest
    return config


def generate() -> list[Path]:
    """Write all eleven standalone configurations and return their paths."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for stage, filename in enumerate(FILENAMES):
        path = CONFIG_DIR / filename
        path.write_text(
            yaml.safe_dump(build_config(stage), sort_keys=False, width=110),
            encoding="utf-8",
        )
        written.append(path)
    return written


def main() -> None:
    for path in generate():
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()


__all__ = [
    "CONFIG_DIR",
    "FILENAMES",
    "STAGE_ADDITIONS",
    "STAGE_LABELS",
    "build_config",
    "generate",
    "model_features_for_stage",
]
