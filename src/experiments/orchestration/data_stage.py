from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from src.experiments.orchestration.common import (
    build_storage_context,
    default_dataset_id,
    resolve_symbols,
    snapshot_context_matches,
)
from src.src_data.storage import load_dataset_snapshot, save_dataset_snapshot


SingleAssetLoader = Callable[..., pd.DataFrame]
PanelLoader = Callable[..., dict[str, pd.DataFrame]]
PitFn = Callable[..., tuple[pd.DataFrame, dict[str, Any]]]
ValidateFrameFn = Callable[[pd.DataFrame], Any]


def load_asset_frames(
    data_cfg: dict[str, Any],
    *,
    load_ohlcv_fn: SingleAssetLoader,
    load_ohlcv_panel_fn: PanelLoader,
    apply_pit_hardening_fn: PitFn,
    validate_ohlcv_fn: ValidateFrameFn,
    validate_data_contract_fn: ValidateFrameFn,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """
    Load raw market data, enforce PIT hardening, and optionally hydrate from snapshot storage.
    """
    symbols = resolve_symbols(data_cfg)
    if not symbols:
        raise ValueError("No symbols resolved from config.")

    storage_cfg = dict(data_cfg.get("storage", {}) or {})
    storage_mode = str(storage_cfg.get("mode", "live"))
    dataset_id = str(storage_cfg.get("dataset_id") or default_dataset_id(data_cfg))
    raw_dir = storage_cfg.get("raw_dir", "data/raw")
    load_path = storage_cfg.get("load_path")
    pit_cfg = dict(data_cfg.get("pit", {}) or {})
    expected_context_obj = build_storage_context(data_cfg, symbols=symbols, pit_cfg=pit_cfg)
    expected_context = expected_context_obj.to_dict()
    storage_meta: dict[str, Any] = {
        "mode": storage_mode,
        "dataset_id": dataset_id,
        "loaded_from_cache": False,
        "saved_raw_snapshot": None,
    }

    asset_frames: dict[str, pd.DataFrame] | None = None
    if storage_mode in {"live_or_cached", "cached_only"}:
        try:
            cached_frames, snapshot_meta = load_dataset_snapshot(
                stage="raw",
                root_dir=raw_dir,
                dataset_id=dataset_id,
                load_path=load_path,
            )
            if not snapshot_context_matches(snapshot_meta, expected_context):
                storage_meta["cache_context_mismatch"] = True
                storage_meta["loaded_snapshot"] = snapshot_meta
                if storage_mode == "cached_only":
                    raise ValueError(
                        "Cached dataset snapshot context does not match the requested data/PIT configuration."
                    )
            else:
                asset_frames = cached_frames
                storage_meta["loaded_from_cache"] = True
                storage_meta["loaded_snapshot"] = snapshot_meta
        except FileNotFoundError:
            if storage_mode == "cached_only":
                raise

    if asset_frames is None:
        load_kwargs = {
            "start": data_cfg.get("start"),
            "end": data_cfg.get("end"),
            "interval": data_cfg.get("interval", "1d"),
            "source": data_cfg.get("source", "yahoo"),
            "api_key": data_cfg.get("api_key"),
        }
        raw_frames = (
            {symbols[0]: load_ohlcv_fn(symbol=symbols[0], **load_kwargs)}
            if len(symbols) == 1
            else load_ohlcv_panel_fn(symbols=symbols, **load_kwargs)
        )

        pit_meta_by_asset: dict[str, Any] = {}
        asset_frames = {}
        for asset, df in sorted(raw_frames.items()):
            hardened_df, pit_meta = apply_pit_hardening_fn(df, pit_cfg=pit_cfg, symbol=asset)
            validate_ohlcv_fn(hardened_df)
            validate_data_contract_fn(hardened_df)
            asset_frames[asset] = hardened_df
            pit_meta_by_asset[asset] = pit_meta

        storage_meta["pit_meta_by_asset"] = pit_meta_by_asset
        if bool(storage_cfg.get("save_raw", False)):
            storage_meta["saved_raw_snapshot"] = save_dataset_snapshot(
                asset_frames,
                dataset_id=dataset_id,
                stage="raw",
                root_dir=raw_dir,
                context=expected_context,
                overwrite=True,
            )
    else:
        for _, df in sorted(asset_frames.items()):
            validate_ohlcv_fn(df)
            validate_data_contract_fn(df)

    return asset_frames, storage_meta


def save_processed_snapshot_if_enabled(
    asset_frames: dict[str, pd.DataFrame],
    *,
    data_cfg: dict[str, Any],
    config_hash_sha256: str,
    feature_steps: list[dict[str, Any]],
) -> dict[str, Any] | None:
    storage_cfg = dict(data_cfg.get("storage", {}) or {})
    if not bool(storage_cfg.get("save_processed", False)):
        return None

    dataset_id = str(storage_cfg.get("dataset_id") or default_dataset_id(data_cfg))
    processed_dataset_id = f"{dataset_id}_{config_hash_sha256[:8]}"
    return save_dataset_snapshot(
        asset_frames,
        dataset_id=processed_dataset_id,
        stage="processed",
        root_dir=storage_cfg.get("processed_dir", "data/processed"),
        context={
            "base_dataset_id": dataset_id,
            "config_hash_sha256": config_hash_sha256,
            "feature_steps": list(feature_steps),
        },
        overwrite=True,
    )


__all__ = ["load_asset_frames", "save_processed_snapshot_if_enabled"]
