from __future__ import annotations

import numpy as np
import pandas as pd

from src.models.registry import get_model_fn
from src.models.rl.risk_pipeline import _apply_normalizer, _fit_train_normalizer


def test_ppo_risk_robust_scaler_uses_train_median_and_iqr() -> None:
    values = np.array(
        [[1.0, 10.0], [2.0, 11.0], [3.0, 12.0], [100.0, 13.0]],
        dtype=np.float32,
    )

    center, scale = _fit_train_normalizer(values, scaler="robust")
    normalized = _apply_normalizer(values, center=center, scale=scale)

    assert np.allclose(center, [2.5, 11.5])
    assert np.allclose(scale, [25.5, 1.5])
    assert np.isfinite(normalized).all()


def test_forecast_candidate_transform_requires_oos_prediction() -> None:
    index = pd.date_range("2024-01-01", periods=6, freq="30min")
    frame = pd.DataFrame(
        {
            "pred_ret": [0.8, 0.9, 0.6, 1.1, 1.2, 0.75],
            "pred_is_oos": [False, True, True, True, False, True],
            "atr_pct_rank_192": [0.5] * 6,
            "range_to_atr": [1.1] * 6,
            "bollinger_bandwidth_rank_192": [0.5] * 6,
        },
        index=index,
    )
    transform = get_model_fn("forecast_candidate_transform")

    out, model, meta = transform(
        frame,
        {
            "kind": "forecast_candidate_transform",
            "params": {
                "forecast_col": "pred_ret",
                "pred_is_oos_col": "pred_is_oos",
                "upper": 0.7,
                "lower": -0.85,
                "mode": "long_only",
                "activation_filters": [
                    {"col": "atr_pct_rank_192", "op": "ge", "value": 0.25},
                    {"col": "range_to_atr", "op": "ge", "value": 0.9},
                    {
                        "col": "bollinger_bandwidth_rank_192",
                        "op": "ge",
                        "value": 0.4,
                    },
                ],
            },
            "outputs": {
                "candidate_col": "candidate",
                "side_col": "side",
                "strength_col": "strength",
                "threshold_distance_col": "distance",
                "signal_col": "signal_candidate",
            },
        },
        None,
    )

    assert model is None
    assert out["candidate"].astype(int).tolist() == [0, 1, 0, 1, 0, 1]
    assert meta["candidate_summary"]["candidate_rows"] == 3
    assert meta["anti_leakage"]["candidate_rows_require_pred_is_oos"] is True
