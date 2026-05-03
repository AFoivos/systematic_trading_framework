from __future__ import annotations

from typing import Any

import pandas as pd

from src.targets import build_classifier_target


def _flatten_target_cfg(target_cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = dict(target_cfg or {})
    params = cfg.pop("params", None)
    if params is not None:
        if not isinstance(params, dict):
            raise ValueError("model.target.params must be a mapping when provided.")
        cfg.update(dict(params))
    return cfg


def _merge_trade_management_defaults(
    target_cfg: dict[str, Any],
    *,
    backtest_cfg: dict[str, Any],
) -> dict[str, Any]:
    cfg = _flatten_target_cfg(target_cfg)
    for key in ("take_profit_r", "stop_loss_r", "max_holding_bars"):
        if cfg.get(key) is None and backtest_cfg.get(key) is not None:
            cfg[key] = backtest_cfg[key]
    return cfg


def should_apply_post_signal_target(model_cfg: dict[str, Any]) -> bool:
    """
    Target-only diagnostics for manual strategies whose candidate signal is emitted in signals stage.
    """
    if str(model_cfg.get("kind", "none")) != "none":
        return False
    target_cfg = _flatten_target_cfg(dict(model_cfg.get("target", {}) or {}))
    return str(target_cfg.get("kind", "")) == "r_multiple"


def _weighted_rate(items: list[dict[str, Any]], *, value_key: str, weight_key: str) -> float | None:
    numerator = 0.0
    denominator = 0
    for item in items:
        value = item.get(value_key)
        weight = int(item.get(weight_key, 0) or 0)
        if value is None or weight <= 0:
            continue
        numerator += float(value) * weight
        denominator += weight
    return float(numerator / denominator) if denominator > 0 else None


def _average_present(items: list[dict[str, Any]], *, key: str) -> float | None:
    values = [float(item[key]) for item in items if item.get(key) is not None]
    if not values:
        return None
    return float(sum(values) / len(values))


def _sum_counts(items: list[dict[str, Any]], *, key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        for label, value in dict(item.get(key, {}) or {}).items():
            counts[str(label)] = counts.get(str(label), 0) + int(value or 0)
    return counts


def _aggregate_winner_loser_feature_summary(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    features = sorted(
        {
            str(feature)
            for item in items
            for feature in dict(item.get("winner_loser_feature_summary", {}) or {})
        }
    )
    out: dict[str, dict[str, Any]] = {}
    for feature in features:
        winner_rows = 0
        loser_rows = 0
        winner_mean_num = 0.0
        loser_mean_num = 0.0
        winner_medians: list[float] = []
        loser_medians: list[float] = []
        for item in items:
            payload = dict(dict(item.get("winner_loser_feature_summary", {}) or {}).get(feature, {}) or {})
            current_winner_rows = int(payload.get("winner_rows", 0) or 0)
            current_loser_rows = int(payload.get("loser_rows", 0) or 0)
            winner_rows += current_winner_rows
            loser_rows += current_loser_rows
            if payload.get("winner_mean") is not None and current_winner_rows > 0:
                winner_mean_num += float(payload["winner_mean"]) * current_winner_rows
            if payload.get("loser_mean") is not None and current_loser_rows > 0:
                loser_mean_num += float(payload["loser_mean"]) * current_loser_rows
            if payload.get("winner_median") is not None:
                winner_medians.append(float(payload["winner_median"]))
            if payload.get("loser_median") is not None:
                loser_medians.append(float(payload["loser_median"]))
        winner_mean = float(winner_mean_num / winner_rows) if winner_rows > 0 else None
        loser_mean = float(loser_mean_num / loser_rows) if loser_rows > 0 else None
        out[feature] = {
            "winner_rows": int(winner_rows),
            "loser_rows": int(loser_rows),
            "winner_mean": winner_mean,
            "loser_mean": loser_mean,
            "mean_diff": (
                float(winner_mean - loser_mean)
                if winner_mean is not None and loser_mean is not None
                else None
            ),
            "winner_median": (
                float(sum(winner_medians) / len(winner_medians)) if winner_medians else None
            ),
            "loser_median": (
                float(sum(loser_medians) / len(loser_medians)) if loser_medians else None
            ),
        }
    return out


def aggregate_target_metas(per_asset_meta: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not per_asset_meta:
        return {}
    items = [dict(meta) for meta in per_asset_meta.values()]
    target = dict(items[0])
    for key in (
        "candidate_rows",
        "labeled_rows",
        "take_profit_count",
        "stop_loss_count",
        "max_holding_close_count",
        "unavailable_tail_count",
        "invalid_entry_count",
    ):
        if any(item.get(key) is not None for item in items):
            target[key] = int(sum(int(item.get(key, 0) or 0) for item in items))

    positive_rate = _weighted_rate(items, value_key="positive_rate", weight_key="labeled_rows")
    if positive_rate is not None:
        target["positive_rate"] = positive_rate

    for key in (
        "avg_trade_r",
        "median_trade_r",
        "q25_trade_r",
        "q75_trade_r",
        "avg_bars_held",
        "median_bars_held",
    ):
        value = _average_present(items, key=key)
        if value is not None:
            target[key] = value

    label_counts = _sum_counts(
        [dict(item.get("label_distribution", {}) or {}) for item in items],
        key="class_counts",
    )
    labeled_rows = int(target.get("labeled_rows", 0) or 0)
    target["label_distribution"] = {
        "rows": labeled_rows,
        "class_counts": label_counts,
        "positive_rate": target.get("positive_rate"),
    }
    target["exit_reason_counts"] = _sum_counts(items, key="exit_reason_counts")
    target["winner_loser_feature_summary"] = _aggregate_winner_loser_feature_summary(items)
    target["assets"] = sorted(per_asset_meta)
    return target


def apply_post_signal_target_to_assets(
    asset_frames: dict[str, pd.DataFrame],
    *,
    model_cfg: dict[str, Any],
    backtest_cfg: dict[str, Any],
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    if not should_apply_post_signal_target(model_cfg):
        return asset_frames, {}

    target_cfg = _merge_trade_management_defaults(
        dict(model_cfg.get("target", {}) or {}),
        backtest_cfg=backtest_cfg,
    )
    out: dict[str, pd.DataFrame] = {}
    per_asset_meta: dict[str, dict[str, Any]] = {}
    for asset, frame in sorted(asset_frames.items()):
        target_frame, _, _, target_meta = build_classifier_target(frame, target_cfg)
        out[asset] = target_frame
        per_asset_meta[str(asset)] = target_meta

    if len(per_asset_meta) == 1:
        target_meta = next(iter(per_asset_meta.values()))
    else:
        target_meta = aggregate_target_metas(per_asset_meta)

    return out, {
        "model_kind": "none",
        "target": target_meta,
        "label_distribution": {
            "full_target": dict(target_meta.get("label_distribution", {}) or {})
        },
    }


__all__ = [
    "aggregate_target_metas",
    "apply_post_signal_target_to_assets",
    "should_apply_post_signal_target",
]
