from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.collect_kraken_orderbook import collect_orderbook, parse_collector_config
from scripts.run_market_making_moment_experiment import run_experiment as run_moment_experiment
from scripts.run_market_making_paper import resolve_output_dir, run_csv_orderbook_replay


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a staged market-making research pipeline from one YAML config.")
    parser.add_argument("--config", required=True)
    args = parser.parse_args(argv)

    cfg_path = Path(args.config)
    cfg = _load_config(cfg_path)
    result = run_pipeline(cfg, config_path=cfg_path)
    manifest = result.get("manifest_path")
    print(f"Market-making pipeline complete: {manifest or 'manifest disabled'}")
    for name, stage in result["stages"].items():
        print(f"{name}: {stage.get('status')}")
    return 0


def run_pipeline(cfg: Mapping[str, Any], *, config_path: str | Path) -> dict[str, Any]:
    """Run enabled market-making stages from a single orchestration config."""
    cfg_dict = dict(cfg)
    data_cfg = _mapping(cfg_dict.get("data"))
    pipeline_cfg = _mapping(cfg_dict.get("pipeline"))
    stages: dict[str, Any] = {}

    orderbook_events_path = _optional_path(_data_value(data_cfg, "orderbook_events_path"))
    quote_events_paths = _path_list(_data_value(data_cfg, "quote_events_paths"))
    trades_path = _optional_path(_data_value(data_cfg, "trades_path"))

    collect_cfg = _stage_config(cfg_dict, "collect_orderbook", _mapping(data_cfg.get("collection")), _mapping(data_cfg.get("collect")))
    if _enabled(collect_cfg):
        _stage_print("collect_orderbook", "starting")
        collect_result = _run_collect_stage(cfg_dict, collect_cfg)
        orderbook_events_path = Path(collect_result["output_path"])
        stages["collect_orderbook"] = collect_result
        _stage_print("collect_orderbook", f"completed events={collect_result.get('events_written')}")
    else:
        stages["collect_orderbook"] = {"status": "skipped", "reason": "enabled=false"}
        _stage_print("collect_orderbook", "skipped")

    paper_cfg = _stage_config(cfg_dict, "paper_replay")
    paper_output_dir: Path | None = None
    if _enabled(paper_cfg):
        _stage_print("paper_replay", "starting")
        input_events = _required_existing_path(
            paper_cfg.get("input_events_path") or orderbook_events_path,
            label="paper_replay.input_events_path or data.orderbook_events_path",
        )
        paper_output_dir = _resolve_paper_output_dir(cfg_dict, paper_cfg)
        summary = run_csv_orderbook_replay(cfg_dict, input_events=input_events, output_dir=paper_output_dir)
        stages["paper_replay"] = {
            "status": "completed",
            "input_events_path": str(input_events),
            "output_dir": str(paper_output_dir),
            "summary": summary,
        }
        _stage_print("paper_replay", f"completed output_dir={paper_output_dir}")
        if bool(paper_cfg.get("use_outputs_for_moment", paper_cfg.get("use_replay_outputs_for_moment", True))):
            replay_quotes = paper_output_dir / "quote_events.csv"
            replay_trades = paper_output_dir / "trades.csv"
            if replay_quotes.exists():
                quote_events_paths = [replay_quotes]
            if replay_trades.exists():
                trades_path = replay_trades
    else:
        stages["paper_replay"] = {"status": "skipped", "reason": "enabled=false"}
        _stage_print("paper_replay", "skipped")

    moment_stage_cfg = _stage_config(cfg_dict, "moment_experiment")
    moment_model_cfg = _mapping(cfg_dict.get("moment"))
    moment_default_enabled = bool(moment_model_cfg.get("enabled", False))
    if _enabled(moment_stage_cfg, default=moment_default_enabled):
        _stage_print("moment_experiment", "starting")
        moment_cfg = _build_moment_experiment_config(
            cfg_dict,
            orderbook_events_path=_required_existing_path(orderbook_events_path, label="data.orderbook_events_path"),
            quote_events_paths=_required_quote_paths(quote_events_paths),
            trades_path=trades_path,
        )
        artifacts = run_moment_experiment(moment_cfg, config_path=config_path)
        stages["moment_experiment"] = {
            "status": "completed",
            "run_dir": artifacts.get("run_dir"),
            "artifacts": artifacts,
        }
        _stage_print("moment_experiment", f"completed run_dir={artifacts.get('run_dir')}")
    else:
        stages["moment_experiment"] = {"status": "skipped", "reason": "enabled=false"}
        _stage_print("moment_experiment", "skipped")

    result: dict[str, Any] = {
        "config_path": str(config_path),
        "stages": stages,
    }
    if bool(pipeline_cfg.get("write_manifest", True)):
        manifest_dir = _resolve_pipeline_output_dir(cfg_dict)
        manifest_dir.mkdir(parents=True, exist_ok=True)
        config_copy = manifest_dir / "pipeline_config_used.yaml"
        config_copy.write_text(yaml.safe_dump(cfg_dict, sort_keys=False), encoding="utf-8")
        manifest_path = manifest_dir / "pipeline_manifest.json"
        payload = {
            "config_path": str(config_path),
            "config_copy": str(config_copy),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "stages": stages,
        }
        manifest_path.write_text(json.dumps(_jsonable(payload), indent=2), encoding="utf-8")
        result["manifest_path"] = str(manifest_path)
        result["manifest_dir"] = str(manifest_dir)
    return result


def _stage_print(stage: str, message: str) -> None:
    print(f"[market-making-pipeline] {stage}: {message}", flush=True)


def _run_collect_stage(cfg: Mapping[str, Any], collect_cfg: Mapping[str, Any]) -> dict[str, Any]:
    collector_cfg = deepcopy(dict(cfg))
    execution = dict(_mapping(collector_cfg.get("execution")))
    for key in ("symbol", "depth", "reconnect", "max_events"):
        if key in collect_cfg:
            execution[key] = collect_cfg[key]
    execution.setdefault("mode", "data_only")
    execution.setdefault("venue", "kraken_spot_public")
    collector_cfg["execution"] = execution
    output_path = collect_cfg.get("output_path")
    parsed = parse_collector_config(collector_cfg, output_override=str(output_path) if output_path else None)
    events = asyncio.run(collect_orderbook(parsed))
    return {
        "status": "completed",
        "events_written": int(events),
        "output_path": str(parsed.output_path),
    }


def _resolve_paper_output_dir(cfg: Mapping[str, Any], paper_cfg: Mapping[str, Any]) -> Path:
    explicit = paper_cfg.get("output_dir")
    if explicit:
        return Path(str(explicit))
    timestamped = bool(paper_cfg.get("timestamped_output", True))
    return resolve_output_dir(
        dict(cfg),
        timestamped_output=timestamped,
        data_source=str(paper_cfg.get("data_source", "kraken_orderbook_csv")),
        fill_model=str(paper_cfg.get("fill_model", "top_of_book_crossing")),
    )


def _build_moment_experiment_config(
    cfg: Mapping[str, Any],
    *,
    orderbook_events_path: Path,
    quote_events_paths: Sequence[Path],
    trades_path: Path | None,
) -> dict[str, Any]:
    data_cfg = _mapping(cfg.get("data"))
    dataset_cfg = _mapping(data_cfg.get("moment_dataset"))
    fees_cfg = _mapping(cfg.get("fees"))
    market_cfg = dict(_mapping(cfg.get("market_making")))
    market_cfg.setdefault("maker_fee_bps", float(fees_cfg.get("maker_fee_bps", 0.0)))

    model_cfg = dict(_mapping(cfg.get("model")))
    moment_cfg = {key: value for key, value in _mapping(cfg.get("moment")).items() if key != "enabled"}
    model_cfg.update(moment_cfg)

    filter_cfg = dict(_mapping(cfg.get("filter")))
    filter_cfg.update(_mapping(cfg.get("moment_filter")))

    output_cfg = dict(_mapping(cfg.get("output")))
    output_cfg.update(_mapping(cfg.get("moment_output")))

    reuse_dataset = bool(dataset_cfg.get("reuse_existing", data_cfg.get("reuse_dataset", True)))
    if bool(dataset_cfg.get("rebuild", False)):
        reuse_dataset = False
    dataset_path = dataset_cfg.get("path", data_cfg.get("dataset_path", "logs/experiments/market_making/datasets/moment_dataset.parquet"))
    horizons = dataset_cfg.get("horizons", data_cfg.get("horizons", [1, 5, 10, 30]))

    return {
        "data": {
            "orderbook_events_path": str(orderbook_events_path),
            "quote_events_paths": [str(path) for path in quote_events_paths],
            "trades_path": str(trades_path) if trades_path else "",
            "dataset_path": str(dataset_path),
            "reuse_dataset": reuse_dataset,
            "horizons": horizons,
        },
        "market_making": market_cfg,
        "model": model_cfg,
        "filter": filter_cfg,
        "split": dict(_mapping(cfg.get("split"))),
        "output": output_cfg,
        "runtime": dict(_mapping(cfg.get("runtime"))),
    }


def _resolve_pipeline_output_dir(cfg: Mapping[str, Any]) -> Path:
    pipeline_cfg = _mapping(cfg.get("pipeline"))
    explicit = pipeline_cfg.get("output_dir")
    if explicit:
        return Path(str(explicit))
    root = Path(str(_mapping(cfg.get("logging")).get("output_dir", "logs/experiments/market_making")))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    digest = hashlib.sha256(yaml.safe_dump(dict(cfg), sort_keys=True).encode("utf-8")).hexdigest()[:8]
    return root / "pipeline_runs" / f"market_making_pipeline_{stamp}_{digest}"


def _load_config(path: str | Path) -> dict[str, Any]:
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(cfg, dict):
        raise ValueError("config must be a YAML mapping")
    return cfg


def _stage_config(cfg: Mapping[str, Any], name: str, *extra_sources: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for source in (*extra_sources, cfg.get(name), _mapping(cfg.get("pipeline")).get(name)):
        if isinstance(source, Mapping):
            merged.update(source)
    return merged


def _enabled(cfg: Mapping[str, Any], *, default: bool = False) -> bool:
    return bool(cfg.get("enabled", default))


def _data_value(data_cfg: Mapping[str, Any], key: str) -> Any:
    existing = _mapping(data_cfg.get("existing"))
    return data_cfg.get(key, existing.get(key))


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _optional_path(value: object) -> Path | None:
    if value is None or value == "":
        return None
    return Path(str(value))


def _path_list(value: object) -> list[Path]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return [Path(str(item)) for item in value if item not in (None, "")]
    return [Path(str(value))]


def _required_existing_path(value: object, *, label: str) -> Path:
    path = _optional_path(value)
    if path is None:
        raise ValueError(f"{label} is required")
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    return path


def _required_quote_paths(paths: Sequence[Path]) -> list[Path]:
    if not paths:
        raise ValueError(
            "No quote_events_paths are available. Enable paper_replay with use_outputs_for_moment=true "
            "or provide data.quote_events_paths."
        )
    return [_required_existing_path(path, label="data.quote_events_paths") for path in paths]


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return value


if __name__ == "__main__":
    raise SystemExit(main())
