from __future__ import annotations

import numpy as np
import pandas as pd

from src.experiments.models import train_lightgbm_classifier


def _synthetic_price_frame(n: int = 260) -> pd.DataFrame:
    """
    Verify that synthetic price frame behaves as expected under a representative regression
    scenario. The test protects the intended contract of the surrounding component and makes
    failures easier to localize.
    """
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
    """
    Verify that walk forward predictions are out-of-sample only behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
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
    """
    Verify that purged splits respect anti leakage gap behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
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


def test_binary_forward_target_keeps_tail_labels_nan() -> None:
    """
    Verify that binary forward target keeps tail labels nan behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    horizon = 5
    df = _synthetic_price_frame()
    out, _, meta = train_lightgbm_classifier(
        df=df,
        model_cfg={
            "params": {"n_estimators": 30, "learning_rate": 0.05},
            "feature_cols": ["feat_1", "feat_2"],
            "target": {"kind": "forward_return", "price_col": "close", "horizon": horizon},
            "runtime": {"seed": 7, "deterministic": True, "threads": 1, "repro_mode": "strict"},
            "split": {"method": "time", "train_frac": 0.7},
        },
    )

    label_col = str(meta["label_col"])
    assert out[label_col].tail(horizon).isna().all()


def test_quantile_target_uses_train_only_distribution_per_fold() -> None:
    """
    Verify that quantile target uses train only distribution per fold behaves as expected under
    a representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    df = _synthetic_price_frame()
    tail_idx = df.index[-40:]
    base = float(df.loc[df.index[-41], "close"])
    df.loc[tail_idx, "close"] = base * np.exp(np.linspace(0.0, 4.0, len(tail_idx)))

    out, _, meta = train_lightgbm_classifier(
        df=df,
        model_cfg={
            "params": {"n_estimators": 30, "learning_rate": 0.05},
            "feature_cols": ["feat_1", "feat_2"],
            "target": {
                "kind": "forward_return",
                "price_col": "close",
                "horizon": 1,
                "quantiles": [0.2, 0.8],
            },
            "runtime": {"seed": 7, "deterministic": True, "threads": 1, "repro_mode": "strict"},
            "split": {
                "method": "walk_forward",
                "train_size": 120,
                "test_size": 40,
                "step_size": 40,
                "expanding": True,
            },
        },
    )

    fwd_col = str(meta["fwd_col"])
    first_fold = meta["folds"][0]
    fold_q_high = float(first_fold["quantile_high_value"])
    global_q_high = float(out[fwd_col].dropna().quantile(0.8))
    assert fold_q_high < global_q_high
