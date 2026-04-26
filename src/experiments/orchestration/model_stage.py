from __future__ import annotations

from copy import deepcopy
from typing import Any

import pandas as pd

from src.experiments.support.diagnostics import aggregate_feature_importance, aggregate_label_distributions
from src.experiments.registry import get_model_fn, is_portfolio_model_kind


def apply_model_step(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None,
) -> tuple[pd.DataFrame, object | None, dict[str, Any]]:
    kind = model_cfg.get("kind", "none")
    if kind == "none":
        return df, None, {}
    fn = get_model_fn(kind)
    return fn(df, model_cfg, returns_col)


def aggregate_model_meta(per_asset_meta: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not per_asset_meta:
        return {}

    def weighted_summary(
        *,
        summary_key: str,
        metric_keys: tuple[str, ...],
        weight_key: str = "evaluation_rows",
    ) -> dict[str, float | int | None]:
        total_eval_rows = sum(
            int(meta.get(summary_key, {}).get(weight_key) or 0)
            for meta in per_asset_meta.values()
        )
        out: dict[str, float | int | None] = {weight_key: int(total_eval_rows)}
        for key in metric_keys:
            out[key] = None
        if total_eval_rows <= 0:
            return out

        for key in metric_keys:
            weighted_value = 0.0
            weight_total = 0
            for meta in per_asset_meta.values():
                summary = dict(meta.get(summary_key, {}) or {})
                value = summary.get(key)
                rows = int(summary.get(weight_key) or 0)
                if value is None or rows <= 0:
                    continue
                weighted_value += float(value) * rows
                weight_total += rows
            if weight_total > 0:
                out[key] = float(weighted_value / weight_total)
        return out

    def weighted_policy_summary() -> dict[str, float | int | None]:
        reward_rows = sum(
            int(meta.get("oos_policy_summary", {}).get("evaluation_rows") or 0)
            for meta in per_asset_meta.values()
        )
        signal_rows = sum(
            int(meta.get("oos_policy_summary", {}).get("signal_rows") or 0)
            for meta in per_asset_meta.values()
        )
        out: dict[str, float | int | None] = {
            "evaluation_rows": int(reward_rows),
            "signal_rows": int(signal_rows),
            "mean_reward": None,
            "total_reward": None,
            "mean_abs_signal": None,
            "signal_turnover": None,
            "long_rate": None,
            "short_rate": None,
            "flat_rate": None,
        }
        if reward_rows > 0:
            total_reward = 0.0
            weighted_reward = 0.0
            weight_total = 0
            for meta in per_asset_meta.values():
                summary = dict(meta.get("oos_policy_summary", {}) or {})
                rows = int(summary.get("evaluation_rows") or 0)
                mean_reward = summary.get("mean_reward")
                if rows > 0 and mean_reward is not None:
                    weighted_reward += float(mean_reward) * rows
                    weight_total += rows
                total = summary.get("total_reward")
                if total is not None:
                    total_reward += float(total)
            if weight_total > 0:
                out["mean_reward"] = float(weighted_reward / weight_total)
            out["total_reward"] = float(total_reward)

        for key in ("mean_abs_signal", "signal_turnover", "long_rate", "short_rate", "flat_rate"):
            numerator = 0.0
            weight_total = 0
            for meta in per_asset_meta.values():
                summary = dict(meta.get("oos_policy_summary", {}) or {})
                rows = int(summary.get("signal_rows") or 0)
                value = summary.get(key)
                if rows <= 0 or value is None:
                    continue
                numerator += float(value) * rows
                weight_total += rows
            if weight_total > 0:
                out[key] = float(numerator / weight_total)
        return out

    def aggregate_target_meta() -> dict[str, Any]:
        target_items = [dict(meta.get("target", {}) or {}) for meta in per_asset_meta.values()]
        target_items = [item for item in target_items if item]
        if not target_items:
            return {}
        target = dict(target_items[0])
        for key in (
            "labeled_rows",
            "upper_barrier_count",
            "lower_barrier_count",
            "neutral_count",
            "candidate_rows",
            "unavailable_tail_count",
        ):
            if any(item.get(key) is not None for item in target_items):
                target[key] = int(sum(int(item.get(key, 0) or 0) for item in target_items))
        labeled_rows = int(target.get("labeled_rows", 0) or 0)
        if labeled_rows > 0:
            positive_sum = 0.0
            positive_weight = 0
            for item in target_items:
                rows = int(item.get("labeled_rows", 0) or 0)
                rate = item.get("positive_rate")
                if rows > 0 and rate is not None:
                    positive_sum += float(rate) * rows
                    positive_weight += rows
            if positive_weight > 0:
                target["positive_rate"] = float(positive_sum / positive_weight)
        for key in ("avg_hit_step", "median_hit_step"):
            values = [float(item[key]) for item in target_items if item.get(key) is not None]
            if values:
                target[key] = float(sum(values) / len(values))
        return target

    first = next(iter(per_asset_meta.values()))
    weighted_classification_summary = weighted_summary(
        summary_key="oos_classification_summary",
        metric_keys=("positive_rate", "accuracy", "brier", "roc_auc", "log_loss"),
    )
    weighted_regression_summary = weighted_summary(
        summary_key="oos_regression_summary",
        metric_keys=(
            "mae",
            "rmse",
            "mse",
            "r2",
            "correlation",
            "directional_accuracy",
            "mean_prediction",
            "mean_target",
        ),
    )
    weighted_volatility_summary = weighted_summary(
        summary_key="oos_volatility_summary",
        metric_keys=("mae", "rmse", "correlation", "mean_prediction", "mean_target"),
    )

    feature_importance = aggregate_feature_importance(
        [list(dict(meta.get("feature_importance", {}) or {}).get("top_features", []) or []) for meta in per_asset_meta.values()]
    )

    prediction_rows = sum(
        int(meta.get("prediction_diagnostics", {}).get("predicted_rows") or 0)
        for meta in per_asset_meta.values()
    )
    oos_rows = sum(
        int(meta.get("prediction_diagnostics", {}).get("oos_rows") or 0)
        for meta in per_asset_meta.values()
    )
    non_oos_prediction_rows = sum(
        int(meta.get("prediction_diagnostics", {}).get("non_oos_prediction_rows") or 0)
        for meta in per_asset_meta.values()
    )
    missing_oos_prediction_rows = sum(
        int(meta.get("prediction_diagnostics", {}).get("missing_oos_prediction_rows") or 0)
        for meta in per_asset_meta.values()
    )
    missing_value_diagnostics = {
        "train_rows_dropped_missing": int(
            sum(int(meta.get("missing_value_diagnostics", {}).get("train_rows_dropped_missing", 0) or 0) for meta in per_asset_meta.values())
        ),
        "test_rows_missing_features": int(
            sum(int(meta.get("missing_value_diagnostics", {}).get("test_rows_missing_features", 0) or 0) for meta in per_asset_meta.values())
        ),
        "test_rows_not_candidates": int(
            sum(int(meta.get("missing_value_diagnostics", {}).get("test_rows_not_candidates", 0) or 0) for meta in per_asset_meta.values())
        ),
        "test_rows_without_prediction": int(
            sum(int(meta.get("missing_value_diagnostics", {}).get("test_rows_without_prediction", 0) or 0) for meta in per_asset_meta.values())
        ),
        "folds_with_zero_predictions": int(
            sum(int(meta.get("missing_value_diagnostics", {}).get("folds_with_zero_predictions", 0) or 0) for meta in per_asset_meta.values())
        ),
    }
    label_distribution = {
        "train": aggregate_label_distributions(
            [dict(meta.get("label_distribution", {}) or {}).get("train", {}) for meta in per_asset_meta.values()]
        ),
        "oos_evaluation": aggregate_label_distributions(
            [dict(meta.get("label_distribution", {}) or {}).get("oos_evaluation", {}) for meta in per_asset_meta.values()]
        ),
    }

    return {
        "model_kind": first.get("model_kind"),
        "assets": sorted(per_asset_meta),
        "per_asset": per_asset_meta,
        "train_rows": int(sum(int(meta.get("train_rows", 0)) for meta in per_asset_meta.values())),
        "test_pred_rows": int(sum(int(meta.get("test_pred_rows", 0)) for meta in per_asset_meta.values())),
        "oos_rows": int(sum(int(meta.get("oos_rows", 0)) for meta in per_asset_meta.values())),
        "oos_classification_summary": weighted_classification_summary,
        "oos_regression_summary": weighted_regression_summary,
        "oos_volatility_summary": weighted_volatility_summary,
        "oos_policy_summary": weighted_policy_summary(),
        "feature_importance": feature_importance,
        "label_distribution": label_distribution,
        "target": aggregate_target_meta(),
        "prediction_diagnostics": {
            "oos_rows": int(oos_rows),
            "predicted_rows": int(prediction_rows),
            "non_oos_prediction_rows": int(non_oos_prediction_rows),
            "missing_oos_prediction_rows": int(missing_oos_prediction_rows),
            "oos_prediction_coverage": float(prediction_rows / max(oos_rows, 1)),
            "alignment_ok": bool(non_oos_prediction_rows == 0),
        },
        "missing_value_diagnostics": missing_value_diagnostics,
    }


def apply_model_to_assets(
    asset_frames: dict[str, pd.DataFrame],
    *,
    model_cfg: dict[str, Any],
    returns_col: str | None,
) -> tuple[dict[str, pd.DataFrame], object | dict[str, object] | None, dict[str, Any]]:
    kind = model_cfg.get("kind", "none")
    if kind == "none":
        return asset_frames, None, {}

    if is_portfolio_model_kind(str(kind)):
        fn = get_model_fn(str(kind))
        return fn(dict(sorted(asset_frames.items())), model_cfg, returns_col)

    out: dict[str, pd.DataFrame] = {}
    models: dict[str, object] = {}
    metas: dict[str, dict[str, Any]] = {}

    for asset, df in sorted(asset_frames.items()):
        frame, model, meta = apply_model_step(df, model_cfg, returns_col)
        out[asset] = frame
        models[asset] = model
        metas[asset] = meta

    if len(out) == 1:
        only_asset = next(iter(sorted(out)))
        return out, models[only_asset], metas[only_asset]
    return out, models, aggregate_model_meta(metas)


def _stage_record(
    *,
    stage_name: str,
    stage_cfg: dict[str, Any],
    stage_meta: dict[str, Any],
) -> dict[str, Any]:
    return {
        "name": stage_name,
        "kind": str(stage_cfg.get("kind", "none")),
        "stage": stage_cfg.get("stage"),
        "feature_cols": list(stage_meta.get("feature_cols", []) or []),
        "embedding_cols": list(stage_meta.get("embedding_cols", []) or []),
        "pred_prob_col": stage_meta.get("pred_prob_col"),
        "pred_ret_col": stage_meta.get("pred_ret_col"),
        "signal_col": stage_meta.get("signal_col"),
        "action_col": stage_meta.get("action_col"),
        "oos_classification_summary": dict(stage_meta.get("oos_classification_summary", {}) or {}),
        "oos_regression_summary": dict(stage_meta.get("oos_regression_summary", {}) or {}),
        "oos_volatility_summary": dict(stage_meta.get("oos_volatility_summary", {}) or {}),
        "prediction_diagnostics": dict(stage_meta.get("prediction_diagnostics", {}) or {}),
        "preprocessing": dict(stage_meta.get("preprocessing", {}) or {}),
        "target": dict(stage_meta.get("target", {}) or {}),
        "anti_leakage": dict(stage_meta.get("anti_leakage", {}) or {}),
        "meta": deepcopy(stage_meta),
    }


def _normalize_enabled_stage_cfgs(model_stages: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    stage_cfgs: list[dict[str, Any]] = []
    for idx, raw_stage in enumerate(list(model_stages or [])):
        stage_cfg = dict(raw_stage)
        if not bool(stage_cfg.get("enabled", True)):
            continue
        stage_cfg.setdefault("stage", idx + 1)
        stage_cfg.setdefault("name", f"stage_{idx + 1}")
        stage_cfgs.append(stage_cfg)
    stage_cfgs.sort(key=lambda stage: (int(stage.get("stage", 0) or 0), str(stage.get("name", ""))))
    return stage_cfgs


def apply_model_pipeline_to_assets(
    asset_frames: dict[str, pd.DataFrame],
    *,
    model_cfg: dict[str, Any] | None,
    model_stages: list[dict[str, Any]] | None,
    returns_col: str | None,
) -> tuple[dict[str, pd.DataFrame], object | dict[str, object] | None, dict[str, Any]]:
    stage_cfgs = _normalize_enabled_stage_cfgs(model_stages)
    if not stage_cfgs:
        return apply_model_to_assets(
            asset_frames,
            model_cfg=dict(model_cfg or {"kind": "none"}) or {"kind": "none"},
            returns_col=returns_col,
        )

    current_frames = dict(sorted(asset_frames.items()))
    stage_models: dict[str, object | dict[str, object] | None] = {}
    stage_records: list[dict[str, Any]] = []
    final_meta: dict[str, Any] = {}

    for idx, raw_stage_cfg in enumerate(stage_cfgs):
        stage_cfg = dict(raw_stage_cfg)
        stage_name = str(stage_cfg.pop("name", f"stage_{idx + 1}"))
        stage_order = int(stage_cfg.pop("stage", idx + 1))
        stage_cfg.pop("enabled", None)
        current_frames, stage_model, stage_meta = apply_model_to_assets(
            current_frames,
            model_cfg=stage_cfg,
            returns_col=returns_col,
        )
        stage_models[stage_name] = stage_model
        stage_records.append(
            _stage_record(
                stage_name=stage_name,
                stage_cfg={"name": stage_name, "kind": stage_cfg.get("kind"), "stage": stage_order},
                stage_meta={"stage": stage_order} | dict(stage_meta),
            )
        )
        final_meta = stage_meta

    pipeline_meta = dict(final_meta)
    pipeline_meta["pipeline_kind"] = "multi_stage"
    pipeline_meta["stage_count"] = int(len(stage_records))
    pipeline_meta["stage_names"] = [str(stage["name"]) for stage in stage_records]
    pipeline_meta["stages"] = stage_records
    return current_frames, stage_models, pipeline_meta


__all__ = [
    "aggregate_model_meta",
    "apply_model_pipeline_to_assets",
    "apply_model_step",
    "apply_model_to_assets",
]
