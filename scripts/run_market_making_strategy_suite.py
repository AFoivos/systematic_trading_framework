from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import json
import math
import sys
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.market_data.order_book import LocalOrderBook
from src.market_data.trades import Trade
from src.market_making.quote_generator import QuoteGenerator, QuoteGeneratorConfig
from src.market_making.risk import RiskDecision, RiskEngine, RiskLimits, RiskState
from src.market_making.spread_model import SpreadConfig
from src.market_making.strategies import (
    AdaptiveInventoryMicropriceStrategy,
    AdaptiveInventoryStrategyConfig,
    BasisNeutralStrategyConfig,
    CrossPairSyntheticFairValueStrategy,
    DirectionalFlowStrategyConfig,
    DirectionalOneSidedFlowStrategy,
    ExternalFairQuoteConfig,
    FundingBasisNeutralStrategy,
    QueueAwareJoinImproveStrategy,
    QueueAwareStrategyConfig,
    QueueState,
    StrategyDecision,
    SyntheticFairValueStrategyConfig,
)


CONFIG_DIRECTORY = PROJECT_ROOT / "config" / "market_making" / "strategies"
DEFAULT_STRATEGY_CONFIGS = (
    CONFIG_DIRECTORY / "01_adaptive_inventory_microprice.yaml",
    CONFIG_DIRECTORY / "02_directional_one_sided_flow.yaml",
    CONFIG_DIRECTORY / "03_queue_aware_join_improve.yaml",
    CONFIG_DIRECTORY / "04_funding_basis_neutral.yaml",
    CONFIG_DIRECTORY / "05_cross_pair_synthetic_fair_value.yaml",
)

STRATEGY_NAMES = {
    "adaptive_inventory_microprice",
    "directional_one_sided_flow",
    "queue_aware_join_improve",
    "funding_basis_neutral",
    "cross_pair_synthetic_fair_value",
}
TOP_LEVEL_KEYS = {
    "schema_version",
    "experiment",
    "execution",
    "instruments",
    "quote",
    "fees",
    "risk",
    "strategy",
    "scenario",
}
EXPERIMENT_KEYS = {"name", "description", "research_only"}
EXECUTION_KEYS = {
    "mode",
    "venue",
    "allow_order_submission",
    "quote_order_type",
    "hedge_order_type",
    "stale_order_book_ms",
}
RISK_KEYS = {
    "max_inventory",
    "max_position_value",
    "max_daily_loss",
    "max_open_orders",
    "max_order_size",
    "max_allowed_spread_bps",
    "kill_on_websocket_disconnect",
    "kill_on_stale_order_book",
    "kill_on_spread_widening",
}
SCENARIO_STATE_KEYS = {
    "timestamp",
    "inventory",
    "realized_pnl",
    "unrealized_pnl",
    "open_orders",
    "websocket_connected",
    "books",
}
BOOK_KEYS = {"symbol", "bids", "asks"}
TRADE_KEYS = {"symbol", "price", "quantity", "timestamp", "aggressor_side"}
QUEUE_STATE_KEYS = {
    "bid_queue_ahead",
    "ask_queue_ahead",
    "expected_aggressive_sell_qty",
    "expected_aggressive_buy_qty",
    "bid_cancel_fraction",
    "ask_cancel_fraction",
    "expected_buy_adverse_markout_bps",
    "expected_sell_adverse_markout_bps",
}
GENERATOR_QUOTE_KEYS = {
    "fair_price_model",
    "quote_placement_mode",
    "spread_model",
    "base_spread_bps",
    "min_spread_bps",
    "max_spread_bps",
    "volatility_multiplier",
    "inventory_skew_strength",
    "order_size",
    "max_inventory",
    "tick_size",
    "lot_size",
    "min_order_size",
    "min_notional",
}
QUEUE_QUOTE_KEYS = {
    "order_size",
    "max_inventory",
    "tick_size",
    "lot_size",
    "min_notional",
}
EXTERNAL_QUOTE_KEYS = {
    "spread_bps",
    "order_size",
    "max_inventory",
    "tick_size",
    "lot_size",
    "inventory_skew_strength",
    "min_order_size",
    "min_notional",
}
COMMON_FEE_METADATA_KEYS = {"assumption", "verified_at", "source_url"}


def run_strategy_suite(
    config_paths: Sequence[str | Path] | None = None,
) -> dict[str, dict[str, Any]]:
    """Evaluate the configured research strategies on deterministic causal scenarios."""
    paths = tuple(Path(path) for path in config_paths) if config_paths else DEFAULT_STRATEGY_CONFIGS
    results: dict[str, dict[str, Any]] = {}
    for path in paths:
        config = load_strategy_config(path)
        result = run_strategy_config(config, config_path=path)
        strategy_name = str(result["strategy_name"])
        if strategy_name in results:
            raise ValueError(f"duplicate strategy config for {strategy_name!r}.")
        results[strategy_name] = result
    return results


def load_strategy_config(path: str | Path) -> dict[str, Any]:
    """Load one self-contained strategy YAML and reject unsupported structure."""
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path
    if not config_path.is_file():
        raise FileNotFoundError(f"market-making strategy config not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    config = dict(_mapping(payload, str(config_path)))
    _validate_config(config)
    return config


def run_strategy_config(
    config: Mapping[str, Any],
    *,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run a validated YAML scenario and apply the central research risk gate."""
    normalized = dict(config)
    _validate_config(normalized)
    decision, quote_book, scenario_time = _decision_from_config(normalized)
    risk_decision = _check_risk(
        config=normalized,
        decision=decision,
        quote_book=quote_book,
        scenario_time=scenario_time,
    )
    result = _serialize_decision(decision)
    result.update(
        {
            "strategy_name": decision.strategy_name,
            "config_path": _portable_path(config_path),
            "risk_allowed": risk_decision.allowed,
            "risk_reason": risk_decision.reason,
            "risk_cancel_all": risk_decision.cancel_all,
            "risk_kill_switch": risk_decision.kill_switch,
        }
    )
    return result


def _validate_config(config: Mapping[str, Any]) -> None:
    _require_exact_keys(config, TOP_LEVEL_KEYS, "config")
    schema_version = config["schema_version"]
    if isinstance(schema_version, bool) or schema_version != 1:
        raise ValueError("schema_version must be integer 1.")

    experiment = _mapping(config["experiment"], "experiment")
    execution = _mapping(config["execution"], "execution")
    strategy = _mapping(config["strategy"], "strategy")
    risk = _mapping(config["risk"], "risk")
    _require_exact_keys(experiment, EXPERIMENT_KEYS, "experiment")
    _require_exact_keys(execution, EXECUTION_KEYS, "execution")
    _require_exact_keys(strategy, {"type", "parameters"}, "strategy")
    _require_exact_keys(risk, RISK_KEYS, "risk")

    strategy_type = _string(strategy["type"], "strategy.type")
    if strategy_type not in STRATEGY_NAMES:
        raise ValueError(f"unsupported strategy.type: {strategy_type!r}.")
    if _string(experiment["name"], "experiment.name") != strategy_type:
        raise ValueError("experiment.name must exactly match strategy.type.")
    _string(experiment["description"], "experiment.description")
    if experiment["research_only"] is not True:
        raise ValueError("experiment.research_only must be true.")

    if execution["mode"] != "research_smoke":
        raise ValueError("execution.mode must be research_smoke.")
    if execution["allow_order_submission"] is not False:
        raise ValueError("execution.allow_order_submission must be false.")
    if execution["quote_order_type"] != "post_only":
        raise ValueError("execution.quote_order_type must be post_only.")
    if execution["hedge_order_type"] not in {"none", "ioc"}:
        raise ValueError("execution.hedge_order_type must be none or ioc.")
    stale_ms = _integer(execution["stale_order_book_ms"], "execution.stale_order_book_ms")
    if stale_ms <= 0:
        raise ValueError("execution.stale_order_book_ms must be > 0.")

    _validate_strategy_sections(config, strategy_type)
    _validate_risk_alignment(config, strategy_type)


def _validate_strategy_sections(config: Mapping[str, Any], strategy_type: str) -> None:
    instruments = _mapping(config["instruments"], "instruments")
    quote = _mapping(config["quote"], "quote")
    fees = _mapping(config["fees"], "fees")
    strategy = _mapping(config["strategy"], "strategy")
    parameters = _mapping(strategy["parameters"], "strategy.parameters")
    scenario = _mapping(config["scenario"], "scenario")

    if strategy_type in {"adaptive_inventory_microprice", "directional_one_sided_flow"}:
        _require_exact_keys(instruments, {"quote_symbol", "quote_market"}, "instruments")
        _require_exact_keys(quote, GENERATOR_QUOTE_KEYS, "quote")
        _require_exact_keys(
            fees,
            {"maker_fee_bps", "taker_fee_bps"} | COMMON_FEE_METADATA_KEYS,
            "fees",
        )
    elif strategy_type == "queue_aware_join_improve":
        _require_exact_keys(instruments, {"quote_symbol", "quote_market"}, "instruments")
        _require_exact_keys(quote, QUEUE_QUOTE_KEYS, "quote")
        _require_exact_keys(
            fees,
            {"maker_fee_bps", "taker_fee_bps"} | COMMON_FEE_METADATA_KEYS,
            "fees",
        )
    elif strategy_type == "funding_basis_neutral":
        _require_exact_keys(
            instruments,
            {"quote_symbol", "quote_market", "hedge_symbol", "hedge_market"},
            "instruments",
        )
        _require_exact_keys(quote, EXTERNAL_QUOTE_KEYS, "quote")
        _require_exact_keys(
            fees,
            {
                "quote_maker_fee_bps",
                "hedge_taker_fee_bps",
                "hedge_slippage_bps",
            }
            | COMMON_FEE_METADATA_KEYS,
            "fees",
        )
    else:
        _require_exact_keys(
            instruments,
            {
                "target_symbol",
                "target_market",
                "numerator_symbol",
                "denominator_symbol",
                "hedge_market",
            },
            "instruments",
        )
        _require_exact_keys(quote, EXTERNAL_QUOTE_KEYS, "quote")
        _require_exact_keys(
            fees,
            {
                "target_maker_fee_bps",
                "numerator_hedge_taker_fee_bps",
                "denominator_hedge_taker_fee_bps",
                "aggregate_hedge_slippage_bps",
            }
            | COMMON_FEE_METADATA_KEYS,
            "fees",
        )

    expected_parameters = {
        "adaptive_inventory_microprice": {
            "min_expected_edge_bps",
            "adverse_selection_buffer_bps",
            "inventory_penalty_bps_per_unit",
        },
        "directional_one_sided_flow": {
            "imbalance_weight",
            "trade_flow_weight",
            "trend_weight",
            "trend_scale_bps",
            "min_abs_signal",
            "max_volatility_bps",
            "inventory_soft_limit_ratio",
            "adverse_selection_buffer_bps",
            "signal_edge_credit_bps",
            "min_expected_edge_bps",
            "quote_both_when_neutral",
        },
        "queue_aware_join_improve": {
            "min_expected_edge_bps",
            "replacement_cost_bps",
            "inventory_penalty_bps_per_unit",
            "allow_improve",
        },
        "funding_basis_neutral": {
            "target_basis_bps",
            "funding_to_basis_multiplier",
            "min_expected_edge_bps",
            "min_dislocation_bps",
            "max_abs_observed_basis_bps",
            "max_book_time_skew_ms",
            "quote_both_when_neutral",
            "hedge_ratio",
        },
        "cross_pair_synthetic_fair_value": {
            "min_expected_edge_bps",
            "min_dislocation_bps",
            "max_abs_dislocation_bps",
            "max_book_time_skew_ms",
            "quote_both_when_neutral",
        },
    }[strategy_type]
    _require_exact_keys(parameters, expected_parameters, "strategy.parameters")

    scenario_keys = set(SCENARIO_STATE_KEYS)
    if strategy_type in {"adaptive_inventory_microprice", "directional_one_sided_flow"}:
        scenario_keys.add("recent_returns")
    if strategy_type == "directional_one_sided_flow":
        scenario_keys.add("trades")
    if strategy_type == "queue_aware_join_improve":
        scenario_keys.add("queue_state")
    if strategy_type == "funding_basis_neutral":
        scenario_keys.add("expected_funding_bps")
    _require_exact_keys(scenario, scenario_keys, "scenario")

    _validate_fee_metadata(fees)
    _validate_execution_and_instruments(config, strategy_type)
    _validate_scenario(config, strategy_type)
    _instantiate_strategy(config, strategy_type)
    _risk_limits(config)


def _validate_fee_metadata(fees: Mapping[str, Any]) -> None:
    _string(fees["assumption"], "fees.assumption")
    _string(fees["verified_at"], "fees.verified_at")
    source_url = _string(fees["source_url"], "fees.source_url")
    if not source_url.startswith("https://"):
        raise ValueError("fees.source_url must be an https URL.")
    for key, value in fees.items():
        if key.endswith("_bps"):
            _finite_float(value, f"fees.{key}")


def _validate_execution_and_instruments(
    config: Mapping[str, Any],
    strategy_type: str,
) -> None:
    execution = _mapping(config["execution"], "execution")
    instruments = _mapping(config["instruments"], "instruments")
    expected_venue = {
        "adaptive_inventory_microprice": "kraken_derivatives",
        "directional_one_sided_flow": "kraken_derivatives",
        "queue_aware_join_improve": "kraken_derivatives",
        "funding_basis_neutral": "kraken_spot_and_derivatives",
        "cross_pair_synthetic_fair_value": "kraken_spot",
    }[strategy_type]
    if execution["venue"] != expected_venue:
        raise ValueError(f"execution.venue must be {expected_venue!r} for {strategy_type}.")
    expected_hedge_type = (
        "ioc"
        if strategy_type in {"funding_basis_neutral", "cross_pair_synthetic_fair_value"}
        else "none"
    )
    if execution["hedge_order_type"] != expected_hedge_type:
        raise ValueError(
            f"execution.hedge_order_type must be {expected_hedge_type!r} for {strategy_type}."
        )
    for key, value in instruments.items():
        _string(value, f"instruments.{key}")
    if strategy_type in {
        "adaptive_inventory_microprice",
        "directional_one_sided_flow",
        "queue_aware_join_improve",
    } and instruments["quote_market"] != "derivatives_perpetual":
        raise ValueError("instruments.quote_market must be derivatives_perpetual.")
    if strategy_type == "funding_basis_neutral":
        if instruments["quote_market"] != "derivatives_perpetual":
            raise ValueError("instruments.quote_market must be derivatives_perpetual.")
        if instruments["hedge_market"] != "spot":
            raise ValueError("instruments.hedge_market must be spot.")
    if strategy_type == "cross_pair_synthetic_fair_value":
        if instruments["target_market"] != "spot" or instruments["hedge_market"] != "spot":
            raise ValueError("synthetic target_market and hedge_market must both be spot.")


def _validate_scenario(config: Mapping[str, Any], strategy_type: str) -> None:
    scenario = _mapping(config["scenario"], "scenario")
    instruments = _mapping(config["instruments"], "instruments")
    timestamp = _timestamp(scenario["timestamp"], "scenario.timestamp")
    _finite_float(scenario["inventory"], "scenario.inventory")
    _finite_float(scenario["realized_pnl"], "scenario.realized_pnl")
    _finite_float(scenario["unrealized_pnl"], "scenario.unrealized_pnl")
    _integer(scenario["open_orders"], "scenario.open_orders")
    _boolean(scenario["websocket_connected"], "scenario.websocket_connected")

    if strategy_type in {
        "adaptive_inventory_microprice",
        "directional_one_sided_flow",
        "queue_aware_join_improve",
    }:
        expected_books = {"quote": instruments["quote_symbol"]}
    elif strategy_type == "funding_basis_neutral":
        expected_books = {
            "quote": instruments["quote_symbol"],
            "hedge": instruments["hedge_symbol"],
        }
    else:
        expected_books = {
            "target": instruments["target_symbol"],
            "numerator": instruments["numerator_symbol"],
            "denominator": instruments["denominator_symbol"],
        }
    books = _mapping(scenario["books"], "scenario.books")
    _require_exact_keys(books, set(expected_books), "scenario.books")
    for book_name, expected_symbol in expected_books.items():
        book = _book_from_mapping(
            books[book_name],
            timestamp=timestamp,
            label=f"scenario.books.{book_name}",
        )
        if book.symbol != expected_symbol:
            raise ValueError(
                f"scenario.books.{book_name}.symbol must match instruments: {expected_symbol!r}."
            )

    if "recent_returns" in scenario:
        _float_sequence(scenario["recent_returns"], "scenario.recent_returns")
    if "trades" in scenario:
        _trades_from_scenario(scenario, expected_symbol=str(instruments["quote_symbol"]))
    if "queue_state" in scenario:
        queue_state = _mapping(scenario["queue_state"], "scenario.queue_state")
        _require_exact_keys(queue_state, QUEUE_STATE_KEYS, "scenario.queue_state")
        QueueState(**{key: queue_state[key] for key in QUEUE_STATE_KEYS})
    if "expected_funding_bps" in scenario:
        _finite_float(scenario["expected_funding_bps"], "scenario.expected_funding_bps")


def _instantiate_strategy(config: Mapping[str, Any], strategy_type: str) -> object:
    parameters = _mapping(
        _mapping(config["strategy"], "strategy")["parameters"],
        "strategy.parameters",
    )
    fees = _mapping(config["fees"], "fees")
    if strategy_type == "adaptive_inventory_microprice":
        return AdaptiveInventoryMicropriceStrategy(
            quote_generator=_quote_generator(config),
            config=AdaptiveInventoryStrategyConfig(
                maker_fee_bps=fees["maker_fee_bps"],
                **parameters,
            ),
        )
    if strategy_type == "directional_one_sided_flow":
        return DirectionalOneSidedFlowStrategy(
            quote_generator=_quote_generator(config),
            config=DirectionalFlowStrategyConfig(
                maker_fee_bps=fees["maker_fee_bps"],
                **parameters,
            ),
        )
    if strategy_type == "queue_aware_join_improve":
        quote = _mapping(config["quote"], "quote")
        return QueueAwareJoinImproveStrategy(
            QueueAwareStrategyConfig(
                **quote,
                maker_fee_bps=fees["maker_fee_bps"],
                **parameters,
            )
        )
    if strategy_type == "funding_basis_neutral":
        return FundingBasisNeutralStrategy(
            BasisNeutralStrategyConfig(
                quote=_external_quote_config(config),
                maker_fee_bps=fees["quote_maker_fee_bps"],
                hedge_fee_bps=fees["hedge_taker_fee_bps"],
                hedge_slippage_bps=fees["hedge_slippage_bps"],
                **parameters,
            )
        )
    return CrossPairSyntheticFairValueStrategy(
        SyntheticFairValueStrategyConfig(
            quote=_external_quote_config(config),
            maker_fee_bps=fees["target_maker_fee_bps"],
            aggregate_hedge_cost_bps=(
                fees["numerator_hedge_taker_fee_bps"]
                + fees["denominator_hedge_taker_fee_bps"]
                + fees["aggregate_hedge_slippage_bps"]
            ),
            **parameters,
        )
    )


def _decision_from_config(
    config: Mapping[str, Any],
) -> tuple[StrategyDecision, LocalOrderBook, datetime]:
    strategy_type = str(_mapping(config["strategy"], "strategy")["type"])
    strategy = _instantiate_strategy(config, strategy_type)
    scenario = _mapping(config["scenario"], "scenario")
    timestamp = _timestamp(scenario["timestamp"], "scenario.timestamp")
    books = _mapping(scenario["books"], "scenario.books")
    inventory = _finite_float(scenario["inventory"], "scenario.inventory")

    if strategy_type == "adaptive_inventory_microprice":
        quote_book = _book_from_mapping(
            books["quote"], timestamp=timestamp, label="scenario.books.quote"
        )
        assert isinstance(strategy, AdaptiveInventoryMicropriceStrategy)
        decision = strategy.decide(
            book=quote_book,
            inventory=inventory,
            recent_returns=_float_sequence(
                scenario["recent_returns"], "scenario.recent_returns"
            ),
        )
    elif strategy_type == "directional_one_sided_flow":
        quote_book = _book_from_mapping(
            books["quote"], timestamp=timestamp, label="scenario.books.quote"
        )
        instruments = _mapping(config["instruments"], "instruments")
        assert isinstance(strategy, DirectionalOneSidedFlowStrategy)
        decision = strategy.decide(
            book=quote_book,
            inventory=inventory,
            recent_returns=_float_sequence(
                scenario["recent_returns"], "scenario.recent_returns"
            ),
            recent_trades=_trades_from_scenario(
                scenario,
                expected_symbol=str(instruments["quote_symbol"]),
            ),
        )
    elif strategy_type == "queue_aware_join_improve":
        quote_book = _book_from_mapping(
            books["quote"], timestamp=timestamp, label="scenario.books.quote"
        )
        queue_state = _mapping(scenario["queue_state"], "scenario.queue_state")
        assert isinstance(strategy, QueueAwareJoinImproveStrategy)
        decision = strategy.decide(
            book=quote_book,
            inventory=inventory,
            queue_state=QueueState(**{key: queue_state[key] for key in QUEUE_STATE_KEYS}),
        )
    elif strategy_type == "funding_basis_neutral":
        quote_book = _book_from_mapping(
            books["quote"], timestamp=timestamp, label="scenario.books.quote"
        )
        hedge_book = _book_from_mapping(
            books["hedge"], timestamp=timestamp, label="scenario.books.hedge"
        )
        assert isinstance(strategy, FundingBasisNeutralStrategy)
        decision = strategy.decide(
            perpetual_book=quote_book,
            hedge_book=hedge_book,
            inventory=inventory,
            expected_funding_bps=_finite_float(
                scenario["expected_funding_bps"],
                "scenario.expected_funding_bps",
            ),
        )
    else:
        quote_book = _book_from_mapping(
            books["target"], timestamp=timestamp, label="scenario.books.target"
        )
        numerator_book = _book_from_mapping(
            books["numerator"], timestamp=timestamp, label="scenario.books.numerator"
        )
        denominator_book = _book_from_mapping(
            books["denominator"], timestamp=timestamp, label="scenario.books.denominator"
        )
        assert isinstance(strategy, CrossPairSyntheticFairValueStrategy)
        decision = strategy.decide(
            target_book=quote_book,
            numerator_book=numerator_book,
            denominator_book=denominator_book,
            inventory=inventory,
        )
    return decision, quote_book, timestamp


def _quote_generator(config: Mapping[str, Any]) -> QuoteGenerator:
    quote = _mapping(config["quote"], "quote")
    fees = _mapping(config["fees"], "fees")
    return QuoteGenerator(
        QuoteGeneratorConfig(
            fair_price_model=quote["fair_price_model"],
            quote_placement_mode=quote["quote_placement_mode"],
            spread=SpreadConfig(
                model=quote["spread_model"],
                base_spread_bps=quote["base_spread_bps"],
                min_spread_bps=quote["min_spread_bps"],
                max_spread_bps=quote["max_spread_bps"],
                maker_fee_bps=fees["maker_fee_bps"],
                taker_fee_bps=fees["taker_fee_bps"],
                volatility_multiplier=quote["volatility_multiplier"],
            ),
            inventory_skew_strength=quote["inventory_skew_strength"],
            order_size=quote["order_size"],
            max_inventory=quote["max_inventory"],
            tick_size=quote["tick_size"],
            lot_size=quote["lot_size"],
            min_order_size=quote["min_order_size"],
            min_notional=quote["min_notional"],
        )
    )


def _external_quote_config(config: Mapping[str, Any]) -> ExternalFairQuoteConfig:
    quote = _mapping(config["quote"], "quote")
    return ExternalFairQuoteConfig(**quote)


def _risk_limits(config: Mapping[str, Any]) -> RiskLimits:
    risk = _mapping(config["risk"], "risk")
    execution = _mapping(config["execution"], "execution")
    return RiskLimits(
        max_inventory=risk["max_inventory"],
        max_position_value=risk["max_position_value"],
        max_daily_loss=risk["max_daily_loss"],
        max_open_orders=risk["max_open_orders"],
        max_order_size=risk["max_order_size"],
        max_allowed_spread_bps=risk["max_allowed_spread_bps"],
        stale_order_book_ms=execution["stale_order_book_ms"],
        kill_on_websocket_disconnect=risk["kill_on_websocket_disconnect"],
        kill_on_stale_order_book=risk["kill_on_stale_order_book"],
        kill_on_spread_widening=risk["kill_on_spread_widening"],
    )


def _validate_risk_alignment(config: Mapping[str, Any], strategy_type: str) -> None:
    risk = _mapping(config["risk"], "risk")
    quote = _mapping(config["quote"], "quote")
    max_inventory = _finite_float(risk["max_inventory"], "risk.max_inventory")
    quote_inventory = _finite_float(quote["max_inventory"], "quote.max_inventory")
    if not math.isclose(max_inventory, quote_inventory, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("risk.max_inventory must exactly match quote.max_inventory.")
    max_order_size = _finite_float(risk["max_order_size"], "risk.max_order_size")
    order_size = _finite_float(quote["order_size"], "quote.order_size")
    if max_order_size < order_size:
        raise ValueError("risk.max_order_size must be >= quote.order_size.")
    if strategy_type in {"adaptive_inventory_microprice", "directional_one_sided_flow"}:
        if quote["fair_price_model"] not in {"mid_price", "microprice"}:
            raise ValueError("quote.fair_price_model must be mid_price or microprice.")
        if quote["quote_placement_mode"] not in {
            "fair_price_bps",
            "join_top_of_book",
            "improve_top_of_book",
        }:
            raise ValueError("unsupported quote.quote_placement_mode.")


def _check_risk(
    *,
    config: Mapping[str, Any],
    decision: StrategyDecision,
    quote_book: LocalOrderBook,
    scenario_time: datetime,
) -> RiskDecision:
    scenario = _mapping(config["scenario"], "scenario")
    engine = RiskEngine(_risk_limits(config))
    return engine.check_quote(
        quote=decision.quote,
        book=quote_book,
        state=RiskState(
            inventory=scenario["inventory"],
            realized_pnl=scenario["realized_pnl"],
            unrealized_pnl=scenario["unrealized_pnl"],
            open_orders=scenario["open_orders"],
            websocket_connected=scenario["websocket_connected"],
            now=scenario_time,
        ),
    )


def _book_from_mapping(
    value: Any,
    *,
    timestamp: datetime,
    label: str,
) -> LocalOrderBook:
    payload = _mapping(value, label)
    _require_exact_keys(payload, BOOK_KEYS, label)
    symbol = _string(payload["symbol"], f"{label}.symbol")
    bids = _book_levels(payload["bids"], f"{label}.bids")
    asks = _book_levels(payload["asks"], f"{label}.asks")
    if not bids or not asks:
        raise ValueError(f"{label} must contain at least one bid and one ask.")
    book = LocalOrderBook(symbol)
    book.apply_snapshot(bids=bids, asks=asks, timestamp=timestamp, sequence=1)
    return book


def _book_levels(value: Any, label: str) -> list[tuple[float, float]]:
    sequence = _sequence(value, label)
    levels: list[tuple[float, float]] = []
    for index, level in enumerate(sequence):
        pair = _sequence(level, f"{label}[{index}]")
        if len(pair) != 2:
            raise ValueError(f"{label}[{index}] must contain [price, quantity].")
        price = _finite_float(pair[0], f"{label}[{index}][0]")
        quantity = _finite_float(pair[1], f"{label}[{index}][1]")
        if price <= 0.0 or quantity <= 0.0:
            raise ValueError(f"{label}[{index}] price and quantity must be > 0.")
        levels.append((price, quantity))
    return levels


def _trades_from_scenario(
    scenario: Mapping[str, Any],
    *,
    expected_symbol: str,
) -> list[Trade]:
    decision_time = _timestamp(scenario["timestamp"], "scenario.timestamp")
    trades = []
    for index, value in enumerate(_sequence(scenario["trades"], "scenario.trades")):
        label = f"scenario.trades[{index}]"
        payload = _mapping(value, label)
        _require_exact_keys(payload, TRADE_KEYS, label)
        symbol = _string(payload["symbol"], f"{label}.symbol")
        if symbol != expected_symbol:
            raise ValueError(f"{label}.symbol must be {expected_symbol!r}.")
        trade_time = _timestamp(payload["timestamp"], f"{label}.timestamp")
        if trade_time > decision_time:
            raise ValueError(f"{label}.timestamp cannot be after scenario.timestamp.")
        aggressor_side = _string(payload["aggressor_side"], f"{label}.aggressor_side")
        if aggressor_side not in {"buy", "sell", "unknown"}:
            raise ValueError(f"{label}.aggressor_side must be buy, sell, or unknown.")
        trades.append(
            Trade(
                symbol=symbol,
                price=_finite_float(payload["price"], f"{label}.price"),
                quantity=_finite_float(payload["quantity"], f"{label}.quantity"),
                timestamp=trade_time,
                aggressor_side=aggressor_side,
            )
        )
    return trades


def _serialize_decision(decision: StrategyDecision) -> dict[str, Any]:
    quote = decision.quote
    active_side = (
        "buy"
        if quote.bid_price is not None
        else "sell"
        if quote.ask_price is not None
        else None
    )
    fill_price = (
        quote.bid_price
        if active_side == "buy"
        else quote.ask_price
        if active_side == "sell"
        else None
    )
    fill_quantity = (
        quote.bid_size
        if active_side == "buy"
        else quote.ask_size
        if active_side == "sell"
        else 0.0
    )
    hedges = (
        decision.hedges_for_fill(
            fill_side=active_side,
            fill_quantity=float(fill_quantity),
            fill_price=float(fill_price),
        )
        if active_side is not None and fill_price is not None and fill_quantity > 0.0
        else ()
    )
    return {
        "should_quote": quote.should_quote,
        "reason": quote.reason,
        "bid_price": quote.bid_price,
        "ask_price": quote.ask_price,
        "bid_size": quote.bid_size,
        "ask_size": quote.ask_size,
        "fair_price": quote.fair_price,
        "expected_edge_bps": decision.expected_edge_bps,
        "diagnostics": dict(decision.diagnostics),
        "example_fill_side": active_side,
        "example_fill_quantity": fill_quantity,
        "example_hedges": [
            {
                "symbol": hedge.symbol,
                "side": hedge.side,
                "quantity": hedge.quantity,
                "reference_price": hedge.reference_price,
                "order_type": hedge.order_type,
            }
            for hedge in hedges
        ],
    }


def _require_exact_keys(
    payload: Mapping[str, Any],
    expected: set[str],
    label: str,
) -> None:
    actual = set(payload)
    missing = sorted(expected - actual)
    unsupported = sorted(actual - expected)
    if missing or unsupported:
        details = []
        if missing:
            details.append(f"missing={missing}")
        if unsupported:
            details.append(f"unsupported={unsupported}")
        raise ValueError(f"{label} has invalid keys: {', '.join(details)}.")


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping.")
    if not all(isinstance(key, str) for key in value):
        raise ValueError(f"{label} keys must be strings.")
    return value


def _sequence(value: Any, label: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{label} must be a sequence.")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string.")
    return value


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean.")
    return value


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer.")
    return value


def _finite_float(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite.")
    return number


def _float_sequence(value: Any, label: str) -> list[float]:
    return [
        _finite_float(item, f"{label}[{index}]")
        for index, item in enumerate(_sequence(value, label))
    ]


def _timestamp(value: Any, label: str) -> datetime:
    if isinstance(value, datetime):
        timestamp = value
    elif isinstance(value, str):
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{label} must be an ISO-8601 timestamp.") from exc
    else:
        raise ValueError(f"{label} must be an ISO-8601 timestamp string.")
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone offset.")
    return timestamp.astimezone(timezone.utc)


def _portable_path(path: str | Path | None) -> str | None:
    if path is None:
        return None
    candidate = Path(path)
    absolute = candidate if candidate.is_absolute() else PROJECT_ROOT / candidate
    try:
        return str(absolute.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(absolute.resolve())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run deterministic research-only market-making YAML scenarios."
    )
    parser.add_argument(
        "--config",
        action="append",
        default=None,
        help="Strategy YAML path. Repeat to run multiple configs; omit to run all five.",
    )
    args = parser.parse_args()
    print(json.dumps(run_strategy_suite(args.config), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
