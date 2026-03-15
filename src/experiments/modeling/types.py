from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd


EstimatorFactory = Callable[[dict[str, Any]], object]
ForecasterFoldPredictor = Callable[
    [pd.DataFrame, np.ndarray, np.ndarray, list[str], str, dict[str, Any], dict[str, Any]],
    tuple[pd.Series, dict[str, pd.Series], object, dict[str, Any]],
]


__all__ = ["EstimatorFactory", "ForecasterFoldPredictor"]
