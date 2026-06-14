from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any, Mapping

import pandas as pd
import yaml

from src.execution.mt5_connector import MT5Connector
from src.execution.mt5_order_manager import MT5OrderManager, OrderResult, TradeParameters
from src.execution.mt5_position_manager import MT5PositionManager
from src.execution.mt5_risk_manager import MT5RiskManager, RiskConfig
from src.execution.mt5_symbol_mapper import MT5SymbolMapper
from src.experiments.orchestration.feature_stage import apply_feature_steps, apply_signal_step
from src.utils.config import load_experiment_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class SingleInstanceLockError(RuntimeError):
    """Raised when another bot process already owns the execution lock."""


class SingleInstanceLock:
    """Atomic pid-file lock that prevents duplicate live bot loops."""

    def __init__(self, path: Path, *, metadata: Mapping[str, Any] | None = None) -> None:
        self.path = path
        self.metadata = dict(metadata or {})
        self._fd: int | None = None

    def __enter__(self) -> SingleInstanceLock:
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": os.getpid(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            **self.metadata,
        }
        while True:
            try:
                self._fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            except FileExistsError as exc:
                existing = _read_lock_payload(self.path)
                pid = _lock_pid(existing)
                if pid is not None and _pid_is_running(pid):
                    raise SingleInstanceLockError(
                        f"MT5 demo bot is already running with pid={pid}. "
                        f"Stop that process before starting another one. lock_path={self.path}"
                    ) from exc
                try:
                    self.path.unlink()
                except FileNotFoundError:
                    pass
                continue
            break

        os.write(self._fd, json.dumps(_jsonable(payload), sort_keys=True).encode("utf-8"))
        os.write(self._fd, b"\n")

    def release(self) -> None:
        if self._fd is None:
            return
        owned_by_self = _lock_pid(_read_lock_payload(self.path)) == os.getpid()
        os.close(self._fd)
        self._fd = None
        if owned_by_self:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class JsonlEventLogger:
    def __init__(self, log_dir: Path) -> None:
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def write(self, stream: str, event: Mapping[str, Any]) -> None:
        path = self.log_dir / f"{stream}.jsonl"
        payload = {"logged_at": datetime.now(timezone.utc).isoformat(), **dict(event)}
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_jsonable(payload), sort_keys=True) + "\n")


class MT5DemoBot:
    def __init__(
        self,
        *,
        config_path: str | Path,
        force_dry_run: bool = False,
        connector: MT5Connector | None = None,
    ) -> None:
        self.config_path = _resolve_path(config_path)
        self.config = load_execution_config(self.config_path)
        self.execution_cfg = dict(self.config.get("execution", {}) or {})
        self.safety_cfg = dict(self.config.get("safety", {}) or {})
        self.risk_cfg = dict(self.config.get("risk", {}) or {})
        self.execution_mode = str(self.execution_cfg.get("mode", "dry_run"))
        self.dry_run = (
            bool(force_dry_run)
            or self.execution_mode != "demo_mt5"
            or bool(self.safety_cfg.get("dry_run_default", True))
        )

        log_dir = _resolve_path(self.config.get("logging", {}).get("output_dir", "logs/mt5_demo"))
        self.lock_path = log_dir / "mt5_demo_bot.lock"
        self.event_logger = JsonlEventLogger(log_dir)
        self.logger = _configure_logger(log_dir)

        strategy_cfg = dict(self.config.get("strategy", {}) or {})
        strategy_path = strategy_cfg.get("config_path")
        if not strategy_path:
            raise ValueError("strategy.config_path is required.")
        self.strategy_config_path = _resolve_path(strategy_path)
        self.strategy_config = load_experiment_config(self.strategy_config_path)

        self.mapper = MT5SymbolMapper.from_config(dict(self.config.get("symbols", {}) or {}))
        mt5_cfg = dict(self.execution_cfg.get("mt5", {}) or {})
        self.connector = connector or MT5Connector(terminal_path=mt5_cfg.get("terminal_path"))
        self.position_manager = MT5PositionManager(
            self.connector,
            magic_number=int(self.execution_cfg.get("magic_number", 260607)),
        )
        kill_switch_path = self.safety_cfg.get(
            "kill_switch_path",
            self.risk_cfg.get("kill_switch_path", "STOP_TRADING"),
        )
        if kill_switch_path not in (None, ""):
            kill_switch_path = str(_resolve_path(kill_switch_path))
        risk_config = RiskConfig.from_mapping(
            {
                **self.risk_cfg,
                "kill_switch_path": kill_switch_path,
            }
        )
        self.risk_manager = MT5RiskManager(risk_config)
        self.order_manager = MT5OrderManager(
            connector=self.connector,
            position_manager=self.position_manager,
            risk_manager=self.risk_manager,
            magic_number=int(self.execution_cfg.get("magic_number", 260607)),
            comment=str(self.execution_cfg.get("comment", "mt5_demo_bot")),
            execution_mode=self.execution_mode,
            dry_run=self.dry_run,
        )
        self._last_processed_bar: dict[str, pd.Timestamp] = {}

    def connect(self) -> None:
        mt5_cfg = dict(self.execution_cfg.get("mt5", {}) or {})
        self.connector.initialize()
        if _has_direct_mt5_credentials(mt5_cfg):
            self.connector.login_from_mapping(mt5_cfg)
        else:
            self.connector.login_from_env(
                login_env=str(mt5_cfg.get("login_env", "MT5_LOGIN")),
                password_env=str(mt5_cfg.get("password_env", "MT5_PASSWORD")),
                server_env=str(mt5_cfg.get("server_env", "MT5_SERVER")),
            )
        require_demo = bool(self.safety_cfg.get("require_demo_account", True)) or bool(
            self.risk_manager.config.demo_only
        )
        self.connector.ensure_demo_account(require_demo=require_demo)
        account = self.connector.account_info()
        equity = float(_attr(account, "equity"))
        self.risk_manager.update_equity_baselines(equity, now_utc=datetime.now(timezone.utc))
        self._log_account(account)
        self.logger.info("connected to MT5 in mode=%s dry_run=%s", self.execution_mode, self.dry_run)

    def shutdown(self) -> None:
        self.connector.shutdown()

    def run_once(self) -> None:
        account = self.connector.account_info()
        self._log_account(account)
        for framework_symbol in self.mapper.enabled_symbols():
            self._process_symbol(framework_symbol, account)

    def run_loop(self, *, sleep_seconds: int | None = None) -> None:
        delay = int(sleep_seconds or self.execution_cfg.get("poll_seconds", 30))
        while True:
            self.run_once()
            time.sleep(delay)

    def _process_symbol(self, framework_symbol: str, account: Any) -> None:
        mt5_symbol = self.mapper.to_mt5(framework_symbol)
        try:
            self.connector.select_symbol(mt5_symbol)
            candles = self.connector.fetch_candles(
                symbol=mt5_symbol,
                timeframe=str(self.execution_cfg.get("timeframe", "M30")),
                count=int(self.execution_cfg.get("lookback_bars", 1000)),
                closed_only=True,
            )
            if candles.empty:
                self.logger.warning("no candles returned for %s", mt5_symbol)
                return
            latest_bar = pd.Timestamp(candles.index[-1])
            if self._last_processed_bar.get(framework_symbol) == latest_bar:
                return

            features = apply_feature_steps(
                candles,
                list(self.strategy_config.get("features", []) or []),
                asset=framework_symbol,
            )
            signal_frame = apply_signal_step(
                features,
                dict(self.strategy_config.get("signals", {}) or {}),
                asset=framework_symbol,
            )
            latest = signal_frame.iloc[-1]
            signal_col = str(self.strategy_config.get("backtest", {}).get("signal_col", "signal_side"))
            signal_side = int(latest.get(signal_col, 0) or 0)
            self._log_signal(framework_symbol, mt5_symbol, latest_bar, latest, signal_col, signal_side)
            self._last_processed_bar[framework_symbol] = latest_bar

            if signal_side == 1:
                result = self.order_manager.place_market_order(
                    framework_symbol=framework_symbol,
                    mt5_symbol=mt5_symbol,
                    side="buy",
                    latest_row=latest,
                    account_info=account,
                    trade_params=self._trade_params_for_asset(framework_symbol),
                    now_utc=datetime.now(timezone.utc),
                )
                self._log_order_result(framework_symbol, mt5_symbol, latest_bar, result)
            elif signal_side < 0:
                self.event_logger.write(
                    "rejected_orders",
                    {
                        "asset": framework_symbol,
                        "mt5_symbol": mt5_symbol,
                        "bar_time": latest_bar.isoformat(),
                        "reason": "short_signals_ignored",
                        "signal_side": signal_side,
                    },
                )
        except Exception:
            self.logger.exception("failed processing symbol %s (%s)", framework_symbol, mt5_symbol)

    def _trade_params_for_asset(self, framework_symbol: str) -> TradeParameters:
        backtest_cfg = dict(self.strategy_config.get("backtest", {}) or {})
        asset_params = dict(backtest_cfg.get("asset_params", {}).get(framework_symbol, {}) or {})
        stop_loss_r = self.risk_cfg.get("stop_loss_r", asset_params.get("stop_barrier_r", backtest_cfg.get("stop_barrier_r")))
        take_profit_r = self.risk_cfg.get(
            "take_profit_r",
            asset_params.get("profit_barrier_r", backtest_cfg.get("profit_barrier_r")),
        )
        volatility_col = self.risk_cfg.get(
            "volatility_col",
            asset_params.get("volatility_col", backtest_cfg.get("volatility_col")),
        )
        if stop_loss_r is None or take_profit_r is None:
            raise ValueError("stop_loss_r/take_profit_r must be configured or resolvable from strategy backtest.")
        return TradeParameters(
            stop_loss_r=float(stop_loss_r),
            take_profit_r=float(take_profit_r),
            volatility_col=str(volatility_col) if volatility_col else None,
            deviation_points=int(self.execution_cfg.get("deviation_points", 20)),
        )

    def _log_account(self, account: Any) -> None:
        self.event_logger.write(
            "account_equity",
            {
                "login": _attr(account, "login"),
                "server": _attr(account, "server"),
                "equity": _attr(account, "equity"),
                "balance": _attr(account, "balance"),
                "margin": _attr(account, "margin"),
                "margin_free": _attr(account, "margin_free"),
            },
        )

    def _log_signal(
        self,
        framework_symbol: str,
        mt5_symbol: str,
        bar_time: pd.Timestamp,
        latest: pd.Series,
        signal_col: str,
        signal_side: int,
    ) -> None:
        self.event_logger.write(
            "signals",
            {
                "asset": framework_symbol,
                "mt5_symbol": mt5_symbol,
                "bar_time": bar_time.isoformat(),
                "signal_col": signal_col,
                "signal_side": signal_side,
                "close": latest.get("close"),
                "spread": latest.get("spread"),
            },
        )

    def _log_order_result(
        self,
        framework_symbol: str,
        mt5_symbol: str,
        bar_time: pd.Timestamp,
        result: OrderResult,
    ) -> None:
        event = {
            "asset": framework_symbol,
            "mt5_symbol": mt5_symbol,
            "bar_time": bar_time.isoformat(),
            "status": result.status,
            "reason": result.reason,
            "request": result.request,
            "response": result.response,
            "sent": result.sent,
            "slippage": result.slippage,
            "details": result.details,
        }
        self.event_logger.write("orders", event)
        if result.status == "filled":
            self.event_logger.write("fills", event)
        if result.status == "rejected":
            self.event_logger.write("rejected_orders", event)


def load_execution_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise TypeError("execution config must be a YAML mapping.")
    return raw


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the MT5 demo execution bot.")
    parser.add_argument("--config", required=True, help="Path to config/execution/mt5_demo.yaml.")
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run mode and never call order_send.")
    parser.add_argument("--once", action="store_true", help="Process the latest closed candle once.")
    parser.add_argument("--loop", action="store_true", help="Poll continuously.")
    parser.add_argument("--sleep-seconds", type=int, default=None, help="Loop sleep interval override.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.once and args.loop:
        parser.error("--once and --loop are mutually exclusive.")
    bot = MT5DemoBot(config_path=args.config, force_dry_run=args.dry_run)
    try:
        with SingleInstanceLock(
            bot.lock_path,
            metadata={"config_path": str(bot.config_path), "execution_mode": bot.execution_mode},
        ):
            try:
                bot.connect()
                if args.loop:
                    bot.run_loop(sleep_seconds=args.sleep_seconds)
                else:
                    bot.run_once()
            finally:
                bot.shutdown()
    except SingleInstanceLockError as exc:
        bot.logger.error("%s", exc)
        return 2
    except KeyboardInterrupt:
        return 130
    return 0


def _resolve_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def _configure_logger(log_dir: Path) -> logging.Logger:
    logger = logging.getLogger("mt5_demo_bot")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(log_dir / "bot.log")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def _read_lock_payload(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return {}
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _lock_pid(payload: Mapping[str, Any]) -> int | None:
    try:
        pid = int(payload.get("pid"))
    except (TypeError, ValueError):
        return None
    return pid if pid > 0 else None


def _pid_is_running(pid: int) -> bool:
    if os.name == "nt":
        return _windows_pid_is_running(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _has_direct_mt5_credentials(config: Mapping[str, Any]) -> bool:
    return any(config.get(field) not in (None, "") for field in ("login", "password", "server"))


def _windows_pid_is_running(pid: int) -> bool:
    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    synchronize = 0x00100000
    still_active = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(process_query_limited_information | synchronize, False, int(pid))
    if not handle:
        return False
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return True
        return int(exit_code.value) == still_active
    finally:
        kernel32.CloseHandle(handle)


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


__all__ = [
    "MT5DemoBot",
    "SingleInstanceLock",
    "SingleInstanceLockError",
    "build_arg_parser",
    "load_execution_config",
    "main",
]
