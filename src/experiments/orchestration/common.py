from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import pandas as pd

from src.experiments.schemas import StorageContext
from src.src_data.storage import asset_frames_to_long_frame


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", str(value)).strip("_").lower()
    return slug or "dataset"


def stable_json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def pit_config_hash(pit_cfg: dict[str, Any] | None) -> str:
    payload = stable_json_dumps(dict(pit_cfg or {})).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def is_sensitive_key(key: str) -> bool:
    k = str(key).lower()
    if k in {"api_key", "token", "secret", "password", "access_key"}:
        return True
    return k.endswith("_key") or k.endswith("_token") or k.endswith("_secret")


def redact_sensitive_values(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if is_sensitive_key(str(k)):
                out[str(k)] = "***REDACTED***" if v is not None else None
            else:
                out[str(k)] = redact_sensitive_values(v)
        return out
    if isinstance(value, list):
        return [redact_sensitive_values(v) for v in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive_values(v) for v in value)
    return value


def resolve_symbols(data_cfg: dict[str, Any]) -> list[str]:
    if data_cfg.get("symbol") is not None:
        return [str(data_cfg["symbol"])]
    return [str(symbol) for symbol in data_cfg.get("symbols", [])]


def default_dataset_id(data_cfg: dict[str, Any]) -> str:
    symbols = resolve_symbols(data_cfg)
    symbol_part = "_".join(slugify(symbol) for symbol in symbols[:6])
    if len(symbols) > 6:
        symbol_part = f"{symbol_part}_plus_{len(symbols) - 6}"
    pit_hash_short = pit_config_hash(dict(data_cfg.get("pit", {}) or {}))[:8]
    return "_".join(
        [
            slugify(data_cfg.get("source", "source")),
            slugify(data_cfg.get("interval", "interval")),
            symbol_part,
            slugify(data_cfg.get("start") or "start"),
            slugify(data_cfg.get("end") or "open"),
            f"pit_{pit_hash_short}",
        ]
    )


def build_storage_context(
    data_cfg: dict[str, Any],
    *,
    symbols: list[str],
    pit_cfg: dict[str, Any],
) -> StorageContext:
    return StorageContext(
        symbols=list(symbols),
        source=data_cfg.get("source"),
        interval=data_cfg.get("interval"),
        start=data_cfg.get("start"),
        end=data_cfg.get("end"),
        pit=dict(pit_cfg or {}),
        pit_hash_sha256=pit_config_hash(pit_cfg),
    )


def snapshot_context_matches(snapshot_meta: dict[str, Any], expected_context: dict[str, Any]) -> bool:
    snapshot_context = dict(snapshot_meta.get("context", {}) or {})
    return stable_json_dumps(snapshot_context) == stable_json_dumps(expected_context)


def align_asset_column(
    asset_frames: dict[str, pd.DataFrame],
    *,
    column: str,
    how: str,
) -> pd.DataFrame:
    series_map: dict[str, pd.Series] = {}
    for asset, df in sorted(asset_frames.items()):
        if column not in df.columns:
            raise KeyError(f"Column '{column}' not found for asset '{asset}'.")
        series_map[asset] = df[column].astype(float)

    out = pd.concat(series_map, axis=1, join=how).sort_index()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)
    out.columns = [str(col) for col in out.columns]
    return out


def data_stats_payload(data: pd.DataFrame | dict[str, pd.DataFrame]) -> dict[str, Any]:
    if isinstance(data, pd.DataFrame):
        return {
            "asset_count": 1,
            "rows": int(len(data)),
            "columns": int(len(data.columns)),
            "start": str(data.index.min()) if not data.empty else None,
            "end": str(data.index.max()) if not data.empty else None,
        }

    long_frame = asset_frames_to_long_frame(data)
    return {
        "asset_count": int(len(data)),
        "rows": int(len(long_frame)),
        "columns": int(len(long_frame.columns)),
        "assets": sorted(data),
        "rows_by_asset": {asset: int(len(df)) for asset, df in sorted(data.items())},
        "start": str(long_frame["timestamp"].min()) if not long_frame.empty else None,
        "end": str(long_frame["timestamp"].max()) if not long_frame.empty else None,
    }


def resolved_feature_columns(model_meta: dict[str, Any]) -> list[str] | dict[str, list[str]] | None:
    if not model_meta:
        return None
    if "feature_cols" in model_meta:
        return list(model_meta.get("feature_cols", []) or [])
    if "per_asset" in model_meta:
        return {
            asset: list(meta.get("feature_cols", []) or [])
            for asset, meta in sorted(dict(model_meta.get("per_asset", {}) or {}).items())
        }
    return None


__all__ = [
    "align_asset_column",
    "build_storage_context",
    "data_stats_payload",
    "default_dataset_id",
    "is_sensitive_key",
    "pit_config_hash",
    "redact_sensitive_values",
    "resolve_symbols",
    "resolved_feature_columns",
    "slugify",
    "snapshot_context_matches",
    "stable_json_dumps",
]
