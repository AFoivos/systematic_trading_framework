from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from src.utils.paths import CONFIG_DIR, PROJECT_ROOT


class ConfigPathError(ValueError):
    """Raised when a config path cannot be resolved safely."""


def resolve_config_path(config_path: str | Path) -> Path:
    """
    Resolve a config path relative to the project config directory and enforce safe access.
    """
    path = Path(config_path)
    if not path.is_absolute():
        candidate = (PROJECT_ROOT / path).resolve()
        if candidate.exists():
            path = candidate
        else:
            path = (CONFIG_DIR / path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    if not path.is_file():
        raise ConfigPathError(f"Config path is not a file: {path}")
    from src.utils.paths import enforce_safe_absolute_path

    return enforce_safe_absolute_path(path)


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    """
    Load a YAML file and require a top-level mapping.
    """
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ConfigPathError(f"Config at {path} must be a mapping at top level.")
    return data


def _resolve_enabled_catalog_entry(
    cfg: dict[str, Any],
    *,
    catalog_key: str,
    output_key: str,
) -> dict[str, Any]:
    catalog = cfg.get(catalog_key)
    if catalog is None:
        return cfg
    if output_key in cfg and cfg.get(output_key) not in (None, {}):
        raise ConfigPathError(
            f"Config must specify either '{output_key}' or '{catalog_key}', not both."
        )
    if not isinstance(catalog, dict) or not catalog:
        raise ConfigPathError(f"'{catalog_key}' must be a non-empty mapping.")

    enabled_items: list[tuple[str, dict[str, Any]]] = []
    for kind, raw_entry in catalog.items():
        if not isinstance(kind, str) or not kind:
            raise ConfigPathError(f"Keys under '{catalog_key}' must be non-empty strings.")
        if raw_entry is None:
            entry: dict[str, Any] = {}
        elif not isinstance(raw_entry, dict):
            raise ConfigPathError(f"'{catalog_key}.{kind}' must be a mapping.")
        else:
            entry = dict(raw_entry)
        enabled = entry.get("enabled", False)
        if not isinstance(enabled, bool):
            raise ConfigPathError(f"'{catalog_key}.{kind}.enabled' must be boolean.")
        if enabled:
            enabled_items.append((kind, entry))

    if len(enabled_items) != 1:
        raise ConfigPathError(
            f"'{catalog_key}' must have exactly one entry with enabled=true; found {len(enabled_items)}."
        )

    selected_kind, selected_entry = enabled_items[0]
    selected_entry.pop("enabled", None)
    resolved = {"kind": selected_kind} | selected_entry

    out = dict(cfg)
    out.pop(catalog_key, None)
    out[output_key] = resolved
    return out


def _normalize_named_outputs(outputs: Any, *, owner: str, allowed: set[str]) -> dict[str, str]:
    if outputs in (None, {}):
        return {}
    if not isinstance(outputs, dict):
        raise ConfigPathError(f"'{owner}.outputs' must be a mapping when provided.")
    normalized: dict[str, str] = {}
    for key, value in outputs.items():
        if not isinstance(key, str) or not key.strip():
            raise ConfigPathError(f"'{owner}.outputs' keys must be non-empty strings.")
        if key not in allowed:
            allowed_display = ", ".join(sorted(allowed))
            raise ConfigPathError(f"'{owner}.outputs.{key}' is not supported. Allowed keys: {allowed_display}.")
        if not isinstance(value, str) or not value.strip():
            raise ConfigPathError(f"'{owner}.outputs.{key}' must be a non-empty string.")
        normalized[key] = value
    return normalized


def _apply_model_outputs_aliases(model: Any, *, owner: str) -> dict[str, Any]:
    if model in (None, {}):
        return {} if model in ({}, None) else dict(model)
    if not isinstance(model, dict):
        raise ConfigPathError(f"'{owner}' must be a mapping.")

    out = dict(model)
    outputs = _normalize_named_outputs(
        out.get("outputs"),
        owner=owner,
        allowed={
            "pred_prob_col",
            "pred_ret_col",
            "returns_input_col",
            "signal_col",
            "action_col",
            "label_col",
            "fwd_col",
            "candidate_out_col",
        },
    )
    target = dict(out.get("target", {}) or {})
    for field in ("pred_prob_col", "pred_ret_col", "returns_input_col", "signal_col", "action_col"):
        if field in outputs and out.get(field) in (None, ""):
            out[field] = outputs[field]
    for field in ("label_col", "fwd_col", "candidate_out_col"):
        if field in outputs and target.get(field) in (None, ""):
            target[field] = outputs[field]
    if target:
        out["target"] = target
    return out


def _apply_signals_outputs_aliases(signals: Any) -> dict[str, Any]:
    if signals in (None, {}):
        return {} if signals in ({}, None) else dict(signals)
    if not isinstance(signals, dict):
        raise ConfigPathError("'signals' must be a mapping.")
    out = dict(signals)
    outputs = _normalize_named_outputs(out.get("outputs"), owner="signals", allowed={"signal_col"})
    if outputs:
        params = dict(out.get("params", {}) or {})
        if params.get("signal_col") in (None, ""):
            params["signal_col"] = outputs["signal_col"]
        out["params"] = params
    return out


def load_resolved_config(path: Path) -> dict[str, Any]:
    """
    Load a self-contained experiment config and reject legacy inheritance.
    """
    cfg = load_yaml_mapping(path)
    if "extends" in cfg:
        raise ConfigPathError(
            "Config inheritance via 'extends' is no longer supported. "
            "Each experiment YAML must be fully self-contained."
        )
    has_model_stages = cfg.get("model_stages") not in (None, [])
    has_single_model = cfg.get("model") not in (None, {})
    has_model_catalog = cfg.get("models") not in (None, {})
    if has_model_stages and (has_single_model or has_model_catalog):
        raise ConfigPathError(
            "Config must specify either 'model'/'models' or 'model_stages', not both."
        )
    cfg = _resolve_enabled_catalog_entry(cfg, catalog_key="models", output_key="model")
    cfg = _resolve_enabled_catalog_entry(cfg, catalog_key="signals_catalog", output_key="signals")
    if cfg.get("model") not in (None, {}):
        cfg["model"] = _apply_model_outputs_aliases(cfg["model"], owner="model")
    if cfg.get("model_stages") not in (None, []):
        if not isinstance(cfg["model_stages"], list):
            raise ConfigPathError("'model_stages' must be a list when provided.")
        cfg["model_stages"] = [
            _apply_model_outputs_aliases(stage, owner=f"model_stages[{idx}]")
            for idx, stage in enumerate(cfg["model_stages"])
        ]
    if cfg.get("signals") not in (None, {}):
        cfg["signals"] = _apply_signals_outputs_aliases(cfg["signals"])
    cfg["config_path"] = str(path)
    return cfg


def inject_api_key_from_env(data: dict[str, Any]) -> None:
    """
    Hydrate provider credentials from environment variables when the config references them.
    """
    env_name = data.get("api_key_env")
    if env_name and not data.get("api_key"):
        data["api_key"] = os.getenv(env_name)


__all__ = [
    "ConfigPathError",
    "inject_api_key_from_env",
    "load_resolved_config",
    "load_yaml_mapping",
    "resolve_config_path",
]
