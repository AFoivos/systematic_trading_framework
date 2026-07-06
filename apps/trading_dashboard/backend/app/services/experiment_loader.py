from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from app.core.paths import DashboardPaths, get_paths
from app.services.data_loader import DataLoader
from app.services.market_making_runs import latest_market_making_run
from app.services.schema_mapper import is_prediction_column


class ExperimentLoader:
    def __init__(self, paths: DashboardPaths | None = None) -> None:
        self.paths = paths or get_paths()

    def _experiment_roots(self) -> list[tuple[str, Path]]:
        roots = [
            ("", self.paths.experiments_root),
            ("bot", self.paths.project_root / "logs" / "bot"),
        ]
        unique_roots: list[tuple[str, Path]] = []
        seen: set[Path] = set()
        for source, root in roots:
            resolved = root.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            unique_roots.append((source, resolved))
        return unique_roots

    def _run_dirs(self) -> list[Path]:
        markers = {"run_metadata.json", "summary.json", "artifact_manifest.json", "study_summary.json"}
        run_dirs: list[Path] = []
        for _, root in self._experiment_roots():
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if path.is_file() and path.name in markers:
                    run_dirs.append(path.parent)
        return sorted(set(run_dirs))

    def run_id_for_path(self, path: Path) -> str:
        resolved = path.resolve()
        for source, root in self._experiment_roots():
            try:
                rel = resolved.relative_to(root)
            except ValueError:
                continue
            parts = (source, *rel.parts) if source else rel.parts
            return "__".join(parts)
        rel = resolved.relative_to(self.paths.experiments_root)
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
            processed_dataset = self._processed_dataset_for_run(run_dir, metadata=metadata, config=config) or {}
            runs.append(
                {
                    "run_id": self.run_id_for_path(run_dir),
                    "name": str(run_name or run_dir.name),
                    "run_type": "experiment",
                    "path": str(run_dir),
                    "created_at_utc": metadata.get("created_at_utc"),
                    "asset": data_cfg.get("symbol") or first_symbol,
                    "timeframe": data_cfg.get("interval"),
                    "config_hash_sha256": config_hash,
                    "processed_dataset_id": processed_dataset.get("id"),
                    "processed_dataset_path": processed_dataset.get("path"),
                    "has_trades": self._find_trades_path(run_dir) is not None,
                    "has_equity": (run_dir / "equity_curve.csv").exists(),
                    "metrics": summary.get("summary") or summary.get("study_summary") or {},
                }
            )
        market_making_run = self._market_making_summary()
        if market_making_run:
            runs.append(market_making_run)
        return sorted(runs, key=lambda item: str(item.get("created_at_utc") or ""), reverse=True)

    def load_run(self, run_id: str) -> dict[str, Any]:
        if run_id == "market_making__latest":
            market_making = self._market_making_summary()
            if not market_making:
                raise FileNotFoundError(f"Unknown experiment run_id: {run_id}")
            run_dir = latest_market_making_run(self.paths)
            if run_dir is None:
                raise FileNotFoundError(f"Unknown experiment run_id: {run_id}")
            return {
                "run_id": market_making["run_id"],
                "name": market_making["name"],
                "run_type": "market_making",
                "path": market_making["path"],
                "metadata": {},
                "config": {},
                "metrics": market_making["metrics"],
                "artifacts": self._report_files(run_dir),
                "available_predictions": [],
                "available_trades": [],
                "available_equity": None,
                "processed_dataset_id": None,
                "processed_dataset_path": None,
            }
        run_dir = self.resolve_run_dir(run_id)
        metadata = self._load_json(run_dir / "run_metadata.json")
        summary = self._load_json(run_dir / "summary.json")
        config = self._load_yaml(run_dir / "config_used.yaml")
        manifest = self._load_json(run_dir / "artifact_manifest.json")
        artifact_files = self._artifact_files(manifest, run_dir)
        processed_dataset = self._processed_dataset_for_run(run_dir, metadata=metadata, config=config) or {}
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
            "run_type": "experiment",
            "path": str(run_dir),
            "metadata": metadata,
            "config": config,
            "metrics": summary,
            "artifacts": artifact_files,
            "available_predictions": predictions,
            "available_trades": [str(self._find_trades_path(run_dir))] if self._find_trades_path(run_dir) else [],
            "available_equity": str(run_dir / "equity_curve.csv") if (run_dir / "equity_curve.csv").exists() else None,
            "processed_dataset_id": processed_dataset.get("id"),
            "processed_dataset_path": processed_dataset.get("path"),
        }

    def _market_making_summary(self) -> dict[str, Any] | None:
        run_dir = latest_market_making_run(self.paths)
        if run_dir is None:
            return None
        summary = self._load_json(run_dir / "summary.json")
        if not run_dir.exists() or not summary:
            return None
        trades_path = run_dir / "trades.csv"
        orderbook_path = run_dir / "orderbook_events.csv"
        quote_events_path = run_dir / "quote_events.csv"
        event_path = orderbook_path if orderbook_path.exists() else quote_events_path
        asset = None
        created_at = None
        if event_path.exists():
            orderbook = pd.read_csv(event_path, nrows=1)
            if not orderbook.empty:
                asset = orderbook.iloc[0].get("symbol")
            tail = pd.read_csv(event_path, usecols=["timestamp"]).tail(1)
            if not tail.empty:
                created_at = str(tail.iloc[-1]["timestamp"])
        if asset is None and trades_path.exists():
            trades = pd.read_csv(trades_path, nrows=1)
            if not trades.empty:
                asset = trades.iloc[0].get("symbol")
        return {
            "run_id": "market_making__latest",
            "name": "market_making_latest",
            "run_type": "market_making",
            "path": str(run_dir),
            "created_at_utc": created_at,
            "asset": str(asset) if asset else None,
            "timeframe": "event",
            "config_hash_sha256": None,
            "processed_dataset_id": None,
            "processed_dataset_path": None,
            "has_trades": False,
            "has_equity": False,
            "metrics": summary,
        }

    def _processed_dataset_for_run(
        self,
        run_dir: Path,
        *,
        metadata: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, str] | None:
        data_cfg = dict((metadata.get("config_hash_input", {}) or {}).get("data", {}) or config.get("data", {}) or {})
        storage = dict(data_cfg.get("storage", {}) or {})
        if not storage.get("save_processed"):
            return None
        base_dataset_id = str(storage.get("dataset_id") or "").strip()
        if not base_dataset_id:
            return None
        datasets = DataLoader(self.paths).discover_datasets()
        candidates: list[dict[str, str]] = []
        for dataset in datasets:
            if dataset.stage != "processed" or not dataset.metadata_path or not dataset.metadata_path.exists():
                continue
            metadata_payload = self._load_json(dataset.metadata_path)
            context = dict(metadata_payload.get("context", {}) or {})
            candidate_base = str(context.get("base_dataset_id") or "")
            candidate_dataset_id = str(metadata_payload.get("dataset_id") or "")
            if candidate_base == base_dataset_id or candidate_dataset_id.startswith(f"{base_dataset_id}_"):
                candidates.append({"id": dataset.id, "path": str(dataset.path)})
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: item["id"], reverse=True)[0]

    @staticmethod
    def _report_files(run_dir: Path) -> list[dict[str, Any]]:
        if not run_dir.exists():
            return []
        out: list[dict[str, Any]] = []
        for path in sorted(run_dir.rglob("*")):
            if not path.is_file():
                continue
            out.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "exists": True,
                    "bytes": path.stat().st_size,
                    "sha256": None,
                }
            )
        return out

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
