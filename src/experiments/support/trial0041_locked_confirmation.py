from __future__ import annotations

"""Frozen, locked-only confirmation for ETHUSD Trial 0041.

This research-only support layer deliberately reuses the Trial 0041 lab's
artifact provenance, purge-aware split construction, feature helpers, and
vectorized robustness mechanics. It never ranks or tunes on folds 0--9 or
reports them as confirmation performance.
"""

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import subprocess
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd
import yaml

from src.backtesting.engine import run_backtest
from src.evaluation.metrics import compute_backtest_metrics
from src.evaluation.model_diagnostics import (
    prediction_quantile_table,
    prediction_realized_metrics,
    quantile_monotonicity,
)
from src.evaluation.robustness import cost_multiplier_stress
from src.experiments.orchestration.feature_stage import apply_signal_step
from src.experiments.runner import run_experiment
from src.experiments.support.trial0041_alpha_lab import (
    ARTIFACT_DIR,
    FULL_FOLD_COUNT,
    LAB_ROOT,
    LOCKED_FOLD_START,
    PROJECT_ROOT,
    RAW_DATA_PATH,
    RAW_DATA_RELATIVE,
    SOURCE_CONFIG,
    LabContractError,
    _append_feature_step,
    _assert_feature_denylist,
    _extend_step_transforms,
    _locked_splits_for_config,
    _single_asset_frame,
)
from src.experiments.support.trial0041_alpha_lab import load_trial_raw
from src.utils.config import load_experiment_config
from src.utils.run_metadata import compute_dataframe_fingerprint, file_sha256


CONFIG_DIR = LAB_ROOT / "07_locked_confirmation"
REPORTS_DIR = LAB_ROOT / "reports/locked_confirmation"
MANIFEST_PATH = PROJECT_ROOT / "reports/locked_confirmation_manifest.json"
HOST_GIT_PROVENANCE_PATH = PROJECT_ROOT / "reports/locked_confirmation_git_provenance.json"
LOGS_RELATIVE = Path("logs/experiments/foundation_alpha/trial0041_locked_confirmation")

VWAP = "vwap48"
RETURN_OVER_VOL = "return_over_vol48"
ROBUST_Z = "robust_z_return192"
ADDED_COLUMNS = {
    VWAP: "close_over_vwap_48",
    RETURN_OVER_VOL: "close_ret_over_vol_48",
    ROBUST_Z: "close_ret_robust_z_192",
}
ROBUSTNESS_SCENARIOS = (
    ("cost", "cost_x1", 1.0),
    ("cost", "cost_x3", 3.0),
    ("cost", "cost_x5", 5.0),
    ("entry_delay", "delay_1_bar", 1),
    ("entry_delay", "delay_2_bars", 2),
)
SCREENING_CONFIG_USED = {
    VWAP: PROJECT_ROOT / "logs/experiments/foundation_alpha/trial0041_alpha_lab/ethusd_30m_trial0041_featadd_vwap_distance_v1_20260712_215748_876641_131a74bd/config_used.yaml",
    RETURN_OVER_VOL: PROJECT_ROOT / "logs/experiments/foundation_alpha/trial0041_alpha_lab/ethusd_30m_trial0041_norm_return_over_vol48_v1_20260712_222201_160845_132a3fe3/config_used.yaml",
    ROBUST_Z: PROJECT_ROOT / "logs/experiments/foundation_alpha/trial0041_alpha_lab/ethusd_30m_trial0041_norm_robust_z_return192_v1_20260712_222538_003434_399e4ba8/config_used.yaml",
}
TRACKED_SCREENING_CONFIGS = {
    VWAP: LAB_ROOT / "03_feature_additions/ethusd_30m_trial0041_featadd_vwap_distance_v1.yaml",
    RETURN_OVER_VOL: LAB_ROOT / "04_normalization_lab/ethusd_30m_trial0041_norm_return_over_vol48_v1.yaml",
    ROBUST_Z: LAB_ROOT / "04_normalization_lab/ethusd_30m_trial0041_norm_robust_z_return192_v1.yaml",
}
RECORDED_BASELINE_REPLAY = PROJECT_ROOT / "logs/experiments/foundation_alpha/trial0041_alpha_lab/ethusd_30m_trial0041_baseline_local_replay_20260712_211814_041588_1d8aa76c/config_used.yaml"


@dataclass(frozen=True)
class ConfirmationSpec:
    experiment_id: str
    additions: tuple[str, ...]
    parent_experiment: str
    hypothesis: str


def confirmation_specs() -> tuple[ConfirmationSpec, ...]:
    baseline = "immutable_trial0041_artifact"
    return (
        ConfirmationSpec("ethusd_30m_trial0041_confirm_baseline_v1", (), baseline, "Replay the exact Trial 0041 artifact semantics on untouched folds 10-16."),
        ConfirmationSpec("ethusd_30m_trial0041_confirm_vwap48_v1", (VWAP,), f"{baseline};ethusd_30m_trial0041_featadd_vwap_distance_v1", "Confirm the preselected causal 48-bar VWAP-distance feature without retuning."),
        ConfirmationSpec("ethusd_30m_trial0041_confirm_return_over_vol48_v1", (RETURN_OVER_VOL,), f"{baseline};ethusd_30m_trial0041_norm_return_over_vol48_v1", "Confirm the preselected close return over trailing 48-bar volatility feature."),
        ConfirmationSpec("ethusd_30m_trial0041_confirm_robust_z_return192_v1", (ROBUST_Z,), f"{baseline};ethusd_30m_trial0041_norm_robust_z_return192_v1", "Confirm the preselected shifted trailing robust-z return feature."),
        ConfirmationSpec("ethusd_30m_trial0041_confirm_vwap48_return_over_vol48_v1", (VWAP, RETURN_OVER_VOL), f"{baseline};ethusd_30m_trial0041_featadd_vwap_distance_v1;ethusd_30m_trial0041_norm_return_over_vol48_v1", "Confirm only the frozen union of VWAP distance and return-over-volatility features."),
        ConfirmationSpec("ethusd_30m_trial0041_confirm_vwap48_robust_z_return192_v1", (VWAP, ROBUST_Z), f"{baseline};ethusd_30m_trial0041_featadd_vwap_distance_v1;ethusd_30m_trial0041_norm_robust_z_return192_v1", "Confirm only the frozen union of VWAP distance and robust-z return features."),
        ConfirmationSpec("ethusd_30m_trial0041_confirm_vwap48_return_over_vol48_robust_z_return192_v1", (VWAP, RETURN_OVER_VOL, ROBUST_Z), f"{baseline};ethusd_30m_trial0041_featadd_vwap_distance_v1;ethusd_30m_trial0041_norm_return_over_vol48_v1;ethusd_30m_trial0041_norm_robust_z_return192_v1", "Confirm only the frozen union of all three preselected causal feature additions."),
    )


def config_paths(*, config_dir: Path = CONFIG_DIR) -> list[Path]:
    return [config_dir / f"{spec.experiment_id}.yaml" for spec in confirmation_specs()]


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise LabContractError(f"Expected YAML mapping: {path}")
    return payload


def _frozen_config_path() -> Path:
    primary = ARTIFACT_DIR / "config_used.yaml"
    if primary.exists():
        return primary
    if RECORDED_BASELINE_REPLAY.exists():
        return RECORDED_BASELINE_REPLAY
    raise LabContractError(f"Missing immutable baseline config and recorded replay fallback: {primary}")


def _artifact_config() -> dict[str, Any]:
    path = _frozen_config_path()
    cfg = _read_yaml(path)
    cfg.pop("config_path", None)
    return cfg


def _vwap_step() -> dict[str, Any]:
    return {
        "step": "vwap",
        "params": {"high_col": "high", "low_col": "low", "close_col": "close", "volume_col": "volume", "windows": [48]},
        "transforms": {"ratio": {"enabled": True, "items": [{"numerator_col": "close", "denominator_col": "vwap_48", "output_col": "close_over_vwap_48", "subtract": 1.0}]}},
        "outputs": {},
        "enabled": True,
    }


def build_confirmation_config(spec: ConfirmationSpec) -> dict[str, Any]:
    """Build one config from the exact artifact, changing only permitted execution details."""
    cfg = _artifact_config()
    storage = cfg["data"]["storage"]
    storage.update({"load_path": str(RAW_DATA_RELATIVE), "raw_dir": "data/raw", "processed_dir": "data/processed", "save_processed": False})
    cfg["logging"].update({"output_dir": str(LOGS_RELATIVE), "run_name": spec.experiment_id, "save_predictions": True})
    cfg["model"]["split"]["max_folds"] = FULL_FOLD_COUNT
    cfg.setdefault("evaluation", {})["strict_oos_only"] = True
    grid = cfg.setdefault("diagnostics", {}).setdefault("threshold_grid", {})
    grid.update({"enabled": False, "symmetric_thresholds": [], "asymmetric_thresholds": []})
    for addition in spec.additions:
        if addition == VWAP:
            cfg = _append_feature_step(cfg, _vwap_step(), (ADDED_COLUMNS[addition],))
        elif addition == RETURN_OVER_VOL:
            cfg = _extend_step_transforms(cfg, step_name="volatility", normalizations={"volatility_scaled_return": {"params": {"return_col": "close_ret", "volatility_col": "vol_rolling_48", "output_col": ADDED_COLUMNS[addition]}}}, columns=(ADDED_COLUMNS[addition],))
        elif addition == ROBUST_Z:
            cfg = _extend_step_transforms(cfg, step_name="volatility", normalizations={"robust_zscore": {"params": {"source_col": "close_ret", "window": 192, "output_col": ADDED_COLUMNS[addition], "shift_stats": True}}}, columns=(ADDED_COLUMNS[addition],))
        else:  # pragma: no cover
            raise LabContractError(f"Unknown frozen feature addition: {addition}")
    cfg["research_metadata"] = {
        "lab": "ethusd_30m_trial_0041_alpha_lab", "family": "locked_confirmation", "phase": "locked",
        "selection_era": "folds_0_to_9", "evaluation_era": "folds_10_to_16_locked",
        "thresholds_frozen": True, "model_params_frozen": True, "feature_selection_frozen": True,
        "no_holdout_tuning": True, "parent_experiment": spec.parent_experiment, "hypothesis": spec.hypothesis,
        "baseline_source": str(SOURCE_CONFIG.relative_to(PROJECT_ROOT)),
        "baseline_artifact": str(ARTIFACT_DIR.relative_to(PROJECT_ROOT)),
        "confirmation_runtime_changes": [
            "max_folds=17 only constructs the locked expanding history.",
            "Storage/logging paths are local Docker normalization.",
            "Threshold-grid diagnostics are disabled; no threshold search is executed.",
        ],
        "leakage_note": "Folds 10–16 are evaluated only after the complete seven-config confirmation set has been frozen and hashed.",
    }
    cols = list(cfg["model"]["feature_cols"])
    if len(cols) != len(set(cols)):
        raise LabContractError(f"Duplicate feature columns in {spec.experiment_id}.")
    _assert_feature_denylist(cfg)
    if cfg["backtest"].get("allow_short") != _artifact_config()["backtest"].get("allow_short"):
        raise LabContractError("Frozen backtest.allow_short changed.")
    return cfg


def _render(spec: ConfirmationSpec, cfg: Mapping[str, Any]) -> str:
    return "\n".join([
        "# ETHUSD Trial 0041 locked confirmation; generated deterministically.",
        "# Only folds 10-16 are scored. Folds 0-9 build expanding history only.",
        f"# Frozen parent: {spec.parent_experiment}", "",
    ]) + yaml.safe_dump(dict(cfg), sort_keys=False, allow_unicode=True)


def _diff(left: Any, right: Any, prefix: str = "") -> list[str]:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        out: list[str] = []
        for key in sorted(set(left) | set(right), key=str):
            field = f"{prefix}.{key}" if prefix else str(key)
            if key not in left or key not in right:
                out.append(field)
            else:
                out.extend(_diff(left[key], right[key], field))
        return out
    return [] if left == right else [prefix or "<root>"]


def _validate_payload(spec: ConfirmationSpec, actual: Mapping[str, Any]) -> None:
    diffs = _diff(build_confirmation_config(spec), actual)
    if diffs:
        raise LabContractError(f"Frozen config divergence for {spec.experiment_id}: {', '.join(diffs[:12])}")


def validate_configs(*, config_dir: Path = CONFIG_DIR) -> pd.DataFrame:
    expected = config_paths(config_dir=config_dir)
    found = sorted(config_dir.glob("*.yaml")) if config_dir.exists() else []
    if {path.name for path in found} != {path.name for path in expected}:
        raise LabContractError("Locked confirmation must contain exactly seven declared YAMLs.")
    rows = []
    for spec, path in zip(confirmation_specs(), expected, strict=True):
        try:
            _validate_payload(spec, _read_yaml(path))
            _assert_feature_denylist(load_experiment_config(path))
            rows.append({"experiment_id": spec.experiment_id, "yaml_path": str(path), "status": "valid", "error": ""})
        except Exception as exc:
            rows.append({"experiment_id": spec.experiment_id, "yaml_path": str(path), "status": "invalid", "error": f"{type(exc).__name__}: {exc}"})
    return pd.DataFrame(rows)


def generate_configs(*, config_dir: Path = CONFIG_DIR, manifest_path: Path = MANIFEST_PATH) -> pd.DataFrame:
    desired = [(spec, config_dir / f"{spec.experiment_id}.yaml", build_confirmation_config(spec)) for spec in confirmation_specs()]
    if manifest_path.exists():
        manifest = _read_json(manifest_path)
        frozen = {str(item["experiment_id"]): str(item["config_sha256"]) for item in manifest.get("configs", [])}
        for spec, path, cfg in desired:
            expected_hash = sha256(_render(spec, cfg).encode("utf-8")).hexdigest()
            if not path.exists() or _sha(path) != expected_hash or frozen.get(spec.experiment_id) != expected_hash:
                raise LabContractError("Confirmation is frozen; refusing config mutation after manifest creation.")
    else:
        config_dir.mkdir(parents=True, exist_ok=True)
        unexpected = {path.name for path in config_dir.glob("*.yaml")} - {path.name for _, path, _ in desired}
        if unexpected:
            raise LabContractError(f"Unexpected YAMLs in confirmation directory: {sorted(unexpected)}")
        for spec, path, cfg in desired:
            path.write_text(_render(spec, cfg), encoding="utf-8")
    validation = validate_configs(config_dir=config_dir)
    if (validation["status"] != "valid").any():
        raise LabContractError("Generated confirmation configs failed validation.")
    return validation


def _value(cfg: Mapping[str, Any], dotted: str) -> Any:
    value: Any = cfg
    for part in dotted.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return "<missing>"
        value = value[part]
    return value


def _audit() -> dict[str, Any]:
    artifact = _artifact_config()
    fields = ("model.kind", "model.params", "model.target", "model.split", "model.outputs", "signals", "backtest", "risk", "validation", "runtime")
    source = _read_yaml(SOURCE_CONFIG)
    selected, tracked = {}, {}
    for key, path in SCREENING_CONFIG_USED.items():
        used = _read_yaml(path)
        used.pop("config_path", None)
        selected[key] = {
            "config_used": str(path.relative_to(PROJECT_ROOT)),
            "unexpected_frozen_semantic_differences": [field for field in fields if _value(used, field) != _value(artifact, field)],
            "expected_added_feature": ADDED_COLUMNS[key],
            "recorded_allow_short": _value(used, "backtest.allow_short"),
        }
        current = _read_yaml(TRACKED_SCREENING_CONFIGS[key])
        tracked[key] = {
            "recorded_allow_short": _value(used, "backtest.allow_short"),
            "tracked_allow_short": _value(current, "backtest.allow_short"),
            "allow_short_mismatch": _value(used, "backtest.allow_short") != _value(current, "backtest.allow_short"),
        }
    return {
        "requested_immutable_artifact": str(ARTIFACT_DIR.relative_to(PROJECT_ROOT)),
        "semantic_source_of_truth": str(_frozen_config_path().relative_to(PROJECT_ROOT)),
        "immutable_artifact_config_available": bool((ARTIFACT_DIR / "config_used.yaml").exists()),
        "current_baseline": str(SOURCE_CONFIG.relative_to(PROJECT_ROOT)),
        "current_baseline_vs_artifact_unexpected_differences": [field for field in fields + ("features",) if _value(source, field) != _value(artifact, field)],
        "selected_screening_runs": selected, "tracked_screening_vs_recorded_config_used": tracked,
        "resolution": "All confirmation configs derive from the immutable artifact config when present, otherwise the exact recorded baseline replay config_used fallback; backtest.allow_short remains false.",
    }


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise LabContractError(f"Expected JSON object: {path}")
    return payload


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None
    if isinstance(value, (Path, pd.Timestamp, datetime)):
        return str(value) if isinstance(value, Path) else value.isoformat()
    return value


def _git_provenance() -> dict[str, Any]:
    """Read git provenance, using a host-generated handoff inside the app image.

    The execution image deliberately contains only the research runtime, not the
    git executable.  The handoff lets the manifest still record the actual host
    repository state that launched the Docker run.
    """
    try:
        def text(*args: str) -> str:
            result = subprocess.run(args, cwd=PROJECT_ROOT, check=False, capture_output=True, text=True)
            return result.stdout.strip() if result.returncode == 0 else ""

        diff = subprocess.run(("git", "diff", "HEAD", "--binary"), cwd=PROJECT_ROOT, check=False, capture_output=True).stdout
        return {
            "git_commit": text("git", "rev-parse", "HEAD"),
            "git_status_porcelain": text("git", "status", "--short").splitlines(),
            "diff_sha256": sha256(diff).hexdigest(),
        }
    except FileNotFoundError as exc:
        if not HOST_GIT_PROVENANCE_PATH.exists():
            raise LabContractError(
                "git is unavailable in this runtime; run `python scripts/run_trial0041_locked_confirmation.py provenance` on the host before freezing."
            ) from exc
        provenance = _read_json(HOST_GIT_PROVENANCE_PATH)
        required = {"git_commit", "git_status_porcelain", "diff_sha256"}
        if not required.issubset(provenance):
            raise LabContractError(f"Host git provenance is incomplete: {HOST_GIT_PROVENANCE_PATH}")
        return provenance


def write_host_git_provenance(path: Path = HOST_GIT_PROVENANCE_PATH) -> Path:
    """Capture host git state for a subsequent Docker-only locked execution."""
    provenance = _git_provenance()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe({**provenance, "captured_at": datetime.now(timezone.utc).isoformat()}), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _dataset_fingerprint() -> dict[str, Any]:
    frame = load_trial_raw()
    return {"path": str(RAW_DATA_RELATIVE), "file_sha256": file_sha256(RAW_DATA_PATH), "dataframe_fingerprint": compute_dataframe_fingerprint(frame), "rows": int(len(frame)), "timestamp_start": frame.index.min().isoformat(), "timestamp_end": frame.index.max().isoformat()}


def create_manifest(*, config_dir: Path = CONFIG_DIR, manifest_path: Path = MANIFEST_PATH, reports_dir: Path = REPORTS_DIR, dataset_fingerprint: Mapping[str, Any] | None = None, git_provenance: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Freeze config/data/provenance before a locked result is read."""
    if manifest_path.exists():
        return verify_manifest(config_dir=config_dir, manifest_path=manifest_path)
    validation = validate_configs(config_dir=config_dir)
    if (validation["status"] != "valid").any():
        raise LabContractError("Cannot freeze invalid confirmation configs.")
    reports_dir.mkdir(parents=True, exist_ok=True)
    audit_path = reports_dir / "locked_confirmation_baseline_audit.json"
    audit_path.write_text(json.dumps(_json_safe(_audit()), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    configs = []
    for spec, path in zip(confirmation_specs(), config_paths(config_dir=config_dir), strict=True):
        configs.append({"experiment_id": spec.experiment_id, "config_path": str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path), "config_sha256": _sha(path)})
    payload = {
        "manifest_version": 1, "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "locked_fold_ids": list(range(LOCKED_FOLD_START, FULL_FOLD_COUNT)), "configs": configs,
        "dataset": dict(dataset_fingerprint) if dataset_fingerprint is not None else _dataset_fingerprint(),
        "baseline": {"source_config": str(SOURCE_CONFIG.relative_to(PROJECT_ROOT)), "source_config_sha256": _sha(SOURCE_CONFIG), "artifact_dir": str(ARTIFACT_DIR.relative_to(PROJECT_ROOT)), "artifact_config_available": bool((ARTIFACT_DIR / "config_used.yaml").exists()), "resolved_semantic_config": str(_frozen_config_path().relative_to(PROJECT_ROOT)), "artifact_config_used_sha256": _sha(_frozen_config_path()), "selected_screening_config_used": {key: str(path.relative_to(PROJECT_ROOT)) for key, path in SCREENING_CONFIG_USED.items()}},
        "git": dict(git_provenance) if git_provenance is not None else _git_provenance(), "audit_path": str(audit_path),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return payload


def verify_manifest(*, config_dir: Path = CONFIG_DIR, manifest_path: Path = MANIFEST_PATH) -> dict[str, Any]:
    if not manifest_path.exists():
        raise LabContractError(f"Manifest must exist before locked execution: {manifest_path}")
    manifest = _read_json(manifest_path)
    expected = {spec.experiment_id for spec in confirmation_specs()}
    entries = {str(item.get("experiment_id")): item for item in manifest.get("configs", [])}
    if set(entries) != expected or manifest.get("locked_fold_ids") != list(range(LOCKED_FOLD_START, FULL_FOLD_COUNT)):
        raise LabContractError("Manifest does not describe exactly seven configs and folds 10-16.")
    for spec, path in zip(confirmation_specs(), config_paths(config_dir=config_dir), strict=True):
        if not path.exists() or _sha(path) != str(entries[spec.experiment_id].get("config_sha256")):
            raise LabContractError(f"Frozen config hash mismatch: {spec.experiment_id}")
    return manifest


def locked_fold_indexes(splits: list[Any]) -> np.ndarray:
    expected = list(range(FULL_FOLD_COUNT))
    actual = [int(split.fold) for split in splits]
    if actual != expected:
        raise LabContractError(f"Expected fold IDs {expected}; received {actual}.")
    positions = np.concatenate([np.asarray(split.test_idx, dtype=int) for split in splits[LOCKED_FOLD_START:FULL_FOLD_COUNT]])
    if len(positions) == 0 or len(np.unique(positions)) != len(positions):
        raise LabContractError("Locked folds are empty or overlap.")
    return positions


def assert_locked_oos_frame(frame: pd.DataFrame, *, splits: list[Any], oos_col: str, prediction_col: str) -> np.ndarray:
    """Fail closed unless every evaluated prediction is strictly OOS and fold-complete."""
    if oos_col not in frame.columns or prediction_col not in frame.columns:
        raise LabContractError(f"OOS/prediction columns missing: {oos_col}, {prediction_col}")
    expected_all = np.concatenate([np.asarray(split.test_idx, dtype=int) for split in splits])
    marker = frame[oos_col].fillna(False).astype(bool).to_numpy()
    if not np.array_equal(np.flatnonzero(marker), expected_all):
        raise LabContractError("OOS marker does not equal the exact 17-fold test schedule.")
    prediction = pd.to_numeric(frame[prediction_col], errors="coerce")
    if bool((prediction.notna() & ~pd.Series(marker, index=frame.index)).any()):
        raise LabContractError("Prediction without OOS marker detected.")
    locked = locked_fold_indexes(splits)
    if not bool(marker[locked].all()):
        raise LabContractError("A locked row is missing its OOS marker.")
    return locked


def _backtest(frame: pd.DataFrame, cfg: Mapping[str, Any], signal_col: str):
    risk, backtest = dict(cfg["risk"]), dict(cfg["backtest"])
    guard = dict(risk.get("dd_guard", {}) or {})
    return run_backtest(
        frame, signal_col=signal_col, returns_col=str(backtest["returns_col"]),
        returns_type=str(backtest.get("returns_type", "simple")),
        missing_return_policy=str(backtest.get("missing_return_policy", "raise_if_exposed")),
        cost_per_unit_turnover=float(risk.get("cost_per_turnover", 0.0)),
        slippage_per_unit_turnover=float(risk.get("slippage_per_turnover", 0.0)),
        target_vol=risk.get("target_vol"), vol_col=backtest.get("vol_col") or risk.get("vol_col"),
        max_leverage=float(risk.get("max_leverage", 1.0)), dd_guard=bool(guard.get("enabled", False)),
        max_drawdown=float(guard.get("max_drawdown", 0.2)), cooloff_bars=int(guard.get("cooloff_bars", 20)),
        rearm_drawdown=guard.get("rearm_drawdown"), periods_per_year=int(backtest.get("periods_per_year", 17_520)),
        min_holding_bars=int(backtest.get("min_holding_bars", 0)),
    )


def _metrics(result: Any, index: pd.Index, periods_per_year: int) -> dict[str, float]:
    return compute_backtest_metrics(
        net_returns=result.returns.reindex(index), turnover=result.turnover.reindex(index),
        costs=result.costs.reindex(index), gross_returns=result.gross_returns.reindex(index),
        periods_per_year=periods_per_year,
    )


def _entry_mask(positions: pd.Series) -> pd.Series:
    current = positions.astype(float).fillna(0.0)
    prior = current.shift(1).fillna(0.0)
    return current.ne(0.0) & (prior.eq(0.0) | np.sign(current).ne(np.sign(prior)))


def _prediction_quality(frame: pd.DataFrame, cfg: Mapping[str, Any], index: pd.Index) -> dict[str, Any]:
    model, target = dict(cfg["model"]), dict(cfg["model"]["target"])
    pred_col = str(model.get("pred_ret_col") or model["outputs"]["pred_ret_col"])
    target_col = str(target.get("label_col") or target["fwd_col"])
    if target_col not in frame.columns:
        raise LabContractError(f"Missing target column for locked prediction quality: {target_col}")
    pair = frame.loc[index, [pred_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
    metrics = prediction_realized_metrics(pair[pred_col], pair[target_col])
    monotonicity = quantile_monotonicity(prediction_quantile_table(pair[pred_col], pair[target_col], quantiles=10))
    return {
        "evaluation_rows": int(metrics.get("evaluation_rows", 0) or 0),
        "prediction_correlation": metrics.get("correlation"),
        "prediction_spearman": metrics.get("spearman_rank_correlation"),
        "directional_accuracy": metrics.get("directional_accuracy"),
        "quantile_monotonicity": monotonicity.get("monotonicity"),
    }


def _robustness(*, full_frame: pd.DataFrame, base_result: Any, locked_index: pd.Index, cfg: Mapping[str, Any], signal_col: str) -> list[dict[str, Any]]:
    periods_per_year = int(cfg["backtest"].get("periods_per_year", 17_520))
    gross, costs, turnover = (base_result.gross_returns.reindex(locked_index), base_result.costs.reindex(locked_index), base_result.turnover.reindex(locked_index))
    compact = cost_multiplier_stress(gross_returns=gross, costs=costs, periods_per_year=periods_per_year, multipliers=(1.0, 3.0, 5.0))
    rows: list[dict[str, Any]] = []
    for multiplier in (1.0, 3.0, 5.0):
        scenario = f"cost_x{multiplier:g}"
        if scenario not in compact:
            raise LabContractError(f"Missing framework cost scenario: {scenario}")
        stressed_cost = costs * multiplier
        metrics = compute_backtest_metrics(net_returns=gross - stressed_cost, turnover=turnover, costs=stressed_cost, gross_returns=gross, periods_per_year=periods_per_year)
        rows.append({"scenario_type": "cost", "scenario_id": scenario, "scenario_value": multiplier, **metrics, "turnover": metrics["total_turnover"], "cost": metrics["total_cost"]})
    for delay in (1, 2):
        delayed = full_frame.copy()
        delayed[signal_col] = delayed[signal_col].shift(delay).fillna(0.0)
        result = _backtest(delayed, cfg, signal_col)
        metrics = _metrics(result, locked_index, periods_per_year)
        rows.append({"scenario_type": "entry_delay", "scenario_id": f"delay_{delay}_bar", "scenario_value": delay, **metrics, "turnover": metrics["total_turnover"], "cost": metrics["total_cost"]})
    return rows


def _evaluate(result: Any, cfg: Mapping[str, Any], spec: ConfirmationSpec, config_sha256: str, run_dir: str) -> dict[str, Any]:
    frame = _single_asset_frame(result)
    if not isinstance(frame.index, pd.DatetimeIndex) or not frame.index.is_unique or not frame.index.is_monotonic_increasing:
        raise LabContractError("Locked confirmation requires a unique, chronological DatetimeIndex.")
    splits = _locked_splits_for_config(frame, cfg)
    model = dict(cfg["model"])
    prediction_col = str(model.get("pred_ret_col") or model["outputs"]["pred_ret_col"])
    oos_col = str(model.get("pred_is_oos_col") or model["outputs"]["pred_is_oos_col"])
    positions = assert_locked_oos_frame(frame, splits=splits, oos_col=oos_col, prediction_col=prediction_col)
    locked_index = frame.index[positions]
    signal_col = str(cfg["backtest"]["signal_col"])
    signal_frame = apply_signal_step(frame, dict(cfg["signals"]), asset="ETHUSD")
    oos = signal_frame[oos_col].fillna(False).astype(bool)
    signal_frame.loc[~oos, signal_col] = 0.0
    first_oos = int(np.flatnonzero(oos.to_numpy())[0])
    full_frame = signal_frame.iloc[first_oos:].copy()
    base_result = _backtest(full_frame, cfg, signal_col)
    periods_per_year = int(cfg["backtest"].get("periods_per_year", 17_520))
    summary = _metrics(base_result, locked_index, periods_per_year)
    entries = _entry_mask(base_result.positions)
    signals = pd.to_numeric(signal_frame.loc[locked_index, signal_col], errors="coerce").fillna(0.0)
    summary.update({"evaluation_rows": int(len(locked_index)), "trade_count": int(entries.reindex(locked_index).fillna(False).sum()), "flat_rate": float((signals == 0).mean()), "long_rate": float((signals > 0).mean()), "short_rate": float((signals < 0).mean())})
    folds: list[dict[str, Any]] = []
    for split in splits[LOCKED_FOLD_START:FULL_FOLD_COUNT]:
        index = frame.index[np.asarray(split.test_idx, dtype=int)]
        metrics = _metrics(base_result, index, periods_per_year)
        folds.append({
            "fold": int(split.fold), "train_start_row": int(split.train_start), "train_end_row": int(split.train_end), "test_start_row": int(split.test_start), "test_end_row": int(split.test_end),
            "train_start": frame.index[int(split.train_start)].isoformat(), "train_end": frame.index[int(split.train_end) - 1].isoformat(), "test_start": index.min().isoformat(), "test_end": index.max().isoformat(),
            "test_rows": int(len(index)), "trade_count": int(entries.reindex(index).fillna(False).sum()), **metrics, "turnover": metrics["total_turnover"], "cost": metrics["total_cost"],
        })
    fold_frame = pd.DataFrame(folds)
    net = pd.to_numeric(fold_frame["net_pnl"], errors="coerce")
    positive = net[net > 0]
    summary.update({
        "profitable_fold_count": int((net > 0).sum()), "profitable_fold_rate": float((net > 0).mean()),
        "mean_fold_sharpe": float(pd.to_numeric(fold_frame["sharpe"], errors="coerce").mean()), "median_fold_sharpe": float(pd.to_numeric(fold_frame["sharpe"], errors="coerce").median()), "std_fold_sharpe": float(pd.to_numeric(fold_frame["sharpe"], errors="coerce").std(ddof=0)),
        "worst_fold_sharpe": float(pd.to_numeric(fold_frame["sharpe"], errors="coerce").min()), "worst_fold_return": float(pd.to_numeric(fold_frame["cumulative_return"], errors="coerce").min()),
        "pnl_concentration_top_fold": float(positive.max() / positive.sum()) if not positive.empty else float("inf"),
    })
    quality = _prediction_quality(frame, cfg, locked_index)
    summary.update(quality)
    return {
        "experiment_id": spec.experiment_id, "config_sha256": config_sha256, "run_dir": run_dir,
        "locked_fold_ids": list(range(LOCKED_FOLD_START, FULL_FOLD_COUNT)),
        "oos_integrity": {"strict_oos": True, "marker_column": oos_col, "prediction_column": prediction_col},
        "summary": summary, "fold_metrics": folds, "robustness": _robustness(full_frame=full_frame, base_result=base_result, locked_index=locked_index, cfg=cfg, signal_col=signal_col), "prediction_quality": quality,
    }


def run_confirmation(*, resume: bool = True) -> pd.DataFrame:
    """Run every frozen config; each loop re-verifies config hashes before proceeding."""
    verify_manifest()
    validation = validate_configs()
    if (validation["status"] != "valid").any():
        raise LabContractError("Refusing locked confirmation because a config is invalid.")
    metrics_dir = REPORTS_DIR / "experiment_metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    index_path = REPORTS_DIR / "locked_confirmation_run_index.json"
    run_index = _read_json(index_path).get("runs", {}) if index_path.exists() else {}
    rows = []
    for spec, path in zip(confirmation_specs(), config_paths(), strict=True):
        verify_manifest()  # explicit pre-run integrity check
        config_sha = _sha(path)
        metrics_path = metrics_dir / f"{spec.experiment_id}.json"
        payload = _read_json(metrics_path) if resume and metrics_path.exists() else None
        if payload is None or payload.get("config_sha256") != config_sha:
            cfg = load_experiment_config(path)
            try:
                result = run_experiment(path)
            except Exception as exc:
                run_index[spec.experiment_id] = {"status": "failed", "config_sha256": config_sha, "error": f"{type(exc).__name__}: {exc}"}
                index_path.write_text(json.dumps(_json_safe({"runs": run_index}), indent=2, allow_nan=False), encoding="utf-8")
                raise LabContractError(f"Locked run failed: {spec.experiment_id}: {type(exc).__name__}: {exc}") from exc
            payload = _evaluate(result, cfg, spec, config_sha, str(result.artifacts.get("run_dir", "")))
            metrics_path.write_text(json.dumps(_json_safe(payload), indent=2, allow_nan=False) + "\n", encoding="utf-8")
        run_index[spec.experiment_id] = {"status": "success", "config_sha256": config_sha, "run_dir": payload.get("run_dir", "")}
        index_path.write_text(json.dumps(_json_safe({"runs": run_index}), indent=2, allow_nan=False), encoding="utf-8")
        rows.append({"experiment_id": spec.experiment_id, "status": "success", "config_sha256": config_sha, "run_dir": payload.get("run_dir", "")})
    table = pd.DataFrame(rows)
    table.to_csv(REPORTS_DIR / "locked_confirmation_execution.csv", index=False)
    write_reports()
    return table


def _payloads() -> list[dict[str, Any]]:
    directory = REPORTS_DIR / "experiment_metrics"
    out = []
    for spec in confirmation_specs():
        path = directory / f"{spec.experiment_id}.json"
        if not path.exists():
            raise LabContractError(f"Missing locked metrics artifact: {path}")
        payload = _read_json(path)
        if payload.get("locked_fold_ids") != list(range(LOCKED_FOLD_START, FULL_FOLD_COUNT)):
            raise LabContractError(f"Invalid locked-fold range in {path}")
        out.append(payload)
    return out


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _markdown_table(frame: pd.DataFrame) -> str:
    """Render a compact Markdown table without Pandas' optional tabulate extra."""
    columns = [str(column) for column in frame.columns]

    def cell(value: Any) -> str:
        if value is None or (isinstance(value, (float, np.floating)) and not math.isfinite(float(value))):
            return ""
        if isinstance(value, (float, np.floating)):
            text = f"{float(value):.10g}"
        else:
            text = str(value)
        return text.replace("|", "\\|").replace("\n", "<br>")

    rows = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    rows.extend("| " + " | ".join(cell(value) for value in values) + " |" for values in frame.itertuples(index=False, name=None))
    return "\n".join(rows)


def _scenario(rows: Iterable[Mapping[str, Any]], name: str, metric: str) -> float:
    for row in rows:
        if row.get("scenario_id") == name:
            return _number(row.get(metric))
    return float("nan")


def _gates(summary: Mapping[str, Any], robustness: Iterable[Mapping[str, Any]]) -> dict[str, bool]:
    concentration, gross = _number(summary.get("pnl_concentration_top_fold")), _number(summary.get("gross_pnl"))
    return {
        "gate_sharpe": _number(summary.get("sharpe")) >= 1.50,
        "gate_profitable_folds": _number(summary.get("profitable_fold_count")) >= 5.0,
        "gate_max_drawdown": _number(summary.get("max_drawdown")) >= -0.25,
        "gate_profit_factor": _number(summary.get("profit_factor")) > 1.05,
        "gate_cost_x5_sharpe": _scenario(robustness, "cost_x5", "sharpe") >= 1.00,
        "gate_delay_1_sharpe": _scenario(robustness, "delay_1_bar", "sharpe") >= 1.00,
        "gate_delay_2_sharpe": _scenario(robustness, "delay_2_bar", "sharpe") >= 1.00,
        "gate_cost_to_gross": gross > 0.0 and _number(summary.get("cost_to_gross_pnl")) <= 0.10,
        "gate_pnl_concentration": math.isfinite(concentration) and concentration <= 0.50,
        "gate_oos_integrity": True,
        "gate_config_integrity": True,
    }


def write_reports() -> Path:
    """Write the required locked-only CSV/JSON/Markdown artifacts."""
    verify_manifest()
    payloads = _payloads()
    summaries, folds, robustness, gate_rows = [], [], [], []
    for payload in payloads:
        experiment_id = str(payload["experiment_id"])
        summaries.append({"experiment_id": experiment_id, "config_sha256": payload["config_sha256"], "evaluation_fold_start": LOCKED_FOLD_START, "evaluation_fold_end": FULL_FOLD_COUNT - 1, "run_dir": payload.get("run_dir", ""), **dict(payload["summary"])})
        folds.extend({"experiment_id": experiment_id, **row} for row in payload["fold_metrics"])
        robustness.extend({"experiment_id": experiment_id, **row} for row in payload["robustness"])
        gates = _gates(payload["summary"], payload["robustness"])
        gate_rows.append({"experiment_id": experiment_id, **gates, "promote_candidate": bool(all(gates.values()))})
    order = {spec.experiment_id: idx for idx, spec in enumerate(confirmation_specs())}
    summary_frame = pd.DataFrame(summaries).assign(_order=lambda frame: frame["experiment_id"].map(order)).sort_values("_order").drop(columns="_order")
    fold_frame = pd.DataFrame(folds).sort_values(["experiment_id", "fold"])
    robustness_frame = pd.DataFrame(robustness).sort_values(["experiment_id", "scenario_type", "scenario_value"])
    gates_frame = pd.DataFrame(gate_rows).sort_values("experiment_id")
    baseline_id = confirmation_specs()[0].experiment_id
    baseline = summary_frame.set_index("experiment_id").loc[baseline_id]
    robustness_lookup = robustness_frame.set_index(["experiment_id", "scenario_id"])
    deltas, recommendations = [], {baseline_id: "retain as baseline reference"}
    for _, row in summary_frame.iterrows():
        experiment_id = str(row["experiment_id"])
        if experiment_id == baseline_id:
            continue
        cost_x5 = _scenario(robustness_frame.loc[robustness_frame["experiment_id"] == experiment_id].to_dict("records"), "cost_x5", "sharpe")
        delay_1 = _scenario(robustness_frame.loc[robustness_frame["experiment_id"] == experiment_id].to_dict("records"), "delay_1_bar", "sharpe")
        delay_2 = _scenario(robustness_frame.loc[robustness_frame["experiment_id"] == experiment_id].to_dict("records"), "delay_2_bar", "sharpe")
        base_cost_x5 = _number(robustness_lookup.loc[(baseline_id, "cost_x5"), "sharpe"])
        base_delay_1 = _number(robustness_lookup.loc[(baseline_id, "delay_1_bar"), "sharpe"])
        base_delay_2 = _number(robustness_lookup.loc[(baseline_id, "delay_2_bar"), "sharpe"])
        deltas.append({
            "experiment_id": experiment_id,
            "delta_cumulative_return": _number(row["cumulative_return"]) - _number(baseline["cumulative_return"]),
            "delta_sharpe": _number(row["sharpe"]) - _number(baseline["sharpe"]),
            "delta_max_drawdown": _number(row["max_drawdown"]) - _number(baseline["max_drawdown"]),
            "delta_profit_factor": _number(row["profit_factor"]) - _number(baseline["profit_factor"]),
            "delta_turnover": _number(row["total_turnover"]) - _number(baseline["total_turnover"]),
            "delta_cost_to_gross": _number(row["cost_to_gross_pnl"]) - _number(baseline["cost_to_gross_pnl"]),
            "delta_profitable_fold_rate": _number(row["profitable_fold_rate"]) - _number(baseline["profitable_fold_rate"]),
            "delta_cost_x5_sharpe": cost_x5 - base_cost_x5,
            "delta_delay_1_sharpe": delay_1 - base_delay_1,
            "delta_delay_2_sharpe": delay_2 - base_delay_2,
        })
        passes = bool(gates_frame.set_index("experiment_id").loc[experiment_id, "promote_candidate"])
        better_sharpe_no_worse_dd = _number(row["sharpe"]) > _number(baseline["sharpe"]) and _number(row["max_drawdown"]) >= _number(baseline["max_drawdown"])
        noninferior_sharpe_lower_dd = _number(row["sharpe"]) >= _number(baseline["sharpe"]) and _number(row["max_drawdown"]) > _number(baseline["max_drawdown"])
        robust_noninferior = _number(row["cumulative_return"]) >= _number(baseline["cumulative_return"]) and cost_x5 >= base_cost_x5 and delay_1 >= base_delay_1 and delay_2 >= base_delay_2
        recommendations[experiment_id] = "promote" if passes and (better_sharpe_no_worse_dd or noninferior_sharpe_lower_dd or robust_noninferior) else ("retain as secondary candidate" if passes else "reject")
    delta_frame = pd.DataFrame(deltas)
    gates_frame["recommendation"] = gates_frame["experiment_id"].map(recommendations)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    summary_frame.to_csv(REPORTS_DIR / "locked_confirmation_summary.csv", index=False)
    fold_frame.to_csv(REPORTS_DIR / "locked_confirmation_fold_metrics.csv", index=False)
    robustness_frame.to_csv(REPORTS_DIR / "locked_confirmation_robustness.csv", index=False)
    delta_frame.to_csv(REPORTS_DIR / "locked_confirmation_deltas_vs_baseline.csv", index=False)
    gates_frame.to_csv(REPORTS_DIR / "locked_confirmation_pass_fail.csv", index=False)
    (REPORTS_DIR / "locked_confirmation_results.json").write_text(json.dumps(_json_safe({"summary": summaries, "fold_metrics": folds, "robustness": robustness, "gates": gates_frame.to_dict(orient="records")}), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    audit_path = REPORTS_DIR / "locked_confirmation_baseline_audit.json"
    audit = _read_json(audit_path) if audit_path.exists() else {}
    report = [
        "# ETHUSD Trial 0041 locked confirmation", "",
        "## Executive summary", "", "Every metric below is calculated only from folds 10-16. Folds 0-9 construct the required expanding history and never enter a confirmation aggregate.", "",
        "## Frozen methodology", "", "The seven YAMLs were SHA-256-frozen before execution. The artifact model, target, purged expanding split parameters (except max_folds=17), thresholds, filters, holding period, costs, runtime seed, deterministic single-thread mode, and vectorized execution semantics are unchanged. Threshold-grid diagnostics are disabled.", "",
        "## Audit baseline/config discrepancies", "", f"Semantic source: `{audit.get('semantic_source_of_truth', 'n/a')}`. Baseline vs artifact differences: `{audit.get('current_baseline_vs_artifact_unexpected_differences', [])}`. The current tracked screening YAMLs have `allow_short: true`, whereas their recorded config_used artifacts and all confirmation configs use `false`.", "",
        "## Locked-only leaderboard", "", _markdown_table(summary_frame[["experiment_id", "cumulative_return", "sharpe", "max_drawdown", "profit_factor", "profitable_fold_count", "cost_to_gross_pnl"]]), "",
        "## Fold-by-fold table", "", _markdown_table(fold_frame[["experiment_id", "fold", "test_start", "test_end", "test_rows", "cumulative_return", "sharpe", "max_drawdown", "net_pnl", "cost"]]), "",
        "## Cost robustness", "", _markdown_table(robustness_frame.loc[robustness_frame["scenario_type"] == "cost", ["experiment_id", "scenario_id", "cumulative_return", "sharpe", "max_drawdown", "profit_factor", "cost_to_gross_pnl"]]), "",
        "## Delay robustness", "", _markdown_table(robustness_frame.loc[robustness_frame["scenario_type"] == "entry_delay", ["experiment_id", "scenario_id", "cumulative_return", "sharpe", "max_drawdown", "profit_factor"]]), "",
        "## Prediction quality", "", _markdown_table(summary_frame[["experiment_id", "prediction_correlation", "prediction_spearman", "directional_accuracy", "quantile_monotonicity"]]), "",
        "## Risk-return comparison", "", _markdown_table(summary_frame[["experiment_id", "annualized_return", "annualized_vol", "sortino", "calmar", "max_drawdown"]]), "",
        "## Deltas versus locked baseline", "", _markdown_table(delta_frame), "",
        "## Pass/fail matrix", "", _markdown_table(gates_frame), "",
        "## Final recommendation", "", "A challenger must pass every stated gate. Replacement comparisons use strict non-inferiority rather than an unannounced tolerance: higher Sharpe without worse drawdown, non-inferior Sharpe with lower drawdown, or non-inferior cost/delay robustness without lower cumulative return.", "", _markdown_table(gates_frame[["experiment_id", "promote_candidate", "recommendation"]]), "",
    ]
    path = REPORTS_DIR / "locked_confirmation_report.md"
    path.write_text("\n".join(report), encoding="utf-8")
    return path


__all__ = [
    "ADDED_COLUMNS", "CONFIG_DIR", "ConfirmationSpec", "HOST_GIT_PROVENANCE_PATH", "LOGS_RELATIVE", "MANIFEST_PATH", "REPORTS_DIR", "ROBUSTNESS_SCENARIOS",
    "assert_locked_oos_frame", "build_confirmation_config", "config_paths", "confirmation_specs", "create_manifest", "generate_configs",
    "locked_fold_indexes", "run_confirmation", "validate_configs", "verify_manifest", "write_host_git_provenance", "write_reports",
]
