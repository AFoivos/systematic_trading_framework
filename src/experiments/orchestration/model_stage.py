from __future__ import annotations

from typing import Any

import pandas as pd

from src.experiments.registry import get_model_fn


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
    ) -> dict[str, float | int | None]:
        total_eval_rows = sum(
            int(meta.get(summary_key, {}).get("evaluation_rows") or 0)
            for meta in per_asset_meta.values()
        )
        out: dict[str, float | int | None] = {"evaluation_rows": int(total_eval_rows)}
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
                rows = int(summary.get("evaluation_rows") or 0)
                if value is None or rows <= 0:
                    continue
                weighted_value += float(value) * rows
                weight_total += rows
            if weight_total > 0:
                out[key] = float(weighted_value / weight_total)
        return out

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
    }


def apply_model_to_assets(
    asset_frames: dict[str, pd.DataFrame],
    *,
    model_cfg: dict[str, Any],
    returns_col: str | None,
) -> tuple[dict[str, pd.DataFrame], object | dict[str, object] | None, dict[str, Any]]:
    if model_cfg.get("kind", "none") == "none":
        return asset_frames, None, {}

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


__all__ = ["aggregate_model_meta", "apply_model_step", "apply_model_to_assets"]
