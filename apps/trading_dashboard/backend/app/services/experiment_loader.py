from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from app.core.paths import DashboardPaths, get_paths
from app.services.schema_mapper import is_prediction_column


class ExperimentLoader:
    def __init__(self, paths: DashboardPaths | None = None) -> None:
        self.paths = paths or get_paths()

    def _run_dirs(self) -> list[Path]:
        root = self.paths.experiments_root
        if not root.exists():
            return []
        markers = {"run_metadata.json", "summary.json", "artifact_manifest.json", "study_summary.json"}
        run_dirs: list[Path] = []
        for path in root.rglob("*"):
            if path.is_file() and path.name in markers:
                run_dirs.append(path.parent)
        return sorted(set(run_dirs))

    def run_id_for_path(self, path: Path) -> str:
        rel = path.relative_to(self.paths.experiments_root)
        return "__".join(rel.parts)

    def resolve_run_dir(self, run_id: str) -> Path:
        for path in self._run_dirs():
            if self.run_id_for_path(path) == run_id or path.name == run_id:
                return path
        raise FileNotFoundError(f"Unknown experiment run_id: {run_id}")

    def list_runs(self) -> list[dict[str, Any]]:
        runs: list[dict[str, Any]] = []
        for run_dir in self._run_dirs():
            metadata = self._load_json(run_dir / "run_metadata.json")
            summary = self._load_json(run_dir / "summary.json")
            config = self._load_yaml(run_dir / "config_used.yaml")
            config_hash = metadata.get("config_hash_sha256")
            run_name = (
                dict(metadata.get("config_hash_input", {}) or {})
                .get("logging", {})
                .get("run_name")
            )
            data_cfg = dict((metadata.get("config_hash_input", {}) or {}).get("data", {}) or config.get("data", {}) or {})
            symbols = data_cfg.get("symbols")
            first_symbol = symbols[0] if isinstance(symbols, list) and symbols else symbols if isinstance(symbols, str) else None
            runs.append(
                {
                    "run_id": self.run_id_for_path(run_dir),
                    "name": str(run_name or run_dir.name),
                    "path": str(run_dir),
                    "created_at_utc": metadata.get("created_at_utc"),
                    "asset": data_cfg.get("symbol") or first_symbol,
                    "timeframe": data_cfg.get("interval"),
                    "config_hash_sha256": config_hash,
                    "has_trades": self._find_trades_path(run_dir) is not None,
                    "has_equity": (run_dir / "equity_curve.csv").exists(),
                    "metrics": summary.get("summary") or summary.get("study_summary") or {},
                }
            )
        return sorted(runs, key=lambda item: str(item.get("created_at_utc") or ""), reverse=True)

    def load_run(self, run_id: str) -> dict[str, Any]:
        run_dir = self.resolve_run_dir(run_id)
        metadata = self._load_json(run_dir / "run_metadata.json")
        summary = self._load_json(run_dir / "summary.json")
        config = self._load_yaml(run_dir / "config_used.yaml")
        manifest = self._load_json(run_dir / "artifact_manifest.json")
        artifact_files = self._artifact_files(manifest, run_dir)
        model_meta = dict(metadata.get("model_meta", {}) or {})
        predictions = sorted(
            {
                str(column)
                for column in model_meta.get("feature_cols", [])
                if is_prediction_column(str(column))
            }
            | {
                str(model_meta[key])
                for key in ("pred_prob_col", "pred_ret_col", "pred_vol_col")
                if model_meta.get(key)
            }
        )
        return {
            "run_id": self.run_id_for_path(run_dir),
            "name": run_dir.name,
            "path": str(run_dir),
            "metadata": metadata,
            "config": config,
            "metrics": summary,
            "artifacts": artifact_files,
            "available_predictions": predictions,
            "available_trades": [str(self._find_trades_path(run_dir))] if self._find_trades_path(run_dir) else [],
            "available_equity": str(run_dir / "equity_curve.csv") if (run_dir / "equity_curve.csv").exists() else None,
        }

    def _artifact_files(self, manifest: dict[str, Any], run_dir: Path) -> list[dict[str, Any]]:
        files = dict(manifest.get("files", {}) or {})
        out: list[dict[str, Any]] = []
        for name, payload in sorted(files.items()):
            if not isinstance(payload, dict):
                continue
            raw_path = payload.get("path")
            resolved = self.paths.resolve_project_path(raw_path) if raw_path else run_dir / str(name)
            if not resolved.exists():
                fallback = run_dir / resolved.name
                resolved = fallback if fallback.exists() else resolved
            out.append(
                {
                    "name": name,
                    "path": str(resolved),
                    "exists": resolved.exists(),
                    "bytes": payload.get("bytes"),
                    "sha256": payload.get("sha256"),
                }
            )
        return out

    def _find_trades_path(self, run_dir: Path) -> Path | None:
        candidates = [
            run_dir / "report_assets" / "trades.csv",
            run_dir / "trades.csv",
            run_dir / "report_assets" / "trade_events.csv",
        ]
        return next((path for path in candidates if path.exists()), None)

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        return payload if isinstance(payload, dict) else {}


def read_csv_timeseries(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)
