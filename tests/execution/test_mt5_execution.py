from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd
import pytest

from src.execution.mt5_connector import MT5Connector, MT5CredentialsError
from src.execution.mt5_bot_runner import SingleInstanceLock, SingleInstanceLockError
from src.execution.mt5_order_manager import MT5OrderManager, TradeParameters
from src.execution.mt5_position_manager import MT5PositionManager
from src.execution.mt5_risk_manager import MT5RiskManager, RiskConfig, calculate_position_size
from src.execution.mt5_symbol_mapper import MT5SymbolMapper


MAGIC = 260607
NOW = datetime(2024, 1, 2, 12, 0, tzinfo=timezone.utc)


class FakeMT5Module:
    ACCOUNT_TRADE_MODE_DEMO = 0
    TRADE_ACTION_DEAL = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 1
    TRADE_RETCODE_DONE = 10009
    TIMEFRAME_M30 = 30

    def __init__(self) -> None:
        self.login_calls = []

    def initialize(self, **_: object) -> bool:
        return True

    def login(self, *, login: int, password: str, server: str) -> bool:
        self.login_calls.append((login, password, server))
        return True

    def shutdown(self) -> None:
        return None

    def last_error(self) -> tuple[int, str]:
        return (0, "")

    def account_info(self) -> SimpleNamespace:
        return SimpleNamespace(login=123, server="FTMO-Demo", trade_mode=self.ACCOUNT_TRADE_MODE_DEMO, equity=10000)


class FakeConnector:
    def __init__(
        self,
        *,
        positions: list[SimpleNamespace] | None = None,
        bid: float = 100.0,
        ask: float = 100.2,
    ) -> None:
        self._positions = positions or []
        self.bid = bid
        self.ask = ask
        self.order_send_calls = 0

    def positions_get(self, *, symbol: str | None = None) -> list[SimpleNamespace]:
        if symbol is None:
            return list(self._positions)
        return [position for position in self._positions if position.symbol == symbol]

    def symbol_info(self, symbol: str) -> SimpleNamespace:
        return SimpleNamespace(
            symbol=symbol,
            point=0.01,
            digits=2,
            trade_tick_value=1.0,
            trade_tick_size=0.1,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
            contract_size=10.0,
        )

    def symbol_info_tick(self, symbol: str) -> SimpleNamespace:
        return SimpleNamespace(symbol=symbol, bid=self.bid, ask=self.ask)

    def build_market_order_request(self, **kwargs: object) -> dict[str, object]:
        return dict(kwargs)

    def order_send(self, request: dict[str, object]) -> SimpleNamespace:
        self.order_send_calls += 1
        return SimpleNamespace(retcode=10009, price=request["price"])

    def is_successful_order(self, result: object) -> bool:
        return getattr(result, "retcode") == 10009


def test_symbol_mapping_resolves_enabled_broker_symbol() -> None:
    mapper = MT5SymbolMapper(
        {
            "SPX500": {"mt5_symbol": "US500.cash", "enabled": True},
            "BTCUSD": {"mt5_symbol": "BTCUSD", "enabled": False},
        }
    )

    assert mapper.to_mt5("SPX500") == "US500.cash"
    assert mapper.enabled_symbols() == ["SPX500"]
    assert mapper.is_enabled("BTCUSD") is False


def test_position_sizing_uses_tick_value_and_stop_distance() -> None:
    symbol_info = SimpleNamespace(
        trade_tick_value=1.0,
        trade_tick_size=0.1,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
    )

    result = calculate_position_size(
        equity=10_000.0,
        risk_per_trade=0.01,
        stop_distance=10.0,
        symbol_info=symbol_info,
    )

    assert result.can_trade is True
    assert result.volume == pytest.approx(1.0)
    assert result.risk_per_lot == pytest.approx(100.0)


def test_order_manager_rejects_duplicate_position_before_order_send() -> None:
    connector = FakeConnector(
        positions=[
            SimpleNamespace(
                ticket=1,
                symbol="US500.cash",
                type=0,
                volume=0.5,
                magic=MAGIC,
                price_open=100.0,
            )
        ]
    )
    order_manager = _order_manager(connector, dry_run=False, execution_mode="demo_mt5")

    result = order_manager.place_market_order(
        framework_symbol="SPX500",
        mt5_symbol="US500.cash",
        side="buy",
        latest_row=pd.Series({"close": 100.0, "atr_14": 1.0}),
        account_info=SimpleNamespace(equity=10_000.0),
        trade_params=TradeParameters(stop_loss_r=3.0, take_profit_r=4.0, volatility_col="atr_14"),
        now_utc=NOW,
    )

    assert result.status == "rejected"
    assert result.reason == "duplicate_position"
    assert connector.order_send_calls == 0


def test_risk_guard_blocks_daily_loss_at_limit() -> None:
    manager = MT5RiskManager(
        RiskConfig(max_daily_loss_pct=0.02, disable_weekend_trading=False),
        initial_equity=10_000.0,
        daily_start_equity=10_000.0,
    )

    decision = manager.evaluate_entry(
        account_equity=9_799.0,
        positions=[],
        mt5_symbol="US500.cash",
        side="buy",
        spread_points=1.0,
        now_utc=NOW,
    )

    assert decision.allowed is False
    assert decision.reason == "max_daily_loss_exceeded"


def test_dry_run_never_calls_order_send() -> None:
    connector = FakeConnector()
    order_manager = _order_manager(connector, dry_run=True, execution_mode="dry_run")

    result = order_manager.place_market_order(
        framework_symbol="SPX500",
        mt5_symbol="US500.cash",
        side="buy",
        latest_row=pd.Series({"close": 100.0, "atr_14": 1.0}),
        account_info=SimpleNamespace(equity=10_000.0),
        trade_params=TradeParameters(stop_loss_r=3.0, take_profit_r=4.0, volatility_col="atr_14"),
        now_utc=NOW,
    )

    assert result.status == "dry_run"
    assert result.sent is False
    assert connector.order_send_calls == 0


def test_demo_mt5_mode_calls_order_send_when_all_guards_pass() -> None:
    connector = FakeConnector()
    order_manager = _order_manager(connector, dry_run=False, execution_mode="demo_mt5")

    result = order_manager.place_market_order(
        framework_symbol="SPX500",
        mt5_symbol="US500.cash",
        side="buy",
        latest_row=pd.Series({"close": 100.0, "atr_14": 1.0}),
        account_info=SimpleNamespace(equity=10_000.0),
        trade_params=TradeParameters(stop_loss_r=3.0, take_profit_r=4.0, volatility_col="atr_14"),
        now_utc=NOW,
    )

    assert result.status == "filled"
    assert result.sent is True
    assert connector.order_send_calls == 1
    assert result.request is not None
    assert result.request["symbol"] == "US500.cash"
    assert result.request["side"] == "buy"


def test_missing_mt5_credentials_fail_safely(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MT5_LOGIN", raising=False)
    monkeypatch.delenv("MT5_PASSWORD", raising=False)
    monkeypatch.delenv("MT5_SERVER", raising=False)
    connector = MT5Connector(mt5_module=FakeMT5Module())

    with pytest.raises(MT5CredentialsError, match="MT5_LOGIN"):
        connector.login_from_env(
            login_env="MT5_LOGIN",
            password_env="MT5_PASSWORD",
            server_env="MT5_SERVER",
        )


def test_single_instance_lock_rejects_second_active_holder(tmp_path) -> None:
    lock_path = tmp_path / "mt5_demo_bot.lock"

    with SingleInstanceLock(lock_path):
        with pytest.raises(SingleInstanceLockError, match="already running"):
            with SingleInstanceLock(lock_path):
                pass

    assert not lock_path.exists()


def test_single_instance_lock_replaces_stale_lock(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock_path = tmp_path / "mt5_demo_bot.lock"
    lock_path.write_text('{"pid": 999999}', encoding="utf-8")
    monkeypatch.setattr("src.execution.mt5_bot_runner._pid_is_running", lambda _: False)

    with SingleInstanceLock(lock_path):
        assert lock_path.exists()

    assert not lock_path.exists()


def test_max_spread_blocks_order_send() -> None:
    connector = FakeConnector(bid=100.0, ask=100.8)
    order_manager = _order_manager(connector, dry_run=False, execution_mode="demo_mt5", max_spread_points=50.0)

    result = order_manager.place_market_order(
        framework_symbol="SPX500",
        mt5_symbol="US500.cash",
        side="buy",
        latest_row=pd.Series({"close": 100.0, "atr_14": 1.0}),
        account_info=SimpleNamespace(equity=10_000.0),
        trade_params=TradeParameters(stop_loss_r=3.0, take_profit_r=4.0, volatility_col="atr_14"),
        now_utc=NOW,
    )

    assert result.status == "rejected"
    assert result.reason == "max_spread_exceeded"
    assert connector.order_send_calls == 0


def _order_manager(
    connector: FakeConnector,
    *,
    dry_run: bool,
    execution_mode: str,
    max_spread_points: float = 50.0,
) -> MT5OrderManager:
    position_manager = MT5PositionManager(connector, magic_number=MAGIC)
    risk_manager = MT5RiskManager(
        RiskConfig(max_spread_points=max_spread_points, disable_weekend_trading=False),
        initial_equity=10_000.0,
        daily_start_equity=10_000.0,
    )
    return MT5OrderManager(
        connector=connector,
        position_manager=position_manager,
        risk_manager=risk_manager,
        magic_number=MAGIC,
        comment="test",
        execution_mode=execution_mode,
        dry_run=dry_run,
    )
