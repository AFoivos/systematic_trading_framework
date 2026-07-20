from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.run_market_making_strategy_suite import (
    load_strategy_config,
    run_strategy_config,
)
from src.market_making.live_engine import BybitLiveMarketMakingEngine
from src.market_making.session_reporting import TABLE_COLUMNS
from src.venues.bybit.instrument import BybitInstrument


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STRATEGY_ROOT = PROJECT_ROOT / "config" / "market_making" / "strategies"
EXECUTION_ROOT = PROJECT_ROOT / "config" / "execution"
JOIN_CONFIG = STRATEGY_ROOT / "01_adaptive_inventory_microprice_bybit_join.yaml"
IMPROVE_CONFIG = STRATEGY_ROOT / "01_adaptive_inventory_microprice_bybit_improve.yaml"
KRAKEN_CONFIG = STRATEGY_ROOT / "01_adaptive_inventory_microprice.yaml"
LOW_CHURN_CONFIG = EXECUTION_ROOT / "bybit_demo_market_making_low_churn.yaml"
CONTINUOUS_CONFIG = EXECUTION_ROOT / "bybit_demo_market_making_continuous.yaml"


def _yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


class _FakeRest:
    def close(self) -> None:
        return None


def _instrument() -> BybitInstrument:
    return BybitInstrument(
        symbol="BTCUSDT",
        category="linear",
        status="Trading",
        contract_type="LinearPerpetual",
        base_coin="BTC",
        quote_coin="USDT",
        settle_coin="USDT",
        tick_size=Decimal("0.25"),
        quantity_step=Decimal("0.01"),
        minimum_order_quantity=Decimal("0.02"),
        minimum_notional=Decimal("50"),
        maximum_order_quantity=Decimal("100"),
        minimum_price=Decimal("0.25"),
        maximum_price=Decimal("2000000"),
    )


def _engine(
    tmp_path: Path,
    *,
    strategy_path: Path,
) -> BybitLiveMarketMakingEngine:
    execution_config = _yaml(LOW_CHURN_CONFIG)
    execution_config["logging"]["output_dir"] = str(tmp_path)
    return BybitLiveMarketMakingEngine(
        config=execution_config,
        strategy_config=_yaml(strategy_path),
        mode="live_dry_run",
        rest_client=_FakeRest(),  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("path", "expected_mode"),
    [
        (JOIN_CONFIG, "join_top_of_book"),
        (IMPROVE_CONFIG, "improve_top_of_book"),
    ],
)
def test_bybit_strategy_variants_pass_validator_and_keep_required_name(
    path: Path,
    expected_mode: str,
) -> None:
    config = load_strategy_config(path)
    result = run_strategy_config(config, config_path=path)

    assert config["experiment"]["name"] == "adaptive_inventory_microprice"
    assert config["strategy"]["type"] == "adaptive_inventory_microprice"
    assert config["quote"]["quote_placement_mode"] == expected_mode
    assert result["strategy_name"] == "adaptive_inventory_microprice"


def test_original_adaptive_strategy_remains_kraken_oriented() -> None:
    config = _yaml(KRAKEN_CONFIG)

    assert config["execution"]["venue"] == "kraken_derivatives"
    assert config["instruments"]["quote_symbol"] == "PF_XBTUSD"
    assert config["quote"]["quote_placement_mode"] == "fair_price_bps"


@pytest.mark.parametrize(
    ("path", "expected_mode"),
    [
        (JOIN_CONFIG, "join_top_of_book"),
        (IMPROVE_CONFIG, "improve_top_of_book"),
    ],
)
def test_live_engine_uses_quote_placement_mode_from_strategy_yaml(
    tmp_path: Path,
    path: Path,
    expected_mode: str,
) -> None:
    engine = _engine(tmp_path, strategy_path=path)
    engine.instrument = _instrument()
    engine._build_strategy_and_risk(reference_price=1000.0)

    assert engine.strategy is not None
    assert engine.strategy.quote_generator.config.quote_placement_mode == expected_mode
    assert engine.reporter.config["runtime_applied"]["quote_placement_mode"] == expected_mode


def test_bybit_metadata_replaces_static_yaml_constraints_for_sizing_and_validation(
    tmp_path: Path,
) -> None:
    # Use the unchanged Kraken YAML deliberately: none of its static exchange
    # constraints may survive construction of a Bybit runtime strategy.
    engine = _engine(tmp_path, strategy_path=KRAKEN_CONFIG)
    instrument = _instrument()
    engine.instrument = instrument
    engine._build_strategy_and_risk(reference_price=1000.0)

    assert engine.strategy is not None
    assert engine.risk_engine is not None
    generator_config = engine.strategy.quote_generator.config
    expected_order_size = 0.06  # ceil((50 * 1.02) / 1000, qtyStep=0.01)
    expected_max_inventory = expected_order_size * 4

    assert generator_config.tick_size == 0.25
    assert generator_config.lot_size == 0.01
    assert generator_config.min_order_size == 0.02
    assert generator_config.min_notional == 50.0
    assert generator_config.order_size == pytest.approx(expected_order_size)
    assert generator_config.max_inventory == pytest.approx(expected_max_inventory)
    assert engine.risk_engine.limits.max_order_size == pytest.approx(expected_order_size)
    assert engine.risk_engine.limits.max_inventory == pytest.approx(expected_max_inventory)

    instrument.validate_order(price=Decimal("1000.00"), quantity=Decimal("0.06"))
    with pytest.raises(ValueError, match="quantity"):
        instrument.validate_order(price=Decimal("1000.00"), quantity=Decimal("0.001"))


def test_runtime_report_contains_actual_placement_mode_and_metadata(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, strategy_path=IMPROVE_CONFIG)
    engine.instrument = _instrument()
    engine._build_strategy_and_risk(reference_price=1000.0)

    runtime = engine.reporter.config["runtime_applied"]
    assert runtime == {
        "quote_placement_mode": "improve_top_of_book",
        "instrument_tick_size": "0.25",
        "instrument_quantity_step": "0.01",
        "instrument_minimum_order_quantity": "0.02",
        "instrument_minimum_notional": "50",
        "runtime_order_size": 0.06,
        "runtime_maximum_inventory": 0.24,
    }

    output = engine.reporter.finalize(
        reconciliation={"status": "test"},
        open_orders_at_end=[],
        position_at_end=[],
        inventory_carried_out=0.0,
    )
    metadata = json.loads((output / "run_metadata.json").read_text(encoding="utf-8"))
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

    assert metadata["quote_placement_mode"] == "improve_top_of_book"
    assert metadata["runtime_applied"] == runtime
    assert summary["quote_placement_mode"] == "improve_top_of_book"
    assert summary["runtime_applied"] == runtime


def test_quote_event_schema_contains_placement_diagnostics() -> None:
    required = {
        "requested_quote_placement_mode",
        "applied_quote_placement_mode",
        "best_bid",
        "best_ask",
        "tick_size",
        "quoted_bid",
        "quoted_ask",
        "quoted_spread_ticks",
        "quoted_spread_bps",
        "fallback_to_join",
    }

    assert required <= set(TABLE_COLUMNS["quote_events"])


def test_no_bybit_tuning_config_enables_order_submission() -> None:
    execution_configs = [
        EXECUTION_ROOT / "bybit_demo_market_making.yaml",
        LOW_CHURN_CONFIG,
    ]
    strategy_configs = [JOIN_CONFIG, IMPROVE_CONFIG]

    for path in execution_configs:
        execution = _yaml(path)["execution"]
        assert execution["mode"] == "live_dry_run"
        assert execution["allow_order_submission"] is False
    for path in strategy_configs:
        execution = _yaml(path)["execution"]
        assert execution["mode"] == "research_smoke"
        assert execution["allow_order_submission"] is False


def test_continuous_bybit_config_is_explicitly_demo_submit_and_low_churn() -> None:
    config = _yaml(CONTINUOUS_CONFIG)
    execution = config["execution"]

    assert execution["environment"] == "demo"
    assert execution["venue"] == "bybit"
    assert execution["mode"] == "demo_submit"
    assert execution["allow_order_submission"] is True
    assert execution["rest_url"] == "https://api-demo.bybit.com"
    assert config["rate_limits"]["minimum_quote_lifetime_ms"] == 3000
    assert config["rate_limits"]["maximum_cancel_rate_per_minute"] == 20
    assert config["risk"]["maximum_session_loss"] == 2.0
