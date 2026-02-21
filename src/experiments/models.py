from __future__ import annotations

from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier

from src.evaluation.time_splits import (
    assert_no_forward_label_leakage,
    build_time_splits,
    trim_train_indices_for_horizon,
)
from src.experiments.contracts import TargetContract, validate_feature_target_contract
from src.models.lightgbm_baseline import default_feature_columns


def _resolve_runtime_for_model(model_cfg: dict[str, Any], model_params: dict[str, Any]) -> dict[str, Any]:
    runtime_cfg = dict(model_cfg.get("runtime", {}) or {})

    seed = runtime_cfg.get("seed", model_params.get("random_state", 7))
    if not isinstance(seed, int) or seed < 0:
        raise ValueError("model.runtime.seed must be an integer >= 0.")

    deterministic = runtime_cfg.get("deterministic", True)
    if not isinstance(deterministic, bool):
        raise ValueError("model.runtime.deterministic must be a boolean.")

    repro_mode = runtime_cfg.get("repro_mode", "strict")
    if repro_mode not in {"strict", "relaxed"}:
        raise ValueError("model.runtime.repro_mode must be 'strict' or 'relaxed'.")

    threads = runtime_cfg.get("threads")
    if threads is not None and (not isinstance(threads, int) or threads <= 0):
        raise ValueError("model.runtime.threads must be null or a positive integer.")
    if repro_mode == "strict" and threads is None:
        threads = 1

    model_params.setdefault("random_state", seed)
    model_params.setdefault("seed", seed)

    if deterministic:
        model_params.setdefault("deterministic", True)
        model_params.setdefault("force_col_wise", True)
        model_params.setdefault("feature_fraction_seed", seed)
        model_params.setdefault("bagging_seed", seed)
        model_params.setdefault("data_random_seed", seed)

    if threads is not None:
        model_params["n_jobs"] = threads
    else:
        model_params.setdefault("n_jobs", -1)

    return {
        "seed": seed,
        "deterministic": deterministic,
        "threads": model_params.get("n_jobs"),
        "repro_mode": repro_mode,
    }


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
    if horizon <= 0:
        raise ValueError("target.horizon must be a positive integer.")
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
    runtime_meta = _resolve_runtime_for_model(model_cfg=model_cfg, model_params=model_params)

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
    contract_meta = validate_feature_target_contract(
        out,
        feature_cols=feature_cols,
        target=TargetContract(target_col=label_col, horizon=int(target_meta["horizon"])),
    )

    split_cfg = model_cfg.get("split", {}) or {}
    method = split_cfg.get("method", "time")
    if method not in {"time", "walk_forward", "purged"}:
        raise ValueError(f"Unsupported split.method: {method}")

    splits = build_time_splits(
        method=method,
        n_samples=len(out),
        split_cfg=dict(split_cfg),
        target_horizon=int(target_meta.get("horizon", 1)),
    )

    pred_prob = pd.Series(np.nan, index=out.index, name=pred_prob_col, dtype="float32")
    oos_mask = pd.Series(False, index=out.index, name="pred_is_oos")
    oos_assignment_count = pd.Series(0, index=out.index, dtype="int32")

    fold_meta: list[dict[str, Any]] = []
    model: LGBMClassifier | None = None
    total_train_rows = 0
    total_test_pred_rows = 0
    total_trimmed_rows = 0
    target_horizon = int(target_meta["horizon"])

    for split in splits:
        raw_train_idx = split.train_idx
        safe_train_idx = trim_train_indices_for_horizon(
            raw_train_idx,
            test_start=int(split.test_start),
            target_horizon=target_horizon,
        )
        assert_no_forward_label_leakage(
            safe_train_idx,
            test_start=int(split.test_start),
            target_horizon=target_horizon,
        )

        trimmed_rows = int(len(raw_train_idx) - len(safe_train_idx))
        total_trimmed_rows += trimmed_rows

        train_df = out.iloc[safe_train_idx]
        test_df = out.iloc[split.test_idx]

        train_fit = train_df.dropna(subset=feature_cols + [label_col])
        if train_fit.empty:
            raise ValueError(f"Fold {split.fold} has no train rows after dropping NaNs in features/labels.")

        X_train = train_fit[feature_cols]
        y_train = train_fit[label_col].astype(int)
        if int(y_train.nunique()) < 2:
            raise ValueError(f"Fold {split.fold} has a single target class after preprocessing.")

        model = LGBMClassifier(**model_params)
        model.fit(X_train, y_train)

        test_features = test_df[feature_cols]
        valid_mask = test_features.notna().all(axis=1)
        pred_rows = int(valid_mask.sum())
        if pred_rows > 0:
            proba = model.predict_proba(test_features.loc[valid_mask])[:, 1].astype("float32")
            pred_prob.loc[test_features.loc[valid_mask].index] = proba

        fold_test_idx = out.index[split.test_idx]
        oos_mask.loc[fold_test_idx] = True
        oos_assignment_count.loc[fold_test_idx] += 1

        total_train_rows += int(len(train_fit))
        total_test_pred_rows += pred_rows
        fold_meta.append(
            {
                "fold": int(split.fold),
                "train_start": int(split.train_start),
                "train_end": int(split.train_end),
                "effective_train_start": int(safe_train_idx.min()) if len(safe_train_idx) else None,
                "effective_train_end": int(safe_train_idx.max() + 1) if len(safe_train_idx) else None,
                "trimmed_for_horizon_rows": trimmed_rows,
                "test_start": int(split.test_start),
                "test_end": int(split.test_end),
                "train_rows": int(len(train_fit)),
                "test_rows": int(len(split.test_idx)),
                "test_pred_rows": pred_rows,
            }
        )

    if model is None:
        raise ValueError("Model training failed: no valid folds were trained.")

    if (oos_assignment_count > 1).any():
        raise ValueError("Overlapping test windows detected. Use non-overlapping split configuration.")

    out[pred_prob_col] = pred_prob
    out["pred_is_oos"] = oos_mask

    meta = {
        "model_kind": "lightgbm_clf",
        "runtime": runtime_meta,
        "feature_cols": feature_cols,
        "pred_prob_col": pred_prob_col,
        "label_col": label_col,
        "fwd_col": fwd_col,
        "split_method": method,
        "split_index": int(splits[0].test_start),
        "n_folds": int(len(splits)),
        "folds": fold_meta,
        "train_rows": int(total_train_rows),
        "test_pred_rows": int(total_test_pred_rows),
        "oos_rows": int(oos_mask.sum()),
        "target": target_meta,
        "returns_col": returns_col,
        "contracts": contract_meta,
        "anti_leakage": {
            "target_horizon": target_horizon,
            "total_trimmed_train_rows": int(total_trimmed_rows),
        },
    }
    return out, model, meta
