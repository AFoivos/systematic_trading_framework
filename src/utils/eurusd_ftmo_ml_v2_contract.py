from __future__ import annotations

from dataclasses import dataclass


STRATEGY_NAME = "EURUSD FTMO 2-Step ML Meta-Ensemble"
STRATEGY_VERSION = "v2"
SYMBOL = "EURUSD"
TIMEFRAME = "30m"
PIP_SIZE = 0.0001
COMMISSION_PIPS_PER_SIDE = 0.25
SLIPPAGE_PIPS_PER_SIDE = 0.05
PULLBACK_FAMILY_WEIGHT = 0.80
SESSION_FAMILY_WEIGHT = 0.20
SCORE_FLOOR = 0.60
SCORE_CAP = 0.80
BASE_NOTIONAL_MULTIPLE = 22.0
VOLATILITY_FACTOR_FLOOR = 0.60
VOLATILITY_FACTOR_CAP = 1.40
DAILY_CIRCUIT_BREAKER = -0.0225
FTMO_TIMEZONE = "Europe/Prague"
BARS_PER_DAY = 48
PERIODS_PER_YEAR = 48 * 252
EWMA_VOL_SPAN_BARS = 20 * 48

REQUIRED_MARKET_COLUMNS = (
    "timestamp", "open", "high", "low", "close", "volume",
    "bid_open", "bid_high", "bid_low", "bid_close",
    "ask_open", "ask_high", "ask_low", "ask_close",
    "spread_close", "spread_bps",
)

REFERENCE_DATASET = {
    "rows": 78_803,
    "start": "2020-01-01 22:00:00",
    "end": "2026-04-27 23:30:00",
    "sha256": "384af9b40271f1598a545c79c77303922ed20d257b968c7b4718820accef4164",
    "research_classifications": ["REGENERATE_REQUIRED", "LEGACY_AMBIGUOUS_UNITS"],
    "spread_bps_semantics": "LEGACY_FRACTION",
    "research_eligible": False,
}

REFERENCE_HASHES = {
    "eurusd_30m.csv": REFERENCE_DATASET["sha256"],
    "eurusd_ftmo_ml_v2_model_bundle.joblib": "276d274cf7fc4e5bcb27b50fb936e1e018f0d2b958d5b5bc5bfb0073caf5ebe5",
    "eurusd_ftmo_ml_v2_feature_dictionary.csv": "4c8aa79a8d4635ddfdb221b6aa9449b05123d5883b81fc6f1fa28e367eebd1b8",
    "eurusd_ftmo_ml_v2_strategy_spec.json": "37289f74e9e3b318349a372443eb6050c9cbe987e14bfe294a867e41af208943",
    "eurusd_ftmo_ml_v2_strategy.py": "9df3a12f7661835eca40a337a0d062e88474859fcb7fd201211ade1e0a22daaa",
    "eurusd_ftmo_ml_v2_period_metrics.csv": "5a9fff9bff85b0f28e231d4949d0c0ae430c6f4ef4adfa1a9415783b278f5582",
}

REFERENCE_FILENAMES = (
    "eurusd_30m.csv",
    "eurusd_ftmo_ml_v2_strategy_spec.json",
    "eurusd_ftmo_ml_v2_strategy.py",
    "eurusd_ftmo_ml_v2_model_bundle.joblib",
    "eurusd_ftmo_ml_v2_feature_dictionary.csv",
    "eurusd_ftmo_ml_v2_feature_importance.csv",
    "eurusd_ftmo_ml_v2_period_metrics.csv",
    "eurusd_ftmo_ml_v2_parameter_sensitivity.csv",
    "eurusd_ftmo_ml_v2_cost_stress.csv",
    "eurusd_ftmo_ml_v2_risk_scenarios.csv",
    "eurusd_ftmo_ml_v2_strategy_report.html",
    "eurusd_ftmo_strategy_spec.json",
    "eurusd_ftmo_ml_strategy_spec.json",
    "eurusd_ftmo_ml_strategy.py",
)


@dataclass(frozen=True)
class PullbackComponent:
    component_id: str
    ema_span: int
    entry_atr: float
    exit_atr: float
    maximum_hold_bars: int
    adverse_z_stop: float


PULLBACK_COMPONENTS = (
    PullbackComponent("component_1", 16, 2.50, 0.75, 24, 99.0),
    PullbackComponent("component_2", 20, 2.25, 0.50, 24, 99.0),
    PullbackComponent("component_3", 12, 2.00, 0.25, 24, 99.0),
    PullbackComponent("component_4", 20, 3.00, 0.75, 8, 4.0),
)

COMMON_MODEL_PARAMS = {
    "boosting_type": "gbdt",
    "class_weight": None,
    "colsample_bytree": 0.60,
    "importance_type": "split",
    "learning_rate": 0.025,
    "max_depth": 4,
    "min_child_samples": 40,
    "min_child_weight": 0.001,
    "min_split_gain": 0.0,
    "n_estimators": 250,
    "n_jobs": -1,
    "objective": "binary",
    "random_state": 42,
    "reg_alpha": 1.0,
    "reg_lambda": 5.0,
    "subsample": 0.80,
    "subsample_for_bin": 200000,
    "subsample_freq": 0,
    "verbosity": -1,
}
MODEL_NUM_LEAVES = (3, 7, 15)

FEATURE_COLUMNS = (
    "mom_1_vol", "mom_1_atr", "mom_2_vol", "mom_2_atr", "mom_4_vol", "mom_4_atr",
    "mom_8_vol", "mom_8_atr", "mom_16_vol", "mom_16_atr", "mom_24_vol", "mom_24_atr",
    "mom_48_vol", "mom_48_atr", "mom_96_vol", "mom_96_atr", "mom_192_vol", "mom_192_atr",
    "ema_dist_8", "ema_slope_8", "ema_dist_16", "ema_slope_16", "ema_dist_32", "ema_slope_32",
    "ema_dist_48", "ema_slope_48", "ema_dist_96", "ema_slope_96", "ema_dist_192", "ema_slope_192",
    "ema_dist_384", "ema_slope_384", "ema_dist_768", "ema_slope_768",
    "rsi_7", "rsi_14", "rsi_28", "rsi_56", "rsi_ratio_7_28", "adx14", "di_diff", "di_logratio",
    "vol_ratio_8_48", "vol_ratio_16_48", "vol_ratio_48_192", "vol_ratio_96_384", "atr_rel_z",
    "body_range", "close_loc", "upper_wick", "lower_wick", "range_atr",
    "range_pos_24", "break_hi_24", "break_lo_24", "range_pos_48", "break_hi_48", "break_lo_48",
    "range_pos_96", "break_hi_96", "break_lo_96", "range_pos_192", "break_hi_192", "break_lo_192",
    "range_pos_384", "break_hi_384", "break_lo_384", "volume_z_48", "volume_z_192", "volume_z_960",
    "spread_atr", "spread_z", "eff_24", "eff_48", "eff_96", "eff_192", "ac_48", "ac_192",
    "hour_sin", "hour_cos", "dow_sin", "dow_cos", "liquid_london_ny",
    "direction", "is_session", "amplitude", "bars_planned",
    "past_win20", "past_mean20", "past_mean_all", "past_win_all",
    "dir_mom_1_vol", "dir_mom_1_atr", "dir_mom_2_vol", "dir_mom_2_atr",
    "dir_mom_4_vol", "dir_mom_4_atr", "dir_mom_8_vol", "dir_mom_8_atr",
    "dir_mom_16_vol", "dir_mom_16_atr", "dir_mom_24_vol", "dir_mom_24_atr",
    "dir_mom_48_vol", "dir_mom_48_atr", "dir_mom_96_vol", "dir_mom_96_atr",
    "dir_mom_192_vol", "dir_mom_192_atr",
    "dir_ema_dist_8", "dir_ema_slope_8", "dir_ema_dist_16", "dir_ema_slope_16",
    "dir_ema_dist_32", "dir_ema_slope_32", "dir_ema_dist_48", "dir_ema_slope_48",
    "dir_ema_dist_96", "dir_ema_slope_96", "dir_ema_dist_192", "dir_ema_slope_192",
    "dir_ema_dist_384", "dir_ema_slope_384", "dir_ema_dist_768", "dir_ema_slope_768",
    "dir_rsi_7", "dir_rsi_14", "dir_rsi_28", "dir_rsi_56", "dir_rsi_ratio_7_28",
    "dir_range_pos_24", "dir_break_hi_24", "dir_break_lo_24",
    "dir_range_pos_48", "dir_break_hi_48", "dir_break_lo_48",
    "dir_range_pos_96", "dir_break_hi_96", "dir_break_lo_96",
    "dir_range_pos_192", "dir_break_hi_192", "dir_break_lo_192",
    "dir_range_pos_384", "dir_break_hi_384", "dir_break_lo_384",
    "dir_di_diff", "dir_di_logratio", "dir_body_range", "dir_close_loc",
    "dir_upper_wick", "dir_lower_wick",
)

if len(FEATURE_COLUMNS) != 151 or len(set(FEATURE_COLUMNS)) != 151:
    raise RuntimeError("EURUSD FTMO ML v2 feature contract must contain 151 unique columns.")

DIRECTION_INTERACTION_COLUMNS = tuple(name for name in FEATURE_COLUMNS if name.startswith("dir_"))
