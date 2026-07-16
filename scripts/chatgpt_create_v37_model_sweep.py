from __future__ import annotations

from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = REPO_ROOT / "config/experiments/foundation_alpha/BEST/ethusd/BEST_ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml"
RAW_DIR = REPO_ROOT / "data/raw/dukascopy_30m_clean"
OUT_DIR = REPO_ROOT / "config/experiments/foundation_alpha/asset_sweep_v3_7"

BASE_ID = "ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid"
SUFFIX = "30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid"


def asset_from_csv(path: Path) -> str:
    stem = path.stem
    if not stem.endswith("_30m"):
        raise ValueError(f"Unexpected raw file name: {path.name}")
    asset = stem.removesuffix("_30m")
    if not asset:
        raise ValueError(f"Missing asset symbol in raw file name: {path.name}")
    return asset


def build_config(base: dict, asset: str, csv_path: Path) -> dict:
    asset_upper = asset.upper()
    run_id = f"{asset}_{SUFFIX}"

    cfg = yaml.safe_load(yaml.safe_dump(base, sort_keys=False))

    cfg["strategy"]["name"] = run_id
    cfg["strategy"]["assets"] = [asset_upper]
    cfg["strategy"]["description"] = (
        f"{asset_upper} 30m asset-sweep clone of the ETHUSD v3.7 LightGBM structured-tail champion. "
        "Feature pipeline, target, split, signal gates, risk, backtest, diagnostics, and model params "
        "are kept frozen except for asset symbol and data path."
    )

    cfg["data"]["symbol"] = asset_upper
    cfg["data"]["storage"]["dataset_id"] = run_id
    cfg["data"]["storage"]["load_path"] = str(csv_path.relative_to(REPO_ROOT))

    for step in cfg.get("features", []) or []:
        if step.get("step") == "indicator_pullback":
            step.setdefault("params", {})["asset_vocab"] = [asset_upper]

    cfg["logging"]["run_name"] = run_id
    return cfg


def main() -> None:
    if not BASE_PATH.exists():
        raise SystemExit(f"Base config not found: {BASE_PATH.relative_to(REPO_ROOT)}")
    if not RAW_DIR.exists():
        raise SystemExit(f"Raw directory not found: {RAW_DIR.relative_to(REPO_ROOT)}")

    with BASE_PATH.open("r", encoding="utf-8") as fh:
        base = yaml.safe_load(fh)

    csvs = sorted(RAW_DIR.glob("*_30m.csv"))
    if not csvs:
        raise SystemExit(f"No *_30m.csv files found under {RAW_DIR.relative_to(REPO_ROOT)}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    skipped: list[str] = []
    for csv_path in csvs:
        asset = asset_from_csv(csv_path)
        run_id = f"{asset}_{SUFFIX}"
        out_path = OUT_DIR / f"{run_id}.yaml"
        if out_path.exists():
            skipped.append(str(out_path.relative_to(REPO_ROOT)))
            continue

        cfg = build_config(base, asset, csv_path)
        with out_path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(cfg, fh, sort_keys=False, allow_unicode=True, width=1000)
        written.append(str(out_path.relative_to(REPO_ROOT)))

    print({"ok": True, "base": str(BASE_PATH.relative_to(REPO_ROOT)), "count": len(written), "written": written, "skipped_existing": skipped})


if __name__ == "__main__":
    main()
