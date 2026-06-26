from __future__ import annotations

from collections.abc import Callable, Mapping

import pandas as pd

from .normalizations.atr_distances import add_atr_distance_features
from .normalizations.returns import add_return_features
from .normalizations.rolling_zscores import add_rolling_zscore_features
from .normalizations.volatility import add_volatility_normalization_features
from .ratio import add_ratio_transform
from .rolling_clip import add_rolling_clip_transform
from .rolling_zscore import add_rolling_zscore_transform
from .rms import add_rms_transform
from .slope import add_slope_transform

HelperFn = Callable[..., pd.DataFrame]

TRANSFORM_HELPERS: Mapping[str, HelperFn] = {
    "ratio": add_ratio_transform,
    "rolling_clip": add_rolling_clip_transform,
    "rolling_zscore": add_rolling_zscore_transform,
    "rms": add_rms_transform,
    "slope": add_slope_transform,
}

NORMALIZATION_HELPERS: Mapping[str, HelperFn] = {
    "returns": add_return_features,
    "atr_distances": add_atr_distance_features,
    "volatility": add_volatility_normalization_features,
    "rolling_zscores": add_rolling_zscore_features,
}


__all__ = ["HelperFn", "NORMALIZATION_HELPERS", "TRANSFORM_HELPERS"]
