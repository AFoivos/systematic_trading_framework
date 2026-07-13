from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import yaml

REPO_ROOT = Path("/workspace")
BASE = REPO_ROOT / "config/experiments/foundation_alpha/BEST/ethusd/optuna_BEST_ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml"
OUT = REPO_ROOT / "config/experiments/foundation_alpha/ethusd/v3_7_validation"

PREFIX = "ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid"

def clone(base: dict, suffix: str, description: str) -> dict:
    cfg = deepcopy(base)
    name = f"{PREFIX}_{suffix}"
    cfg["strategy"]["name"] = name
    cfg["strategy"]["description"] = description
    cfg["data"]["storage"]["dataset_id"] = name
    cfg["logging"]["run_name"] = name
    cfg["logging"]["output_dir"] = "/workspace/logs/experiments"
    return cfg

def remove_features(cfg: dict, names: list[str]) -> None:
    remove = set(names)
    cfg["model"]["feature_cols"] = [c for c in cfg["model"]["feature_cols"] if c not in remove]

def remove_filter(cfg: dict, col: str, op: str | None = None) -> None:
    filters = cfg["signals"]["params"].get("activation_filters", [])
    cfg["signals"]["params"]["activation_filters"] = [
        f for f in filters
        if not (f.get("col") == col and (op is None or f.get("op") == op))
    ]

def main() -> None:
    with BASE.open("r", encoding="utf-8") as fh:
        base = yaml.safe_load(fh)

    variants: list[tuple[str, dict]] = []

    cfg = clone(
        base,
        "tail_holdout_6folds",
        "Frozen v3.7 champion evaluated only on the previously untouched post-2024-09 tail. "
        "Model, features, thresholds, gates, costs and holding logic remain unchanged."
    )
    cfg["model"]["split"].update(
        train_size=78840,
        test_size=4380,
        step_size=4380,
        expanding=True,
        max_folds=6,
        purge_bars=24,
        embargo_bars=24,
    )
    variants.append(("tail_holdout_6folds", cfg))

    cfg = clone(
        base,
        "ablation_no_raw_atr",
        "Feature ablation removing raw price-unit ATR from model inputs while retaining ATN-normalized/rank features."
    )
    remove_features(cfg, ["atr_48"])
    variants.append(("ablation_no_raw_atr", cfg))

    cfg = clone(
        base,
        "ablation_deduplicated_features",
        "Feature ablation removing near-duplicate return and ATR representations while keeping the original model and signal contract."
    )
    remove_features(cfg, ["ret_1", "rolling_return_24", "rolling_return_48", "atr_pct"])
    variants.append(("ablation_deduplicated_features", cfg))

    cfg = clone(
        base,
        "ablation_normalized_vol_only",
        "Stationarity-focused ablation removing raw ATR, raw rolling volatility levels, raw Bollinger bandwidth and duplicate ATR percentage."
    )
    remove_features(
        cfg,
        ["atr_48", "atr_pct", "vol_rolling_24", "vol_rolling_48", "vol_rolling_96",
         "vol_rolling_192", "bollinger_bandwidth"],
    )
    variants.append(("ablation_normalized_vol_only", cfg))

    cfg = clone(
        base,
        "gate_ablation_no_atr_rank",
        "Signal-gate ablation removing both ATR percentile bounds while preserving range and Bollinger expansion gates."
    )
    remove_filter(cfg, "atr_pct_rank_192")
    variants.append(("gate_ablation_no_atr_rank", cfg))

    cfg = clone(
        base,
        "gate_ablation_no_range",
        "Signal-gate ablation removing the range-to-ATR expansion gate while preserving ATR percentile and Bollinger gates."
    )
    remove_filter(cfg, "range_to_atr")
    variants.append(("gate_ablation_no_range", cfg))

    cfg = clone(
        base,
        "gate_ablation_no_bollingen_rank",
        "Signal-gate ablation removing the Bollinger bandwidth percentile gate while preserving ATR percentile and range gates."
    )
    remove_filter(cfg, "bollinger_bandwidth_rank_192")
    variants.append(("gate_ablation_no_bollingen_rank", cfg))

    cfg = clone(
        base,
        "gate_ablation_no_filters",
        "Signal-gate ablation using the optimized asymmetric forecast thresholds without any activation filters."
    )
    cfg["signals"]["params"]["activation_filters"] = []
    variants.append(("gate_ablation_no_filters", cfg))

    cfg = clone(
        base,
        "side_ablation_long_only",
        "Long-only decomposition with the original long threshold and all original activation filters."
    )
    cfg["signals"]["params"]["mode"] = "long_only"
    cfg["backtest"]["allow_short"] = False
    variants.append(("side_ablation_long_only", cfg))

    cfg = clone(
        base,
        "side_ablation_short_only",
        "Short-only decomposition with the original short threshold and all original activation filters."
    )
    cfg["signals"]["params"]["mode"] = "short_only"
    cfg["backtest"]["allow_short"] = True
    variants.append(("side_ablation_short_only", cfg))

    cfg = clone(
        base,
        "robustness_cost_delay",
        "Frozen champion with robustness diagnostics enabled for cost multipliers and one/two-bar execution delays."
   )
    cfg["diagnostics"]["robustness"].update(
        enabled=True,
        cost_multipliers=[1.0, 2.0, 3.0, 5.0],
        entry_delay_bars=[1, 2],
        walk_forward_frequency="YE",
        gap_loss_per_exposure=0.0,
        max_gap_multiple=3.0,
        strict_no_remap=True,
    )
    variants.append(("robustness_cost_delay", cfg))

    OUT.mkdir(parents=True, exist_ok=True)
    written = []
    for suffix, cfg in variants:
        path = OUT / f"{PREFIX}_{suffix}.yaml"
        with path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(cfg, fh, sort_keys=False, allow_unicode=True, width=1000)
        # Parse-back validation.
        with path.open("r", encoding="utf-8") as fh:
            parsed = yaml.safe_load(fh)
        assert parsed["strategy"]["name"].endswith(suffix)
        assert parsed["logging"]["run_name"] == parsed["strategy"]["name"]
        assert parsed["model"]["target"]["horizon_bars"] == 24
        assert parsed["model"]["split"]["purge_bars"] == 24
        assert parsed["model"]["split"]["embargo_bars"] == 24
        written.append(str(path.relative_to(REPO_ROOT)))

    print({"ok": True, "count": len(written), "written": written})

if __name__ == "__main__":
    main()
