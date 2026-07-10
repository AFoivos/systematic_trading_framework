from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from src.execution.mt5_connector import (
    MT5Connector,
    MT5CredentialsError,
    MT5TradingDisabledError,
)
from src.execution.mt5_bot_runner import (
    SingleInstanceLock,
    SingleInstanceLockError,
    _feature_snapshot_payload,
    _order_side_for_signal,
)
from src.execution.mt5_order_manager import MT5OrderManager, TradeParameters
from src.execution.mt5_position_manager import MT5PositionManager
from src.execution.mt5_risk_manager import MT5RiskManager, RiskConfig, calculate_position_size
from src.execution.mt5_symbol_mapper import MT5SymbolMapper
from src.models.artifacts import load_model_bundle, predict_with_model_bundle, save_model_artifacts


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
        return SimpleNamespace(
            login=123,
            server="FTMO-Demo",
            trade_mode=self.ACCOUNT_TRADE_MODE_DEMO,
            trade_allowed=True,
            trade_expert=True,
            equity=10000,
        )

    def terminal_info(self) -> SimpleNamespace:
        return SimpleNamespace(trade_allowed=True, tradeapi_disabled=False)


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


class ConstantRegressor:
    def predict(self, frame: pd.DataFrame) -> list[float]:
        return [float(value) * 2.0 + 1.0 for value in frame["feature_a"]]


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


def test_sell_order_rejected_when_short_trading_disabled() -> None:
    connector = FakeConnector()
    order_manager = _order_manager(connector, dry_run=False, execution_mode="demo_mt5")

    result = order_manager.place_market_order(
        framework_symbol="SPX500",
        mt5_symbol="US500.cash",
        side="sell",
        latest_row=pd.Series({"close": 100.0, "atr_14": 1.0}),
        account_info=SimpleNamespace(equity=10_000.0),
        trade_params=TradeParameters(stop_loss_r=3.0, take_profit_r=4.0, volatility_col="atr_14"),
        now_utc=NOW,
    )

    assert result.status == "rejected"
    assert result.reason == "short_trading_disabled"
    assert connector.order_send_calls == 0


def test_demo_mt5_mode_calls_order_send_for_sell_when_short_enabled() -> None:
    connector = FakeConnector(bid=99.8, ask=100.2)
    order_manager = _order_manager(
        connector,
        dry_run=False,
        execution_mode="demo_mt5",
        allow_short=True,
    )

    result = order_manager.place_market_order(
        framework_symbol="SPX500",
        mt5_symbol="US500.cash",
        side="sell",
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
    assert result.request["side"] == "sell"
    assert result.request["price"] == pytest.approx(99.8)
    assert result.request["sl"] == pytest.approx(102.8)
    assert result.request["tp"] == pytest.approx(95.8)


def test_mt5_bot_maps_negative_signal_to_sell_order_side() -> None:
    assert _order_side_for_signal(1) == "buy"
    assert _order_side_for_signal(-1) == "sell"
    assert _order_side_for_signal(0) is None


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


def test_direct_mt5_credentials_from_config_mapping() -> None:
    fake_mt5 = FakeMT5Module()
    connector = MT5Connector(mt5_module=fake_mt5)

    connector.login_from_mapping(
        {
            "login": "1513691391",
            "password": "secret",
            "server": "FTMO-Demo",
        }
    )

    assert fake_mt5.login_calls == [(1513691391, "secret", "FTMO-Demo")]


def test_direct_mt5_credentials_require_all_fields() -> None:
    connector = MT5Connector(mt5_module=FakeMT5Module())

    with pytest.raises(MT5CredentialsError, match="password"):
        connector.credentials_from_mapping({"login": 1513691391, "server": "FTMO-Demo"})


def test_algo_trading_preflight_rejects_disabled_terminal() -> None:
    fake_mt5 = FakeMT5Module()
    fake_mt5.terminal_info = lambda: SimpleNamespace(
        trade_allowed=False,
        tradeapi_disabled=False,
    )
    connector = MT5Connector(mt5_module=fake_mt5)

    with pytest.raises(MT5TradingDisabledError, match="terminal.trade_allowed=false"):
        connector.ensure_algo_trading_enabled()


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


def test_per_symbol_spread_limit_overrides_global_limit() -> None:
    connector = FakeConnector(bid=100.0, ask=100.8)
    order_manager = _order_manager(
        connector,
        dry_run=False,
        execution_mode="demo_mt5",
        max_spread_points=50.0,
        max_spread_points_by_symbol={"SPX500": 100.0},
    )

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
    assert connector.order_send_calls == 1


def test_risk_config_parses_per_symbol_spread_limits() -> None:
    config = RiskConfig.from_mapping(
        {
            "max_spread_points": 50,
            "max_spread_points_by_symbol": {"SPX500": 70, "US100.cash": 225},
        }
    )
    manager = MT5RiskManager(config)

    assert manager.spread_limit_for_symbol(
        framework_symbol="SPX500",
        mt5_symbol="US500.cash",
    ) == pytest.approx(70.0)
    assert manager.spread_limit_for_symbol(mt5_symbol="US100.cash") == pytest.approx(225.0)
    assert manager.spread_limit_for_symbol(mt5_symbol="UNKNOWN") == pytest.approx(50.0)


def test_feature_snapshot_payload_keeps_recent_numeric_feature_rows() -> None:
    frame = pd.DataFrame(
        {
            "close": [100.0, 101.0, 102.0],
            "ema_50": [99.5, 100.2, 100.9],
            "atr_14": [1.2, 1.3, 1.4],
            "signal_side": [0, 1, 0],
        },
        index=pd.date_range("2026-06-15T12:00:00Z", periods=3, freq="30min"),
    )

    payload = _feature_snapshot_payload(
        asset="SPX500",
        mt5_symbol="US500.cash",
        latest_bar=pd.Timestamp("2026-06-15T13:00:00Z"),
        timeframe="M30",
        strategy_config_path="config/example.yaml",
        signal_frame=frame,
        max_rows=2,
    )

    assert payload["row_count"] == 2
    assert payload["market_columns"] == ["close"]
    assert payload["feature_columns"] == ["ema_50", "atr_14"]
    assert payload["records"][0]["time"] == "2026-06-15T12:30:00+00:00"
    assert payload["records"][-1]["ema_50"] == 100.9


def test_model_artifact_custom_name_installs_and_predicts(tmp_path: Path) -> None:
    cfg = {
        "config_path": "config/demo.yaml",
        "logging": {
            "save_model": True,
            "model_name": "ETH Model v1.pkl",
            "model_install_dir": str(tmp_path / "installed"),
        },
        "model": {
            "kind": "lightgbm_regressor",
            "feature_cols": ["feature_a"],
            "pred_ret_col": "pred_ret",
            "pred_prob_col": "pred_prob",
            "pred_is_oos_col": "pred_is_oos",
        },
        "signals": {"kind": "forecast_threshold", "params": {"forecast_col": "pred_ret"}},
    }
    model_meta = {
        "model_kind": "lightgbm_regressor",
        "feature_cols": ["feature_a"],
        "pred_ret_col": "pred_ret",
        "pred_prob_col": "pred_prob",
        "pred_is_oos_col": "pred_is_oos",
    }

    artifacts = save_model_artifacts(
        run_dir=tmp_path / "run",
        model=ConstantRegressor(),
        cfg=cfg,
        model_meta=model_meta,
        run_metadata={"created_at_utc": NOW.isoformat(), "git": {}, "environment": {}},
        config_hash_sha256="a" * 64,
        data_fingerprint={"sha256": "b" * 64},
    )

    run_model_path = Path(artifacts["model_artifact"])
    installed_model_path = Path(artifacts["installed_model_artifact"])
    assert run_model_path.name == "ETH_Model_v1.pkl"
    assert installed_model_path.name == "ETH_Model_v1.pkl"
    assert installed_model_path.exists()
    assert Path(artifacts["installed_model_manifest"]).exists()

    bundle = load_model_bundle(installed_model_path)
    frame = pd.DataFrame({"feature_a": [1.0, None, 3.0]})
    out = predict_with_model_bundle(frame, bundle, asset="ETHUSD")

    assert out["pred_ret"].iloc[0] == pytest.approx(3.0)
    assert pd.isna(out["pred_ret"].iloc[1])
    assert out["pred_ret"].iloc[2] == pytest.approx(7.0)
    assert out["pred_is_oos"].eq(False).all()
    assert "pred_prob" in out.columns


def _order_manager(
    connector: FakeConnector,
    *,
    dry_run: bool,
    execution_mode: str,
    max_spread_points: float = 50.0,
    max_spread_points_by_symbol: dict[str, float] | None = None,
    allow_short: bool = False,
) -> MT5OrderManager:
    position_manager = MT5PositionManager(connector, magic_number=MAGIC)
    risk_manager = MT5RiskManager(
        RiskConfig(
            max_spread_points=max_spread_points,
            max_spread_points_by_symbol=max_spread_points_by_symbol or {},
            disable_weekend_trading=False,
            allow_short=allow_short,
        ),
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
