from __future__ import annotations

import numpy as np
import pandas as pd

from src.experiments.models import train_lightgbm_classifier


def _synthetic_price_frame(n: int = 260) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    base = np.where(np.arange(n) % 2 == 0, 0.01, -0.01)
    rets = base + rng.normal(0.0, 0.001, size=n)
    close = 100.0 * np.exp(np.cumsum(rets))

    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    df = pd.DataFrame({"close": close}, index=idx)
    df["feat_1"] = pd.Series(rets, index=idx).rolling(5, min_periods=1).mean()
    df["feat_2"] = pd.Series(rets, index=idx).rolling(10, min_periods=1).std().fillna(0.0)
    return df


def test_walk_forward_predictions_are_oos_only() -> None:
    df = _synthetic_price_frame()
    out, _, meta = train_lightgbm_classifier(
        df=df,
        model_cfg={
            "params": {"n_estimators": 30, "learning_rate": 0.05},
            "feature_cols": ["feat_1", "feat_2"],
            "target": {"kind": "forward_return", "price_col": "close", "horizon": 2},
            "runtime": {"seed": 7, "deterministic": True, "threads": 1, "repro_mode": "strict"},
            "split": {
                "method": "walk_forward",
                "train_size": 120,
                "test_size": 20,
                "step_size": 20,
                "expanding": True,
            },
        },
    )

    assert meta["split_method"] == "walk_forward"
    assert meta["n_folds"] > 1
    assert int(out["pred_is_oos"].sum()) == sum(f["test_rows"] for f in meta["folds"])
    assert meta["split_index"] == meta["folds"][0]["test_start"]


def test_purged_splits_respect_anti_leakage_gap() -> None:
    df = _synthetic_price_frame()
    purge_bars = 3
    out, _, meta = train_lightgbm_classifier(
        df=df,
        model_cfg={
            "params": {"n_estimators": 30, "learning_rate": 0.05},
            "feature_cols": ["feat_1", "feat_2"],
            "target": {"kind": "forward_return", "price_col": "close", "horizon": 3},
            "runtime": {"seed": 7, "deterministic": True, "threads": 1, "repro_mode": "strict"},
            "split": {
                "method": "purged",
                "train_size": 120,
                "test_size": 20,
                "step_size": 20,
                "purge_bars": purge_bars,
                "embargo_bars": 2,
                "expanding": True,
            },
        },
    )

    assert meta["split_method"] == "purged"
    assert out["pred_is_oos"].any()
    for fold in meta["folds"]:
        assert fold["train_end"] <= fold["test_start"] - purge_bars
