from __future__ import annotations

from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier

from src.models.lightgbm_baseline import default_feature_columns


def infer_feature_columns(
    df: pd.DataFrame,
    explicit_cols: Sequence[str] | None = None,
    exclude: Iterable[str] | None = None,
) -> list[str]:
    if explicit_cols:
        missing = [c for c in explicit_cols if c not in df.columns]
        if missing:
            raise KeyError(f"Missing feature columns: {missing}")
        return list(explicit_cols)

    inferred = default_feature_columns(df)
    if inferred:
        return inferred

    exclude_set = set(exclude or [])
    exclude_set.update({"open", "high", "low", "close", "adj_close", "volume"})

    numeric_cols = df.select_dtypes(include=["number"]).columns
    features: list[str] = []
    for col in numeric_cols:
        if col in exclude_set:
            continue
        if col.startswith(("signal_", "pred_", "target_")):
            continue
        features.append(col)
    return features


def _build_forward_return_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    cfg = dict(target_cfg or {})
    price_col = cfg.get("price_col", "close")
    horizon = int(cfg.get("horizon", 1))
    fwd_col = cfg.get("fwd_col", f"target_fwd_{horizon}")
    label_col = cfg.get("label_col", "label")
    threshold = float(cfg.get("threshold", 0.0))
    quantiles = cfg.get("quantiles")

    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame")

    out = df.copy()
    out[fwd_col] = out[price_col].pct_change(periods=horizon).shift(-horizon)

    if quantiles:
        if not isinstance(quantiles, (list, tuple)) or len(quantiles) != 2:
            raise ValueError("target.quantiles must be a [low, high] pair")
        q_low, q_high = out[fwd_col].quantile([quantiles[0], quantiles[1]])
        label = pd.Series(np.nan, index=out.index, dtype="float32")
        label[out[fwd_col] <= q_low] = 0.0
        label[out[fwd_col] >= q_high] = 1.0
        out[label_col] = label
    else:
        out[label_col] = (out[fwd_col] > threshold).astype(int)

    meta = {
        "kind": "forward_return",
        "price_col": price_col,
        "horizon": horizon,
        "fwd_col": fwd_col,
        "label_col": label_col,
        "threshold": threshold,
        "quantiles": quantiles,
    }
    return out, label_col, fwd_col, meta


def train_lightgbm_classifier(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, LGBMClassifier, dict[str, Any]]:
    model_cfg = dict(model_cfg or {})
    model_params = dict(model_cfg.get("params", {}) or {})
    model_params.setdefault("n_jobs", -1)

    pred_prob_col = model_cfg.get("pred_prob_col", "pred_prob")
    target_cfg = model_cfg.get("target", {}) or {}
    target_kind = target_cfg.get("kind", "forward_return")
    if target_kind != "forward_return":
        raise ValueError(f"Unsupported target.kind: {target_kind}")

    out, label_col, fwd_col, target_meta = _build_forward_return_target(df=df, target_cfg=target_cfg)

    feature_cols = infer_feature_columns(
        out,
        explicit_cols=model_cfg.get("feature_cols"),
        exclude={label_col, fwd_col, pred_prob_col},
    )
    if not feature_cols:
        raise ValueError("No feature columns resolved for model training.")

    split_cfg = model_cfg.get("split", {}) or {}
    method = split_cfg.get("method", "time")
    train_frac = float(split_cfg.get("train_frac", 0.7))
    if method != "time":
        raise ValueError(f"Unsupported split.method: {method}")
    if not 0.0 < train_frac < 1.0:
        raise ValueError("split.train_frac must be in (0,1)")

    split_idx = int(len(out) * train_frac)
    train_df = out.iloc[:split_idx]
    test_df = out.iloc[split_idx:]

    train_fit = train_df.dropna(subset=feature_cols + [label_col])
    if train_fit.empty:
        raise ValueError("No training rows after dropping NaNs in features/labels.")

    X_train = train_fit[feature_cols]
    y_train = train_fit[label_col].astype(int)

    model = LGBMClassifier(**model_params)
    model.fit(X_train, y_train)

    pred_prob = pd.Series(np.nan, index=out.index, name=pred_prob_col, dtype="float32")
    test_features = test_df[feature_cols]
    valid_mask = test_features.notna().all(axis=1)
    if valid_mask.any():
        proba = model.predict_proba(test_features.loc[valid_mask])[:, 1]
        pred_prob.loc[test_features.loc[valid_mask].index] = proba

    out[pred_prob_col] = pred_prob

    meta = {
        "model_kind": "lightgbm_clf",
        "feature_cols": feature_cols,
        "pred_prob_col": pred_prob_col,
        "label_col": label_col,
        "fwd_col": fwd_col,
        "split_method": method,
        "train_frac": train_frac,
        "split_index": split_idx,
        "train_rows": int(len(train_fit)),
        "test_pred_rows": int(valid_mask.sum()),
        "target": target_meta,
        "returns_col": returns_col,
    }
    return out, model, meta
