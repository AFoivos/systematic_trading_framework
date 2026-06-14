from __future__ import annotations

import importlib
import os
from typing import Any

import pandas as pd


class MT5ConnectorError(RuntimeError):
    """Base error for MT5 connection and API failures."""


class MT5ImportError(ImportError):
    """Raised when the optional MetaTrader5 package is unavailable."""


class MT5CredentialsError(MT5ConnectorError):
    """Raised when MT5 credentials are missing or malformed."""


class MT5LoginError(MT5ConnectorError):
    """Raised when MT5 login fails."""


class MT5DemoAccountError(MT5ConnectorError):
    """Raised when a configured account is not verifiably a demo account."""


_TIMEFRAME_NAMES = {
    "M1": "TIMEFRAME_M1",
    "M5": "TIMEFRAME_M5",
    "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30",
    "H1": "TIMEFRAME_H1",
    "H4": "TIMEFRAME_H4",
    "D1": "TIMEFRAME_D1",
}


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class MT5Connector:
    """
    Thin adapter around the MetaTrader5 Python package.

    All direct MT5 package calls live in this module so execution behavior can be tested with
    injected fakes and without importing MetaTrader5 on CI machines.
    """

    def __init__(self, *, terminal_path: str | None = None, mt5_module: Any | None = None) -> None:
        self.terminal_path = terminal_path
        self._mt5 = mt5_module
        self.connected = False
        self.logged_in = False

    @property
    def mt5(self) -> Any:
        if self._mt5 is None:
            try:
                self._mt5 = importlib.import_module("MetaTrader5")
            except ImportError as exc:
                raise MT5ImportError(
                    "MetaTrader5 package is not installed. Install it with: pip install MetaTrader5"
                ) from exc
        return self._mt5

    def initialize(self) -> None:
        mt5 = self.mt5
        if self.terminal_path:
            ok = mt5.initialize(path=self.terminal_path)
        else:
            ok = mt5.initialize()
        if not ok:
            raise MT5ConnectorError(f"MT5 initialize failed: {self.last_error()}")
        self.connected = True

    def shutdown(self) -> None:
        if self._mt5 is not None:
            self._mt5.shutdown()
        self.connected = False
        self.logged_in = False

    def last_error(self) -> Any:
        try:
            return self.mt5.last_error()
        except Exception:
            return None

    def credentials_from_env(
        self,
        *,
        login_env: str,
        password_env: str,
        server_env: str,
    ) -> tuple[int, str, str]:
        values = {
            "login": os.getenv(login_env),
            "password": os.getenv(password_env),
            "server": os.getenv(server_env),
        }
        missing = [
            env_name
            for field, env_name in (
                ("login", login_env),
                ("password", password_env),
                ("server", server_env),
            )
            if not values[field]
        ]
        if missing:
            raise MT5CredentialsError(
                "Missing MT5 credential environment variables: " + ", ".join(missing)
            )
        try:
            login = int(str(values["login"]))
        except ValueError as exc:
            raise MT5CredentialsError(f"{login_env} must be an integer login id.") from exc
        return login, str(values["password"]), str(values["server"])

    def login_from_env(self, *, login_env: str, password_env: str, server_env: str) -> None:
        login, password, server = self.credentials_from_env(
            login_env=login_env,
            password_env=password_env,
            server_env=server_env,
        )
        self.login(login=login, password=password, server=server)

    def login_from_mapping(self, config: dict[str, Any]) -> None:
        login, password, server = self.credentials_from_mapping(config)
        self.login(login=login, password=password, server=server)

    def credentials_from_mapping(self, config: dict[str, Any]) -> tuple[int, str, str]:
        values = {
            "login": config.get("login"),
            "password": config.get("password"),
            "server": config.get("server"),
        }
        missing = [field for field, value in values.items() if value in (None, "")]
        if missing:
            raise MT5CredentialsError(
                "Missing MT5 credential config fields: " + ", ".join(missing)
            )
        try:
            login = int(str(values["login"]))
        except ValueError as exc:
            raise MT5CredentialsError("mt5.login must be an integer login id.") from exc
        return login, str(values["password"]), str(values["server"])

    def login(self, *, login: int, password: str, server: str) -> None:
        ok = self.mt5.login(login=int(login), password=password, server=server)
        if not ok:
            raise MT5LoginError(f"MT5 login failed for login={login}, server={server}: {self.last_error()}")
        self.logged_in = True

    def account_info(self) -> Any:
        info = self.mt5.account_info()
        if info is None:
            raise MT5ConnectorError(f"MT5 account_info failed: {self.last_error()}")
        return info

    def ensure_demo_account(self, *, require_demo: bool = True) -> None:
        if not require_demo:
            return
        info = self.account_info()
        trade_mode = _attr(info, "trade_mode")
        demo_mode = getattr(self.mt5, "ACCOUNT_TRADE_MODE_DEMO", None)
        if demo_mode is None:
            raise MT5DemoAccountError("Cannot verify MT5 demo account; ACCOUNT_TRADE_MODE_DEMO is unavailable.")
        if trade_mode != demo_mode:
            login = _attr(info, "login", "<unknown>")
            server = _attr(info, "server", "<unknown>")
            raise MT5DemoAccountError(
                f"Refusing to trade because MT5 account login={login}, server={server} is not DEMO."
            )

    def timeframe(self, timeframe: str) -> Any:
        key = str(timeframe).upper()
        attr_name = _TIMEFRAME_NAMES.get(key)
        if attr_name is None:
            raise ValueError(f"Unsupported MT5 timeframe: {timeframe!r}.")
        value = getattr(self.mt5, attr_name, None)
        if value is None:
            raise ValueError(f"MetaTrader5 module does not expose {attr_name}.")
        return value

    def select_symbol(self, symbol: str) -> None:
        symbol_select = getattr(self.mt5, "symbol_select", None)
        if symbol_select is None:
            return
        if not symbol_select(symbol, True):
            raise MT5ConnectorError(f"MT5 symbol_select failed for {symbol}: {self.last_error()}")

    def symbol_info(self, symbol: str) -> Any:
        return self.mt5.symbol_info(symbol)

    def symbol_info_tick(self, symbol: str) -> Any:
        return self.mt5.symbol_info_tick(symbol)

    def positions_get(self, *, symbol: str | None = None) -> list[Any]:
        raw = self.mt5.positions_get(symbol=symbol) if symbol else self.mt5.positions_get()
        if raw is None:
            return []
        return list(raw)

    def fetch_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        count: int,
        closed_only: bool = True,
    ) -> pd.DataFrame:
        if int(count) <= 0:
            raise ValueError("count must be positive.")
        start_pos = 1 if closed_only else 0
        rates = self.mt5.copy_rates_from_pos(symbol, self.timeframe(timeframe), start_pos, int(count))
        if rates is None:
            raise MT5ConnectorError(f"MT5 copy_rates_from_pos failed for {symbol}: {self.last_error()}")
        raw = pd.DataFrame(rates)
        if raw.empty:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        if "time" not in raw.columns:
            raise MT5ConnectorError("MT5 rates response is missing required 'time' column.")

        out = raw.copy()
        out["time"] = pd.to_datetime(out["time"].astype("int64"), unit="s", utc=True)
        if "tick_volume" in out.columns:
            out["volume"] = out["tick_volume"]
        elif "real_volume" in out.columns:
            out["volume"] = out["real_volume"]
        elif "volume" not in out.columns:
            out["volume"] = 0.0

        base_cols = ["open", "high", "low", "close", "volume"]
        missing = [col for col in base_cols if col not in out.columns]
        if missing:
            raise MT5ConnectorError(f"MT5 rates response is missing OHLCV columns: {missing}")
        optional_cols = [col for col in ("tick_volume", "spread", "real_volume") if col in out.columns]
        out = out[["time", *base_cols, *optional_cols]].copy()
        for col in base_cols:
            out[col] = pd.to_numeric(out[col], errors="coerce")
        out = out.sort_values("time").set_index("time")
        out.index.name = "time"
        return out

    def build_market_order_request(
        self,
        *,
        symbol: str,
        side: str,
        volume: float,
        price: float,
        sl: float,
        tp: float,
        deviation: int,
        magic: int,
        comment: str,
    ) -> dict[str, Any]:
        mt5 = self.mt5
        normalized_side = str(side).lower()
        if normalized_side not in {"buy", "sell"}:
            raise ValueError("side must be 'buy' or 'sell'.")
        order_type = mt5.ORDER_TYPE_BUY if normalized_side == "buy" else mt5.ORDER_TYPE_SELL
        request: dict[str, Any] = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": float(price),
            "sl": float(sl),
            "tp": float(tp),
            "deviation": int(deviation),
            "magic": int(magic),
            "comment": str(comment),
        }
        type_time = getattr(mt5, "ORDER_TIME_GTC", None)
        if type_time is not None:
            request["type_time"] = type_time
        type_filling = getattr(mt5, "ORDER_FILLING_IOC", None)
        if type_filling is not None:
            request["type_filling"] = type_filling
        return request

    def order_send(self, request: dict[str, Any]) -> Any:
        return self.mt5.order_send(request)

    def is_successful_order(self, result: Any) -> bool:
        retcode = _attr(result, "retcode")
        success_codes = {
            getattr(self.mt5, "TRADE_RETCODE_DONE", None),
            getattr(self.mt5, "TRADE_RETCODE_PLACED", None),
            getattr(self.mt5, "TRADE_RETCODE_DONE_PARTIAL", None),
        }
        success_codes.discard(None)
        return retcode in success_codes


__all__ = [
    "MT5Connector",
    "MT5ConnectorError",
    "MT5CredentialsError",
    "MT5DemoAccountError",
    "MT5ImportError",
    "MT5LoginError",
]
