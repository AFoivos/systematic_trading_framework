from __future__ import annotations

from collections.abc import Callable, Mapping

import pandas as pd

from .normalizations.atr_distances import add_atr_distance_features
from .normalizations.atr_scaled_distance import add_atr_scaled_distance_features
from .normalizations.range_position import add_range_position_features
from .normalizations.realized_vol_percentile import add_realized_vol_percentile_features
from .normalizations.returns import add_return_features
from .normalizations.robust_zscore import add_robust_zscore_features
from .normalizations.rolling_beta_residual import add_rolling_beta_residual_features
from .normalizations.rolling_percent_rank import add_rolling_percent_rank_features
from .normalizations.rolling_zscores import add_rolling_zscore_features
from .normalizations.volatility import add_volatility_normalization_features
from .normalizations.volatility_scaled_return import add_volatility_scaled_return_features
from .normalizations.volume_relative import add_volume_relative_features
from .difference import add_difference_transform
from .flags import (
    add_between_flag_transform,
    add_crossing_flag_transform,
    add_rising_flag_transform,
    add_threshold_flag_transform,
)
from .lag import add_lag_transform
from .ratio import add_ratio_transform
from .reciprocal import add_reciprocal_transform
from .rolling_clip import add_rolling_clip_transform
from .rolling_linear_regression import add_rolling_linear_regression_transform
from .rolling_mean import add_rolling_mean_transform
from .rolling_std import add_rolling_std_transform
from .rolling_sum import add_rolling_sum_transform
from .rolling_zscore import add_rolling_zscore_transform
from .rms import add_rms_transform
from .slope import add_slope_transform

HelperFn = Callable[..., pd.DataFrame]

TRANSFORM_HELPERS: Mapping[str, HelperFn] = {
    "between_flag": add_between_flag_transform,
    "crossing_flag": add_crossing_flag_transform,
    "difference": add_difference_transform,
    "lag": add_lag_transform,
    "ratio": add_ratio_transform,
    "reciprocal": add_reciprocal_transform,
    "rolling_clip": add_rolling_clip_transform,
    "rolling_linear_regression": add_rolling_linear_regression_transform,
    "rolling_mean": add_rolling_mean_transform,
    "rolling_std": add_rolling_std_transform,
    "rolling_sum": add_rolling_sum_transform,
    "rolling_zscore": add_rolling_zscore_transform,
    "rms": add_rms_transform,
    "rising_flag": add_rising_flag_transform,
    "slope": add_slope_transform,
    "threshold_flag": add_threshold_flag_transform,
}

NORMALIZATION_HELPERS: Mapping[str, HelperFn] = {
    "returns": add_return_features,
    "atr_distances": add_atr_distance_features,
    "atr_scaled_distance": add_atr_scaled_distance_features,
    "range_position": add_range_position_features,
    "realized_vol_percentile": add_realized_vol_percentile_features,
    "robust_zscore": add_robust_zscore_features,
    "rolling_beta_residual": add_rolling_beta_residual_features,
    "rolling_percent_rank": add_rolling_percent_rank_features,
    "volatility": add_volatility_normalization_features,
    "volatility_scaled_return": add_volatility_scaled_return_features,
    "volume_relative": add_volume_relative_features,
    "rolling_zscores": add_rolling_zscore_features,
}


__all__ = ["HelperFn", "NORMALIZATION_HELPERS", "TRANSFORM_HELPERS"]
