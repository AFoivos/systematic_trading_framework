from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import threading
import time
from typing import Any, Mapping

import pandas as pd
import yaml

from src.experiments.orchestration.feature_stage import apply_feature_steps, apply_signal_step
from src.models.artifacts import load_model_bundle, predict_with_model_bundle

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ContractError(ValueError):
    pass


@dataclass(frozen=True)
class ServiceConfig:
    host: str
    port: int
    strategy_config_path: Path
    model_artifact_path: Path
    symbol: str
    timeframe: str
    minimum_bars: int
    maximum_bars: int
    max_bar_age_seconds: int
    api_token: str | None
    log_dir: Path

    @classmethod
    def load(cls, path: str | Path) -> "ServiceConfig":
        cfg_path = _resolve(path)
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        server = dict(raw.get("server", {}) or {})
        strategy = dict(raw.get("strategy", {}) or {})
        contract = dict(raw.get("contract", {}) or {})
        logging_cfg = dict(raw.get("logging", {}) or {})
        token_env = str(server.get("api_token_env", "MODEL06_API_TOKEN"))
        return cls(
            host=str(server.get("host", "127.0.0.1")),
            port=int(server.get("port", 8765)),
            strategy_config_path=_resolve(strategy["config_path"]),
            model_artifact_path=_resolve(strategy["model_artifact_path"]),
            symbol=str(contract.get("symbol", "ETHUSD")),
            timeframe=str(contract.get("timeframe", "M30")),
            minimum_bars=int(contract.get("minimum_bars", 1200)),
            maximum_bars=int(contract.get("maximum_bars", 3000)),
            max_bar_age_seconds=int(contract.get("max_bar_age_seconds", 5400)),
            api_token=os.environ.get(token_env) or None,
            log_dir=_resolve(logging_cfg.get("output_dir", "logs/ctrader_model06_service")),
        )


class JsonlLogger:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def write(self, stream: str, payload: Mapping[str, Any]) -> None:
        event = {"logged_at": datetime.now(timezone.utc).isoformat(), **dict(payload)}
        line = json.dumps(event, sort_keys=True, default=_json_default)
        with self._lock:
            with (self.directory / f"{stream}.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")


class Model06Runtime:
    def __init__(self, config: ServiceConfig) -> None:
        self.config = config
        # Load the research YAML verbatim. Its logging block contains Docker-only
        # absolute paths such as /workspace/logs, which are irrelevant to live
        # inference and fail local macOS path validation.
        self.strategy_config = yaml.safe_load(
            config.strategy_config_path.read_text(encoding="utf-8")
        ) or {}
        self.bundle = load_model_bundle(config.model_artifact_path)
        self.logger = JsonlLogger(config.log_dir)
        self.feature_cols = _feature_columns(self.bundle, self.strategy_config)
        self.signal_cfg = dict(self.strategy_config.get("signals", {}) or {})
        self.signal_col = str(dict(self.signal_cfg.get("params", {}) or {}).get("signal_col", "signal_structured_tail"))
        self.model_name = str(dict(self.bundle.get("manifest", {}) or {}).get("model_name", "model06_vwap32_rz128"))
        self.model_sha256 = _sha256_file(config.model_artifact_path)
        self._cache_lock = threading.Lock()
        self._cached_bar_time: str | None = None
        self._cached_response: dict[str, Any] | None = None

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "service": "ctrader-model06-inference",
            "model_name": self.model_name,
            "model_sha256": self.model_sha256,
            "feature_count": len(self.feature_cols),
            "symbol": self.config.symbol,
            "timeframe": self.config.timeframe,
        }

    def model_info(self) -> dict[str, Any]:
        return {
            **self.health(),
            "strategy_config_path": str(self.config.strategy_config_path),
            "model_artifact_path": str(self.config.model_artifact_path),
            "feature_order": self.feature_cols,
            "signal": self.signal_cfg,
            "minimum_bars": self.config.minimum_bars,
            "maximum_bars": self.config.maximum_bars,
        }

    def predict(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        request_id = str(payload.get("request_id") or "")
        symbol = str(payload.get("symbol") or "")
        timeframe = str(payload.get("timeframe") or "")
        
        # Normalize cTrader timeframe names to model contract format.
        timeframe_aliases = {
            "Minute": "M1",
            "Minute5": "M5",
            "Minute15": "M15",
            "Minute30": "M30",
            "Hour": "H1",
            "Hour4": "H4",
        }
        timeframe = timeframe_aliases.get(timeframe, timeframe)
        
        if symbol != self.config.symbol:
            raise ContractError(f"symbol must be {self.config.symbol!r}, got {symbol!r}")
        if timeframe.upper() != self.config.timeframe.upper():
            raise ContractError(f"timeframe must be {self.config.timeframe!r}, got {timeframe!r}")

        bars = payload.get("bars")
        if not isinstance(bars, list):
            raise ContractError("bars must be a JSON array")
        if len(bars) < self.config.minimum_bars:
            raise ContractError(f"at least {self.config.minimum_bars} closed bars are required")
        if len(bars) > self.config.maximum_bars:
            bars = bars[-self.config.maximum_bars :]

        frame = _bars_to_frame(bars)
        latest_time = frame.index[-1]
        latest_iso = latest_time.isoformat()
        self._validate_freshness(latest_time, payload)

        with self._cache_lock:
            if latest_iso == self._cached_bar_time and self._cached_response is not None:
                response = dict(self._cached_response)
                response["request_id"] = request_id
                response["cache_hit"] = True
                return response

        features = apply_feature_steps(
            frame,
            list(self.strategy_config.get("features", []) or []),
            asset=self.config.symbol,
        )
        missing = [name for name in self.feature_cols if name not in features.columns]
        if missing:
            raise ContractError(f"feature pipeline missing columns: {missing}")

        predicted = predict_with_model_bundle(features, self.bundle, asset=self.config.symbol)
        signaled = apply_signal_step(predicted, self.signal_cfg, asset=self.config.symbol)
        latest = signaled.iloc[-1]

        feature_values = latest[self.feature_cols]
        bad_features = [
            name for name, value in feature_values.items()
            if value is None or not math.isfinite(float(value))
        ]
        if bad_features:
            raise ContractError(f"latest closed bar has non-finite model features: {bad_features}")

        pred_ret = float(latest["pred_ret"])
        signal = int(round(float(latest[self.signal_col])))
        if signal not in (-1, 0, 1):
            raise ContractError(f"invalid signal value generated: {signal}")

        params = dict(self.signal_cfg.get("params", {}) or {})
        filters = _filter_diagnostics(latest, list(params.get("activation_filters", []) or []))
        response = {
            "ok": True,
            "request_id": request_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "bar_time": latest_iso,
            "prediction": pred_ret,
            "signal": signal,
            "upper_threshold": float(params.get("upper", 0.7)),
            "lower_threshold": float(params.get("lower", -0.85)),
            "filters_passed": all(item["passed"] for item in filters),
            "filters": filters,
            "feature_count": len(self.feature_cols),
            "model_name": self.model_name,
            "model_sha256": self.model_sha256,
            "cache_hit": False,
            "latency_ms": round((time.perf_counter() - started) * 1000.0, 3),
        }
        with self._cache_lock:
            self._cached_bar_time = latest_iso
            self._cached_response = dict(response)
        self.logger.write("predictions", response)
        return response

    def _validate_freshness(self, latest_time: pd.Timestamp, payload: Mapping[str, Any]) -> None:
        if bool(payload.get("allow_stale", False)) and os.environ.get("MODEL06_ALLOW_STALE") == "1":
            return
        now = pd.Timestamp.now(tz="UTC")
        age = (now - latest_time).total_seconds()
        if age < -60:
            raise ContractError("latest bar timestamp is in the future")
        if age > self.config.max_bar_age_seconds:
            raise ContractError(
                f"latest closed bar is stale: age_seconds={age:.1f}, "
                f"limit={self.config.max_bar_age_seconds}"
            )


class RequestHandler(BaseHTTPRequestHandler):
    runtime: Model06Runtime

    def do_GET(self) -> None:  # noqa: N802
        try:
            self._authorise()
            if self.path == "/health":
                self._json(200, self.runtime.health())
            elif self.path == "/model-info":
                self._json(200, self.runtime.model_info())
            else:
                self._json(404, {"ok": False, "error": "not_found"})
        except PermissionError as exc:
            self._json(401, {"ok": False, "error": str(exc)})
        except Exception as exc:  # defensive boundary
            self.runtime.logger.write("errors", {"path": self.path, "error": repr(exc)})
            self._json(500, {"ok": False, "error": "internal_error"})

    def do_POST(self) -> None:  # noqa: N802
        try:
            self._authorise()
            if self.path != "/predict":
                self._json(404, {"ok": False, "error": "not_found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 5_000_000:
                raise ContractError("invalid request body size")
            body = self.rfile.read(length)
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ContractError("request body must be a JSON object")
            result = self.runtime.predict(payload)
            self._json(200, result)
        except PermissionError as exc:
            self._json(401, {"ok": False, "error": str(exc)})
        except (ContractError, json.JSONDecodeError) as exc:
            self.runtime.logger.write("rejections", {"path": self.path, "error": str(exc)})
            self._json(422, {"ok": False, "error": str(exc)})
        except Exception as exc:  # defensive boundary
            self.runtime.logger.write("errors", {"path": self.path, "error": repr(exc)})
            self._json(500, {"ok": False, "error": "internal_error"})

    def log_message(self, format: str, *args: Any) -> None:
        self.runtime.logger.write("http", {"message": format % args})

    def _authorise(self) -> None:
        expected = self.runtime.config.api_token
        if expected is None:
            return
        supplied = self.headers.get("X-Model06-Token")
        if supplied != expected:
            raise PermissionError("invalid_api_token")

    def _json(self, status: int, payload: Mapping[str, Any]) -> None:
        encoded = json.dumps(payload, sort_keys=True, default=_json_default).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def _bars_to_frame(rows: list[Any]) -> pd.DataFrame:
    parsed: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ContractError(f"bars[{index}] must be an object")
        try:
            timestamp = pd.Timestamp(row["time"])
            if timestamp.tzinfo is None:
                timestamp = timestamp.tz_localize("UTC")
            else:
                timestamp = timestamp.tz_convert("UTC")
            parsed.append(
                {
                    "time": timestamp,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume", row.get("tick_volume", 0.0))),
                }
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ContractError(f"invalid bars[{index}]: {exc}") from exc
    frame = pd.DataFrame.from_records(parsed).set_index("time")
    if frame.index.has_duplicates:
        raise ContractError("bar timestamps must be unique")
    if not frame.index.is_monotonic_increasing:
        raise ContractError("bars must be ordered oldest to newest")
    values = frame[["open", "high", "low", "close", "volume"]].to_numpy(dtype=float)
    if not bool(pd.notna(values).all()) or not bool((abs(values) != float("inf")).all()):
        raise ContractError("bars contain non-finite values")
    if bool((frame[["open", "high", "low", "close"]] <= 0).any().any()):
        raise ContractError("OHLC prices must be positive")
    if bool((frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any()):
        raise ContractError("bar high is inconsistent with OHLC")
    if bool((frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any()):
        raise ContractError("bar low is inconsistent with OHLC")
    return frame


def _feature_columns(bundle: Mapping[str, Any], strategy_config: Mapping[str, Any]) -> list[str]:
    manifest = dict(bundle.get("manifest", {}) or {})
    columns = list(manifest.get("feature_order", []) or manifest.get("feature_cols", []) or [])
    if not columns:
        columns = list(dict(strategy_config.get("model", {}) or {}).get("feature_cols", []) or [])
    if not columns:
        raise RuntimeError("model bundle/config does not define feature order")
    return [str(name) for name in columns]


def _filter_diagnostics(row: pd.Series, filters: list[Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    operations = {
        "ge": lambda actual, target: actual >= target,
        "gt": lambda actual, target: actual > target,
        "le": lambda actual, target: actual <= target,
        "lt": lambda actual, target: actual < target,
        "eq": lambda actual, target: actual == target,
    }
    for item in filters:
        spec = dict(item or {})
        column = str(spec.get("col"))
        operation = str(spec.get("op"))
        target = float(spec.get("value"))
        actual = float(row[column])
        if operation not in operations:
            raise ContractError(f"unsupported activation filter operation: {operation}")
        results.append(
            {"column": column, "operation": operation, "target": target, "actual": actual,
             "passed": bool(operations[operation](actual, target))}
        )
    return results


def _resolve(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve Model06 inference to a local cTrader cBot.")
    parser.add_argument("--config", default="integrations/ctrader_model06/service_config.yaml")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = ServiceConfig.load(args.config)
    runtime = Model06Runtime(config)
    handler = type("BoundRequestHandler", (RequestHandler,), {"runtime": runtime})
    server = ThreadingHTTPServer((config.host, config.port), handler)
    print(json.dumps({"event": "service_started", **runtime.health(), "url": f"http://{config.host}:{config.port}"}))
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
