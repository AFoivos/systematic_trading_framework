from __future__ import annotations

import copy
from pathlib import Path

import yaml


BASE_CONFIG = Path(
    "config/experiments/foundation_alpha/trend_vwap_expected_r_us100_m30/"
    "10_us100_m30_trend_vwap_expected_r_yaml10_FINAL.yaml"
)
OUTPUT_DIR = Path(
    "config/experiments/foundation_alpha/sparse_trend_vwap_expected_r_us100_m30"
)

SPARSE_FEATURES = [
    "atr_over_price_20",
    "atr_percent_rank_252",
    "volatility_ratio_24_96",
    "d_vwap_atr",
    "d_vwap_atr_robust_z96",
    "d_vwap_atr_percent_rank_252",
    "session_vwap_slope_5_atr",
    "d_rolling_vwap40_atr",
    "pullback_depth_atr",
    "bars_since_d_vwap_expansion_080",
    "ema50_ema100_spread_atr",
    "ema50_slope_5_atr",
    "rolling_log_price_slope_96",
    "rolling_log_price_r2_96",
    "mama_fama_spread_atr",
    "roofing_filter_slope_atr",
    "return_1_atr",
    "return_4_atr",
    "return_8_atr",
    "return_4_vol96",
    "return_8_vol96",
    "ppo_hist_diff_1",
    "stoch_rsi_bullish_cross",
    "mfi_14_centered",
    "relative_volume_96",
    "range_position_96",
    "bar_range_atr",
    "close_location_value",
    "minutes_since_ny_cash_open",
    "shock_active",
    "resistance_distance_atr",
]

MODEL_PARAMS = {
    "n_estimators": 350,
    "learning_rate": 0.03,
    "num_leaves": 7,
    "max_depth": 3,
    "min_child_samples": 180,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.5,
    "reg_lambda": 3.0,
    "random_state": 7,
    "n_jobs": 1,
    "verbosity": -1,
}


def make_config(base: dict, *, run_name: str, version: str, hypothesis: str, threshold: float, dynamic_exits: dict) -> dict:
    cfg = copy.deepcopy(base)
    cfg["strategy"] = {"name": "Sparse Causal Trend-VWAP Pullback with Expected-R", "version": version, "stage": hypothesis, "symbol": "US100", "timeframe": "M30", "direction": "long_only"}
    cfg["data"]["storage"]["dataset_id"] = run_name
    cfg["data"]["storage"]["processed_dir"] = "data/processed/sparse_trend_vwap_expected_r_us100_m30"
    cfg["model"]["feature_cols"] = list(SPARSE_FEATURES)
    cfg["model"]["params"] = dict(MODEL_PARAMS)
    cfg["signals"]["params"]["upper"] = float(threshold)
    cfg["backtest"]["dynamic_exits"] = copy.deepcopy(dynamic_exits)
    cfg["backtest"]["partial_exits"] = {"enabled": False}
    cfg["logging"]["run_name"] = run_name
    cfg["logging"]["output_dir"] = "logs/experiments/sparse_trend_vwap_expected_r_us100_m30"
    cfg["research_metadata"] = {"family": "sparse_trend_vwap_expected_r_us100_m30", "base_config": str(BASE_CONFIG), "feature_count": len(SPARSE_FEATURES), "forecast_threshold_r": float(threshold), "hypothesis": hypothesis, "random_search_used": False}
    return cfg


def main() -> None:
    base = yaml.safe_load(BASE_CONFIG.read_text(encoding="utf-8"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    variants = [
        ("00_us100_m30_sparse_trend_vwap_expected_r_baseline.yaml", "us100_m30_sparse_trend_vwap_expected_r_baseline", "sparse_v1", "Sparse normalized feature baseline", 0.25, {"enabled": False}),
        ("01_us100_m30_sparse_trend_vwap_expected_r_no_progress.yaml", "us100_m30_sparse_trend_vwap_expected_r_no_progress", "sparse_v2", "Exit stale trades after 6 bars if MFE < 0.30R", 0.25, {"enabled": True, "no_progress": {"enabled": True, "bars": 6, "min_favorable_r": 0.30, "exit_price": "close"}}),
        ("02_us100_m30_sparse_trend_vwap_expected_r_profit_lock.yaml", "us100_m30_sparse_trend_vwap_expected_r_profit_lock", "sparse_v3", "No-progress + 0.40R lock after +1.00R", 0.25, {"enabled": True, "profit_lock": {"enabled": True, "trigger_r": 1.0, "lock_r": 0.4}, "no_progress": {"enabled": True, "bars": 6, "min_favorable_r": 0.30, "exit_price": "close"}}),
        ("03_us100_m30_sparse_trend_vwap_expected_r_threshold035.yaml", "us100_m30_sparse_trend_vwap_expected_r_threshld035", "sparse_v4", "Threshold 0.35R + no-progress", 0.35, {"enabled": True, "no_progress": {"enabled": True, "bars": 6, "min_favorable_r": 0.30, "exit_price": "close"}}),
    ]
    for filename, run_name, version, hypothesis, threshold, dynamic_exits in variants:
        cfg = make_config(base, run_name=run_name, version=version, hypothesis=hypothesis, threshold=threshold, dynamic_exits=dynamic_exits)
        path = OUTPUT_DIR / filename
        path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
        print(path)


if __name__ == "__main__":
    main()
