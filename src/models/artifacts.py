from __future__ import annotations

import json
import os
import pickle
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from src.evaluation.model_metrics import forecast_to_probability
from src.utils.paths import PROJECT_ROOT, enforce_safe_absolute_path


MODEL_BUNDLE_VERSION = 2
_MODEL_EXTENSION = ".pkl"


def safe_model_name(value: object, *, default: str = "model") -> str:
    """
    Normalize a YAML-provided model name into a single safe filename stem.
    """
    raw = str(value or "").strip()
    if raw.lower().endswith(_MODEL_EXTENSION):
        raw = raw[: -len(_MODEL_EXTENSION)]
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._-")
    if not name:
        name = default
    if name in {".", ".."}:
        raise ValueError("model_name must resolve to a safe filename stem.")
    return name


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            json.dump(_jsonable(dict(payload)), handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()


def _atomic_write_pickle(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            pickle.dump(dict(payload), handle, protocol=pickle.HIGHEST_PROTOCOL)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()


def _model_name_from_config(cfg: Mapping[str, Any], model_meta: Mapping[str, Any]) -> str:
    logging_cfg = dict(cfg.get("logging", {}) or {})
    configured = (
        logging_cfg.get("model_name")
        or logging_cfg.get("model_artifact_name")
        or logging_cfg.get("model_filename")
    )
    if configured not in (None, ""):
        return safe_model_name(configured)

    strategy_cfg = dict(cfg.get("strategy", {}) or {})
    fallback = (
        strategy_cfg.get("name")
        or logging_cfg.get("run_name")
        or model_meta.get("model_kind")
        or "model"
    )
    return safe_model_name(fallback)


def _resolve_install_dir(raw_path: object) -> Path:
    path = Path(str(raw_path or "logs/models"))
    if path.is_absolute():
        return enforce_safe_absolute_path(path)
    return (PROJECT_ROOT / path).resolve()


def _bundle_payload(
    *,
    model: object,
    cfg: Mapping[str, Any],
    model_meta: Mapping[str, Any],
    run_metadata: Mapping[str, Any],
    config_hash_sha256: str,
    data_fingerprint: Mapping[str, Any],
    model_name: str,
) -> dict[str, Any]:
    return {
        "bundle_version": MODEL_BUNDLE_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_name": model_name,
        "model": model,
        "model_meta": dict(model_meta),
        "model_config": dict(cfg.get("model", {}) or {}),
        "model_stages_config": list(cfg.get("model_stages", []) or []),
        "signals_config": dict(cfg.get("signals", {}) or {}),
        "strategy": dict(cfg.get("strategy", {}) or {}),
        "reproducibility": {
            "config_hash_sha256": str(config_hash_sha256),
            "data_hash_sha256": data_fingerprint.get("sha256"),
            "config_path": cfg.get("config_path"),
            "run_created_at_utc": run_metadata.get("created_at_utc"),
            "git": dict(run_metadata.get("git", {}) or {}),
            "environment": dict(run_metadata.get("environment", {}) or {}),
        },
    }


def _bundle_manifest(bundle: Mapping[str, Any], *, model_path: Path) -> dict[str, Any]:
    model_meta = dict(bundle.get("model_meta", {}) or {})
    model_config = dict(bundle.get("model_config", {}) or {})
    feature_cols = (
        list(model_meta.get("feature_cols", []) or [])
        or list(dict(model_meta.get("feature_pipeline", {}) or {}).get("final_feature_names", []) or [])
        or list(model_config.get("feature_cols", []) or [])
    )
    return {
        "bundle_version": MODEL_BUNDLE_VERSION,
        "model_name": bundle.get("model_name"),
        "model_path": str(model_path),
        "model_kind": model_meta.get("model_kind") or model_config.get("kind"),
        "task_type": model_meta.get("task_type"),
        "feature_cols": feature_cols,
        "pred_ret_col": model_meta.get("pred_ret_col") or model_config.get("pred_ret_col"),
        "pred_prob_col": model_meta.get("pred_prob_col") or model_config.get("pred_prob_col"),
        "pred_label_col": model_meta.get("pred_label_col") or model_config.get("pred_label_col"),
        "pred_is_oos_col": model_meta.get("pred_is_oos_col") or model_config.get("pred_is_oos_col"),
        "prob_scale": model_meta.get("prob_scale"),
        "created_at_utc": bundle.get("created_at_utc"),
        "reproducibility": dict(bundle.get("reproducibility", {}) or {}),
    }


def save_model_artifacts(
    *,
    run_dir: Path,
    model: object | None,
    cfg: Mapping[str, Any],
    model_meta: Mapping[str, Any],
    run_metadata: Mapping[str, Any],
    config_hash_sha256: str,
    data_fingerprint: Mapping[str, Any],
) -> dict[str, str]:
    """
    Persist a fitted model bundle when logging.save_model is enabled.

    The run-local copy is always written under artifacts/models. By default, a stable
    installed copy is also written to logs/models/<model_name>.pkl so execution
    configs can reference a predictable path.
    """
    logging_cfg = dict(cfg.get("logging", {}) or {})
    if not bool(logging_cfg.get("save_model", False)):
        return {}
    if model is None:
        raise ValueError("logging.save_model=true but the experiment did not return a fitted model.")

    model_name = _model_name_from_config(cfg, model_meta)
    bundle = _bundle_payload(
        model=model,
        cfg=cfg,
        model_meta=model_meta,
        run_metadata=run_metadata,
        config_hash_sha256=config_hash_sha256,
        data_fingerprint=data_fingerprint,
        model_name=model_name,
    )

    run_model_dir = run_dir / "artifacts" / "models"
    run_model_path = run_model_dir / f"{model_name}{_MODEL_EXTENSION}"
    run_manifest_path = run_model_dir / f"{model_name}.manifest.json"
    _atomic_write_pickle(run_model_path, bundle)
    _atomic_write_json(run_manifest_path, _bundle_manifest(bundle, model_path=run_model_path))

    artifacts = {
        "model_artifact": str(run_model_path),
        "model_artifact_manifest": str(run_manifest_path),
    }

    install_enabled = bool(logging_cfg.get("install_model", True))
    if install_enabled:
        install_dir = _resolve_install_dir(
            logging_cfg.get("model_install_dir")
            or logging_cfg.get("installed_model_dir")
            or logging_cfg.get("model_registry_dir")
            or "logs/models"
        )
        installed_model_path = install_dir / f"{model_name}{_MODEL_EXTENSION}"
        installed_manifest_path = install_dir / f"{model_name}.manifest.json"
        _atomic_write_pickle(installed_model_path, bundle)
        _atomic_write_json(installed_manifest_path, _bundle_manifest(bundle, model_path=installed_model_path))
        artifacts["installed_model_artifact"] = str(installed_model_path)
        artifacts["installed_model_manifest"] = str(installed_manifest_path)

    return artifacts


def load_model_bundle(path: str | Path) -> dict[str, Any]:
    bundle_path = Path(path)
    with bundle_path.open("rb") as handle:
        payload = pickle.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Model artifact must contain a mapping payload: {bundle_path}")
    version = int(payload.get("bundle_version", 0) or 0)
    if version != MODEL_BUNDLE_VERSION:
        raise ValueError(f"Unsupported model bundle version {version}; expected {MODEL_BUNDLE_VERSION}.")
    if "model" not in payload:
        raise ValueError(f"Model artifact is missing the fitted model payload: {bundle_path}")
    return payload


def _asset_model(bundle: Mapping[str, Any], asset: str | None) -> object:
    model = bundle.get("model")
    if isinstance(model, Mapping):
        if asset is not None and asset in model:
            return model[asset]
        if len(model) == 1:
            return next(iter(model.values()))
        raise KeyError(f"Model artifact contains per-asset models; asset '{asset}' is not available.")
    return model


def _asset_model_meta(bundle: Mapping[str, Any], asset: str | None) -> dict[str, Any]:
    meta = dict(bundle.get("model_meta", {}) or {})
    per_asset = dict(meta.get("per_asset", {}) or {})
    if per_asset:
        if asset is not None and asset in per_asset:
            return dict(per_asset[asset] or {})
        if len(per_asset) == 1:
            return dict(next(iter(per_asset.values())) or {})
    return meta


def _feature_cols_for_bundle(bundle: Mapping[str, Any], asset: str | None) -> list[str]:
    meta = _asset_model_meta(bundle, asset)
    model_config = dict(bundle.get("model_config", {}) or {})
    feature_cols = (
        list(meta.get("feature_cols", []) or [])
        or list(dict(meta.get("feature_pipeline", {}) or {}).get("final_feature_names", []) or [])
        or list(model_config.get("feature_cols", []) or [])
    )
    return [str(column) for column in feature_cols]


def predict_with_model_bundle(
    df: pd.DataFrame,
    bundle: Mapping[str, Any],
    *,
    asset: str | None = None,
) -> pd.DataFrame:
    """
    Apply a saved fitted model bundle to a feature frame for live/paper execution.
    """
    meta = _asset_model_meta(bundle, asset)
    model_config = dict(bundle.get("model_config", {}) or {})
    feature_cols = _feature_cols_for_bundle(bundle, asset)
    if not feature_cols:
        raise ValueError("Model artifact does not declare feature columns for inference.")

    missing = [column for column in feature_cols if column not in df.columns]
    if missing:
        sample = ", ".join(missing[:10])
        suffix = "" if len(missing) <= 10 else f" (+{len(missing) - 10} more)"
        raise KeyError(f"Feature frame is missing model columns: {sample}{suffix}")

    out = df.copy()
    model = _asset_model(bundle, asset)
    if model is None:
        raise ValueError("Model artifact contains no fitted model.")

    pred_ret_col = str(meta.get("pred_ret_col") or model_config.get("pred_ret_col") or "pred_ret")
    pred_prob_col = str(meta.get("pred_prob_col") or model_config.get("pred_prob_col") or "pred_prob")
    pred_label_col = str(meta.get("pred_label_col") or model_config.get("pred_label_col") or "pred_label")
    pred_is_oos_col = str(meta.get("pred_is_oos_col") or model_config.get("pred_is_oos_col") or "pred_is_oos")

    features = out.loc[:, feature_cols].apply(pd.to_numeric, errors="coerce").astype(float)
    complete = features.notna().all(axis=1)
    out[pred_is_oos_col] = False

    has_predict_proba = hasattr(model, "predict_proba")
    has_predict = hasattr(model, "predict")
    if not has_predict and not has_predict_proba:
        raise TypeError(f"Saved model object does not expose predict or predict_proba: {type(model)!r}")

    model_kind = str(meta.get("model_kind") or model_config.get("kind") or "").lower()
    task_type = str(meta.get("task_type") or "").lower()
    if task_type not in {"classification", "regression"}:
        task_type = "classification" if has_predict_proba or "classifier" in model_kind else "regression"

    if task_type == "regression":
        if not has_predict:
            raise TypeError("Regression model artifact must expose predict().")
        pred_ret = pd.Series(np.nan, index=out.index, name=pred_ret_col, dtype="float32")
        if bool(complete.any()):
            values = model.predict(features.loc[complete, feature_cols])
            pred_ret.loc[complete] = np.asarray(values, dtype=float).reshape(-1).astype("float32")
        out[pred_ret_col] = pred_ret
        configured_scale = meta.get("prob_scale")
        if configured_scale is None:
            configured_scale = model_config.get(
                "prob_scale",
                dict(model_config.get("params", {}) or {}).get("prob_scale"),
            )
        out[pred_prob_col] = forecast_to_probability(
            out[pred_ret_col].astype(float),
            scale=float(configured_scale) if configured_scale is not None else None,
        )
        return out

    if has_predict:
        pred_label = pd.Series(pd.NA, index=out.index, name=pred_label_col, dtype="object")
        if bool(complete.any()):
            values = model.predict(features.loc[complete, feature_cols])
            pred_label.loc[complete] = np.asarray(values).reshape(-1)
        out[pred_label_col] = pred_label

    if has_predict_proba:
        pred_prob = pd.Series(np.nan, index=out.index, name=pred_prob_col, dtype="float32")
        if bool(complete.any()):
            proba = model.predict_proba(features.loc[complete, feature_cols])
            proba_arr = np.asarray(proba, dtype=float)
            if proba_arr.ndim == 2 and proba_arr.shape[1] == 2:
                values = proba_arr[:, 1]
                pred_prob.loc[complete] = values.astype("float32")
            elif proba_arr.ndim == 1 or (proba_arr.ndim == 2 and proba_arr.shape[1] == 1):
                values = proba_arr.reshape(-1)
                pred_prob.loc[complete] = values.astype("float32")
            elif proba_arr.ndim == 2:
                classes = list(getattr(model, "classes_", range(proba_arr.shape[1])))
                for class_idx, class_label in enumerate(classes):
                    class_col = (
                        f"{pred_prob_col}_"
                        f"{safe_model_name(class_label, default=str(class_idx))}"
                    )
                    class_prob = pd.Series(np.nan, index=out.index, dtype="float32")
                    class_prob.loc[complete] = proba_arr[:, class_idx].astype("float32")
                    out[class_col] = class_prob
                return out
            else:
                raise ValueError("Classifier predict_proba returned an unsupported shape.")
        out[pred_prob_col] = pred_prob

    return out


__all__ = [
    "MODEL_BUNDLE_VERSION",
    "load_model_bundle",
    "predict_with_model_bundle",
    "safe_model_name",
    "save_model_artifacts",
]
