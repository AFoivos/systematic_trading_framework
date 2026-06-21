"""Reproducible ablations for the Ehlers ML long-only v2 experiment."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from src.utils.config import load_experiment_config
from src.utils.paths import PROJECT_ROOT


RAW_EHLERS_FEATURES = [
    "mama",
    "fama",
    "mama_minus_fama",
    "close_minus_decycler",
    "instantaneous_trendline_slope",
    "decycler_slope",
    "frama_slope",
    "supersmoother_slope",
    "roofing_filter",
    "roofing_filter_slope",
    "hilbert_amplitude",
    "hilbert_instantaneous_frequency",
    "dominant_cycle_period",
    "dominant_cycle_phase_normalized",
    "sinewave",
    "lead_sine",
    "cyber_cycle",
    "cyber_cycle_signal",
    "even_better_sinewave",
    "autocorrelation_periodogram_period",
    "homodyne_period",
    "fisher_transform",
    "inverse_fisher_transform",
    "decycler_oscillator",
    "laguerre_rsi",
    "center_of_gravity",
]


def build_ehlers_ml_ablation_configs(base_config_path: str | Path) -> dict[str, dict[str, Any]]:
    """Build full-normalized, indices-normalized, and full-raw standalone configs."""
    base = load_experiment_config(base_config_path)
    variants: dict[str, dict[str, Any]] = {}

    full_normalized = deepcopy(base)
    full_normalized["strategy"]["name"] = "ehlers_ml_v2_full_normalized"
    full_normalized["logging"]["run_name"] = "ehlers_ml_v2_full_normalized"
    variants["full_normalized"] = full_normalized

    indices = deepcopy(base)
    selected = ["SPX500", "US100"]
    indices["strategy"]["name"] = "ehlers_ml_v2_indices_normalized"
    indices["strategy"]["assets"] = selected
    indices["data"]["symbols"] = selected
    indices["data"]["storage"]["load_paths"] = {
        asset: indices["data"]["storage"]["load_paths"][asset]
        for asset in selected
    }
    indices["risk"]["portfolio_guard"]["max_open_trades"] = 2
    indices["risk"]["portfolio_guard"]["group_max_open_trades"] = {"equity_indices": 2}
    indices["portfolio"]["constraints"]["max_weight"] = 0.50
    indices["portfolio"]["constraints"]["group_max_exposure"] = {"equity_indices": 1.0}
    indices["portfolio"]["asset_groups"] = {asset: "equity_indices" for asset in selected}
    indices["logging"]["run_name"] = "ehlers_ml_v2_indices_normalized"
    variants["indices_normalized"] = indices

    full_raw = deepcopy(base)
    full_raw["strategy"]["name"] = "ehlers_ml_v2_full_raw_ablation"
    full_raw["model"]["feature_cols"] = list(RAW_EHLERS_FEATURES)
    full_raw["logging"]["run_name"] = "ehlers_ml_v2_full_raw_ablation"
    variants["full_raw"] = full_raw
    return variants


def run_ehlers_ml_ablation(
    base_config_path: str | Path,
    *,
    variants: list[str] | None = None,
) -> dict[str, Any]:
    """Run every ablation through the standard experiment runner and normal report path."""
    from src.experiments.runner import run_experiment

    tmp_dir = PROJECT_ROOT / "tmp" / "ehlers_ml_ablation"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    available = build_ehlers_ml_ablation_configs(base_config_path)
    selected = list(variants) if variants is not None else list(available)
    unknown = sorted(set(selected).difference(available))
    if unknown:
        raise ValueError(f"Unknown Ehlers ML ablation variants: {unknown}")
    results: dict[str, Any] = {}
    for name in selected:
        cfg = available[name]
        path = tmp_dir / f"{name}.yaml"
        try:
            with path.open("w", encoding="utf-8") as handle:
                yaml.safe_dump(cfg, handle, sort_keys=False)
            results[name] = run_experiment(path)
        finally:
            path.unlink(missing_ok=True)
    return results


__all__ = [
    "RAW_EHLERS_FEATURES",
    "build_ehlers_ml_ablation_configs",
    "run_ehlers_ml_ablation",
]
