from __future__ import annotations

"""Deterministic, baseline-centred research support for ETHUSD Trial 0041.

This module deliberately lives under :mod:`src.experiments.support`: it is a
research orchestrator around existing framework registries rather than a new
production strategy.  It keeps the historical Trial 0041 artifact immutable,
uses folds 0--9 only for screening, and reserves the unused 2024-09--2026-06
continuation (folds 10--16) as a locked holdout.

Causality contract
------------------
Feature and target builders are framework-owned and are called through their
registered interfaces.  Target outputs are never added to model features.
The support code rejects feature names that look like targets, predictions,
barrier diagnostics, or realised-trade outcomes.  Screening ranking is built
only from folds 0--9; locked-fold metrics are reported after finalist configs
have been frozen and are never fed back into config selection.
"""

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import shutil
from typing import Any, Callable, Iterable, Mapping

import numpy as np
import pandas as pd
import yaml

from src.backtesting.engine import run_backtest
from src.evaluation.metrics import compute_backtest_metrics, compute_ftmo_style_metrics
from src.evaluation.time_splits import build_time_splits
from src.experiments.orchestration.feature_stage import apply_feature_steps, apply_signal_step
from src.experiments.runner import run_experiment
from src.src_data.storage import load_ohlcv_csv
from src.src_data.validation import validate_ohlcv
from src.targets.registry import build_target
from src.utils.config import load_experiment_config
from src.utils.run_metadata import compute_dataframe_fingerprint, file_sha256


PROJECT_ROOT = Path(__file__).resolve().parents[3]
LAB_RELATIVE = Path("config/experiments/foundation_alpha/ethusd_30m_trial_0041_alpha_lab")
LAB_ROOT = PROJECT_ROOT / LAB_RELATIVE
REPORTS_DIR = LAB_ROOT / "reports"
SOURCE_CONFIG = PROJECT_ROOT / (
    "config/experiments/foundation_alpha/BEST/ethusd/"
    "optuna_BEST_ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml"
)
ARTIFACT_DIR = PROJECT_ROOT / (
    "logs/experiments/"
    "ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_"
    "trial_0041_20260712_190851_716023_013d079c"
)
RAW_DATA_RELATIVE = Path("data/raw/dukascopy_30m_clean/ethusd_30m.csv")
RAW_DATA_PATH = PROJECT_ROOT / RAW_DATA_RELATIVE
LOCAL_LOGS_RELATIVE = Path("logs/experiments/foundation_alpha/trial0041_alpha_lab")

SCREENING_FOLD_COUNT = 10
LOCKED_FOLD_START = 10
LOCKED_FOLD_COUNT = 7
FULL_FOLD_COUNT = LOCKED_FOLD_START + LOCKED_FOLD_COUNT
INITIAL_TRAIN_ROWS = 35_040

FEATURE_DENYLIST_TOKENS = (
    "target_",
    "label",
    "pred_",
    "mfe",
    "mae",
    "barrier",
    "hit_",
    "exit",
    "trade_r",
    "realized",
    "future",
)


class LabContractError(ValueError):
    """Raised when a Trial 0041 lab configuration violates research policy."""


@dataclass(frozen=True)
class ExperimentSpec:
    """A controlled, one-axis trial description and deterministic mutation."""

    experiment_id: str
    family: str
    hypothesis: str
    expected_effect: str
    parent_experiment: str
    mutation: Callable[[dict[str, Any]], dict[str, Any]]
    notes: str = ""


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise LabContractError(f"Expected a YAML mapping: {path}")
    return payload


def _config_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _deep_merge(base: Mapping[str, Any], updates: Mapping[str, Any]) -> dict[str, Any]:
    out = deepcopy(dict(base))
    for key, value in updates.items():
        if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
            out[key] = _deep_merge(dict(out[key]), dict(value))
        else:
            out[key] = deepcopy(value)
    return out


def _find_step(features: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for step in features:
        if str(step.get("step")) == name:
            return step
    raise LabContractError(f"Baseline feature step '{name}' was not found.")


def _append_feature_step(cfg: dict[str, Any], step: Mapping[str, Any], columns: Iterable[str]) -> dict[str, Any]:
    out = deepcopy(cfg)
    out.setdefault("features", []).append(deepcopy(dict(step)))
    feature_cols = list(out["model"]["feature_cols"])
    for column in columns:
        if column not in feature_cols:
            feature_cols.append(str(column))
    out["model"]["feature_cols"] = feature_cols
    return out


def _replace_feature_cols(cfg: dict[str, Any], feature_cols: Iterable[str]) -> dict[str, Any]:
    out = deepcopy(cfg)
    values = [str(column) for column in feature_cols]
    if not values:
        raise LabContractError("A feature ablation must retain at least one feature.")
    out["model"]["feature_cols"] = values
    return out


def _extend_step_transforms(
    cfg: dict[str, Any],
    *,
    step_name: str,
    transforms: Mapping[str, Any] | None = None,
    normalizations: Mapping[str, Any] | None = None,
    columns: Iterable[str] = (),
) -> dict[str, Any]:
    out = deepcopy(cfg)
    step = _find_step(out["features"], step_name)
    if transforms:
        current = dict(step.get("transforms", {}) or {})
        step["transforms"] = _deep_merge(current, transforms)
    if normalizations:
        current = dict(step.get("normalizations", {}) or {})
        step["normalizations"] = _deep_merge(current, normalizations)
    feature_cols = list(out["model"]["feature_cols"])
    for column in columns:
        if column not in feature_cols:
            feature_cols.append(str(column))
    out["model"]["feature_cols"] = feature_cols
    return out


def _set_target(cfg: dict[str, Any], target: Mapping[str, Any]) -> dict[str, Any]:
    out = deepcopy(cfg)
    out["model"]["target"] = deepcopy(dict(target))
    horizon = int(target.get("horizon_bars", target.get("horizon", 24)))
    # The split builder requires a purge no shorter than the forward target.  This is
    # an anti-leakage companion change, not an independently optimized parameter.
    if horizon > int(out["model"]["split"].get("purge_bars", 0)):
        out["model"]["split"]["purge_bars"] = horizon
        out["model"]["split"]["embargo_bars"] = horizon
        out["validation"]["purge_bars"] = horizon
        out["validation"]["embargo_bars"] = horizon
    return out


def _set_signal(cfg: dict[str, Any], signals: Mapping[str, Any], signal_col: str) -> dict[str, Any]:
    out = deepcopy(cfg)
    out["signals"] = deepcopy(dict(signals))
    out["backtest"]["signal_col"] = str(signal_col)
    return out


def _set_model(cfg: dict[str, Any], model_updates: Mapping[str, Any]) -> dict[str, Any]:
    out = deepcopy(cfg)
    out["model"] = _deep_merge(out["model"], model_updates)
    return out


def _replace_model_params(cfg: dict[str, Any], *, kind: str, params: Mapping[str, Any]) -> dict[str, Any]:
    """Replace estimator params rather than deep-merging incompatible families."""
    out = deepcopy(cfg)
    out["model"]["kind"] = str(kind)
    out["model"]["params"] = deepcopy(dict(params))
    return out


def _set_single_axis_metadata(
    cfg: dict[str, Any],
    *,
    spec: ExperimentSpec,
    phase: str,
) -> dict[str, Any]:
    out = deepcopy(cfg)
    out["research_metadata"] = {
        "lab": "ethusd_30m_trial_0041_alpha_lab",
        "baseline_source": str(SOURCE_CONFIG.relative_to(PROJECT_ROOT)),
        "baseline_artifact": str(ARTIFACT_DIR.relative_to(PROJECT_ROOT)),
        "family": spec.family,
        "experiment_id": spec.experiment_id,
        "parent_experiment": spec.parent_experiment,
        "hypothesis": spec.hypothesis,
        "expected_effect": spec.expected_effect,
        "phase": phase,
        "selection_era": "folds_0_to_9" if phase == "screening" else "folds_10_to_16_locked",
        "leakage_note": (
            "Feature values are causal at t; targets are future-only labels and are excluded "
            "from model.feature_cols. Screening rankings never read folds 10-16."
        ),
    }
    return out


def _base_runtime_config(*, phase: str, run_name: str) -> dict[str, Any]:
    """Return a locally runnable, semantically equivalent Trial 0041 base.

    The literal source has immutable ``/workspace`` paths and must remain
    untouched.  These three path/output changes are documented environment
    normalization only: raw CSV path, output directory, and processed snapshot
    persistence (disabled to avoid writing 50 duplicate 100k-row snapshots).
    """
    if phase not in {"screening", "locked"}:
        raise ValueError("phase must be 'screening' or 'locked'.")
    cfg = _read_yaml(SOURCE_CONFIG)
    storage = cfg["data"]["storage"]
    storage["load_path"] = str(RAW_DATA_RELATIVE)
    storage["raw_dir"] = "data/raw"
    storage["processed_dir"] = "data/processed"
    storage["save_processed"] = False
    logging = cfg["logging"]
    logging["output_dir"] = str(LOCAL_LOGS_RELATIVE)
    logging["run_name"] = run_name
    logging["save_predictions"] = True
    logging["stage_tails"] = {
        "enabled": False,
        "stdout": False,
        "report": False,
        "limit": 10,
        "max_columns": 16,
        "max_assets": 3,
    }
    # The training/evaluation regime is exactly the source 10-fold schedule for
    # screening.  Finalists add only untouched later folds, never change early folds.
    cfg["model"]["split"]["max_folds"] = SCREENING_FOLD_COUNT if phase == "screening" else FULL_FOLD_COUNT
    cfg["diagnostics"]["robustness"]["enabled"] = phase == "locked"
    if phase == "locked":
        cfg["diagnostics"]["robustness"].update(
            {
                "cost_multipliers": [1.0, 2.0, 5.0, 10.0, 15.0],
                "entry_delay_bars": [1, 2],
                "walk_forward_frequency": "YE",
            }
        )
    return cfg


def _header_for(spec: ExperimentSpec, *, phase: str) -> str:
    return "\n".join(
        [
            "# ETHUSD Trial 0041 Alpha Research Lab.",
            f"# Family: {spec.family}; phase: {phase}.",
            f"# Baseline: {SOURCE_CONFIG.relative_to(PROJECT_ROOT)}",  # immutable source
            f"# Parent: {spec.parent_experiment}",
            f"# Hypothesis: {spec.hypothesis}",
            f"# Expected mechanism: {spec.expected_effect}",
            "# Causality: target/diagnostic columns are excluded from model features; only prior/current-bar features are used.",
            "",
        ]
    )


def _write_config(path: Path, cfg: Mapping[str, Any], *, spec: ExperimentSpec, phase: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _header_for(spec, phase=phase) + yaml.safe_dump(dict(cfg), sort_keys=False, allow_unicode=True)
    path.write_text(payload, encoding="utf-8")


def _baseline_runtime_spec() -> ExperimentSpec:
    return ExperimentSpec(
        experiment_id="ethusd_30m_trial0041_baseline_local_replay",
        family="baseline",
        hypothesis="Path-normalized replay establishes the local 10-fold screening reference.",
        expected_effect="None; this changes no model, target, feature, signal, risk, or execution setting.",
        parent_experiment="immutable_trial0041_source",
        mutation=lambda cfg: cfg,
        notes="Only local file/output paths and processed-snapshot persistence differ from the immutable source.",
    )


def _baseline_feature_cols() -> list[str]:
    return list(_read_yaml(SOURCE_CONFIG)["model"]["feature_cols"])


def _remove_by_prefix_or_name(columns: Iterable[str], tokens: Iterable[str]) -> list[str]:
    needles = tuple(str(token) for token in tokens)
    return [column for column in columns if not any(str(column).startswith(token) or str(column) == token for token in needles)]


def _assert_feature_denylist(cfg: Mapping[str, Any]) -> None:
    offending = [
        str(column)
        for column in list(cfg.get("model", {}).get("feature_cols", []) or [])
        if any(token in str(column).lower() for token in FEATURE_DENYLIST_TOKENS)
    ]
    if offending:
        raise LabContractError(f"Model feature denylist violation: {offending}")


def _base_target(horizon: int, *, clip: list[float] | None = None) -> dict[str, Any]:
    return {
        "kind": "future_return_regression",
        "price_col": "close",
        "returns_col": "close_ret",
        "returns_type": "simple",
        "horizon_bars": int(horizon),
        "normalize_by_volatility": True,
        "volatility_col": "atr_48",
        "clip": [-4.0, 4.0] if clip is None else list(clip),
        "fwd_col": f"target_trial0041_h{int(horizon)}",
        "label_col": f"target_trial0041_h{int(horizon)}",
    }


def _target_specs() -> list[ExperimentSpec]:
    specs: list[ExperimentSpec] = []
    for horizon in (8, 12, 16, 36, 48):
        specs.append(
            ExperimentSpec(
                experiment_id=f"ethusd_30m_trial0041_tgt_atrnorm_h{horizon}_v1",
                family="target",
                hypothesis=f"A {horizon}-bar ATR-normalized return may align better with the fixed 24-bar holding policy.",
                expected_effect="Tests horizon alignment while retaining target units, model, features, and stateless signal logic.",
                parent_experiment="baseline_local_replay",
                mutation=lambda cfg, h=horizon: _set_target(cfg, _base_target(h)),
            )
        )
    specs.extend(
        [
            ExperimentSpec(
                experiment_id="ethusd_30m_trial0041_tgt_risk_adjusted_h24_v1",
                family="target",
                hypothesis="Future return scaled by its future realized volatility may favor paths with higher risk-adjusted edge.",
                expected_effect="Tests a risk-adjusted regression label while keeping feature/model/signal families fixed.",
                parent_experiment="baseline_local_replay",
                mutation=_mutate_risk_adjusted_target,
            ),
            ExperimentSpec(
                experiment_id="ethusd_30m_trial0041_tgt_trend_slope_h24_v1",
                family="target",
                hypothesis="A signed, volatility-normalized future trend slope may reward directional persistence rather than terminal return alone.",
                expected_effect="Tests a path-shape regression label with predeclared threshold units.",
                parent_experiment="baseline_local_replay",
                mutation=_mutate_trend_slope_target,
            ),
            ExperimentSpec(
                experiment_id="ethusd_30m_trial0041_tgt_path_efficiency_h24_v1",
                family="target",
                hypothesis="Path efficiency may separate persistent moves from volatile round trips over the existing 12-hour horizon.",
                expected_effect="Tests a bounded path-quality label with predeclared symmetric threshold units.",
                parent_experiment="baseline_local_replay",
                mutation=_mutate_path_efficiency_target,
            ),
            ExperimentSpec(
                experiment_id="ethusd_30m_trial0041_tgt_forward_sign_h24_lgbmclf_v1",
                family="target",
                hypothesis="A fold-local sign classifier tests whether directional probability is more stable than magnitude regression.",
                expected_effect="Required target/model/signal contract branch: forward-return classifier plus stateless probability threshold.",
                parent_experiment="baseline_local_replay",
                mutation=_mutate_forward_sign_classifier,
            ),
            ExperimentSpec(
                experiment_id="ethusd_30m_trial0041_tgt_triple_barrier_h24_lgbmclf_v1",
                family="target",
                hypothesis="A next-open binary triple barrier tests path-defined directional outcomes rather than terminal return magnitude.",
                expected_effect="Required target/model/signal contract branch: a causal barrier label and stateless probability threshold.",
                parent_experiment="baseline_local_replay",
                mutation=_mutate_triple_barrier_classifier,
            ),
        ]
    )
    return specs


def _mutate_risk_adjusted_target(cfg: dict[str, Any]) -> dict[str, Any]:
    target = {
        "kind": "risk_adjusted_future_return",
        "price_col": "close",
        "returns_col": "close_ret",
        "returns_type": "simple",
        "horizon_bars": 24,
        "clip": [-4.0, 4.0],
        "fwd_col": "target_risk_adjusted_h24",
        "label_col": "target_risk_adjusted_h24",
    }
    return _set_target(cfg, target)


def _mutate_trend_slope_target(cfg: dict[str, Any]) -> dict[str, Any]:
    target = {
        "kind": "future_trend_slope",
        "price_col": "close",
        "horizon_bars": 24,
        "normalize_by_price": True,
        "normalize_by_volatility": True,
        "volatility_col": "atr_48",
        "clip": [-4.0, 4.0],
        "fwd_col": "target_trend_slope_h24_atr",
        "label_col": "target_trend_slope_h24_atr",
    }
    out = _set_target(cfg, target)
    return _set_signal(
        out,
        {
            "kind": "forecast_threshold",
            "params": {
                "forecast_col": "pred_ret",
                "signal_col": "signal_trend_slope",
                "upper": 0.05,
                "lower": -0.05,
                "mode": "long_short",
                "activation_filters": deepcopy(cfg["signals"]["params"]["activation_filters"]),
            },
            "outputs": {},
        },
        "signal_trend_slope",
    )


def _mutate_path_efficiency_target(cfg: dict[str, Any]) -> dict[str, Any]:
    target = {
        "kind": "future_path_efficiency",
        "price_col": "close",
        "horizon_bars": 24,
        "signed": True,
        "clip": [-1.0, 1.0],
        "fwd_col": "target_path_efficiency_h24",
        "label_col": "target_path_efficiency_h24",
    }
    out = _set_target(cfg, target)
    return _set_signal(
        out,
        {
            "kind": "forecast_threshold",
            "params": {
                "forecast_col": "pred_ret",
                "signal_col": "signal_path_efficiency",
                "upper": 0.10,
                "lower": -0.10,
                "mode": "long_short",
                "activation_filters": deepcopy(cfg["signals"]["params"]["activation_filters"]),
            },
            "outputs": {},
        },
        "signal_path_efficiency",
    )


def _mutate_forward_sign_classifier(cfg: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(cfg)
    out["model"] = {
        "kind": "lightgbm_clf",
        "params": {
            "n_estimators": 500,
            "learning_rate": 0.04,
            "max_depth": 5,
            "num_leaves": 15,
            "min_child_samples": 250,
            "subsample": 0.9,
            "colsample_bytree": 0.75,
            "reg_alpha": 0.02,
            "reg_lambda": 1.8,
            "random_state": 7,
            "n_jobs": 1,
            "verbosity": -1,
        },
        "outputs": {"pred_prob_col": "pred_prob", "pred_is_oos_col": "pred_is_oos"},
        "preprocessing": {"scaler": "none"},
        "calibration": {"method": "none", "fraction": 0.2, "min_rows": 500},
        "feature_cols": list(cfg["model"]["feature_cols"]),
        "target": {
            "kind": "forward_return",
            "price_col": "close",
            "returns_col": "close_ret",
            "returns_type": "simple",
            "horizon": 24,
            "threshold": 0.0,
            "fwd_col": "target_forward_sign_h24",
            "label_col": "label_forward_sign_h24",
        },
        "split": deepcopy(cfg["model"]["split"]),
        "runtime": {},
        "env": {},
        "use_features": True,
        "pred_prob_col": "pred_prob",
        "pred_raw_prob_col": "pred_prob_raw",
        "pred_ret_col": "pred_ret",
        "pred_is_oos_col": "pred_is_oos",
        "returns_input_col": None,
        "signal_col": None,
        "action_col": None,
    }
    return _set_signal(
        out,
        {
            "kind": "probability_threshold",
            "params": {
                "prob_col": "pred_prob",
                "signal_col": "signal_forward_sign_prob",
                "upper": 0.56,
                "lower": 0.44,
                "mode": "long_short",
            },
            "outputs": {},
        },
        "signal_forward_sign_prob",
    )


def _mutate_triple_barrier_classifier(cfg: dict[str, Any]) -> dict[str, Any]:
    """Use the already-registered next-open triple-barrier target contract."""
    out = _mutate_forward_sign_classifier(cfg)
    out["model"]["target"] = {
        "kind": "triple_barrier",
        "price_col": "close",
        "open_col": "open",
        "high_col": "high",
        "low_col": "low",
        "returns_col": "close_ret",
        "volatility_col": None,
        "vol_window": 48,
        "max_holding": 24,
        "upper_mult": 1.4,
        "lower_mult": 1.0,
        "min_vol": 1.0e-6,
        "neutral_label": "drop",
        "tie_break": "closest_to_open",
        "entry_price_mode": "next_open",
        "label_mode": "binary",
        "add_r_multiple": False,
        "label_col": "tb_label_h24",
        "event_ret_col": "tb_event_ret_h24",
        "fwd_col": "tb_event_ret_h24",
        "hit_step_col": "tb_hit_step_h24",
        "hit_type_col": "tb_hit_type_h24",
        "upper_barrier_col": "tb_upper_h24",
        "lower_barrier_col": "tb_lower_h24",
    }
    return _set_signal(
        out,
        {
            "kind": "probability_threshold",
            "params": {
                "prob_col": "pred_prob",
                "signal_col": "signal_tb_probability",
                "upper": 0.56,
                "lower": 0.44,
                "mode": "long_short",
            },
            "outputs": {},
        },
        "signal_tb_probability",
    )


def _feature_addition_specs() -> list[ExperimentSpec]:
    """One coherent, existing-registry feature family per configuration."""
    entries: list[tuple[str, str, str, Mapping[str, Any], tuple[str, ...]]] = [
        (
            "adx24",
            "ADX tests whether trend strength adds information beyond EMA alignment.",
            "Adds only causal 24-bar ADX.",
            {"step": "adx", "params": {"high_col": "high", "low_col": "low", "close_col": "close", "windows": [24]}, "outputs": {}, "enabled": True},
            ("adx_24",),
        ),
        (
            "ppo_hist",
            "PPO histogram tests percentage momentum acceleration rather than level MACD.",
            "Adds only a 12/48/9 PPO histogram.",
            {"step": "ppo", "params": {"price_col": "close", "fast": 12, "slow": 48, "signal": 9}, "outputs": {}, "enabled": True},
            ("ppo_hist_12_48_9",),
        ),
        (
            "vwap_distance",
            "Distance from trailing VWAP may distinguish participation-supported moves from mean reversion.",
            "Adds a causal 48-bar volume-weighted price distance.",
            {
                "step": "vwap",
                "params": {"high_col": "high", "low_col": "low", "close_col": "close", "volume_col": "volume", "windows": [48]},
                "transforms": {"ratio": {"enabled": True, "items": [{"numerator_col": "close", "denominator_col": "vwap_48", "output_col": "close_over_vwap_48", "subtract": 1.0}]}},
                "outputs": {},
                "enabled": True,
            },
            ("close_over_vwap_48",),
        ),
        (
            "trend_regime",
            "A simple causal SMA state can provide regime context that is less scale-sensitive than raw price distance.",
            "Adds only the 24/96 trailing SMA trend-state flag.",
            {"step": "trend_regime", "params": {"price_col": "close", "base_sma_for_sign": 96, "short_sma": 24, "long_sma": 96}, "outputs": {}, "enabled": True},
            ("close_trend_state_sma_24_96",),
        ),
        (
            "vol_regime",
            "A relative volatility regime may be more stable than raw volatility levels flagged by PSI.",
            "Adds only a 48/384 causal volatility ratio.",
            {"step": "volatility_regime", "params": {"vol_col": "vol_rolling_48", "regime_window": 384, "method": "ratio", "output_col": "vol_regime_ratio_48_384"}, "outputs": {}, "enabled": True},
            ("vol_regime_ratio_48_384",),
        ),
        (
            "fisher48",
            "Fisher-transformed trailing price position may isolate extreme cycle states.",
            "Adds only a causal 48-bar Fisher transform.",
            {"step": "fisher_transform", "params": {"price_col": "close", "window": 48, "output_col": "fisher_48", "add_signal": False}, "outputs": {}, "enabled": True},
            ("fisher_48",),
        ),
        (
            "fractal96",
            "Katz fractal dimension may separate directional from noisy paths.",
            "Adds only a causal 96-bar fractal dimension.",
            {"step": "fractal_dimension", "params": {"price_col": "close", "window": 96, "output_col": "fractal_dimension_96"}, "outputs": {}, "enabled": True},
            ("fractal_dimension_96",),
        ),
        (
            "hurst96",
            "A trailing Hurst estimate may condition trend persistence without observing future path data.",
            "Adds only a causal 96-bar Hurst estimate.",
            {"step": "hurst_exponent", "params": {"price_col": "close", "window": 96, "output_col": "hurst_96"}, "outputs": {}, "enabled": True},
            ("hurst_96",),
        ),
        (
            "entropy48",
            "Permutation entropy on past returns may identify predictable versus disordered local structure.",
            "Adds only a causal 48-bar order-3 permutation entropy.",
            {"step": "permutation_entropy", "params": {"source_col": "close_ret", "window": 48, "order": 3, "output_col": "permutation_entropy_48"}, "outputs": {}, "enabled": True},
            ("permutation_entropy_48",),
        ),
        (
            "garman_klass48",
            "Range-based volatility may be a more efficient intrabar risk estimate than close-return volatility.",
            "Adds only a causal 48-bar Garman-Klass volatility estimate.",
            {"step": "garman_klass_volatility", "params": {"open_col": "open", "high_col": "high", "low_col": "low", "close_col": "close", "window": 48, "output_col": "garman_klass_vol_48"}, "outputs": {}, "enabled": True},
            ("garman_klass_vol_48",),
        ),
        (
            "yang_zhang48",
            "Yang-Zhang volatility tests whether open/close and range information improves the volatility context.",
            "Adds only a causal 48-bar Yang-Zhang volatility estimate.",
            {"step": "yang_zhang_volatility", "params": {"open_col": "open", "high_col": "high", "low_col": "low", "close_col": "close", "window": 48, "output_col": "yang_zhang_vol_48"}, "outputs": {}, "enabled": True},
            ("yang_zhang_vol_48",),
        ),
        (
            "mfi14",
            "Money-flow index tests whether supplied volume carries independent directional information.",
            "Adds only a causal 14-bar MFI; it is rejected if volume quality is unstable.",
            {"step": "mfi", "params": {"high_col": "high", "low_col": "low", "close_col": "close", "volume_col": "volume", "window": 14}, "outputs": {}, "enabled": True},
            ("mfi_14",),
        ),
    ]
    specs: list[ExperimentSpec] = []
    for suffix, hypothesis, effect, step, columns in entries:
        specs.append(
            ExperimentSpec(
                experiment_id=f"ethusd_30m_trial0041_featadd_{suffix}_v1",
                family="feature_addition",
                hypothesis=hypothesis,
                expected_effect=effect,
                parent_experiment="baseline_local_replay",
                mutation=lambda cfg, s=step, c=columns: _append_feature_step(cfg, s, c),
            )
        )
    return specs


def _feature_ablation_specs() -> list[ExperimentSpec]:
    baseline = _baseline_feature_cols()
    families: list[tuple[str, tuple[str, ...], str]] = [
        ("no_lag_returns", ("close_ret", "lag_close_ret_"), "Tests whether raw close-return lags add stable edge beyond engineered momentum."),
        ("no_momentum", ("ret_1", "ret_4", "ret_8", "ret_16", "ret_24", "ret_48", "rolling_return_24", "rolling_return_48"), "Tests whether the overlapping return-momentum family is redundant."),
        ("no_rolling_vol", ("vol_rolling_24", "vol_rolling_48", "vol_rolling_96", "vol_rolling_192"), "Tests dependence on high-PSI rolling-volatility levels."),
        ("no_atr_level", ("atr_48", "atr_over_price_48"), "Tests raw ATR level and price-scaled ATR dependence."),
        ("no_atr_rank", ("atr_pct", "atr_pct_rank_192"), "Tests whether ATR percentile features add predictive information rather than only gate state."),
        ("no_ema_structure", ("ema_trend_48_192", "ema_alignment_score", "distance_from_ema24_atr", "distance_from_ema96_atr"), "Tests EMA trend/alignment family as a block."),
        ("no_bollinger", ("close_over_bb_upper_192", "close_over_bb_mid_192", "bollinger_percent_b", "bollinger_bandwidth", "bollinger_bandwidth_rank_192"), "Tests Bollinger position and compression family as a block."),
        ("no_ehlers_trend", ("mama_minus_fama_over_atr", "close_minus_decycler_over_atr", "instantaneous_trendline_slope_over_atr", "decycler_slope_over_atr", "frama_slope_over_atr", "supersmoother_slope_over_atr"), "Tests normalized Ehlers trend family."),
        ("no_ehlers_cycle", ("roofing_filter_over_atr", "dominant_cycle_phase_normalized"), "Tests Ehlers cycle/roofing family."),
        ("no_candle_structure", ("body_ratio", "upper_wick_ratio", "lower_wick_ratio", "close_location", "range_to_atr"), "Tests candle/range structure family while retaining the signal gate columns in the frame."),
    ]
    specs: list[ExperimentSpec] = []
    for suffix, removed, hypothesis in families:
        retained = _remove_by_prefix_or_name(baseline, removed)
        specs.append(
            ExperimentSpec(
                experiment_id=f"ethusd_30m_trial0041_ablate_{suffix}_v1",
                family="feature_ablation",
                hypothesis=hypothesis,
                expected_effect="A robust family should not improve only through one historical fold when removed.",
                parent_experiment="baseline_local_replay",
                mutation=lambda cfg, cols=retained: _replace_feature_cols(cfg, cols),
            )
        )
    return specs


def _normalization_specs() -> list[ExperimentSpec]:
    variants: list[tuple[str, str, str, Callable[[dict[str, Any]], dict[str, Any]]]] = [
        (
            "return_over_vol48",
            "Scaling current return by trailing volatility may improve cross-regime comparability.",
            "Adds a causal close-return / rolling-volatility normalization.",
            lambda cfg: _extend_step_transforms(
                cfg,
                step_name="volatility",
                normalizations={"volatility_scaled_return": {"params": {"return_col": "close_ret", "volatility_col": "vol_rolling_48", "output_col": "close_ret_over_vol_48"}}},
                columns=("close_ret_over_vol_48",),
            ),
        ),
        (
            "robust_z_return192",
            "A shifted rolling median/MAD normalization may make return shocks comparable across regimes.",
            "Adds a train-agnostic causal robust z-score with shifted trailing statistics.",
            lambda cfg: _extend_step_transforms(
                cfg,
                step_name="volatility",
                normalizations={"robust_zscore": {"params": {"source_col": "close_ret", "window": 192, "output_col": "close_ret_robust_z_192", "shift_stats": True}}},
                columns=("close_ret_robust_z_192",),
            ),
        ),
        (
            "vol_rank384",
            "A past-only rolling volatility rank may be more stable than raw volatility levels.",
            "Adds a causal 384-bar percent rank, excluding the current bar from its reference window.",
            lambda cfg: _extend_step_transforms(
                cfg,
                step_name="volatility",
                normalizations={"rolling_percent_rank": {"params": {"source_col": "vol_rolling_48", "window": 384, "output_col": "vol_rolling_48_rank_384", "shift_window": True}}},
                columns=("vol_rolling_48_rank_384",),
            ),
        ),
        (
            "ema48_atr_distance",
            "An explicit ATR-scaled close-to-EMA48 distance may improve stationarity versus raw price distances.",
            "Adds one causal ATR-scaled distance.",
            lambda cfg: _extend_step_transforms(
                cfg,
                step_name="atr",
                normalizations={"atr_scaled_distance": {"params": {"base_col": "close", "ref_col": "ema_48", "atr_col": "atr_48", "output_col": "close_minus_ema48_atr"}}},
                columns=("close_minus_ema48_atr",),
            ),
        ),
        (
            "range_position96",
            "Trailing range position may normalize price location without using future support/resistance.",
            "Adds a causal 96-bar high-low range position.",
            lambda cfg: _extend_step_transforms(
                cfg,
                step_name="indicator_pullback",
                normalizations={"range_position": {"params": {"value_col": "close", "high_col": "high", "low_col": "low", "window": 96, "output_col": "close_range_pos_96"}}},
                columns=("close_range_pos_96",),
            ),
        ),
        (
            "relative_volume96",
            "Relative volume tests whether the supplied volume is informative after past-only normalization.",
            "Adds causal 96-bar relative volume; it is rejected if volume quality is weak or unstable.",
            lambda cfg: _extend_step_transforms(
                cfg,
                step_name="indicator_pullback",
                normalizations={"volume_relative": {"params": {"volume_col": "volume", "window": 96, "output_col": "volume_relative_96", "shift_stats": True}}},
                columns=("volume_relative_96",),
            ),
        ),
    ]
    return [
        ExperimentSpec(
            experiment_id=f"ethusd_30m_trial0041_norm_{suffix}_v1",
            family="normalization",
            hypothesis=hypothesis,
            expected_effect=effect,
            parent_experiment="baseline_local_replay",
            mutation=mutation,
        )
        for suffix, hypothesis, effect, mutation in variants
    ]


def _baseline_filters(cfg: Mapping[str, Any]) -> list[dict[str, Any]]:
    return deepcopy(list(cfg["signals"]["params"].get("activation_filters", []) or []))


def _forecast_signal_variant(
    cfg: dict[str, Any],
    *,
    signal_col: str,
    upper: float = 0.7,
    lower: float = -0.85,
    mode: str = "long_short",
    filters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return _set_signal(
        cfg,
        {
            "kind": "forecast_threshold",
            "params": {
                "forecast_col": "pred_ret",
                "signal_col": signal_col,
                "upper": float(upper),
                "lower": float(lower),
                "mode": mode,
                "activation_filters": _baseline_filters(cfg) if filters is None else filters,
            },
            "outputs": {},
        },
        signal_col,
    )


def _signal_specs() -> list[ExperimentSpec]:
    def mutator(
        suffix: str,
        *,
        upper: float = 0.7,
        lower: float = -0.85,
        mode: str = "long_short",
        filters: Callable[[dict[str, Any]], list[dict[str, Any]]] | None = None,
    ) -> Callable[[dict[str, Any]], dict[str, Any]]:
        return lambda cfg: _forecast_signal_variant(
            cfg,
            signal_col=f"signal_{suffix}",
            upper=upper,
            lower=lower,
            mode=mode,
            filters=filters(cfg) if filters else None,
        )

    baseline_filters = lambda cfg: _baseline_filters(cfg)
    low_vol_filters = lambda cfg: [
        {"col": "atr_pct_rank_192", "op": "ge", "value": 0.25},
        {"col": "atr_pct_rank_192", "op": "le", "value": 0.60},
        {"col": "range_to_atr", "op": "ge", "value": 0.9},
        {"col": "bollinger_bandwidth_rank_192", "op": "ge", "value": 0.4},
    ]
    high_vol_filters = lambda cfg: [
        {"col": "atr_pct_rank_192", "op": "ge", "value": 0.45},
        {"col": "atr_pct_rank_192", "op": "le", "value": 0.90},
        {"col": "range_to_atr", "op": "ge", "value": 0.9},
        {"col": "bollinger_bandwidth_rank_192", "op": "ge", "value": 0.4},
    ]
    trend_long_filters = lambda cfg: _baseline_filters(cfg) + [
        {"col": "ema_trend_48_192", "op": "ge", "value": 0.0}
    ]
    expansion_filters = lambda cfg: [
        {"col": "atr_pct_rank_192", "op": "ge", "value": 0.25},
        {"col": "atr_pct_rank_192", "op": "le", "value": 0.85},
        {"col": "range_to_atr", "op": "ge", "value": 1.10},
        {"col": "bollinger_bandwidth_rank_192", "op": "ge", "value": 0.55},
    ]
    specs = [
        ExperimentSpec("ethusd_30m_trial0041_sig_loose_v1", "signal", "A wider entry region may retain moderate forecast edge.", "Tests only a less selective asymmetric forecast threshold.", "baseline_local_replay", mutator("loose", upper=0.50, lower=-0.65, filters=baseline_filters)),
        ExperimentSpec("ethusd_30m_trial0041_sig_tight_v1", "signal", "A narrower entry region may concentrate the largest forecast edges.", "Tests only a more selective asymmetric forecast threshold.", "baseline_local_replay", mutator("tight", upper=0.90, lower=-1.00, filters=baseline_filters)),
        ExperimentSpec("ethusd_30m_trial0041_sig_long_only_v1", "signal", "Long and short edges may be asymmetric under ETHUSD quote costs and regimes.", "Tests the existing long side in isolation.", "baseline_local_replay", mutator("long_only", mode="long_only", filters=baseline_filters)),
        ExperimentSpec("ethusd_30m_trial0041_sig_short_only_v1", "signal", "Short and long edges may be asymmetric under ETHUSD quote costs and regimes.", "Tests the existing short side in isolation.", "baseline_local_replay", mutator("short_only", mode="short_only", filters=baseline_filters)),
        ExperimentSpec("ethusd_30m_trial0041_sig_low_vol_v1", "signal", "The medium/low ATR regime may be less vulnerable to quote friction.", "Changes only the ATR-rank upper gate.", "baseline_local_replay", mutator("low_vol", filters=low_vol_filters)),
        ExperimentSpec("ethusd_30m_trial0041_sig_high_vol_v1", "signal", "A higher-volatility subset may improve signal-to-cost after forecast gates.", "Changes only the ATR-rank gate range.", "baseline_local_replay", mutator("high_vol", filters=high_vol_filters)),
        ExperimentSpec("ethusd_30m_trial0041_sig_trend_long_v1", "signal", "Trend confirmation may reduce countertrend long entries.", "Adds one causal EMA-trend gate to a long-only signal.", "baseline_local_replay", mutator("trend_long", mode="long_only", filters=trend_long_filters)),
        ExperimentSpec("ethusd_30m_trial0041_sig_expansion_v1", "signal", "Stronger range and bandwidth expansion may identify continuation rather than churn.", "Changes only two predeclared causal gate thresholds.", "baseline_local_replay", mutator("expansion", filters=expansion_filters)),
        ExperimentSpec(
            "ethusd_30m_trial0041_sig_dense_net_v1",
            "signal",
            "Cost-adjusted continuous normalized forecasts may reduce marginal trades.",
            "Replaces the threshold mapping with existing dense forecast-to-net-return logic.",
            "baseline_local_replay",
            lambda cfg: _set_signal(
                cfg,
                {
                    "kind": "dense_return_forecast",
                    "params": {
                        "forecast_col": "pred_ret", "signal_col": "signal_dense_net", "expected_net_return_col": "expected_net_return", "estimated_cost_col": "estimated_round_trip_cost", "cost_per_turnover": 0.0001, "slippage_per_turnover": 0.0, "cost_round_trip_mult": 2.0, "forecast_is_vol_normalized": True, "volatility_col": "atr_48", "price_col": "close", "volatility_floor": 1.0e-12, "signed_cost_adjustment": True, "clip": 1.0,
                    },
                    "outputs": {},
                },
                "signal_dense_net",
            ),
        ),
        ExperimentSpec(
            "ethusd_30m_trial0041_sig_rule_momentum_v1",
            "signal",
            "A simple causal momentum rule is a non-model comparator for the same OOS calendar.",
            "Replaces only the signal mapping; model output remains unused and is not treated as alpha.",
            "baseline_local_replay",
            lambda cfg: _set_signal(
                cfg,
                {"kind": "momentum", "params": {"momentum_col": "rolling_return_24", "long_threshold": 0.01, "short_threshold": -0.01, "signal_col": "signal_rule_momentum", "mode": "long_short"}, "outputs": {}},
                "signal_rule_momentum",
            ),
        ),
    ]
    return specs


def _model_specs() -> list[ExperimentSpec]:
    shallow_params = {
        "n_estimators": 600, "learning_rate": 0.04, "max_depth": 4, "num_leaves": 15,
        "min_child_samples": 300, "subsample": 0.9, "colsample_bytree": 0.75,
        "reg_alpha": 0.05, "reg_lambda": 2.0, "random_state": 7, "n_jobs": 1, "verbosity": -1,
    }
    xgb_reg_params = {
        "n_estimators": 600, "learning_rate": 0.04, "max_depth": 4, "min_child_weight": 20,
        "subsample": 0.9, "colsample_bytree": 0.75, "reg_alpha": 0.05, "reg_lambda": 2.0,
        "objective": "reg:squarederror", "eval_metric": "rmse", "tree_method": "hist", "random_state": 7, "n_jobs": 1,
    }
    xgb_clf_params = {
        "n_estimators": 600, "learning_rate": 0.04, "max_depth": 4, "min_child_weight": 20,
        "subsample": 0.9, "colsample_bytree": 0.75, "reg_alpha": 0.05, "reg_lambda": 2.0,
        "objective": "binary:logistic", "eval_metric": "logloss", "tree_method": "hist", "random_state": 7, "n_jobs": 1,
    }
    return [
        ExperimentSpec(
            "ethusd_30m_trial0041_model_lgbm_shallow_reg_v1", "model",
            "A shallower, more regularized LightGBM may reduce variance across folds.",
            "Changes only baseline LightGBM capacity/regularization.", "baseline_local_replay",
            lambda cfg: _set_model(cfg, {"params": shallow_params}),
        ),
        ExperimentSpec(
            "ethusd_30m_trial0041_model_xgboost_reg_v1", "model",
            "Histogram XGBoost is an independent tree implementation for the same regression contract.",
            "Changes only regression estimator family and deterministic capacity.", "baseline_local_replay",
            lambda cfg: _replace_model_params(cfg, kind="xgboost_regressor", params=xgb_reg_params),
        ),
        ExperimentSpec(
            "ethusd_30m_trial0041_model_xgboost_tb_clf_v1", "model",
            "XGBoost classifier is compared on the matched triple-barrier branch.",
            "Model-family comparison uses the same path-defined target and probability signal.", "triple_barrier_target_branch",
            lambda cfg: _replace_model_params(_mutate_triple_barrier_classifier(cfg), kind="xgboost_clf", params=xgb_clf_params),
        ),
        ExperimentSpec(
            "ethusd_30m_trial0041_model_logistic_tb_clf_v1", "model",
            "Regularized logistic regression is a low-variance linear benchmark on the matched triple-barrier branch.",
            "Changes classifier family and uses fold-local StandardScaler only.", "triple_barrier_target_branch",
            lambda cfg: _set_model(
                _replace_model_params(
                    _mutate_triple_barrier_classifier(cfg),
                    kind="logistic_regression_clf",
                    params={"C": 0.1, "max_iter": 2000, "solver": "lbfgs", "random_state": 7},
                ),
                {"preprocessing": {"scaler": "standard"}},
            ),
        ),
        ExperimentSpec(
            "ethusd_30m_trial0041_model_elasticnet_tb_clf_v1", "model",
            "Elastic-net logistic regression tests a sparse low-variance classifier on the matched barrier branch.",
            "Changes classifier family and uses fold-local StandardScaler only.", "triple_barrier_target_branch",
            lambda cfg: _set_model(
                _replace_model_params(
                    _mutate_triple_barrier_classifier(cfg),
                    kind="elastic_net_clf",
                    params={"penalty": "elasticnet", "solver": "saga", "l1_ratio": 0.5, "C": 0.1, "max_iter": 3000, "random_state": 7, "n_jobs": 1},
                ),
                {"preprocessing": {"scaler": "standard"}},
            ),
        ),
        ExperimentSpec(
            "ethusd_30m_trial0041_model_lgbm_tb_calibrated_v1", "model",
            "Fold-local sigmoid calibration may improve probability threshold stability for the matched barrier branch.",
            "Changes only calibration within the matched LightGBM triple-barrier classifier branch.", "triple_barrier_target_branch",
            lambda cfg: _set_model(_mutate_triple_barrier_classifier(cfg), {"calibration": {"method": "sigmoid", "fraction": 0.2, "min_rows": 200}, "pred_raw_prob_col": "pred_prob_raw"}),
        ),
    ]


def first_stage_specs() -> list[ExperimentSpec]:
    """Return the fixed 54-run, non-Cartesian screening matrix."""
    specs = [
        *_target_specs(),
        *_feature_ablation_specs(),
        *_feature_addition_specs(),
        *_normalization_specs(),
        *_signal_specs(),
        *_model_specs(),
    ]
    expected = {
        "target": 10,
        "feature_ablation": 10,
        "feature_addition": 12,
        "normalization": 6,
        "signal": 10,
        "model": 6,
    }
    actual = pd.Series([spec.family for spec in specs]).value_counts().to_dict()
    if actual != expected:
        raise AssertionError(f"Unexpected first-stage matrix: {actual}")
    if len({spec.experiment_id for spec in specs}) != len(specs):
        raise AssertionError("First-stage experiment IDs must be unique.")
    return specs


_FAMILY_DIRS = {
    "target": "01_target_lab",
    "feature_ablation": "02_feature_ablation",
    "feature_addition": "03_feature_additions",
    "normalization": "04_normalization_lab",
    "signal": "05_signal_lab",
    "model": "06_model_lab",
}


def _spec_config(spec: ExperimentSpec, *, phase: str) -> dict[str, Any]:
    cfg = _base_runtime_config(phase=phase, run_name=spec.experiment_id)
    cfg = spec.mutation(cfg)

    # Keep diagnostics aligned with the actual baseline volatility-rank feature.
    cfg.setdefault("diagnostics", {}).setdefault("forecast", {})["volatility_col"] = (
        "atr_pct_rank_192"
    )

    # Keep the YAML execution contract consistent with directional signal intent.
    signals = dict(cfg.get("signals", {}) or {})
    signal_params = dict(signals.get("params", {}) or {})
    mode = str(signal_params.get("mode", "")).lower()
    signed_signal_kinds = {"dense_return_forecast"}
    cfg.setdefault("backtest", {})["allow_short"] = bool(
        mode in {"long_short", "short_only"}
        or str(signals.get("kind", "")) in signed_signal_kinds
    )

    cfg = _set_single_axis_metadata(cfg, spec=spec, phase=phase)
    _assert_feature_denylist(cfg)
    return cfg


def _yaml_path_for_spec(spec: ExperimentSpec) -> Path:
    directory = _FAMILY_DIRS[spec.family]
    return LAB_ROOT / directory / f"{spec.experiment_id}.yaml"


def _manifest_row(spec: ExperimentSpec, path: Path, cfg: Mapping[str, Any]) -> dict[str, Any]:
    model = dict(cfg.get("model", {}) or {})
    target = dict(model.get("target", {}) or {})
    signal = dict(cfg.get("signals", {}) or {})
    signal_params = dict(signal.get("params", {}) or {})
    base_features = set(_baseline_feature_cols())
    feature_cols = [str(column) for column in list(model.get("feature_cols", []) or [])]
    added = sorted(set(feature_cols) - base_features)
    removed = sorted(base_features - set(feature_cols))
    return {
        "experiment_id": spec.experiment_id,
        "yaml_path": str(path.relative_to(PROJECT_ROOT)),
        "family": spec.family,
        "parent_experiment": spec.parent_experiment,
        "hypothesis": spec.hypothesis,
        "target": target.get("kind"),
        "horizon": target.get("horizon_bars", target.get("horizon")),
        "feature_set": f"{len(feature_cols)} explicit features",
        "added_features": ";".join(added),
        "removed_features": ";".join(removed),
        "normalization": "yes" if spec.family == "normalization" else "baseline",
        "model": model.get("kind"),
        "signal": signal.get("kind"),
        "long_threshold": signal_params.get("upper", signal_params.get("long_threshold")),
        "short_threshold": signal_params.get("lower", signal_params.get("short_threshold")),
        "risk_settings": "baseline fixed 1bp/turnover, zero slippage, leverage 1",
        "expected_effect": spec.expected_effect,
        "actual_result": "pending",
        "screening_status": "not_run",
        "robustness_status": "not_run",
        "notes": spec.notes,
    }


def generate_lab_configs() -> dict[str, Any]:
    """Create all standalone YAMLs, provenance copy, manifest, and lab README."""
    for directory in (
        "00_baseline", "01_target_lab", "02_feature_ablation", "03_feature_additions",
        "04_normalization_lab", "05_signal_lab", "06_model_lab", "07_combined_finalists",
        "08_stress_validated", "reports",
    ):
        (LAB_ROOT / directory).mkdir(parents=True, exist_ok=True)

    immutable_copy = LAB_ROOT / "00_baseline/ethusd_30m_trial_0041_baseline.yaml"
    # Exact artifact-source copy: byte preservation is intentional provenance, not a
    # runnable config because it contains historical /workspace paths.
    shutil.copy2(SOURCE_CONFIG, immutable_copy)

    baseline_spec = _baseline_runtime_spec()
    baseline_cfg = _spec_config(baseline_spec, phase="screening")
    baseline_runtime = LAB_ROOT / "00_baseline/ethusd_30m_trial_0041_baseline_local_replay.yaml"
    _write_config(baseline_runtime, baseline_cfg, spec=baseline_spec, phase="screening")

    manifest_rows = [_manifest_row(baseline_spec, baseline_runtime, baseline_cfg)]
    target_rows: list[dict[str, Any]] = []
    for spec in first_stage_specs():
        cfg = _spec_config(spec, phase="screening")
        path = _yaml_path_for_spec(spec)
        _write_config(path, cfg, spec=spec, phase="screening")
        row = _manifest_row(spec, path, cfg)
        manifest_rows.append(row)
        if spec.family == "target":
            target_rows.append(row)

    manifest = pd.DataFrame(manifest_rows)
    manifest.to_csv(REPORTS_DIR / "experiment_manifest.csv", index=False)
    pd.DataFrame(target_rows).to_csv(REPORTS_DIR / "target_lab_manifest.csv", index=False)
    _write_lab_readme(manifest)
    return {
        "immutable_baseline": str(immutable_copy),
        "immutable_baseline_sha256": _config_sha256(immutable_copy),
        "source_baseline_sha256": _config_sha256(SOURCE_CONFIG),
        "runtime_baseline": str(baseline_runtime),
        "first_stage_count": len(first_stage_specs()),
        "manifest": str(REPORTS_DIR / "experiment_manifest.csv"),
    }


def list_lab_yaml_paths(*, include_finalists: bool = False) -> list[Path]:
    paths = [LAB_ROOT / "00_baseline/ethusd_30m_trial_0041_baseline_local_replay.yaml"]
    paths.extend(_yaml_path_for_spec(spec) for spec in first_stage_specs())
    if include_finalists:
        paths.extend(sorted((LAB_ROOT / "07_combined_finalists").glob("*.yaml")))
        paths.extend(sorted((LAB_ROOT / "08_stress_validated").glob("*.yaml")))
    return [path for path in paths if path.exists()]


def validate_lab_configs(*, include_finalists: bool = False) -> pd.DataFrame:
    """Load each config through the public loader and enforce lab-only contracts."""
    rows: list[dict[str, Any]] = []
    for path in list_lab_yaml_paths(include_finalists=include_finalists):
        try:
            cfg = load_experiment_config(path)
            _assert_feature_denylist(cfg)
            rows.append({"yaml_path": str(path.relative_to(PROJECT_ROOT)), "status": "valid", "error": ""})
        except Exception as exc:  # keep every failure visible in the lab ledger
            rows.append({"yaml_path": str(path.relative_to(PROJECT_ROOT)), "status": "invalid", "error": f"{type(exc).__name__}: {exc}"})
    frame = pd.DataFrame(rows)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_csv(REPORTS_DIR / "config_validation.csv", index=False)
    return frame


def _write_lab_readme(manifest: pd.DataFrame) -> None:
    counts = manifest["family"].value_counts().to_dict() if not manifest.empty else {}
    content = f"""# ETHUSD Trial 0041 Alpha Research Lab

This is a controlled, baseline-centred research lab around Trial 0041. It does not reuse a
previous leaderboard as a selection source. The historical artifact is used only for baseline
provenance and descriptive diagnostics.

## Provenance and split discipline

- Immutable source: `{SOURCE_CONFIG.relative_to(PROJECT_ROOT)}`.
- Exact copy: `00_baseline/ethusd_30m_trial_0041_baseline.yaml`.
- Local replay: `00_baseline/ethusd_30m_trial_0041_baseline_local_replay.yaml`. It changes only
  `/workspace` paths and disables duplicate processed snapshots; its trading semantics remain the
  source baseline.
- Screening uses the source purged expanding folds 0--9 only (through 2024-09-17).
- Folds 10--16 (2024-09-17 through 2026-06) are the locked continuation. They are opened only
  after finalist YAMLs are frozen and are reported separately.

The vectorized runner applies a one-bar-lagged close-return exposure, not an explicit next-open
fill. Final reports therefore treat quote-cost and delay checks as mandatory blockers for any
paper-trading claim.

## Matrix

| Family | YAMLs |
|---|---:|
| Baseline local replay | {counts.get('baseline', 0)} |
| Target lab | {counts.get('target', 0)} |
| Feature ablation | {counts.get('feature_ablation', 0)} |
| Feature additions | {counts.get('feature_addition', 0)} |
| Normalization | {counts.get('normalization', 0)} |
| Signal lab | {counts.get('signal', 0)} |
| Model lab | {counts.get('model', 0)} |

## Reproducible sequence

```bash
PYTHONHASHSEED=7 python scripts/run_trial0041_alpha_lab.py generate
PYTHONHASHSEED=7 python scripts/run_trial0041_alpha_lab.py validate
PYTHONHASHSEED=7 python scripts/run_trial0041_alpha_lab.py diagnostics
PYTHONHASHSEED=7 python scripts/run_trial0041_alpha_lab.py screen
PYTHONHASHSEED=7 python scripts/run_trial0041_alpha_lab.py finalists
PYTHONHASHSEED=7 python scripts/run_trial0041_alpha_lab.py locked
PYTHONHASHSEED=7 python scripts/run_trial0041_alpha_lab.py report
```

`07_combined_finalists` is generated only from the screening leaderboard. `08_stress_validated`
contains no YAML unless a frozen finalist passes the stated locked-fold and execution stresses.
"""
    (LAB_ROOT / "README.md").write_text(content, encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise LabContractError(f"Expected JSON object: {path}")
    return payload


def _read_series(path: Path, *, name: str) -> pd.Series:
    frame = pd.read_csv(path)
    if frame.empty or len(frame.columns) < 2:
        return pd.Series(dtype=float, name=name)
    timestamp_col = frame.columns[0]
    index = pd.DatetimeIndex(pd.to_datetime(frame[timestamp_col], errors="coerce", utc=True)).tz_localize(None)
    numeric_cols = [column for column in frame.columns[1:] if pd.to_numeric(frame[column], errors="coerce").notna().any()]
    if not numeric_cols:
        return pd.Series(dtype=float, name=name)
    values = pd.to_numeric(frame[numeric_cols[0]], errors="coerce")
    out = pd.Series(values.to_numpy(dtype=float), index=index, name=name).sort_index()
    return out


def load_trial_raw() -> pd.DataFrame:
    frame = load_ohlcv_csv(RAW_DATA_PATH, symbol="ETHUSD")
    validate_ohlcv(frame)
    return frame


def _gap_summary(index: pd.DatetimeIndex, expected: pd.Timedelta = pd.Timedelta(minutes=30)) -> dict[str, Any]:
    diffs = pd.Series(index[1:] - index[:-1], index=index[1:])
    gaps = diffs[diffs > expected]
    missing = int(sum(max(0, int(delta / expected) - 1) for delta in gaps))
    return {
        "expected_interval": str(expected),
        "gap_count": int(len(gaps)),
        "missing_bars": missing,
        "max_gap": str(gaps.max()) if not gaps.empty else "0 days 00:30:00",
        "examples": [str(ts) for ts in gaps.index[:5]],
    }


def audit_raw_data() -> dict[str, Any]:
    frame = load_trial_raw()
    numeric = frame[["open", "high", "low", "close", "volume"]].apply(pd.to_numeric, errors="coerce")
    payload = {
        "path": str(RAW_DATA_RELATIVE),
        "file_sha256": file_sha256(RAW_DATA_PATH),
        "dataframe_fingerprint": compute_dataframe_fingerprint(frame),
        "rows": int(len(frame)),
        "columns": list(frame.columns),
        "timestamp_start": frame.index.min().isoformat(),
        "timestamp_end": frame.index.max().isoformat(),
        "timezone": "UTC-naive after canonical external-CSV normalization",
        "duplicates": int(frame.index.duplicated().sum()),
        "missing_ohlcv": {column: int(numeric[column].isna().sum()) for column in numeric.columns},
        "nonpositive_prices": {column: int((numeric[column] <= 0).sum()) for column in ("open", "high", "low", "close")},
        "low_gt_high": int((numeric["low"] > numeric["high"]).sum()),
        "open_outside_range": int(((numeric["open"] < numeric["low"]) | (numeric["open"] > numeric["high"])).sum()),
        "close_outside_range": int(((numeric["close"] < numeric["low"]) | (numeric["close"] > numeric["high"])).sum()),
        "gaps": _gap_summary(frame.index),
        "symbol_from_file": "ETHUSD",
        "timeframe_from_file": "30m",
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "data_audit.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def _conventional_return_metrics(returns: pd.Series, *, periods_per_year: int) -> dict[str, float]:
    values = pd.to_numeric(returns, errors="coerce").dropna().astype(float)
    if len(values) < 2:
        return {"arithmetic_sharpe": float("nan"), "arithmetic_sortino": float("nan"), "mean_return": float("nan")}
    std = float(values.std(ddof=1))
    sharpe = float(values.mean() / std * math.sqrt(periods_per_year)) if std > 0 else float("nan")
    downside = np.minimum(values.to_numpy(dtype=float), 0.0)
    down_std = float(np.sqrt(np.mean(np.square(downside))))
    sortino = float(values.mean() / down_std * math.sqrt(periods_per_year)) if down_std > 0 else float("nan")
    return {"arithmetic_sharpe": sharpe, "arithmetic_sortino": sortino, "mean_return": float(values.mean())}


def _series_compound(values: pd.Series) -> float:
    values = pd.to_numeric(values, errors="coerce").dropna().astype(float)
    return float((1.0 + values).prod() - 1.0) if not values.empty else float("nan")


def _trade_metrics(trades: pd.DataFrame) -> dict[str, Any]:
    if trades.empty:
        return {"trade_count": 0}
    work = trades.copy()
    for column in ("net_return", "gross_return", "total_cost", "bars_held", "trade_r"):
        if column in work:
            work[column] = pd.to_numeric(work[column], errors="coerce")
    net = work["net_return"].dropna() if "net_return" in work else pd.Series(dtype=float)
    gains = float(net[net > 0].sum())
    losses = float(-net[net < 0].sum())
    result: dict[str, Any] = {
        "completed_round_trips": int(len(work)),
        "net_return_sum": float(net.sum()) if not net.empty else float("nan"),
        "mean_net_return": float(net.mean()) if not net.empty else float("nan"),
        "median_net_return": float(net.median()) if not net.empty else float("nan"),
        "trade_win_rate": float((net > 0).mean()) if not net.empty else float("nan"),
        "trade_profit_factor": float(gains / losses) if losses > 0 else float("nan"),
        "mean_holding_bars": float(work["bars_held"].mean()) if "bars_held" in work else float("nan"),
        "long_trades": int((work.get("side", pd.Series(dtype=str)).astype(str) == "long").sum()),
        "short_trades": int((work.get("side", pd.Series(dtype=str)).astype(str) == "short").sum()),
    }
    if "side" in work and "net_return" in work:
        by_side: dict[str, Any] = {}
        for side, group in work.groupby(work["side"].astype(str), sort=True):
            side_net = group["net_return"].dropna()
            side_gains = float(side_net[side_net > 0].sum())
            side_losses = float(-side_net[side_net < 0].sum())
            by_side[str(side)] = {
                "trades": int(len(group)), "net_return_sum": float(side_net.sum()),
                "win_rate": float((side_net > 0).mean()) if not side_net.empty else float("nan"),
                "profit_factor": float(side_gains / side_losses) if side_losses > 0 else float("nan"),
            }
        result["by_side"] = by_side
    return result


def _entry_session(timestamp: pd.Timestamp) -> str:
    hour = int(timestamp.hour)
    if hour < 8:
        return "00:00-07:59 UTC"
    if hour < 13:
        return "08:00-12:59 UTC"
    if hour < 21:
        return "13:00-20:59 UTC"
    return "21:00-23:59 UTC"


def write_baseline_diagnostics() -> dict[str, Any]:
    """Write a provenance-first, discrepancy-aware baseline report."""
    summary_payload = _read_json(ARTIFACT_DIR / "summary.json")
    run_metadata = _read_json(ARTIFACT_DIR / "run_metadata.json")
    primary = dict(summary_payload.get("evaluation", {}).get("primary_summary", {}) or {})
    folds = list(summary_payload.get("evaluation", {}).get("fold_backtest_summaries", []) or [])
    returns = _read_series(ARTIFACT_DIR / "returns.csv", name="net_return")
    gross = _read_series(ARTIFACT_DIR / "gross_returns.csv", name="gross_return")
    costs = _read_series(ARTIFACT_DIR / "costs.csv", name="cost")
    positions = _read_series(ARTIFACT_DIR / "positions.csv", name="position")
    turnover = _read_series(ARTIFACT_DIR / "turnover.csv", name="turnover")
    pred_diag = _read_json(ARTIFACT_DIR / "prediction_diagnostics.json")
    trades_path = ARTIFACT_DIR / "report_assets/trades_enriched.csv"
    trades = pd.read_csv(trades_path, parse_dates=["signal_timestamp", "entry_timestamp", "exit_timestamp"]) if trades_path.exists() else pd.DataFrame()
    oos_start = pd.Timestamp(pred_diag["first_prediction_index"])
    oos_end = pd.Timestamp(pred_diag["last_prediction_index"])
    oos_returns = returns.loc[(returns.index >= oos_start) & (returns.index <= oos_end)]
    oos_gross = gross.reindex(oos_returns.index).fillna(0.0)
    oos_costs = costs.reindex(oos_returns.index).fillna(0.0)
    oos_positions = positions.reindex(oos_returns.index).fillna(0.0)
    oos_turnover = turnover.reindex(oos_returns.index).fillna(0.0)
    period_metrics = _conventional_return_metrics(oos_returns, periods_per_year=17_520)
    ftmo = compute_ftmo_style_metrics(net_returns=oos_returns, max_daily_loss=0.05, max_total_loss=0.10)

    years = []
    for year, group in oos_returns.groupby(oos_returns.index.year):
        years.append({
            "year": int(year), "rows": int(len(group)), "compounded_return": _series_compound(group),
            "net_pnl_sum": float(group.sum()), "gross_pnl_sum": float(oos_gross.reindex(group.index).sum()),
            "cost": float(oos_costs.reindex(group.index).sum()), "turnover": float(oos_turnover.reindex(group.index).sum()),
            "exposure": float(oos_positions.reindex(group.index).ne(0.0).mean()),
        })
    months = []
    for timestamp, group in oos_returns.groupby(oos_returns.index.to_period("M")):
        months.append({"month": str(timestamp), "compounded_return": _series_compound(group), "rows": int(len(group))})
    sessions: list[dict[str, Any]] = []
    if not trades.empty and "entry_timestamp" in trades:
        work = trades.copy()
        work["session"] = work["entry_timestamp"].map(_entry_session)
        for session, group in work.groupby("session", sort=False):
            metrics = _trade_metrics(group)
            sessions.append({"session": session, **metrics})

    raw = load_trial_raw()
    spread_proxy = pd.to_numeric(raw.get("spread_close", pd.Series(dtype=float)), errors="coerce") / pd.to_numeric(raw.get("close", pd.Series(dtype=float)), errors="coerce")
    spread_proxy = spread_proxy.replace([np.inf, -np.inf], np.nan).dropna()
    modeled_round_trip = 2.0 * 0.0001
    quote_cost_proxy = float(spread_proxy.median()) if not spread_proxy.empty else float("nan")
    quote_multiplier = float(quote_cost_proxy / modeled_round_trip) if modeled_round_trip > 0 and math.isfinite(quote_cost_proxy) else float("nan")

    fold_rows = [dict(item.get("metrics", {}) or {}) for item in folds]
    diagnostics = {
        "primary_summary": primary,
        "conventional_return_metrics": period_metrics,
        "trade_ledger": _trade_metrics(trades),
        "oos_window": {"start": oos_start.isoformat(), "end": oos_end.isoformat(), "rows": int(len(oos_returns))},
        "yearly": years,
        "monthly": months,
        "sessions": sessions,
        "folds": fold_rows,
        "ftmo_style": ftmo,
        "quote_cost_proxy": {"median_full_spread_relative": quote_cost_proxy, "modeled_round_trip_cost": modeled_round_trip, "multiple_of_modeled_cost": quote_multiplier},
        "artifact_config_hash": run_metadata.get("config_hash_sha256"),
    }
    (REPORTS_DIR / "baseline_diagnostics.json").write_text(json.dumps(diagnostics, indent=2, default=str), encoding="utf-8")
    pd.DataFrame(years).to_csv(REPORTS_DIR / "baseline_yearly.csv", index=False)
    pd.DataFrame(months).to_csv(REPORTS_DIR / "baseline_monthly.csv", index=False)
    pd.DataFrame(sessions).to_csv(REPORTS_DIR / "baseline_sessions.csv", index=False)
    pd.DataFrame(fold_rows).to_csv(REPORTS_DIR / "baseline_fold_metrics.csv", index=False)

    md = [
        "# Trial 0041 baseline diagnostics",
        "",
        "## Provenance",
        "",
        f"- Immutable source YAML: `{SOURCE_CONFIG.relative_to(PROJECT_ROOT)}` (SHA-256 `{_config_sha256(SOURCE_CONFIG)}`).",
        f"- Historical artifact: `{ARTIFACT_DIR.relative_to(PROJECT_ROOT)}`.",
        f"- Raw local source: `{RAW_DATA_RELATIVE}`; detailed integrity audit is in `data_audit.json`.",
        "- The artifact's 10 folds cover only 2022-03-14 through 2024-09-17; later raw data is not evidence and is reserved as a lockbox.",
        "",
        "## Primary strict-OOS metrics (framework definitions)",
        "",
        "| Metric | Value |",
        "|---|---:|",
        *[f"| {key} | {value:.6g} |" for key, value in primary.items() if isinstance(value, (int, float))],
        "",
        "The framework's `sharpe` is annualized return divided by annualized volatility, not the conventional mean-excess-return Sharpe. The recomputed arithmetic Sharpe is "
        f"`{period_metrics['arithmetic_sharpe']:.3f}`.",
        "",
        "## Trade and execution interpretation",
        "",
        f"- Completed ledger round trips: `{diagnostics['trade_ledger'].get('completed_round_trips', 0)}` (long `{diagnostics['trade_ledger'].get('long_trades', 0)}`, short `{diagnostics['trade_ledger'].get('short_trades', 0)}`).",
        f"- Modeled round-trip cost is `{modeled_round_trip:.4%}`; median raw full-spread proxy is `{quote_cost_proxy:.4%}` ({quote_multiplier:.1f}× modeled cost).",
        "- The vectorized engine applies a one-bar-lagged close-return exposure. It is not an explicit next-open or bid/ask-fill simulation.",
        "- `backtest.allow_short: false` in the source did not prevent short trades in the historical artifact; all long/short claims require an explicit stress check.",
        "",
        "## FTMO-style diagnostic (not broker certification)",
        "",
        f"- Max daily-loss breach count at 5%: `{ftmo.get('daily_loss_breach_count')}`; max-total-loss breach count at 10%: `{ftmo.get('max_total_loss_breach_count')}`.",
        f"- Historical max drawdown: `{primary.get('max_drawdown', float('nan')):.2%}`. The baseline has no hard risk-per-trade, stop, or drawdown guard.",
        "",
        "## Artifact limitations and discrepancies",
        "",
        "- The literal baseline config contains `/workspace` paths and is preserved unchanged only for provenance; the local replay maps paths under the repository.",
        "- The historical artifact mixes completed-trade, turnover-event, and exposed-bar count semantics; this lab uses the enriched trade ledger for completed trades.",
        "- Forecast volatility diagnostics reference a missing `atr_pct_rank_100` column; they are not used for lab decisions.",
        "- Monitoring flags drift in several raw volatility-level features. Feature selection therefore uses train/screen diagnostics rather than aggregate gain alone.",
    ]
    (REPORTS_DIR / "baseline_diagnostics.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return diagnostics


def _baseline_feature_target_frame() -> tuple[pd.DataFrame, list[str], str, list[Any], dict[str, Any]]:
    """Build the baseline feature/target frame once for diagnostics only."""
    cfg = _base_runtime_config(phase="screening", run_name="trial0041_diagnostics_internal")
    raw = load_trial_raw()
    featured = apply_feature_steps(raw, list(cfg["features"]), asset="ETHUSD")
    labelled, _, target_col, target_meta = build_target(featured, dict(cfg["model"]["target"]))
    horizon = int(target_meta.get("horizon", 24))
    splits = build_time_splits(
        method="purged",
        n_samples=len(labelled),
        split_cfg=dict(cfg["model"]["split"]),
        target_horizon=horizon,
    )
    return labelled, list(cfg["model"]["feature_cols"]), str(target_col), splits, cfg


def _psi(reference: pd.Series, current: pd.Series, *, bins: int = 10) -> float:
    ref = pd.to_numeric(reference, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    cur = pd.to_numeric(current, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(ref) < bins or len(cur) < bins:
        return float("nan")
    edges = np.unique(np.quantile(ref.to_numpy(dtype=float), np.linspace(0.0, 1.0, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    ref_hist = np.histogram(ref, bins=edges)[0].astype(float)
    cur_hist = np.histogram(cur, bins=edges)[0].astype(float)
    expected = np.clip(ref_hist / ref_hist.sum(), 1e-8, None)
    actual = np.clip(cur_hist / cur_hist.sum(), 1e-8, None)
    return float(np.sum((actual - expected) * np.log(actual / expected)))


def _ks_statistic(reference: pd.Series, current: pd.Series) -> float:
    ref = pd.to_numeric(reference, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    cur = pd.to_numeric(current, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if ref.empty or cur.empty:
        return float("nan")
    try:
        from scipy.stats import ks_2samp

        return float(ks_2samp(ref.to_numpy(dtype=float), cur.to_numpy(dtype=float), method="asymp").statistic)
    except Exception:
        values = np.sort(np.unique(np.concatenate([ref.to_numpy(dtype=float), cur.to_numpy(dtype=float)])))
        return float(np.max(np.abs(np.searchsorted(np.sort(ref), values, side="right") / len(ref) - np.searchsorted(np.sort(cur), values, side="right") / len(cur))))


def _safe_corr(left: pd.Series, right: pd.Series, *, method: str) -> float:
    pair = pd.concat([pd.to_numeric(left, errors="coerce"), pd.to_numeric(right, errors="coerce")], axis=1).dropna()
    if len(pair) < 3 or pair.iloc[:, 0].nunique() < 2 or pair.iloc[:, 1].nunique() < 2:
        return float("nan")
    return float(pair.iloc[:, 0].corr(pair.iloc[:, 1], method=method))


def _feature_importance_diagnostics(
    frame: pd.DataFrame,
    *,
    feature_cols: list[str],
    target_col: str,
    splits: list[Any],
    model_params: Mapping[str, Any],
) -> dict[str, dict[str, list[float]]]:
    """Compute fold-local gain/split/permutation and IC values on screening folds."""
    from lightgbm import LGBMRegressor

    records = {feature: {"gain": [], "split": [], "permutation_mse_delta": [], "spearman_ic": []} for feature in feature_cols}
    params = dict(model_params)
    params.pop("_diagnostics", None)
    for split in splits[:SCREENING_FOLD_COUNT]:
        horizon = 24
        safe_train = np.asarray(split.train_idx, dtype=int)
        safe_train = safe_train[safe_train < int(split.test_start) - horizon]
        train = frame.iloc[safe_train]
        test = frame.iloc[np.asarray(split.test_idx, dtype=int)]
        train_mask = train[feature_cols].notna().all(axis=1) & train[target_col].notna()
        test_mask = test[feature_cols].notna().all(axis=1) & test[target_col].notna()
        if int(train_mask.sum()) < 500 or int(test_mask.sum()) < 100:
            continue
        x_train = train.loc[train_mask, feature_cols].astype(float)
        y_train = train.loc[train_mask, target_col].astype(float)
        x_test = test.loc[test_mask, feature_cols].astype(float)
        y_test = test.loc[test_mask, target_col].astype(float)
        model = LGBMRegressor(**params)
        model.fit(x_train, y_train)
        prediction = np.asarray(model.predict(x_test), dtype=float)
        base_mse = float(np.mean(np.square(y_test.to_numpy(dtype=float) - prediction)))
        gain = model.booster_.feature_importance(importance_type="gain")
        split_importance = model.booster_.feature_importance(importance_type="split")
        rng = np.random.default_rng(7 + int(split.fold))
        for pos, feature in enumerate(feature_cols):
            records[feature]["gain"].append(float(gain[pos]))
            records[feature]["split"].append(float(split_importance[pos]))
            shuffled = x_test.copy()
            shuffled[feature] = rng.permutation(shuffled[feature].to_numpy(dtype=float))
            shuffled_prediction = np.asarray(model.predict(shuffled), dtype=float)
            records[feature]["permutation_mse_delta"].append(
                float(np.mean(np.square(y_test.to_numpy(dtype=float) - shuffled_prediction)) - base_mse)
            )
            records[feature]["spearman_ic"].append(_safe_corr(test[feature], test[target_col], method="spearman"))
    return records


def _redundancy_clusters(frame: pd.DataFrame, feature_cols: list[str], *, threshold: float = 0.90) -> pd.DataFrame:
    sample = frame[feature_cols].replace([np.inf, -np.inf], np.nan).dropna()
    if len(sample) > 20_000:
        sample = sample.iloc[np.linspace(0, len(sample) - 1, 20_000, dtype=int)]
    corr = sample.corr(method="spearman").abs() if not sample.empty else pd.DataFrame()
    parent = {feature: feature for feature in feature_cols}

    def find(value: str) -> str:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: str, right: str) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    if not corr.empty:
        for pos, left in enumerate(feature_cols):
            for right in feature_cols[pos + 1 :]:
                if float(corr.loc[left, right]) >= threshold:
                    union(left, right)
    groups: dict[str, list[str]] = {}
    for feature in feature_cols:
        groups.setdefault(find(feature), []).append(feature)
    rows: list[dict[str, Any]] = []
    for cluster_no, members in enumerate(sorted(groups.values(), key=lambda values: (len(values), values), reverse=True), start=1):
        for feature in sorted(members):
            peers = [member for member in members if member != feature]
            max_corr = max((float(corr.loc[feature, peer]) for peer in peers), default=0.0) if not corr.empty else float("nan")
            rows.append({"feature": feature, "cluster_id": cluster_no, "cluster_size": len(members), "members": ";".join(sorted(members)), "max_abs_spearman_within_cluster": max_corr})
    return pd.DataFrame(rows)


def write_feature_diagnostics() -> pd.DataFrame:
    """Generate train/screen-only feature diagnostics and redundancy clusters."""
    frame, feature_cols, target_col, splits, cfg = _baseline_feature_target_frame()
    screen_end = int(splits[SCREENING_FOLD_COUNT - 1].test_end)
    screen = frame.iloc[:screen_end].copy()
    initial_train = frame.iloc[np.asarray(splits[0].train_idx, dtype=int)].copy()
    validation_indices = np.concatenate([np.asarray(split.test_idx, dtype=int) for split in splits[:SCREENING_FOLD_COUNT]])
    validation = frame.iloc[validation_indices].copy()
    importance = _feature_importance_diagnostics(
        frame,
        feature_cols=feature_cols,
        target_col=target_col,
        splits=splits,
        model_params=dict(cfg["model"]["params"]),
    )
    target = screen[target_col]
    valid_mi = screen[feature_cols + [target_col]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(valid_mi) > 30_000:
        valid_mi = valid_mi.iloc[np.linspace(0, len(valid_mi) - 1, 30_000, dtype=int)]
    mi_values: dict[str, float] = {feature: float("nan") for feature in feature_cols}
    if len(valid_mi) >= 500:
        try:
            from sklearn.feature_selection import mutual_info_regression

            values = mutual_info_regression(valid_mi[feature_cols].to_numpy(dtype=float), valid_mi[target_col].to_numpy(dtype=float), random_state=7)
            mi_values = {feature: float(value) for feature, value in zip(feature_cols, values, strict=True)}
        except Exception:
            pass
    rows: list[dict[str, Any]] = []
    for feature in feature_cols:
        values = pd.to_numeric(screen[feature], errors="coerce").replace([np.inf, -np.inf], np.nan)
        ic = importance[feature]["spearman_ic"]
        finite_ic = np.asarray([value for value in ic if np.isfinite(value)], dtype=float)
        gains = np.asarray(importance[feature]["gain"], dtype=float)
        splits_imp = np.asarray(importance[feature]["split"], dtype=float)
        permutation = np.asarray(importance[feature]["permutation_mse_delta"], dtype=float)
        rows.append(
            {
                "feature": feature,
                "missing_ratio": float(values.isna().mean()),
                "variance": float(values.dropna().var(ddof=1)) if values.notna().sum() >= 2 else float("nan"),
                "unique_ratio": float(values.nunique(dropna=True) / max(values.notna().sum(), 1)),
                "pearson_target": _safe_corr(values, target, method="pearson"),
                "spearman_ic_screen": _safe_corr(values, target, method="spearman"),
                "mutual_information": mi_values[feature],
                "fold_spearman_ic_mean": float(np.nanmean(finite_ic)) if finite_ic.size else float("nan"),
                "fold_spearman_ic_std": float(np.nanstd(finite_ic, ddof=1)) if finite_ic.size > 1 else float("nan"),
                "fold_ic_sign_stability": float(abs(np.sign(finite_ic).mean())) if finite_ic.size else float("nan"),
                "gain_importance_mean": float(np.nanmean(gains)) if gains.size else float("nan"),
                "gain_importance_std": float(np.nanstd(gains, ddof=1)) if gains.size > 1 else float("nan"),
                "split_importance_mean": float(np.nanmean(splits_imp)) if splits_imp.size else float("nan"),
                "permutation_mse_delta_mean": float(np.nanmean(permutation)) if permutation.size else float("nan"),
                "permutation_mse_delta_std": float(np.nanstd(permutation, ddof=1)) if permutation.size > 1 else float("nan"),
                "psi_initial_train_to_screen": _psi(initial_train[feature], validation[feature]),
                "ks_initial_train_to_screen": _ks_statistic(initial_train[feature], validation[feature]),
                "fold_count": int(len(finite_ic)),
            }
        )
    diagnostics = pd.DataFrame(rows).sort_values(["permutation_mse_delta_mean", "gain_importance_mean"], ascending=False, na_position="last")
    clusters = _redundancy_clusters(screen, feature_cols)
    diagnostics.to_csv(REPORTS_DIR / "feature_diagnostics.csv", index=False)
    clusters.to_csv(REPORTS_DIR / "feature_clusters.csv", index=False)
    stable = diagnostics.loc[(diagnostics["fold_ic_sign_stability"] >= 0.60) & (diagnostics["psi_initial_train_to_screen"] < 0.20)].head(12)
    unstable = diagnostics.loc[(diagnostics["psi_initial_train_to_screen"] >= 0.20) | (diagnostics["fold_ic_sign_stability"] < 0.30)].head(20)
    shap_available = False
    try:
        import shap  # noqa: F401

        shap_available = True
    except Exception:
        shap_available = False
    md = [
        "# Feature diagnostics (screening era only)",
        "",
        "All statistics use rows available no later than fold 9. Gain/split and permutation values are recomputed fold-locally; no target, barrier, or trade diagnostic column enters the model feature set.",
        "",
        f"- Features: `{len(feature_cols)}`; screening folds: `0-9`; target: `{target_col}`.",
        f"- SHAP available in this environment: `{shap_available}`. It is not substituted with a fabricated proxy.",
        "",
        "## Candidate stable features",
        "",
        stable[["feature", "fold_spearman_ic_mean", "fold_ic_sign_stability", "permutation_mse_delta_mean", "psi_initial_train_to_screen"]].to_markdown(index=False),
        "",
        "## Drift/instability watchlist",
        "",
        unstable[["feature", "fold_spearman_ic_mean", "fold_ic_sign_stability", "gain_importance_mean", "psi_initial_train_to_screen", "ks_initial_train_to_screen"]].to_markdown(index=False),
        "",
        "Correlation clusters are in `feature_clusters.csv`; clusters are used for family-level ablations rather than single-feature fishing.",
    ]
    (REPORTS_DIR / "feature_diagnostics.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return diagnostics


def _distribution_summary(values: pd.Series) -> dict[str, float]:
    series = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna().astype(float)
    if series.empty:
        return {"rows": 0}
    try:
        from scipy.stats import kurtosis, skew

        skewness = float(skew(series.to_numpy(dtype=float), bias=False))
        kurt = float(kurtosis(series.to_numpy(dtype=float), bias=False))
    except Exception:
        skewness = float("nan")
        kurt = float("nan")
    return {
        "rows": int(len(series)), "mean": float(series.mean()), "median": float(series.median()), "std": float(series.std(ddof=1)),
        "skew": skewness, "excess_kurtosis": kurt, "min": float(series.min()), "max": float(series.max()),
        **{f"q{int(q * 100):02d}": float(series.quantile(q)) for q in (0.01, 0.05, 0.25, 0.75, 0.95, 0.99)},
    }


def write_target_diagnostics() -> dict[str, Any]:
    frame, _, target_col, splits, cfg = _baseline_feature_target_frame()
    screen_end = int(splits[SCREENING_FOLD_COUNT - 1].test_end)
    screen = frame.iloc[:screen_end].copy()
    base_target = screen[target_col]
    horizon_rows: list[dict[str, Any]] = []
    for horizon in (8, 12, 16, 24, 36, 48):
        labelled, _, col, _ = build_target(frame, _base_target(horizon))
        values = labelled.iloc[:screen_end][col]
        row = {"horizon_bars": horizon, **_distribution_summary(values), "acf_1": float(values.autocorr(lag=1)), "acf_horizon": float(values.autocorr(lag=horizon))}
        horizon_rows.append(row)
    future_returns = pd.concat([screen["close_ret"].shift(-step) for step in range(1, 25)], axis=1)
    future_vol = future_returns.std(axis=1, ddof=1)
    atr_pct = screen["atr_48"] / screen["close"].replace(0.0, np.nan)
    index_series = pd.Series(screen.index, index=screen.index)
    elapsed = index_series.shift(-24) - index_series
    base_summary = _distribution_summary(base_target)
    payload = {
        "target": target_col,
        "baseline_distribution": base_summary,
        "positive_rate": float((base_target > 0).mean()),
        "negative_rate": float((base_target < 0).mean()),
        "clip_bound_frequency": float((base_target.abs() >= 4.0 - 1e-12).mean()),
        "autocorrelation": {str(lag): float(base_target.autocorr(lag=lag)) for lag in (1, 2, 4, 8, 16, 24)},
        "corr_with_current_atr_pct": _safe_corr(base_target, atr_pct, method="spearman"),
        "corr_with_future_realized_vol": _safe_corr(base_target, future_vol, method="spearman"),
        "nominal_holding_bars": 24,
        "nominal_holding_hours": 12.0,
        "gap_spanning_target_rows": int((elapsed > pd.Timedelta(hours=12)).sum()),
        "max_target_elapsed": str(elapsed.max()),
        "horizon_comparison": horizon_rows,
        "yearly": [{"year": int(year), **_distribution_summary(group)} for year, group in base_target.groupby(base_target.index.year)],
    }
    (REPORTS_DIR / "target_diagnostics.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    pd.DataFrame(horizon_rows).to_csv(REPORTS_DIR / "target_horizon_diagnostics.csv", index=False)
    fold_rows = []
    for split in splits[:SCREENING_FOLD_COUNT]:
        values = frame.iloc[np.asarray(split.test_idx, dtype=int)][target_col]
        fold_rows.append({"fold": int(split.fold), **_distribution_summary(values)})
    pd.DataFrame(fold_rows).to_csv(REPORTS_DIR / "target_fold_diagnostics.csv", index=False)
    md = [
        "# Target diagnostics (screening era only)",
        "",
        f"Baseline target `{target_col}` is a {24}-bar (nominal 12-hour) ATR-normalized future return, clipped at ±4. `{payload['clip_bound_frequency']:.2%}` of screening labels lie at a clip bound.",
        "",
        f"- Spearman relationship with current ATR percentage: `{payload['corr_with_current_atr_pct']:.4f}`.",
        f"- Spearman relationship with future realized volatility: `{payload['corr_with_future_realized_vol']:.4f}`.",
        f"- Target rows crossing a gap longer than the nominal horizon: `{payload['gap_spanning_target_rows']}`.",
        "",
        "## Horizon distribution comparison",
        "",
        pd.DataFrame(horizon_rows)[["horizon_bars", "rows", "mean", "median", "std", "acf_1", "acf_horizon"]].to_markdown(index=False),
        "",
        "The horizon variants are predeclared candidates. Their locked-fold results are not used to select a different threshold or target after the fact.",
    ]
    (REPORTS_DIR / "target_diagnostics.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return payload


def run_diagnostics() -> dict[str, Any]:
    """Run data, artifact, target, and feature diagnostics before screening."""
    return {
        "data_audit": audit_raw_data(),
        "baseline": write_baseline_diagnostics(),
        "target": write_target_diagnostics(),
        "feature_rows": int(len(write_feature_diagnostics())),
    }


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _run_index_path(phase: str) -> Path:
    return REPORTS_DIR / f"{phase}_run_index.json"


def _load_run_index(phase: str) -> dict[str, Any]:
    path = _run_index_path(phase)
    if not path.exists():
        return {}
    payload = _read_json(path)
    return dict(payload.get("runs", {}) or {})


def _save_run_index(phase: str, runs: Mapping[str, Any]) -> None:
    _run_index_path(phase).write_text(json.dumps({"runs": dict(runs)}, indent=2, default=_json_default), encoding="utf-8")


def _summary_from_run_dir(run_dir: Path) -> dict[str, Any]:
    summary_path = run_dir / "summary.json"
    return _read_json(summary_path) if summary_path.exists() else {}


def _run_config(path: Path, *, phase: str, resume: bool) -> tuple[dict[str, Any], Any | None]:
    run_id = str(path.relative_to(PROJECT_ROOT))
    existing = _load_run_index(phase).get(run_id)
    config_hash = _config_sha256(path)
    if resume and isinstance(existing, dict) and existing.get("config_sha256") == config_hash and existing.get("status") == "success":
        run_dir = Path(str(existing.get("run_dir", "")))
        if run_dir.exists() and (run_dir / "summary.json").exists():
            return dict(existing), None
    try:
        result = run_experiment(path)
        run_dir = Path(str(result.artifacts.get("run_dir", "")))
        summary = _summary_from_run_dir(run_dir) if run_dir.exists() else {}
        record = {
            "status": "success",
            "config_sha256": config_hash,
            "run_dir": str(run_dir),
            "summary": summary,
            "artifacts": dict(result.artifacts),
        }
        return record, result
    except Exception as exc:  # failures are research evidence, not discarded output
        return {
            "status": "failed", "config_sha256": config_hash,
            "error": f"{type(exc).__name__}: {exc}", "run_dir": "", "summary": {},
        }, None


def run_screening(*, resume: bool = True) -> pd.DataFrame:
    """Execute the local baseline plus the frozen single-axis matrix on folds 0--9."""
    validation = validate_lab_configs()
    if not validation.empty and (validation["status"] != "valid").any():
        raise LabContractError("Refusing to screen invalid lab configs; see reports/config_validation.csv.")
    runs = _load_run_index("screening")
    rows: list[dict[str, Any]] = []
    for path in list_lab_yaml_paths():
        record, _ = _run_config(path, phase="screening", resume=resume)
        runs[str(path.relative_to(PROJECT_ROOT))] = record
        _save_run_index("screening", runs)
        rows.append({"yaml_path": str(path.relative_to(PROJECT_ROOT)), "status": record["status"], "run_dir": record.get("run_dir", ""), "error": record.get("error", "")})
    table = pd.DataFrame(rows)
    table.to_csv(REPORTS_DIR / "screening_execution.csv", index=False)
    return table


def _oos_series_from_artifact(run_dir: Path, summary: Mapping[str, Any]) -> tuple[pd.Series, pd.Series, pd.Series]:
    returns = _read_series(run_dir / "returns.csv", name="net")
    gross = _read_series(run_dir / "gross_returns.csv", name="gross")
    costs = _read_series(run_dir / "costs.csv", name="cost")
    prediction = dict(summary.get("model_meta", {}).get("prediction_diagnostics", {}) or {})
    if not prediction:
        prediction = dict(_read_json(run_dir / "prediction_diagnostics.json") if (run_dir / "prediction_diagnostics.json").exists() else {})
    first, last = prediction.get("first_prediction_index"), prediction.get("last_prediction_index")
    if first and last:
        start, end = pd.Timestamp(first), pd.Timestamp(last)
        returns = returns.loc[(returns.index >= start) & (returns.index <= end)]
    return returns, gross.reindex(returns.index).fillna(0.0), costs.reindex(returns.index).fillna(0.0)


def _zscore(values: pd.Series, *, higher_is_better: bool = True) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)
    finite = numeric.dropna()
    if len(finite) < 2 or float(finite.std(ddof=0)) <= 1e-12:
        out = pd.Series(0.0, index=values.index)
    else:
        out = (numeric - finite.mean()) / finite.std(ddof=0)
        out = out.fillna(0.0)
    return out if higher_is_better else -out


def _bootstrap_positive_probability(values: Iterable[float], *, seed: int = 7, draws: int = 5000) -> float:
    array = np.asarray([value for value in values if np.isfinite(value)], dtype=float)
    if array.size == 0:
        return float("nan")
    rng = np.random.default_rng(seed)
    samples = rng.choice(array, size=(draws, len(array)), replace=True).mean(axis=1)
    return float((samples > 0.0).mean())


def build_screening_leaderboard() -> pd.DataFrame:
    """Rank successful first-stage runs only from folds 0--9 and OOS artifacts."""
    runs = _load_run_index("screening")
    manifest = pd.read_csv(REPORTS_DIR / "experiment_manifest.csv")
    rows: list[dict[str, Any]] = []
    for _, manifest_row in manifest.iterrows():
        path = str(manifest_row["yaml_path"])
        record = dict(runs.get(path, {}) or {})
        if record.get("status") != "success":
            rows.append({"experiment_id": manifest_row["experiment_id"], "yaml_path": path, "family": manifest_row["family"], "run_status": record.get("status", "not_run"), "error": record.get("error", "")})
            continue
        summary = dict(record.get("summary", {}) or {})
        evaluation = dict(summary.get("evaluation", {}) or {})
        primary = dict(evaluation.get("primary_summary", {}) or {})
        folds = [dict(item.get("metrics", {}) or {}) for item in list(evaluation.get("fold_backtest_summaries", []) or [])]
        fold_frame = pd.DataFrame(folds)
        run_dir = Path(str(record["run_dir"]))
        net, gross, costs = _oos_series_from_artifact(run_dir, summary)
        cost2 = gross - 2.0 * costs
        cost2_metrics = compute_backtest_metrics(net_returns=cost2, periods_per_year=17_520)
        pnl_values = pd.to_numeric(fold_frame.get("net_pnl", pd.Series(dtype=float)), errors="coerce").dropna()
        pos_pnl = pnl_values[pnl_values > 0]
        concentration = float(pos_pnl.max() / pos_pnl.sum()) if len(pos_pnl) and float(pos_pnl.sum()) > 0 else float("nan")
        model_regression = dict(evaluation.get("model_oos_regression_summary", {}) or {})
        rows.append(
            {
                "experiment_id": manifest_row["experiment_id"], "yaml_path": path, "family": manifest_row["family"], "run_status": "success", "run_dir": str(run_dir),
                "cumulative_return": primary.get("cumulative_return"), "annualized_return": primary.get("annualized_return"), "annualized_vol": primary.get("annualized_vol"),
                "sharpe_framework_cagr_over_vol": primary.get("sharpe"), "sortino_framework": primary.get("sortino"), "calmar": primary.get("calmar"), "max_drawdown": primary.get("max_drawdown"),
                "profit_factor": primary.get("profit_factor"), "net_pnl": primary.get("net_pnl"), "total_cost": primary.get("total_cost"), "total_turnover": primary.get("total_turnover"), "trade_count": primary.get("trade_count"),
                "positive_folds": int((pd.to_numeric(fold_frame.get("net_pnl", pd.Series(dtype=float)), errors="coerce") > 0).sum()), "fold_count": int(len(fold_frame)),
                "median_fold_sharpe_framework": float(pd.to_numeric(fold_frame.get("sharpe", pd.Series(dtype=float)), errors="coerce").median()),
                "q25_fold_sharpe_framework": float(pd.to_numeric(fold_frame.get("sharpe", pd.Series(dtype=float)), errors="coerce").quantile(0.25)),
                "median_fold_net_pnl": float(pnl_values.median()) if not pnl_values.empty else float("nan"),
                "q25_fold_net_pnl": float(pnl_values.quantile(0.25)) if not pnl_values.empty else float("nan"),
                "min_fold_net_pnl": float(pnl_values.min()) if not pnl_values.empty else float("nan"),
                "return_concentration": concentration,
                "bootstrap_prob_fold_expectancy_positive": _bootstrap_positive_probability(pnl_values),
                "prediction_ic": model_regression.get("correlation"),
                "cost2_net_pnl": float(cost2.sum()), "cost2_cumulative_return": cost2_metrics.get("cumulative_return"), "cost2_sharpe_framework": cost2_metrics.get("sharpe"),
                "error": "",
            }
        )
    table = pd.DataFrame(rows)
    success = table[table["run_status"] == "success"].copy()
    if not success.empty:
        baseline_row = success.loc[success["family"] == "baseline"].head(1)
        baseline_dd = float(baseline_row["max_drawdown"].iloc[0]) if not baseline_row.empty else 0.0
        baseline_turnover = float(baseline_row["total_turnover"].iloc[0]) if not baseline_row.empty else 1.0
        success["robust_score"] = (
            0.35 * _zscore(success["median_fold_sharpe_framework"])
            + 0.15 * _zscore(success["q25_fold_sharpe_framework"])
            + 0.15 * _zscore(success["calmar"])
            + 0.10 * _zscore(success["sortino_framework"])
            + 0.10 * _zscore(success["profit_factor"])
            + 0.10 * _zscore(success["bootstrap_prob_fold_expectancy_positive"])
            + 0.05 * _zscore(success["prediction_ic"])
            - 0.15 * np.maximum(0.0, success["max_drawdown"].abs() - abs(baseline_dd)) / max(abs(baseline_dd), 1e-6)
            - 0.10 * np.maximum(0.0, success["total_turnover"] / max(baseline_turnover, 1e-6) - 1.0)
            - 0.15 * np.maximum(0.0, 0.50 - success["cost2_net_pnl"] / success["net_pnl"].abs().clip(lower=1e-8))
            - 0.10 * np.maximum(0.0, success["return_concentration"] - 0.50).fillna(0.0)
            - 0.10 * np.maximum(0.0, 7 - success["positive_folds"])
        )
        success["screening_status"] = np.where(
            (success["positive_folds"] >= 7) & (success["q25_fold_net_pnl"] >= 0.0) & (success["cost2_net_pnl"] > 0.0) & (success["trade_count"].fillna(0) >= 40),
            "screening_winner", "rejected_screening",
        )
        table = table.merge(success[["experiment_id", "robust_score", "screening_status"]], on="experiment_id", how="left")
        table = table.sort_values(["run_status", "robust_score"], ascending=[True, False], na_position="last")
    else:
        table["robust_score"] = np.nan
        table["screening_status"] = "not_run"
    table.to_csv(REPORTS_DIR / "experiment_leaderboard.csv", index=False)
    visible = table.loc[table["run_status"] == "success"].head(20)
    md = [
        "# Screening experiment leaderboard",
        "",
        "Ranking is deterministic and uses strict-OOS folds 0--9 only. It gives 35% to median fold framework Sharpe (CAGR/vol), 15% lower-quartile fold Sharpe, 15% Calmar, 10% Sortino, 10% profit factor, 10% fold-bootstrap positive-expectancy probability, and 5% prediction IC. Penalties apply for drawdown, turnover, 2× cost deterioration, concentration, and negative folds.",
        "",
        "This is a screening score, not a claim of alpha. The locked 2024-09--2026 continuation is untouched at this stage.",
        "",
        visible[["experiment_id", "family", "robust_score", "positive_folds", "median_fold_net_pnl", "cost2_net_pnl", "max_drawdown", "screening_status"]].to_markdown(index=False),
    ]
    (REPORTS_DIR / "experiment_leaderboard.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    _update_manifest_from_leaderboard(table)
    return table


def _update_manifest_from_leaderboard(leaderboard: pd.DataFrame) -> None:
    path = REPORTS_DIR / "experiment_manifest.csv"
    manifest = pd.read_csv(path)
    fields = leaderboard[["experiment_id", "screening_status", "robust_score"]].copy() if not leaderboard.empty else pd.DataFrame()
    if not fields.empty:
        manifest = manifest.drop(columns=[column for column in ("screening_status", "actual_result") if column in manifest], errors="ignore").merge(fields, on="experiment_id", how="left")
        manifest["actual_result"] = manifest["robust_score"].map(lambda value: f"screening_robust_score={value:.4f}" if pd.notna(value) else "pending")
        manifest = manifest.drop(columns=["robust_score"])
    manifest.to_csv(path, index=False)


def _stage_config_from_row(row: pd.Series) -> dict[str, Any]:
    return _read_yaml(PROJECT_ROOT / str(row["yaml_path"]))


def _choose_screening_component(
    leaderboard: pd.DataFrame,
    *,
    families: set[str],
    regression_only: bool = False,
    allowed_model_kinds: set[str] | None = None,
) -> tuple[pd.Series | None, dict[str, Any] | None]:
    candidates = leaderboard.loc[(leaderboard["run_status"] == "success") & (leaderboard["family"].isin(families))].copy()
    if candidates.empty:
        return None, None
    candidates["preferred"] = candidates["screening_status"].eq("screening_winner")
    candidates = candidates.sort_values(["preferred", "robust_score"], ascending=[False, False], na_position="last")
    for _, row in candidates.iterrows():
        cfg = _stage_config_from_row(row)
        model_kind = str(cfg.get("model", {}).get("kind"))
        if regression_only and model_kind not in {"lightgbm_regressor", "xgboost_regressor"}:
            continue
        if allowed_model_kinds is not None and model_kind not in allowed_model_kinds:
            continue
        return row, cfg
    return None, None


def _apply_final_axis(base: dict[str, Any], source: Mapping[str, Any], *, axis: str) -> dict[str, Any]:
    out = deepcopy(base)
    source_model = dict(source.get("model", {}) or {})
    if axis == "target":
        out["model"]["target"] = deepcopy(source_model["target"])
        target_horizon = int(out["model"]["target"].get("horizon_bars", out["model"]["target"].get("horizon", 24)))
        if target_horizon > int(out["model"]["split"].get("purge_bars", 0)):
            out["model"]["split"]["purge_bars"] = target_horizon
            out["model"]["split"]["embargo_bars"] = target_horizon
            out["validation"]["purge_bars"] = target_horizon
            out["validation"]["embargo_bars"] = target_horizon
    elif axis == "feature":
        out["features"] = deepcopy(list(source.get("features", []) or []))
        out["model"]["feature_cols"] = deepcopy(list(source_model.get("feature_cols", []) or []))
    elif axis == "signal":
        out["signals"] = deepcopy(dict(source.get("signals", {}) or {}))
        out["backtest"]["signal_col"] = str(source.get("backtest", {}).get("signal_col"))
    elif axis == "model":
        for key in ("kind", "params", "outputs", "preprocessing", "calibration", "pred_prob_col", "pred_raw_prob_col", "pred_ret_col", "pred_is_oos_col", "returns_input_col", "signal_col", "action_col", "use_features"):
            if key in source_model:
                out["model"][key] = deepcopy(source_model[key])
    else:
        raise LabContractError(f"Unknown finalist axis: {axis}")
    return out


def generate_finalists() -> pd.DataFrame:
    """Freeze 10 finalists using only the already-written screening leaderboard."""
    leaderboard_path = REPORTS_DIR / "experiment_leaderboard.csv"
    if not leaderboard_path.exists():
        raise LabContractError("Run screening and build the leaderboard before generating finalists.")
    leaderboard = pd.read_csv(leaderboard_path)
    target_row, target_cfg = _choose_screening_component(leaderboard, families={"target"}, regression_only=True)
    feature_row, feature_cfg = _choose_screening_component(leaderboard, families={"feature_ablation", "feature_addition", "normalization"}, regression_only=True)
    signal_row, signal_cfg = _choose_screening_component(leaderboard, families={"signal"}, regression_only=True)
    model_row, model_cfg = _choose_screening_component(leaderboard, families={"model"}, regression_only=True)
    classifier_row, classifier_cfg = _choose_screening_component(
        leaderboard,
        families={"target", "model"},
        allowed_model_kinds={"lightgbm_clf", "xgboost_clf", "logistic_regression_clf", "elastic_net_clf"},
    )

    components: dict[str, tuple[pd.Series | None, dict[str, Any] | None]] = {
        "target": (target_row, target_cfg), "feature": (feature_row, feature_cfg), "signal": (signal_row, signal_cfg), "model": (model_row, model_cfg),
    }

    designs: list[tuple[str, tuple[str, ...], str]] = [
        ("baseline", (), "Frozen local baseline replay on locked folds 10-16."),
        ("target", ("target",), "Best screening regression-target change only."),
        ("feature", ("feature",), "Best screening feature-family change only."),
        ("signal", ("signal",), "Best screening signal change only."),
        ("model", ("model",), "Best screening regression-model change only."),
        ("target_feature", ("target", "feature"), "Greedy target plus feature combination."),
        ("target_signal", ("target", "signal"), "Greedy target plus signal combination."),
        ("feature_signal", ("feature", "signal"), "Greedy feature plus signal combination."),
        ("target_feature_signal", ("target", "feature", "signal"), "Greedy target, feature, and signal combination."),
        ("full_greedy", ("target", "feature", "signal", "model"), "Greedy forward combination of the four winning axes."),
    ]
    if classifier_cfg is not None:
        designs[5] = ("classifier_branch", (), "Matched classifier branch frozen after its screening result.")

    rows: list[dict[str, Any]] = []
    final_dir = LAB_ROOT / "07_combined_finalists"
    for ordinal, (slug, axes, hypothesis) in enumerate(designs, start=1):
        experiment_id = f"ethusd_30m_trial0041_final_{ordinal:02d}_{slug}_v1"
        cfg = _base_runtime_config(phase="locked", run_name=experiment_id)
        lineage: list[str] = []
        if slug == "classifier_branch" and classifier_cfg is not None and classifier_row is not None:
            cfg = deepcopy(classifier_cfg)
            cfg["model"]["split"]["max_folds"] = FULL_FOLD_COUNT
            cfg["logging"]["run_name"] = experiment_id
            cfg["logging"]["output_dir"] = str(LOCAL_LOGS_RELATIVE)
            cfg["diagnostics"]["robustness"]["enabled"] = True
            cfg["diagnostics"]["robustness"].update({"cost_multipliers": [1.0, 2.0, 5.0, 10.0, 15.0], "entry_delay_bars": [1, 2]})
            lineage.append(str(classifier_row["experiment_id"]))
        else:
            for axis in axes:
                row, source = components[axis]
                if row is None or source is None:
                    continue
                cfg = _apply_final_axis(cfg, source, axis=axis)
                lineage.append(str(row["experiment_id"]))
        spec = ExperimentSpec(
            experiment_id=experiment_id,
            family="combined_finalist",
            hypothesis=hypothesis,
            expected_effect="Frozen before folds 10-16 are accessed; no post-lock modification is permitted.",
            parent_experiment=";".join(lineage) if lineage else "baseline_local_replay",
            mutation=lambda value: value,
        )
        cfg = _set_single_axis_metadata(cfg, spec=spec, phase="locked")
        cfg["research_metadata"]["lineage"] = lineage
        cfg["research_metadata"]["selection_rule"] = "deterministic screening leaderboard; locked folds not read"
        _assert_feature_denylist(cfg)
        path = final_dir / f"{experiment_id}.yaml"
        _write_config(path, cfg, spec=spec, phase="locked")
        rows.append({"experiment_id": experiment_id, "yaml_path": str(path.relative_to(PROJECT_ROOT)), "hypothesis": hypothesis, "lineage": ";".join(lineage), "locked_status": "not_run"})
    table = pd.DataFrame(rows)
    table.to_csv(REPORTS_DIR / "finalist_manifest.csv", index=False)
    validate_lab_configs(include_finalists=True)
    return table


def _single_asset_frame(result: Any) -> pd.DataFrame:
    data = result.data
    if isinstance(data, dict):
        if len(data) != 1:
            raise LabContractError("Trial 0041 lab supports one ETHUSD asset only.")
        return next(iter(data.values())).copy()
    return data.copy()


def _locked_splits_for_config(frame: pd.DataFrame, cfg: Mapping[str, Any]) -> list[Any]:
    target = dict(cfg.get("model", {}).get("target", {}) or {})
    horizon = int(target.get("horizon_bars", target.get("horizon", 24)))
    return build_time_splits(
        method="purged",
        n_samples=len(frame),
        split_cfg=dict(cfg["model"]["split"]),
        target_horizon=horizon,
    )


def _run_vector_stress(frame: pd.DataFrame, cfg: Mapping[str, Any], *, signal_col: str, cost_multiplier: float = 1.0, delay: int = 0) -> tuple[dict[str, Any], pd.Series]:
    work = frame.copy()
    work[signal_col] = pd.to_numeric(work[signal_col], errors="coerce").fillna(0.0).shift(int(delay)).fillna(0.0)
    result = run_backtest(
        work,
        signal_col=signal_col,
        returns_col=str(cfg["backtest"]["returns_col"]),
        returns_type=str(cfg["backtest"].get("returns_type", "simple")),
        missing_return_policy=str(cfg["backtest"].get("missing_return_policy", "raise_if_exposed")),
        cost_per_unit_turnover=float(cfg["risk"].get("cost_per_turnover", 0.0)) * float(cost_multiplier),
        slippage_per_unit_turnover=float(cfg["risk"].get("slippage_per_turnover", 0.0)) * float(cost_multiplier),
        target_vol=cfg["risk"].get("target_vol"),
        vol_col=cfg["backtest"].get("vol_col") or cfg["risk"].get("vol_col"),
        max_leverage=float(cfg["risk"].get("max_leverage", 1.0)),
        dd_guard=False,
        periods_per_year=int(cfg["backtest"].get("periods_per_year", 17_520)),
        min_holding_bars=int(cfg["backtest"].get("min_holding_bars", 0)),
    )
    metrics = dict(result.summary)
    metrics.update(_conventional_return_metrics(result.returns, periods_per_year=int(cfg["backtest"].get("periods_per_year", 17_520))))
    metrics["net_pnl"] = float(result.returns.sum())
    metrics["gross_pnl"] = float(result.gross_returns.sum())
    metrics["total_cost"] = float(result.costs.sum())
    metrics["total_turnover"] = float(result.turnover.sum())
    return metrics, result.returns


def _threshold_perturbation_config(cfg: Mapping[str, Any], multiplier: float) -> dict[str, Any] | None:
    variant = deepcopy(dict(cfg))
    params = variant.get("signals", {}).get("params", {})
    kind = str(variant.get("signals", {}).get("kind"))
    if kind == "forecast_threshold":
        params["upper"] = float(params["upper"]) * float(multiplier)
        params["lower"] = float(params["lower"]) * float(multiplier)
        return variant
    if kind == "probability_threshold":
        upper = float(params.get("upper", 0.55))
        lower = float(params.get("lower", 0.45))
        params["upper"] = 0.5 + (upper - 0.5) * float(multiplier)
        params["lower"] = 0.5 - (0.5 - lower) * float(multiplier)
        return variant
    if kind == "momentum":
        params["long_threshold"] = float(params.get("long_threshold", 0.0)) * float(multiplier)
        short = params.get("short_threshold")
        if short is not None:
            params["short_threshold"] = float(short) * float(multiplier)
        return variant
    return None


def _probabilistic_sharpe_ratio(returns: pd.Series, *, periods_per_year: int) -> float:
    values = pd.to_numeric(returns, errors="coerce").dropna().astype(float).to_numpy()
    if len(values) < 3:
        return float("nan")
    std = float(np.std(values, ddof=1))
    if std <= 0:
        return float("nan")
    sr = float(np.mean(values) / std * math.sqrt(periods_per_year))
    centered = values - values.mean()
    skewness = float(np.mean(centered**3) / max(np.std(values, ddof=0) ** 3, 1e-16))
    kurtosis = float(np.mean(centered**4) / max(np.std(values, ddof=0) ** 4, 1e-16))
    denominator = math.sqrt(max(1e-12, 1.0 - skewness * sr + ((kurtosis - 1.0) / 4.0) * sr * sr))
    z = sr * math.sqrt(len(values) - 1.0) / denominator
    return float(0.5 * (1.0 + math.erf(z / math.sqrt(2.0))))


def _daily_bootstrap(returns: pd.Series, *, seed: int = 7, draws: int = 5000) -> dict[str, float]:
    daily = returns.groupby(returns.index.normalize()).apply(_series_compound).dropna().to_numpy(dtype=float)
    if daily.size == 0:
        return {"mean_ci_low": float("nan"), "mean_ci_high": float("nan"), "probability_mean_positive": float("nan")}
    rng = np.random.default_rng(seed)
    samples = rng.choice(daily, size=(draws, len(daily)), replace=True).mean(axis=1)
    return {"mean_ci_low": float(np.quantile(samples, 0.025)), "mean_ci_high": float(np.quantile(samples, 0.975)), "probability_mean_positive": float((samples > 0).mean())}


def _locked_fold_metrics(signal_frame: pd.DataFrame, cfg: Mapping[str, Any], splits: list[Any], signal_col: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for split in splits[LOCKED_FOLD_START:FULL_FOLD_COUNT]:
        segment = signal_frame.iloc[np.asarray(split.test_idx, dtype=int)].copy()
        metrics, _ = _run_vector_stress(segment, cfg, signal_col=signal_col)
        rows.append({"fold": int(split.fold), "start": str(segment.index.min()), "end": str(segment.index.max()), **metrics})
    return rows


def _stress_finalist(result: Any, config_path: Path) -> dict[str, Any]:
    cfg = load_experiment_config(config_path)
    frame = _single_asset_frame(result)
    splits = _locked_splits_for_config(frame, cfg)
    if len(splits) < FULL_FOLD_COUNT:
        raise LabContractError(f"Finalist did not produce {FULL_FOLD_COUNT} purged folds.")
    signal_frame = apply_signal_step(frame, dict(cfg["signals"]), asset="ETHUSD")
    signal_col = str(cfg["backtest"]["signal_col"])
    locked_positions = np.concatenate([np.asarray(split.test_idx, dtype=int) for split in splits[LOCKED_FOLD_START:FULL_FOLD_COUNT]])
    locked = signal_frame.iloc[locked_positions].copy()
    base_metrics, base_returns = _run_vector_stress(locked, cfg, signal_col=signal_col)
    comparators: dict[str, Any] = {}
    no_trade = locked.copy()
    no_trade[signal_col] = 0.0
    comparators["no_trade"], _ = _run_vector_stress(no_trade, cfg, signal_col=signal_col)
    passive = locked.copy()
    passive[signal_col] = 1.0
    comparators["buy_and_hold"], _ = _run_vector_stress(passive, cfg, signal_col=signal_col)
    trend = locked.copy()
    if "ema_trend_48_192" in trend.columns:
        trend[signal_col] = np.sign(pd.to_numeric(trend["ema_trend_48_192"], errors="coerce").fillna(0.0))
        comparators["causal_ema_trend"], _ = _run_vector_stress(trend, cfg, signal_col=signal_col)
    active = pd.to_numeric(locked[signal_col], errors="coerce").fillna(0.0).ne(0.0)
    random_stats: list[float] = []
    for seed in range(100):
        random_frame = locked.copy()
        signs = np.random.default_rng(seed).choice(np.array([-1.0, 1.0]), size=int(active.sum()))
        random_frame[signal_col] = 0.0
        random_frame.loc[active, signal_col] = signs
        random_metrics, _ = _run_vector_stress(random_frame, cfg, signal_col=signal_col)
        random_stats.append(float(random_metrics.get("net_pnl", 0.0)))
    comparators["random_sign_same_active_rate"] = {
        "seeds": 100, "net_pnl_mean": float(np.mean(random_stats)), "net_pnl_p05": float(np.quantile(random_stats, 0.05)), "net_pnl_p95": float(np.quantile(random_stats, 0.95)), "probability_net_pnl_positive": float((np.asarray(random_stats) > 0.0).mean()),
    }
    costs = {"x1": base_metrics}
    cost_returns: dict[str, pd.Series] = {"x1": base_returns}
    raw = load_trial_raw()
    spread_proxy = (pd.to_numeric(raw.get("spread_close"), errors="coerce") / pd.to_numeric(raw.get("close"), errors="coerce")).replace([np.inf, -np.inf], np.nan).dropna()
    quote_multiplier = max(1.0, float(spread_proxy.median() / (2.0 * float(cfg["risk"].get("cost_per_turnover", 0.0001))))) if not spread_proxy.empty else 15.0
    for multiplier in (2.0, 5.0, 10.0, quote_multiplier):
        key = "quote_proxy" if multiplier == quote_multiplier else f"x{int(multiplier)}"
        metrics, values = _run_vector_stress(locked, cfg, signal_col=signal_col, cost_multiplier=multiplier)
        costs[key] = metrics
        cost_returns[key] = values
    delays: dict[str, Any] = {}
    for delay in (1, 2):
        metrics, values = _run_vector_stress(locked, cfg, signal_col=signal_col, delay=delay)
        delays[f"delay_{delay}"] = metrics
    threshold: dict[str, Any] = {}
    for label, multiplier in (("minus_5pct", 0.95), ("plus_5pct", 1.05), ("minus_10pct", 0.90), ("plus_10pct", 1.10)):
        variant_cfg = _threshold_perturbation_config(cfg, multiplier)
        if variant_cfg is None:
            threshold[label] = {"status": "not_applicable"}
            continue
        varied = apply_signal_step(frame, dict(variant_cfg["signals"]), asset="ETHUSD").iloc[locked_positions].copy()
        metrics, _ = _run_vector_stress(varied, variant_cfg, signal_col=str(variant_cfg["backtest"]["signal_col"]))
        threshold[label] = metrics
    side_metrics: dict[str, Any] = {}
    for side in ("long_only", "short_only"):
        variant_cfg = deepcopy(cfg)
        if "mode" not in variant_cfg.get("signals", {}).get("params", {}):
            side_metrics[side] = {"status": "not_applicable"}
            continue
        variant_cfg["signals"]["params"]["mode"] = side
        varied = apply_signal_step(frame, dict(variant_cfg["signals"]), asset="ETHUSD").iloc[locked_positions].copy()
        metrics, _ = _run_vector_stress(varied, variant_cfg, signal_col=str(variant_cfg["backtest"]["signal_col"]))
        side_metrics[side] = metrics
    fold_metrics = _locked_fold_metrics(signal_frame, cfg, splits, signal_col)
    positive_folds = int((pd.DataFrame(fold_metrics).get("net_pnl", pd.Series(dtype=float)) > 0.0).sum())
    ftmo = compute_ftmo_style_metrics(net_returns=base_returns, max_daily_loss=0.05, max_total_loss=0.10)
    bootstrap = _daily_bootstrap(base_returns)
    psr = _probabilistic_sharpe_ratio(base_returns, periods_per_year=int(cfg["backtest"].get("periods_per_year", 17_520)))
    pass_stress = bool(
        base_metrics.get("net_pnl", 0.0) > 0.0
        and costs["x2"].get("net_pnl", 0.0) > 0.0
        and delays["delay_1"].get("net_pnl", 0.0) > 0.0
        and positive_folds >= 5
        and float(base_metrics.get("max_drawdown", -1.0)) >= -0.10
        and int(ftmo.get("daily_loss_breach_count", 1)) == 0
        and int(ftmo.get("max_total_loss_breach_count", 1)) == 0
        and costs["quote_proxy"].get("net_pnl", 0.0) > 0.0
    )
    return {
        "config": str(config_path.relative_to(PROJECT_ROOT)), "locked_fold_range": [LOCKED_FOLD_START, FULL_FOLD_COUNT - 1],
        "base": base_metrics, "comparators": comparators, "cost_sensitivity": costs, "delay_sensitivity": delays, "threshold_sensitivity": threshold, "side_sensitivity": side_metrics,
        "fold_metrics": fold_metrics, "positive_locked_folds": positive_folds, "ftmo_style": ftmo, "bootstrap_daily": bootstrap, "probabilistic_sharpe_ratio_vs_zero": psr,
        "quote_cost_multiplier_proxy": quote_multiplier, "stress_validated": pass_stress,
        "verdict": "stress_validated" if pass_stress else "rejected_locked_or_execution_stress",
    }


def run_locked_finalists(*, resume: bool = True) -> pd.DataFrame:
    """Open folds 10--16 for frozen finalists and execute all fixed stress checks."""
    manifest_path = REPORTS_DIR / "finalist_manifest.csv"
    if not manifest_path.exists():
        raise LabContractError("Generate finalists before running the locked continuation.")
    final_manifest = pd.read_csv(manifest_path)
    stress_dir = REPORTS_DIR / "stress_tests"
    stress_dir.mkdir(parents=True, exist_ok=True)
    runs = _load_run_index("locked")
    rows: list[dict[str, Any]] = []
    for _, final in final_manifest.iterrows():
        path = PROJECT_ROOT / str(final["yaml_path"])
        stress_path = stress_dir / f"{final['experiment_id']}.json"
        record, result = _run_config(path, phase="locked", resume=resume and stress_path.exists())
        runs[str(path.relative_to(PROJECT_ROOT))] = record
        _save_run_index("locked", runs)
        if record["status"] != "success":
            rows.append({"experiment_id": final["experiment_id"], "status": "failed", "stress_validated": False, "error": record.get("error", "")})
            continue
        if result is None:
            # A resume hit has no in-memory feature/prediction frame. Re-run through the
            # public runner because stress must use the frozen final config, not artifact guesses.
            result = run_experiment(path)
        stress = _stress_finalist(result, path)
        stress_path.write_text(json.dumps(stress, indent=2, default=_json_default), encoding="utf-8")
        if bool(stress["stress_validated"]):
            destination = LAB_ROOT / "08_stress_validated" / path.name
            shutil.copy2(path, destination)
        rows.append({"experiment_id": final["experiment_id"], "status": "success", "stress_validated": bool(stress["stress_validated"]), "locked_net_pnl": stress["base"].get("net_pnl"), "locked_max_drawdown": stress["base"].get("max_drawdown"), "positive_locked_folds": stress["positive_locked_folds"], "error": ""})
    table = pd.DataFrame(rows)
    table.to_csv(REPORTS_DIR / "locked_execution.csv", index=False)
    if not table.empty:
        final_manifest = final_manifest.drop(columns=[column for column in ("locked_status", "stress_validated") if column in final_manifest], errors="ignore").merge(table[["experiment_id", "status", "stress_validated"]], on="experiment_id", how="left")
        final_manifest = final_manifest.rename(columns={"status": "locked_status"})
        final_manifest.to_csv(manifest_path, index=False)
    if not any((LAB_ROOT / "08_stress_validated").glob("*.yaml")):
        (LAB_ROOT / "08_stress_validated/README.md").write_text("# Stress-validated configurations\n\nNo frozen finalist met the locked-fold, daily-loss, drawdown, delay, and quote-cost proxy gates.\n", encoding="utf-8")
    return table


def _safe_read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _yaml_counts() -> dict[str, int]:
    return {
        directory: len(list((LAB_ROOT / directory).glob("*.yaml")))
        for directory in ("00_baseline", "01_target_lab", "02_feature_ablation", "03_feature_additions", "04_normalization_lab", "05_signal_lab", "06_model_lab", "07_combined_finalists", "08_stress_validated")
    }


def write_final_alpha_report() -> Path:
    """Assemble the evidence-first final lab report from persisted, reproducible outputs."""
    baseline = _read_json(REPORTS_DIR / "baseline_diagnostics.json") if (REPORTS_DIR / "baseline_diagnostics.json").exists() else {}
    data_audit = _read_json(REPORTS_DIR / "data_audit.json") if (REPORTS_DIR / "data_audit.json").exists() else {}
    target = _read_json(REPORTS_DIR / "target_diagnostics.json") if (REPORTS_DIR / "target_diagnostics.json").exists() else {}
    leaderboard = _safe_read_csv(REPORTS_DIR / "experiment_leaderboard.csv")
    final_manifest = _safe_read_csv(REPORTS_DIR / "finalist_manifest.csv")
    locked = _safe_read_csv(REPORTS_DIR / "locked_execution.csv")
    stress_files = sorted((REPORTS_DIR / "stress_tests").glob("*.json")) if (REPORTS_DIR / "stress_tests").exists() else []
    stress = [_read_json(path) for path in stress_files]
    validated = [item for item in stress if bool(item.get("stress_validated"))]
    counts = _yaml_counts()
    screening_success = leaderboard.loc[leaderboard.get("run_status", pd.Series(dtype=str)).eq("success")] if not leaderboard.empty else pd.DataFrame()
    rejected = leaderboard.loc[~leaderboard.get("screening_status", pd.Series(dtype=str)).eq("screening_winner")] if not leaderboard.empty else pd.DataFrame()
    top10 = screening_success.head(10) if not screening_success.empty else pd.DataFrame()
    final_verdict = (
        "stress-validated configurations exist"
        if validated
        else "no configuration is cleared for paper trading under this lab's stated execution/FTMO gates"
    )

    report: list[str] = [
        "# Final Alpha Research Report — ETHUSD Trial 0041 Lab",
        "",
        "## Executive conclusion",
        "",
        "This lab treats Trial 0041 as a historical baseline, not as an already-deployed alpha. Screening used only the source 10-fold OOS era (folds 0–9, ending 2024-09-17). Finalist configurations were frozen before the unused 2024-09–2026-06 continuation (folds 10–16) was opened. A configuration is called **stress validated** only when it passes the locked-fold, 2×-cost, delay, drawdown, daily-loss, and quote-cost-proxy gates. All other positive screening results remain **promising but not validated** or **rejected**.",
        "",
        f"- First-stage YAMLs: `{sum(counts[directory] for directory in ('01_target_lab', '02_feature_ablation', '03_feature_additions', '04_normalization_lab', '05_signal_lab', '06_model_lab'))}`.",
        f"- Frozen combined finalists: `{counts['07_combined_finalists']}`; stress-validated YAMLs: `{counts['08_stress_validated']}`.",
        f"- Screening runs recorded: `{len(leaderboard)}`; locked finalist runs recorded: `{len(locked)}`.",
        f"- Final verdict: `{final_verdict}`.",
        "",
        "## Data and provenance",
        "",
        f"- Source: `{RAW_DATA_RELATIVE}`, `{data_audit.get('rows', 'n/a')}` rows, `{data_audit.get('timestamp_start', 'n/a')}` to `{data_audit.get('timestamp_end', 'n/a')}`, SHA-256 `{data_audit.get('file_sha256', 'n/a')}`.",
        f"- Integrity: duplicates `{data_audit.get('duplicates', 'n/a')}`, OHLC range violations low>high `{data_audit.get('low_gt_high', 'n/a')}`, missing 30-minute bars `{data_audit.get('gaps', {}).get('missing_bars', 'n/a')}` across `{data_audit.get('gaps', {}).get('gap_count', 'n/a')}` gaps.",
        f"- Exact immutable source YAML: `{SOURCE_CONFIG.relative_to(PROJECT_ROOT)}` (SHA-256 `{_config_sha256(SOURCE_CONFIG)}`). Its exact lab copy is `00_baseline/ethusd_30m_trial_0041_baseline.yaml`; the separate local replay changes only `/workspace` paths and snapshot persistence.",
        "",
        "## Baseline assessment",
        "",
    ]
    primary = dict(baseline.get("primary_summary", {}) or {})
    if primary:
        baseline_table = pd.DataFrame([primary]).T.reset_index().rename(columns={"index": "metric", 0: "value"})
        report.extend([baseline_table.to_markdown(index=False), ""])
    trade = dict(baseline.get("trade_ledger", {}) or {})
    quote = dict(baseline.get("quote_cost_proxy", {}) or {})
    ftmo = dict(baseline.get("ftmo_style", {}) or {})
    report.extend(
        [
            f"The ledger contains `{trade.get('completed_round_trips', 'n/a')}` completed round trips (long `{trade.get('long_trades', 'n/a')}`, short `{trade.get('short_trades', 'n/a')}`). The vectorized historical cost is `{quote.get('modeled_round_trip_cost', float('nan')):.4%}` per round trip versus a median raw full-spread proxy of `{quote.get('median_full_spread_relative', float('nan')):.4%}` (`{quote.get('multiple_of_modeled_cost', float('nan')):.1f}×`).",
            f"The baseline has `{ftmo.get('daily_loss_breach_count', 'n/a')}` daily-loss breaches at 5% and `{ftmo.get('max_total_loss_breach_count', 'n/a')}` total-loss breaches at 10%; its historical result is therefore not FTMO-ready as-is.",
            "The framework's reported Sharpe is CAGR/annualized-volatility, not conventional arithmetic Sharpe. All lab reports label this distinction explicitly.",
            "",
            "## Target and feature evidence",
            "",
            f"The baseline h24 target is 24 30-minute bars (nominally 12 hours), not 24 clock-hours. It has a clip-bound frequency of `{target.get('clip_bound_frequency', float('nan')):.2%}` and `{target.get('gap_spanning_target_rows', 'n/a')}` labels spanning a gap longer than its nominal horizon. Target details are in `target_diagnostics.md` and `target_horizon_diagnostics.csv`.",
            "Feature selection was never made from aggregate gain alone: `feature_diagnostics.csv` contains missingness, variance, unique ratio, Pearson/Spearman target association, mutual information, fold-local gain/split/permutation importance, IC stability, PSI, KS, and cluster membership. SHAP was not installed and is explicitly reported as unavailable.",
            "",
            "## Screening leaderboard (folds 0–9 only)",
            "",
        ]
    )
    if not top10.empty:
        columns = [column for column in ("experiment_id", "family", "robust_score", "positive_folds", "median_fold_net_pnl", "cost2_net_pnl", "max_drawdown", "screening_status") if column in top10]
        report.extend([top10[columns].to_markdown(index=False), ""])
    else:
        report.extend(["No completed screening leaderboard is available yet.", ""])
    report.extend([
        "## Rejected or non-validated ideas",
        "",
        "The lab retains failures rather than hiding them. A screening rejection means it missed at least one deterministic gate (fold support, lower-quartile fold PnL, trade density, or 2× modeled cost). A locked/stress rejection is stronger: it means a frozen finalist failed later-fold, delay, drawdown, daily-loss, or quote-cost-proxy evidence.",
        "",
    ])
    if not rejected.empty:
        reject_columns = [column for column in ("experiment_id", "family", "screening_status", "positive_folds", "q25_fold_net_pnl", "cost2_net_pnl", "error") if column in rejected]
        report.extend([rejected.head(30)[reject_columns].to_markdown(index=False), ""])
    else:
        report.extend(["No screening failures have been recorded yet.", ""])
    report.extend(["## Frozen finalists and locked continuation", ""])
    if not final_manifest.empty:
        report.extend([final_manifest.to_markdown(index=False), ""])
    if stress:
        stress_rows = []
        for item in stress:
            base = dict(item.get("base", {}) or {})
            cost2 = dict(item.get("cost_sensitivity", {}).get("x2", {}) or {})
            delay1 = dict(item.get("delay_sensitivity", {}).get("delay_1", {}) or {})
            ftmo_row = dict(item.get("ftmo_style", {}) or {})
            stress_rows.append({
                "config": item.get("config"), "verdict": item.get("verdict"), "locked_net_pnl": base.get("net_pnl"), "locked_mdd": base.get("max_drawdown"),
                "cost2_net_pnl": cost2.get("net_pnl"), "delay1_net_pnl": delay1.get("net_pnl"), "positive_locked_folds": item.get("positive_locked_folds"),
                "daily_loss_breaches": ftmo_row.get("daily_loss_breach_count"), "quote_proxy_multiplier": item.get("quote_cost_multiplier_proxy"),
            })
        report.extend([pd.DataFrame(stress_rows).to_markdown(index=False), ""])
    else:
        report.extend(["Locked-fold stress results have not been run yet.", ""])
    report.extend([
        "## Final recommendation",
        "",
        "- **Best overall / risk-adjusted / low-drawdown / high-return:** only assign these labels among stress-validated finalists; otherwise no deployment ranking is justified.",
        "- **Long-only / short-only:** reported only as locked stress slices, never selected from the historical ledger alone.",
        "- **Paper trading:** requires a frozen config to pass the quote-cost proxy, one/two-bar delay, daily-loss, total-drawdown, and later-fold gates. The current baseline itself does not meet those constraints.",
        "- **Execution limitation:** the vectorized engine is a one-bar-lagged close-return simulator. A broker/FTMO-facing next-open/bid-ask implementation remains a separate validation requirement.",
        "",
        "## Reproduction commands",
        "",
        "```bash",
        "PYTHONHASHSEED=7 python scripts/run_trial0041_alpha_lab.py generate",
        "PYTHONHASHSEED=7 python scripts/run_trial0041_alpha_lab.py validate",
        "PYTHONHASHSEED=7 python scripts/run_trial0041_alpha_lab.py diagnostics",
        "PYTHONHASHSEED=7 python scripts/run_trial0041_alpha_lab.py screen",
        "PYTHONHASHSEED=7 python scripts/run_trial0041_alpha_lab.py finalists",
        "PYTHONHASHSEED=7 python scripts/run_trial0041_alpha_lab.py locked",
        "PYTHONHASHSEED=7 python scripts/run_trial0041_alpha_lab.py report",
        "```",
        "",
        "The runner command for an individual YAML is `PYTHONHASHSEED=7 python -m src.experiments.runner <yaml-path>`.",
    ])
    path = REPORTS_DIR / "final_alpha_research_report.md"
    path.write_text("\n".join(report) + "\n", encoding="utf-8")
    return path


__all__ = [
    "ARTIFACT_DIR",
    "ExperimentSpec",
    "FEATURE_DENYLIST_TOKENS",
    "FULL_FOLD_COUNT",
    "LAB_ROOT",
    "LabContractError",
    "LOCKED_FOLD_COUNT",
    "LOCKED_FOLD_START",
    "PROJECT_ROOT",
    "RAW_DATA_PATH",
    "REPORTS_DIR",
    "SCREENING_FOLD_COUNT",
    "SOURCE_CONFIG",
    "audit_raw_data",
    "build_screening_leaderboard",
    "first_stage_specs",
    "generate_finalists",
    "generate_lab_configs",
    "list_lab_yaml_paths",
    "run_diagnostics",
    "run_locked_finalists",
    "run_screening",
    "validate_lab_configs",
    "write_baseline_diagnostics",
    "write_feature_diagnostics",
    "write_final_alpha_report",
    "write_target_diagnostics",
]
