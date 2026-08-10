from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from src.experiments.orchestration.feature_stage import apply_feature_steps
from src.models.artifacts import load_model_bundle, predict_with_model_bundle


PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_PATH = (
    PROJECT_ROOT
    / "config/experiments/foundation_alpha/best_runs/"
      "model06_vwap32_rz128_20260801_191133_164398_3475c432/"
      "artifacts/models/model_06_vwap_plus_robust_z.pkl"
)

MANIFEST_PATH = MODEL_PATH.with_suffix(".manifest.json")

STRATEGY_CONFIG_PATH = (
    PROJECT_ROOT
    / "config/experiments/foundation_alpha/foundation_alpha_lab/FTMO/"
      "yaml_only_risk_overlay_v2/02_conservative_0600_daily015_total075.yaml"
)

DATA_PATH = (
    PROJECT_ROOT
    / "data/raw/dukascopy_30m_clean/ethusd_30m.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "integrations/ctrader_model06/standalone"
)


def find_lightgbm_booster(obj: Any, seen: set[int] | None = None):
    """
    Recursively find the underlying LightGBM Booster inside the saved bundle.
    Works with Booster, LGBMRegressor and nested dict/list/wrapper objects.
    """
    if seen is None:
        seen = set()

    if obj is None:
        return None

    obj_id = id(obj)
    if obj_id in seen:
        return None

    seen.add(obj_id)

    # Native lightgbm.Booster-like object
    if (
        hasattr(obj, "dump_model")
        and callable(getattr(obj, "dump_model"))
        and hasattr(obj, "model_to_string")
    ):
        return obj

    # sklearn LGBMRegressor / LGBMClassifier
    if hasattr(obj, "booster_"):
        try:
            booster = obj.booster_
            if booster is not None and hasattr(booster, "dump_model"):
                return booster
        except Exception:
            pass

    if isinstance(obj, dict):
        for key, value in obj.items():
            found = find_lightgbm_booster(value, seen)
            if found is not None:
                print(f"Booster found under dict key: {key!r}")
                return found

    if isinstance(obj, (list, tuple)):
        for value in obj:
            found = find_lightgbm_booster(value, seen)
            if found is not None:
                return found

    # Search wrapper object's fields
    try:
        values = vars(obj)
    except Exception:
        values = None

    if isinstance(values, dict):
        for key, value in values.items():
            if key.startswith("__"):
                continue

            found = find_lightgbm_booster(value, seen)
            if found is not None:
                print(
                    f"Booster found under object attribute: "
                    f"{type(obj).__name__}.{key}"
                )
                return found

    return None


def load_market_data(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)

    lower_to_original = {
        str(column).lower(): column
        for column in frame.columns
    }

    time_column = None

    for candidate in (
        "time",
        "timestamp",
        "datetime",
        "date",
        "open_time",
    ):
        if candidate in lower_to_original:
            time_column = lower_to_original[candidate]
            break

    if time_column is None:
        raise RuntimeError(
            f"Could not detect timestamp column. Columns={list(frame.columns)}"
        )

    rename = {}

    for expected in ("open", "high", "low", "close", "volume"):
        if expected not in lower_to_original:
            raise RuntimeError(
                f"Missing required column {expected!r}. "
                f"Columns={list(frame.columns)}"
            )

        rename[lower_to_original[expected]] = expected

    frame = frame.rename(columns=rename)

    timestamps = pd.to_datetime(
        frame[time_column],
        utc=True,
        errors="raise",
    )

    frame = frame[
        ["open", "high", "low", "close", "volume"]
    ].copy()

    frame.index = timestamps

    frame = frame.sort_index()

    if frame.index.has_duplicates:
        before = len(frame)
        frame = frame[~frame.index.duplicated(keep="last")]

        print(
            f"Removed {before - len(frame)} duplicate timestamps "
            f"from source data."
        )

    return frame


def main() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=" * 70)
    print("MODEL06 -> C# EXPORT")
    print("=" * 70)

    print(f"Model:    {MODEL_PATH}")
    print(f"Manifest: {MANIFEST_PATH}")
    print(f"Config:   {STRATEGY_CONFIG_PATH}")
    print(f"Data:     {DATA_PATH}")

    bundle = load_model_bundle(MODEL_PATH)

    manifest = json.loads(
        MANIFEST_PATH.read_text(
            encoding="utf-8",
        )
    )

    feature_order = list(
        manifest.get("feature_order")
        or manifest.get("feature_cols")
        or []
    )

    if len(feature_order) != 48:
        raise RuntimeError(
            f"Expected 48 model features, got {len(feature_order)}"
        )

    print()
    print(f"Model kind: {manifest.get('model_kind')}")
    print(f"Model name: {manifest.get('model_name')}")
    print(f"Feature count: {len(feature_order)}")
    print(f"Target horizon: {manifest.get('final_refit', {}).get('target_horizon')}")
    print(f"prob_scale: {manifest.get('prob_scale')}")

    booster = find_lightgbm_booster(bundle)

    if booster is None:
        raise RuntimeError(
            "Could not locate underlying LightGBM Booster inside model bundle."
        )

    print()
    print(f"Booster type: {type(booster)}")

    model_dump = booster.dump_model()

    tree_info = model_dump.get("tree_info", [])

    print(f"Tree count: {len(tree_info)}")
    print(
        f"Booster num_feature: "
        f"{model_dump.get('max_feature_idx', -1) + 1}"
    )

    if model_dump.get("max_feature_idx", -1) + 1 != 48:
        raise RuntimeError(
            "LightGBM feature count does not match manifest feature count."
        )

    # ------------------------------------------------------------
    # 1. Save complete LightGBM tree dump
    # ------------------------------------------------------------

    dump_path = (
        OUTPUT_DIR
        / "model06_lightgbm_dump.json"
    )

    dump_path.write_text(
        json.dumps(
            model_dump,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    print(f"Saved: {dump_path}")

    # ------------------------------------------------------------
    # 2. Save native LightGBM textual representation
    # ------------------------------------------------------------

    text_path = (
        OUTPUT_DIR
        / "model06_lightgbm_model.txt"
    )

    text_path.write_text(
        booster.model_to_string(),
        encoding="utf-8",
    )

    print(f"Saved: {text_path}")

    # ------------------------------------------------------------
    # 3. Save exact C# feature contract
    # ------------------------------------------------------------

    contract = {
        "model_name": manifest.get("model_name"),
        "model_kind": manifest.get("model_kind"),
        "feature_count": len(feature_order),
        "feature_order": feature_order,
        "prob_scale": manifest.get("prob_scale"),
        "target_horizon": (
            manifest
            .get("final_refit", {})
            .get("target_horizon")
        ),
        "tree_count": len(tree_info),
        "max_feature_idx": model_dump.get(
            "max_feature_idx"
        ),
        "objective": model_dump.get("objective"),
        "average_output": model_dump.get(
            "average_output"
        ),
    }

    contract_path = (
        OUTPUT_DIR
        / "model06_contract.json"
    )

    contract_path.write_text(
        json.dumps(
            contract,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    print(f"Saved: {contract_path}")

    # ------------------------------------------------------------
    # 4. Generate reference Python predictions
    #
    # These are what the future C# predictor MUST reproduce.
    # ------------------------------------------------------------

    strategy_config = yaml.safe_load(
        STRATEGY_CONFIG_PATH.read_text(
            encoding="utf-8",
        )
    ) or {}

    market = load_market_data(DATA_PATH)

    print()
    print(
        f"Raw market rows: {len(market):,}"
    )

    features = apply_feature_steps(
        market,
        list(
            strategy_config.get(
                "features",
                [],
            )
            or []
        ),
        asset="ETHUSD",
    )

    missing = [
        feature
        for feature in feature_order
        if feature not in features.columns
    ]

    if missing:
        raise RuntimeError(
            f"Feature pipeline missing: {missing}"
        )

    predicted = predict_with_model_bundle(
        features,
        bundle,
        asset="ETHUSD",
    )

    if "pred_ret" not in predicted.columns:
        raise RuntimeError(
            "Model bundle did not create pred_ret."
        )

    reference = predicted[
        feature_order + ["pred_ret"]
    ].copy()

    finite_mask = np.isfinite(
        reference[
            feature_order + ["pred_ret"]
        ]
        .to_numpy(dtype=float)
    ).all(axis=1)

    reference = reference.loc[
        finite_mask
    ]

    # Use recent 1000 valid rows for parity.
    reference = reference.tail(1000)

    reference.insert(
        0,
        "time",
        reference.index.astype(str),
    )

    reference_path = (
        OUTPUT_DIR
        / "model06_python_reference.csv"
    )

    reference.to_csv(
        reference_path,
        index=False,
        float_format="%.17g",
    )

    print(f"Saved: {reference_path}")
    print(
        f"Reference prediction rows: "
        f"{len(reference)}"
    )

    print()
    print("Prediction range:")
    print(
        f"  min  = "
        f"{reference['pred_ret'].min():.17g}"
    )
    print(
        f"  max  = "
        f"{reference['pred_ret'].max():.17g}"
    )
    print(
        f"  mean = "
        f"{reference['pred_ret'].mean():.17g}"
    )

    print()
    print("FEATURE ORDER")

    for index, name in enumerate(
        feature_order
    ):
        print(
            f"{index:02d}: {name}"
        )

    print()
    print("=" * 70)
    print("EXPORT COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()