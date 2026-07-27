from __future__ import annotations

"""Causal research harness for spot/perpetual positive-funding carry.

The strategy is deliberately rules-only: after funding settlement ``t`` is
known, a trailing forecast determines the position held over ``(t, t+1]``.
Consequently, the funding rate received at ``t+1`` is never an input to the
decision that earns it.  Each evaluation split starts flat and is liquidated
at its final settlement so transaction costs cannot leak across split edges.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
import yaml

from src.evaluation.metrics import compute_backtest_metrics
from src.experiments.support.funding_carry_reporting import (
    build_extended_metrics,
    build_reporting_tables,
    flatten_metrics,
)
from src.src_data.binance_public import load_binance_snapshot_frame
from src.utils.paths import enforce_safe_absolute_path
from src.utils.run_metadata import collect_git_metadata, file_sha256


@dataclass(frozen=True)
class FundingCarryDataSpec:
    snapshot_dir: Path
    symbols: tuple[str, ...]
    interval: str
    start: pd.Timestamp
    end: pd.Timestamp
    verify_hashes: bool
    max_price_age_minutes: int


@dataclass(frozen=True)
class FundingCarrySignalSpec:
    lookback_events: int
    expected_holding_events: int
    expected_funding_interval_hours: float
    entry_cost_multiplier: float
    exit_forecast_rate: float
    max_holding_events: int
    positive_funding_only: bool


@dataclass(frozen=True)
class FundingCarryExecutionSpec:
    spot_fee_bps_per_side: float
    perpetual_fee_bps_per_side: float
    spot_slippage_bps_per_side: float
    perpetual_slippage_bps_per_side: float
    capital_per_spot_notional: float
    annual_financing_rate: float
    max_execution_price_age_minutes: int

    @property
    def one_way_transaction_cost(self) -> float:
        return (
            self.spot_fee_bps_per_side
            + self.perpetual_fee_bps_per_side
            + self.spot_slippage_bps_per_side
            + self.perpetual_slippage_bps_per_side
        ) / 10_000.0

    @property
    def round_trip_transaction_cost(self) -> float:
        return 2.0 * self.one_way_transaction_cost


@dataclass(frozen=True)
class FundingCarrySplit:
    name: str
    start: pd.Timestamp
    end: pd.Timestamp
    locked: bool


@dataclass(frozen=True)
class FundingCarryResearchSpec:
    timezone: str
    periods_per_year: int
    splits: tuple[FundingCarrySplit, ...]


@dataclass(frozen=True)
class FundingCarryAcceptanceSpec:
    validation_split: str
    min_portfolio_sharpe: float
    min_portfolio_cumulative_return: float
    min_entries_per_symbol: int
    require_positive_each_symbol: bool
    cost_stress_multiplier: float


@dataclass(frozen=True)
class FundingCarryArtifactSpec:
    output_root: Path


@dataclass(frozen=True)
class FundingCarryBootstrapSpec:
    enabled: bool
    samples: int
    block_length_days: int
    confidence_level: float
    random_seed: int


@dataclass(frozen=True)
class FundingCarryReportingSpec:
    extended_performance_metrics: bool
    risk_and_tail_metrics: bool
    drawdown_metrics: bool
    trade_metrics: bool
    funding_and_basis_attribution: bool
    cost_attribution: bool
    exposure_and_leverage_metrics: bool
    calendar_metrics: bool
    rolling_metrics: bool
    data_quality_metrics: bool
    write_event_level_csv: bool
    write_trade_ledger_csv: bool
    write_calendar_returns_csv: bool
    write_rolling_metrics_csv: bool
    write_flat_metrics_csv: bool
    var_confidence_levels: tuple[float, ...]
    rolling_windows_days: tuple[int, ...]
    cost_stress_multipliers: tuple[float, ...]
    bootstrap: FundingCarryBootstrapSpec


@dataclass(frozen=True)
class FundingCarryConfig:
    version: int
    strategy_id: str
    hypothesis: str
    preregistered_at_utc: str
    data: FundingCarryDataSpec
    signal: FundingCarrySignalSpec
    execution: FundingCarryExecutionSpec
    research: FundingCarryResearchSpec
    acceptance: FundingCarryAcceptanceSpec
    artifacts: FundingCarryArtifactSpec
    reporting: FundingCarryReportingSpec
    config_path: Path
    config_sha256: str
    parent_strategy_id: str | None = None
    revision_scope: str | None = None


@dataclass
class FundingCarrySegmentResult:
    symbol_events: dict[str, pd.DataFrame]
    symbol_metrics: dict[str, dict[str, Any]]
    portfolio: pd.DataFrame
    portfolio_metrics: dict[str, Any]


@dataclass
class FundingCarryRunResult:
    strategy_id: str
    phase: str
    cost_multiplier: float
    segments: dict[str, FundingCarrySegmentResult]
    acceptance: dict[str, Any] | None
    cost_stress: dict[str, Any] | None = None


def _require_mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a mapping.")
    return value


def _require_exact_keys(
    value: Mapping[str, Any],
    *,
    field: str,
    required: set[str],
) -> None:
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required)
    if missing or unknown:
        raise ValueError(f"{field} keys mismatch; missing={missing}, unknown={unknown}.")


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a positive integer.")
    result = int(value)
    if result <= 0 or float(value) != result:
        raise ValueError(f"{field} must be a positive integer.")
    return result


def _nonnegative_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a nonnegative integer.")
    result = int(value)
    if result < 0 or float(value) != result:
        raise ValueError(f"{field} must be a nonnegative integer.")
    return result


def _finite_float(value: Any, *, field: str) -> float:
    result = float(value)
    if not np.isfinite(result):
        raise ValueError(f"{field} must be finite.")
    return result


def _positive_float(value: Any, *, field: str) -> float:
    result = _finite_float(value, field=field)
    if result <= 0.0:
        raise ValueError(f"{field} must be > 0.")
    return result


def _nonnegative_float(value: Any, *, field: str) -> float:
    result = _finite_float(value, field=field)
    if result < 0.0:
        raise ValueError(f"{field} must be >= 0.")
    return result


def _utc_timestamp(value: Any, *, field: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        raise ValueError(f"{field} must be a valid timestamp.")
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp


def _resolve_project_path(value: Any, *, field: str) -> Path:
    raw = str(value).strip()
    if not raw:
        raise ValueError(f"{field} must be a non-empty path.")
    path = Path(raw)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[3] / path
    return enforce_safe_absolute_path(path.resolve())


def _strict_bool(value: Any, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be boolean.")
    return value


def _unique_positive_ints(value: Any, *, field: str) -> tuple[int, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise ValueError(f"{field} must be a non-empty list of positive integers.")
    values = tuple(_positive_int(item, field=f"{field}[]") for item in value)
    if len(set(values)) != len(values):
        raise ValueError(f"{field} must not contain duplicates.")
    return values


def _unique_positive_floats(value: Any, *, field: str) -> tuple[float, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise ValueError(f"{field} must be a non-empty list of positive numbers.")
    values = tuple(_positive_float(item, field=f"{field}[]") for item in value)
    if len(set(values)) != len(values):
        raise ValueError(f"{field} must not contain duplicates.")
    return values


def _default_reporting_spec(*, cost_stress_multiplier: float) -> FundingCarryReportingSpec:
    return FundingCarryReportingSpec(
        extended_performance_metrics=False,
        risk_and_tail_metrics=False,
        drawdown_metrics=False,
        trade_metrics=False,
        funding_and_basis_attribution=False,
        cost_attribution=False,
        exposure_and_leverage_metrics=False,
        calendar_metrics=False,
        rolling_metrics=False,
        data_quality_metrics=False,
        write_event_level_csv=True,
        write_trade_ledger_csv=False,
        write_calendar_returns_csv=False,
        write_rolling_metrics_csv=False,
        write_flat_metrics_csv=False,
        var_confidence_levels=(0.95, 0.99),
        rolling_windows_days=(30, 90, 180, 365),
        cost_stress_multipliers=(1.0, cost_stress_multiplier),
        bootstrap=FundingCarryBootstrapSpec(
            enabled=False,
            samples=1_000,
            block_length_days=21,
            confidence_level=0.95,
            random_seed=42,
        ),
    )


def _parse_reporting_spec(value: Any) -> FundingCarryReportingSpec:
    reporting = _require_mapping(value, field="reporting")
    bool_fields = {
        "extended_performance_metrics",
        "risk_and_tail_metrics",
        "drawdown_metrics",
        "trade_metrics",
        "funding_and_basis_attribution",
        "cost_attribution",
        "exposure_and_leverage_metrics",
        "calendar_metrics",
        "rolling_metrics",
        "data_quality_metrics",
        "write_event_level_csv",
        "write_trade_ledger_csv",
        "write_calendar_returns_csv",
        "write_rolling_metrics_csv",
        "write_flat_metrics_csv",
    }
    required = bool_fields | {
        "var_confidence_levels",
        "rolling_windows_days",
        "cost_stress_multipliers",
        "bootstrap",
    }
    _require_exact_keys(reporting, field="reporting", required=required)
    confidence_levels = _unique_positive_floats(
        reporting["var_confidence_levels"], field="reporting.var_confidence_levels"
    )
    if any(value >= 1.0 for value in confidence_levels):
        raise ValueError("reporting.var_confidence_levels values must be < 1.")
    stress_multipliers = _unique_positive_floats(
        reporting["cost_stress_multipliers"],
        field="reporting.cost_stress_multipliers",
    )
    if 1.0 not in stress_multipliers:
        raise ValueError("reporting.cost_stress_multipliers must include 1.0.")

    bootstrap = _require_mapping(reporting["bootstrap"], field="reporting.bootstrap")
    _require_exact_keys(
        bootstrap,
        field="reporting.bootstrap",
        required={"enabled", "samples", "block_length_days", "confidence_level", "random_seed"},
    )
    bootstrap_confidence = _positive_float(
        bootstrap["confidence_level"], field="reporting.bootstrap.confidence_level"
    )
    if bootstrap_confidence >= 1.0:
        raise ValueError("reporting.bootstrap.confidence_level must be < 1.")
    return FundingCarryReportingSpec(
        **{
            field: _strict_bool(reporting[field], field=f"reporting.{field}")
            for field in bool_fields
        },
        var_confidence_levels=confidence_levels,
        rolling_windows_days=_unique_positive_ints(
            reporting["rolling_windows_days"], field="reporting.rolling_windows_days"
        ),
        cost_stress_multipliers=stress_multipliers,
        bootstrap=FundingCarryBootstrapSpec(
            enabled=_strict_bool(bootstrap["enabled"], field="reporting.bootstrap.enabled"),
            samples=_positive_int(bootstrap["samples"], field="reporting.bootstrap.samples"),
            block_length_days=_positive_int(
                bootstrap["block_length_days"],
                field="reporting.bootstrap.block_length_days",
            ),
            confidence_level=bootstrap_confidence,
            random_seed=_nonnegative_int(
                bootstrap["random_seed"], field="reporting.bootstrap.random_seed"
            ),
        ),
    )


def load_funding_carry_config(path: str | Path) -> FundingCarryConfig:
    """Load the strict, isolated funding-carry pre-registration contract."""
    config_path = Path(path).resolve()
    with config_path.open("r", encoding="utf-8") as handle:
        root = _require_mapping(yaml.safe_load(handle), field="root")
    version = int(root.get("version", 0))
    if version not in {1, 2}:
        raise ValueError("version must equal 1 or 2.")
    root_keys = {
        "version",
        "strategy",
        "data",
        "signal",
        "execution",
        "research",
        "acceptance",
        "artifacts",
    }
    if version == 2:
        root_keys.add("reporting")
    _require_exact_keys(
        root,
        field="root",
        required=root_keys,
    )

    strategy = _require_mapping(root["strategy"], field="strategy")
    strategy_keys = {"id", "hypothesis", "preregistered_at_utc"}
    if version == 2:
        strategy_keys |= {"parent_strategy_id", "revision_scope"}
    _require_exact_keys(
        strategy,
        field="strategy",
        required=strategy_keys,
    )
    data = _require_mapping(root["data"], field="data")
    _require_exact_keys(
        data,
        field="data",
        required={
            "provider",
            "snapshot_dir",
            "symbols",
            "interval",
            "start_inclusive_utc",
            "end_exclusive_utc",
            "verify_hashes",
            "max_price_age_minutes",
        },
    )
    if data["provider"] != "binance_public_rest":
        raise ValueError("data.provider must be binance_public_rest.")
    symbols_raw = data["symbols"]
    if not isinstance(symbols_raw, Sequence) or isinstance(symbols_raw, (str, bytes)):
        raise ValueError("data.symbols must be a non-empty list.")
    symbols = tuple(dict.fromkeys(str(value).strip().upper() for value in symbols_raw))
    if not symbols or any(not symbol.isalnum() for symbol in symbols):
        raise ValueError("data.symbols must contain valid Binance symbols.")

    signal = _require_mapping(root["signal"], field="signal")
    _require_exact_keys(
        signal,
        field="signal",
        required={
            "forecast",
            "lookback_events",
            "expected_holding_events",
            "expected_funding_interval_hours",
            "entry_cost_multiplier",
            "exit_forecast_rate",
            "max_holding_events",
            "positive_funding_only",
        },
    )
    if signal["forecast"] != "trailing_median":
        raise ValueError("signal.forecast must be trailing_median.")
    if signal["positive_funding_only"] is not True:
        raise ValueError("signal.positive_funding_only must be true; short spot is out of scope.")

    execution = _require_mapping(root["execution"], field="execution")
    _require_exact_keys(
        execution,
        field="execution",
        required={
            "spot_fee_bps_per_side",
            "perpetual_fee_bps_per_side",
            "spot_slippage_bps_per_side",
            "perpetual_slippage_bps_per_side",
            "capital_per_spot_notional",
            "annual_financing_rate",
            "max_execution_price_age_minutes",
        },
    )

    research = _require_mapping(root["research"], field="research")
    _require_exact_keys(
        research,
        field="research",
        required={"timezone", "periods_per_year", "splits"},
    )
    if research["timezone"] != "UTC":
        raise ValueError("research.timezone must be UTC.")
    split_rows = research["splits"]
    if not isinstance(split_rows, Sequence) or isinstance(split_rows, (str, bytes)):
        raise ValueError("research.splits must be a non-empty list.")
    parsed_splits: list[FundingCarrySplit] = []
    for index, raw_split in enumerate(split_rows):
        split = _require_mapping(raw_split, field=f"research.splits[{index}]")
        _require_exact_keys(
            split,
            field=f"research.splits[{index}]",
            required={"name", "start_inclusive_utc", "end_exclusive_utc", "locked"},
        )
        parsed = FundingCarrySplit(
            name=str(split["name"]).strip(),
            start=_utc_timestamp(
                split["start_inclusive_utc"], field=f"research.splits[{index}].start"
            ),
            end=_utc_timestamp(
                split["end_exclusive_utc"], field=f"research.splits[{index}].end"
            ),
            locked=bool(split["locked"]),
        )
        if not parsed.name or parsed.start >= parsed.end:
            raise ValueError(f"Invalid research split at index {index}.")
        parsed_splits.append(parsed)
    if len({split.name for split in parsed_splits}) != len(parsed_splits):
        raise ValueError("research split names must be unique.")
    ordered = sorted(parsed_splits, key=lambda split: split.start)
    if ordered != parsed_splits:
        raise ValueError("research.splits must be chronological.")
    for prior, current in zip(parsed_splits, parsed_splits[1:]):
        if prior.end > current.start:
            raise ValueError(f"research splits {prior.name!r} and {current.name!r} overlap.")

    acceptance = _require_mapping(root["acceptance"], field="acceptance")
    _require_exact_keys(
        acceptance,
        field="acceptance",
        required={
            "validation_split",
            "min_portfolio_sharpe",
            "min_portfolio_cumulative_return",
            "min_entries_per_symbol",
            "require_positive_each_symbol",
            "cost_stress_multiplier",
        },
    )
    validation_split = str(acceptance["validation_split"]).strip()
    if validation_split not in {split.name for split in parsed_splits}:
        raise ValueError("acceptance.validation_split must name a configured research split.")

    artifacts = _require_mapping(root["artifacts"], field="artifacts")
    _require_exact_keys(artifacts, field="artifacts", required={"output_root"})

    if version == 2:
        reporting = _parse_reporting_spec(root["reporting"])
    else:
        reporting = _default_reporting_spec(
            cost_stress_multiplier=_positive_float(
                acceptance["cost_stress_multiplier"],
                field="acceptance.cost_stress_multiplier",
            )
        )

    start = _utc_timestamp(data["start_inclusive_utc"], field="data.start_inclusive_utc")
    end = _utc_timestamp(data["end_exclusive_utc"], field="data.end_exclusive_utc")
    if start >= end:
        raise ValueError("data.start_inclusive_utc must precede data.end_exclusive_utc.")
    for split in parsed_splits:
        if split.start < start or split.end > end:
            raise ValueError(f"research split {split.name!r} lies outside the data interval.")

    strategy_id = str(strategy["id"]).strip()
    hypothesis = str(strategy["hypothesis"]).strip()
    if not strategy_id or not hypothesis:
        raise ValueError("strategy.id and strategy.hypothesis must be non-empty.")
    if not isinstance(data["verify_hashes"], bool):
        raise ValueError("data.verify_hashes must be boolean.")
    if not isinstance(acceptance["require_positive_each_symbol"], bool):
        raise ValueError("acceptance.require_positive_each_symbol must be boolean.")

    result = FundingCarryConfig(
        version=version,
        strategy_id=strategy_id,
        hypothesis=hypothesis,
        preregistered_at_utc=str(strategy["preregistered_at_utc"]),
        data=FundingCarryDataSpec(
            snapshot_dir=_resolve_project_path(data["snapshot_dir"], field="data.snapshot_dir"),
            symbols=symbols,
            interval=str(data["interval"]),
            start=start,
            end=end,
            verify_hashes=bool(data["verify_hashes"]),
            max_price_age_minutes=_positive_int(
                data["max_price_age_minutes"], field="data.max_price_age_minutes"
            ),
        ),
        signal=FundingCarrySignalSpec(
            lookback_events=_positive_int(signal["lookback_events"], field="signal.lookback_events"),
            expected_holding_events=_positive_int(
                signal["expected_holding_events"], field="signal.expected_holding_events"
            ),
            expected_funding_interval_hours=_positive_float(
                signal["expected_funding_interval_hours"],
                field="signal.expected_funding_interval_hours",
            ),
            entry_cost_multiplier=_positive_float(
                signal["entry_cost_multiplier"], field="signal.entry_cost_multiplier"
            ),
            exit_forecast_rate=_finite_float(
                signal["exit_forecast_rate"], field="signal.exit_forecast_rate"
            ),
            max_holding_events=_positive_int(
                signal["max_holding_events"], field="signal.max_holding_events"
            ),
            positive_funding_only=True,
        ),
        execution=FundingCarryExecutionSpec(
            spot_fee_bps_per_side=_nonnegative_float(
                execution["spot_fee_bps_per_side"], field="execution.spot_fee_bps_per_side"
            ),
            perpetual_fee_bps_per_side=_nonnegative_float(
                execution["perpetual_fee_bps_per_side"],
                field="execution.perpetual_fee_bps_per_side",
            ),
            spot_slippage_bps_per_side=_nonnegative_float(
                execution["spot_slippage_bps_per_side"],
                field="execution.spot_slippage_bps_per_side",
            ),
            perpetual_slippage_bps_per_side=_nonnegative_float(
                execution["perpetual_slippage_bps_per_side"],
                field="execution.perpetual_slippage_bps_per_side",
            ),
            capital_per_spot_notional=_positive_float(
                execution["capital_per_spot_notional"],
                field="execution.capital_per_spot_notional",
            ),
            annual_financing_rate=_nonnegative_float(
                execution["annual_financing_rate"], field="execution.annual_financing_rate"
            ),
            max_execution_price_age_minutes=_positive_int(
                execution["max_execution_price_age_minutes"],
                field="execution.max_execution_price_age_minutes",
            ),
        ),
        research=FundingCarryResearchSpec(
            timezone="UTC",
            periods_per_year=_positive_int(
                research["periods_per_year"], field="research.periods_per_year"
            ),
            splits=tuple(parsed_splits),
        ),
        acceptance=FundingCarryAcceptanceSpec(
            validation_split=validation_split,
            min_portfolio_sharpe=_finite_float(
                acceptance["min_portfolio_sharpe"], field="acceptance.min_portfolio_sharpe"
            ),
            min_portfolio_cumulative_return=_finite_float(
                acceptance["min_portfolio_cumulative_return"],
                field="acceptance.min_portfolio_cumulative_return",
            ),
            min_entries_per_symbol=_nonnegative_int(
                acceptance["min_entries_per_symbol"],
                field="acceptance.min_entries_per_symbol",
            ),
            require_positive_each_symbol=bool(acceptance["require_positive_each_symbol"]),
            cost_stress_multiplier=_positive_float(
                acceptance["cost_stress_multiplier"],
                field="acceptance.cost_stress_multiplier",
            ),
        ),
        artifacts=FundingCarryArtifactSpec(
            output_root=_resolve_project_path(artifacts["output_root"], field="artifacts.output_root")
        ),
        reporting=reporting,
        config_path=config_path,
        config_sha256=file_sha256(config_path),
        parent_strategy_id=(
            str(strategy["parent_strategy_id"]).strip() if version == 2 else None
        ),
        revision_scope=str(strategy["revision_scope"]).strip() if version == 2 else None,
    )
    if result.signal.max_holding_events < result.signal.expected_holding_events:
        raise ValueError("signal.max_holding_events must be >= signal.expected_holding_events.")
    if result.execution.max_execution_price_age_minutes > result.data.max_price_age_minutes:
        raise ValueError(
            "execution.max_execution_price_age_minutes must not exceed "
            "data.max_price_age_minutes."
        )
    if result.version == 2:
        if not result.parent_strategy_id or not result.revision_scope:
            raise ValueError("Version 2 requires non-empty parent_strategy_id and revision_scope.")
        if result.acceptance.cost_stress_multiplier not in result.reporting.cost_stress_multipliers:
            raise ValueError(
                "reporting.cost_stress_multipliers must include "
                "acceptance.cost_stress_multiplier."
            )
    return result


def validate_snapshot_contract(config: FundingCarryConfig) -> dict[str, Any]:
    manifest_path = config.data.snapshot_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"Funding-carry snapshot is missing: {manifest_path}. Run the downloader first."
        )
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    request = _require_mapping(manifest.get("request"), field="snapshot.request")
    if request.get("provider") != "binance_public_rest":
        raise ValueError("Snapshot provider is not binance_public_rest.")
    if request.get("interval") != config.data.interval:
        raise ValueError("Snapshot interval does not match funding-carry config.")
    available_symbols = set(request.get("symbols", []))
    if not set(config.data.symbols).issubset(available_symbols):
        raise ValueError("Snapshot does not contain every configured symbol.")
    available_datasets = set(request.get("datasets", []))
    required_datasets = {"spot_klines", "perp_klines", "funding_rates"}
    if not required_datasets.issubset(available_datasets):
        raise ValueError(f"Snapshot is missing required datasets: {sorted(required_datasets)}.")
    snapshot_start = _utc_timestamp(
        request.get("start_inclusive_utc"), field="snapshot.request.start_inclusive_utc"
    )
    snapshot_end = _utc_timestamp(
        request.get("end_exclusive_utc"), field="snapshot.request.end_exclusive_utc"
    )
    if snapshot_start > config.data.start or snapshot_end < config.data.end:
        raise ValueError("Snapshot does not cover the configured data interval.")
    return dict(manifest)


def align_funding_with_causal_prices(
    funding: pd.DataFrame,
    spot: pd.DataFrame,
    perpetual: pd.DataFrame,
    *,
    max_price_age_minutes: int,
) -> pd.DataFrame:
    """Backward-asof funding events to the latest fully closed price bars."""
    if "funding_rate" not in funding.columns:
        raise ValueError("funding frame must contain funding_rate.")
    for name, frame in (("spot", spot), ("perpetual", perpetual)):
        if "close" not in frame.columns:
            raise ValueError(f"{name} frame must contain close.")
        if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
            raise ValueError(f"{name} frame must use timezone-aware timestamps.")
    if not isinstance(funding.index, pd.DatetimeIndex) or funding.index.tz is None:
        raise ValueError("funding frame must use timezone-aware timestamps.")
    if max_price_age_minutes <= 0:
        raise ValueError("max_price_age_minutes must be positive.")

    left = funding[["funding_rate"]].sort_index().reset_index()
    left = left.rename(columns={left.columns[0]: "timestamp"})
    result = left
    tolerance = pd.Timedelta(minutes=max_price_age_minutes)
    for prefix, source in (("spot", spot), ("perpetual", perpetual)):
        prices = source[["close"]].sort_index().reset_index()
        prices = prices.rename(
            columns={prices.columns[0]: f"{prefix}_price_time", "close": f"{prefix}_close"}
        )
        result = pd.merge_asof(
            result.sort_values("timestamp"),
            prices.sort_values(f"{prefix}_price_time"),
            left_on="timestamp",
            right_on=f"{prefix}_price_time",
            direction="backward",
            tolerance=tolerance,
            allow_exact_matches=True,
        )

    missing = result[["spot_close", "perpetual_close"]].isna().any(axis=1)
    if missing.any():
        first_valid_time = max(spot.index.min(), perpetual.index.min())
        interior_missing = missing & result["timestamp"].ge(first_valid_time)
        if interior_missing.any():
            examples = result.loc[interior_missing, "timestamp"].head(3).astype(str).tolist()
            raise ValueError(
                "Funding events lack causal price bars within the configured tolerance; "
                f"examples={examples}."
            )
        result = result.loc[~missing].copy()
    if result.empty:
        raise ValueError("No funding events could be aligned to causal price bars.")
    if (result["spot_price_time"] > result["timestamp"]).any() or (
        result["perpetual_price_time"] > result["timestamp"]
    ).any():
        raise AssertionError("Causal price alignment selected a future bar.")
    result = result.set_index("timestamp").sort_index()
    result["spot_price_age_seconds"] = (
        result.index.to_series() - result["spot_price_time"]
    ).dt.total_seconds()
    result["perpetual_price_age_seconds"] = (
        result.index.to_series() - result["perpetual_price_time"]
    ).dt.total_seconds()
    result["spot_return"] = result["spot_close"].pct_change(fill_method=None)
    result["perpetual_return"] = result["perpetual_close"].pct_change(fill_method=None)
    return result


def add_causal_funding_forecast(
    events: pd.DataFrame,
    *,
    lookback_events: int,
) -> pd.DataFrame:
    """Use the median of funding rates observed through each settlement only."""
    if lookback_events <= 0:
        raise ValueError("lookback_events must be positive.")
    out = events.copy()
    out["funding_forecast"] = out["funding_rate"].rolling(
        lookback_events,
        min_periods=lookback_events,
    ).median()
    return out


def _entry_threshold(
    signal: FundingCarrySignalSpec,
    execution: FundingCarryExecutionSpec,
    *,
    cost_multiplier: float,
) -> float:
    holding_years = (
        signal.expected_holding_events * signal.expected_funding_interval_hours / (365.25 * 24.0)
    )
    expected_financing = (
        execution.annual_financing_rate * holding_years * execution.capital_per_spot_notional
    )
    required_total = cost_multiplier * execution.round_trip_transaction_cost + expected_financing
    return signal.entry_cost_multiplier * required_total / signal.expected_holding_events


def simulate_funding_carry_segment(
    events: pd.DataFrame,
    *,
    signal: FundingCarrySignalSpec,
    execution: FundingCarryExecutionSpec,
    start: pd.Timestamp,
    end: pd.Timestamp,
    cost_multiplier: float = 1.0,
) -> pd.DataFrame:
    """Simulate one self-contained, initially-flat chronological segment."""
    if cost_multiplier <= 0.0:
        raise ValueError("cost_multiplier must be > 0.")
    segment = events.loc[(events.index >= start) & (events.index < end)].copy()
    if len(segment) < 2:
        raise ValueError(f"Funding-carry split [{start}, {end}) has fewer than two events.")
    if "funding_forecast" not in segment.columns:
        raise ValueError("events must contain funding_forecast.")
    required_age_columns = {"spot_price_age_seconds", "perpetual_price_age_seconds"}
    if not required_age_columns.issubset(segment.columns):
        raise ValueError(f"events must contain price-age fields: {sorted(required_age_columns)}.")

    threshold = _entry_threshold(signal, execution, cost_multiplier=cost_multiplier)
    state = 0
    hedge_units = 0.0
    held_intervals = 0
    position_for_interval: list[int] = []
    position_after_event: list[int] = []
    hedge_units_for_interval: list[float] = []
    turnover: list[float] = []
    transaction_cost: list[float] = []
    fee_cost: list[float] = []
    slippage_cost: list[float] = []
    financing_cost: list[float] = []
    spot_pnl: list[float] = []
    perpetual_pnl: list[float] = []
    funding_pnl: list[float] = []
    gross_pnl: list[float] = []
    gross_return: list[float] = []
    net_return: list[float] = []
    equity_curve: list[float] = []
    equity_before_curve: list[float] = []
    spot_return_component: list[float] = []
    perpetual_return_component: list[float] = []
    funding_return_component: list[float] = []
    gross_leverage: list[float] = []
    net_mark_notional_ratio: list[float] = []
    entry_threshold: list[float] = []
    event_count = len(segment)
    forecasts = segment["funding_forecast"].to_numpy(dtype=float)
    spot_prices = segment["spot_close"].to_numpy(dtype=float)
    perpetual_prices = segment["perpetual_close"].to_numpy(dtype=float)
    funding_rates = segment["funding_rate"].to_numpy(dtype=float)
    maximum_execution_age_seconds = execution.max_execution_price_age_minutes * 60.0
    execution_available = (
        segment["spot_price_age_seconds"].to_numpy(dtype=float)
        <= maximum_execution_age_seconds
    ) & (
        segment["perpetual_price_age_seconds"].to_numpy(dtype=float)
        <= maximum_execution_age_seconds
    )
    if not execution_available[-1]:
        raise ValueError("The final split event has no sufficiently recent price for liquidation.")
    elapsed_years = segment.index.to_series().diff().dt.total_seconds().fillna(0.0) / (
        365.25 * 24.0 * 60.0 * 60.0
    )
    equity = 1.0
    for row_number, forecast in enumerate(forecasts):
        equity_before = equity
        equity_before_curve.append(equity_before)
        position_for_interval.append(state)
        hedge_units_for_interval.append(hedge_units)
        spot_notional = state * abs(hedge_units * spot_prices[row_number])
        perpetual_notional = state * abs(hedge_units * perpetual_prices[row_number])
        gross_leverage.append((spot_notional + perpetual_notional) / equity_before)
        net_mark_notional_ratio.append((spot_notional - perpetual_notional) / equity_before)
        if state:
            held_intervals += 1
        if state and row_number > 0:
            spot_pnl.append(hedge_units * (spot_prices[row_number] - spot_prices[row_number - 1]))
            perpetual_pnl.append(
                -hedge_units * (perpetual_prices[row_number] - perpetual_prices[row_number - 1])
            )
            funding_pnl.append(
                hedge_units * perpetual_prices[row_number] * funding_rates[row_number]
            )
        else:
            spot_pnl.append(0.0)
            perpetual_pnl.append(0.0)
            funding_pnl.append(0.0)
        row_gross_pnl = spot_pnl[-1] + perpetual_pnl[-1] + funding_pnl[-1]
        row_financing_cost = (
            state
            * execution.annual_financing_rate
            * float(elapsed_years.iloc[row_number])
            * equity_before
        )
        equity_before_transition = equity_before + row_gross_pnl - row_financing_cost
        if equity_before_transition <= 0.0:
            raise ValueError("Funding-carry equity was exhausted before a position transition.")

        next_state = state
        if row_number == event_count - 1:
            next_state = 0
        elif not execution_available[row_number]:
            # A stale bar remains usable for causal mark-to-market, but never
            # for a hypothetical fill.  Hold the existing hedge unchanged.
            next_state = state
        elif state:
            if not np.isfinite(forecast) or forecast <= signal.exit_forecast_rate:
                next_state = 0
            elif held_intervals >= signal.max_holding_events:
                next_state = 0
        elif np.isfinite(forecast) and forecast > 0.0 and forecast > threshold:
            next_state = 1
            held_intervals = 0

        transition = abs(next_state - state)
        turnover.append(float(transition))
        if transition:
            traded_units = (
                hedge_units
                if state
                else equity_before_transition
                / execution.capital_per_spot_notional
                / spot_prices[row_number]
            )
            raw_fee_cost = traded_units * (
                spot_prices[row_number] * execution.spot_fee_bps_per_side / 10_000.0
                + perpetual_prices[row_number]
                * execution.perpetual_fee_bps_per_side
                / 10_000.0
            )
            raw_slippage_cost = traded_units * (
                spot_prices[row_number] * execution.spot_slippage_bps_per_side / 10_000.0
                + perpetual_prices[row_number]
                * execution.perpetual_slippage_bps_per_side
                / 10_000.0
            )
            row_fee_cost = raw_fee_cost * cost_multiplier
            row_slippage_cost = raw_slippage_cost * cost_multiplier
            row_transaction_cost = row_fee_cost + row_slippage_cost
        else:
            traded_units = 0.0
            row_fee_cost = 0.0
            row_slippage_cost = 0.0
            row_transaction_cost = 0.0
        equity = equity_before_transition - row_transaction_cost
        if equity <= 0.0:
            raise ValueError("Funding-carry transaction costs exhausted the portfolio equity.")
        row_gross_return = row_gross_pnl / equity_before
        row_spot_return = spot_pnl[-1] / equity_before
        row_perpetual_return = perpetual_pnl[-1] / equity_before
        row_funding_return = funding_pnl[-1] / equity_before
        row_financing_return = row_financing_cost / equity_before
        row_fee_return = row_fee_cost / equity_before
        row_slippage_return = row_slippage_cost / equity_before
        row_transaction_return = row_transaction_cost / equity_before
        row_net_return = equity / equity_before - 1.0
        gross_pnl.append(row_gross_pnl)
        gross_return.append(row_gross_return)
        spot_return_component.append(row_spot_return)
        perpetual_return_component.append(row_perpetual_return)
        funding_return_component.append(row_funding_return)
        financing_cost.append(row_financing_return)
        fee_cost.append(row_fee_return)
        slippage_cost.append(row_slippage_return)
        transaction_cost.append(row_transaction_return)
        net_return.append(row_net_return)
        equity_curve.append(equity)
        position_after_event.append(next_state)
        entry_threshold.append(threshold)
        if not state and next_state:
            # Equal underlying units, not equal dollar notionals, make the
            # linear spot/perpetual pair delta-neutral without free rehedging.
            hedge_units = traded_units
        elif state and not next_state:
            hedge_units = 0.0
        state = next_state
        if not state:
            held_intervals = 0

    segment["position_for_interval"] = position_for_interval
    segment["position_after_event"] = position_after_event
    segment["hedge_units"] = hedge_units_for_interval
    segment["execution_price_available"] = execution_available
    segment["turnover"] = turnover
    segment["entry_threshold_rate"] = entry_threshold

    segment["spot_pnl"] = spot_pnl
    segment["perpetual_pnl"] = perpetual_pnl
    segment["funding_pnl"] = funding_pnl
    segment["gross_pnl"] = gross_pnl
    segment["spot_return_component"] = spot_return_component
    segment["perpetual_return_component"] = perpetual_return_component
    segment["basis_return_component"] = (
        segment["spot_return_component"] + segment["perpetual_return_component"]
    )
    segment["funding_return_component"] = funding_return_component
    segment["financing_cost"] = financing_cost
    segment["fee_cost"] = fee_cost
    segment["slippage_cost"] = slippage_cost
    segment["transaction_cost"] = transaction_cost
    segment["gross_return"] = gross_return
    segment["net_return"] = net_return
    segment["equity_before"] = equity_before_curve
    segment["equity"] = equity_curve
    segment["basis_bps"] = (segment["perpetual_close"] / segment["spot_close"] - 1.0) * 10_000.0
    segment["gross_leverage"] = gross_leverage
    segment["net_mark_notional_ratio"] = net_mark_notional_ratio
    accounting_error = (
        segment["spot_return_component"]
        + segment["perpetual_return_component"]
        + segment["funding_return_component"]
        - segment["financing_cost"]
        - segment["fee_cost"]
        - segment["slippage_cost"]
        - segment["net_return"]
    ).abs()
    if float(accounting_error.max()) > 1e-12:
        raise AssertionError("Funding-carry component returns do not reconcile to net_return.")
    if not np.isfinite(segment["net_return"].to_numpy(dtype=float)).all():
        raise ValueError("Funding-carry simulation produced non-finite returns.")
    if (segment["net_return"] <= -1.0).any():
        raise ValueError("Funding-carry simulation produced a return <= -100% in one event.")
    return segment


def _metrics(
    frame: pd.DataFrame,
    *,
    periods_per_year: int,
    reporting: FundingCarryReportingSpec,
    include_trades: bool,
) -> dict[str, Any]:
    metrics = compute_backtest_metrics(
        net_returns=frame["net_return"],
        gross_returns=frame["gross_return"],
        costs=frame["transaction_cost"] + frame["financing_cost"],
        turnover=frame["turnover"],
        periods_per_year=periods_per_year,
        annualization_mode="calendar_daily",
    )
    entries = (
        (frame["position_after_event"] == 1) & (frame["position_for_interval"] == 0)
    ).sum()
    exits = (
        (frame["position_after_event"] == 0) & (frame["position_for_interval"] == 1)
    ).sum()
    metrics.update(
        {
            "observations": float(len(frame)),
            "active_intervals": float(frame["position_for_interval"].sum()),
            "exposure_fraction": float(frame["position_for_interval"].mean()),
            "entries": float(entries),
            "exits": float(exits),
            "spot_pnl_sum": float(frame["spot_pnl"].sum()),
            "perpetual_pnl_sum": float(frame["perpetual_pnl"].sum()),
            "funding_pnl_sum": float(frame["funding_pnl"].sum()),
            "financing_cost_sum": float(frame["financing_cost"].sum()),
            "transaction_cost_sum": float(frame["transaction_cost"].sum()),
            "execution_unavailable_events": float((~frame["execution_price_available"]).sum()),
        }
    )
    return build_extended_metrics(
        frame,
        base_metrics=metrics,
        reporting=reporting,
        include_trades=include_trades,
    )


def _portfolio_from_symbols(
    symbol_events: Mapping[str, pd.DataFrame],
    *,
    periods_per_year: int,
    reporting: FundingCarryReportingSpec,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not symbol_events:
        raise ValueError("symbol_events cannot be empty.")
    components = {}
    portfolio_columns = (
        "net_return",
        "gross_return",
        "spot_return_component",
        "perpetual_return_component",
        "basis_return_component",
        "funding_return_component",
        "fee_cost",
        "slippage_cost",
        "transaction_cost",
        "financing_cost",
        "turnover",
        "position_for_interval",
        "gross_leverage",
        "net_mark_notional_ratio",
        "spot_return",
        "funding_rate",
        "basis_bps",
        "execution_price_available",
        "spot_price_age_seconds",
        "perpetual_price_age_seconds",
    )
    for symbol, frame in symbol_events.items():
        for column in portfolio_columns:
            components[(symbol, column)] = frame[column]
    joined = pd.concat(components, axis=1, join="inner").sort_index()
    if joined.empty:
        raise ValueError("Configured symbols have no common funding settlements.")
    symbols = sorted(symbol_events)
    portfolio = pd.DataFrame(index=joined.index)
    for column in portfolio_columns:
        portfolio[column] = pd.concat(
            [joined[(symbol, column)] for symbol in symbols], axis=1
        ).mean(axis=1)
    metrics = compute_backtest_metrics(
        net_returns=portfolio["net_return"],
        gross_returns=portfolio["gross_return"],
        costs=portfolio["transaction_cost"] + portfolio["financing_cost"],
        turnover=portfolio["turnover"],
        periods_per_year=periods_per_year,
        annualization_mode="calendar_daily",
    )
    metrics["observations"] = float(len(portfolio))
    metrics["symbol_count"] = float(len(symbols))
    return portfolio, build_extended_metrics(
        portfolio,
        base_metrics=metrics,
        reporting=reporting,
        include_trades=False,
    )


def select_funding_carry_splits(
    config: FundingCarryConfig,
    *,
    phase: str,
    allow_locked_test: bool,
) -> tuple[FundingCarrySplit, ...]:
    names = {split.name for split in config.research.splits}
    if phase == "all":
        selected = config.research.splits
    elif phase in names:
        selected = tuple(split for split in config.research.splits if split.name == phase)
    else:
        raise ValueError(f"Unknown phase {phase!r}; expected one of {sorted(names | {'all'})}.")
    locked = [split.name for split in selected if split.locked]
    if locked and not allow_locked_test:
        raise PermissionError(
            f"Refusing to reveal locked split(s) {locked}. Pass allow_locked_test=True explicitly."
        )
    return tuple(selected)


def _load_symbol_events(config: FundingCarryConfig, symbol: str) -> pd.DataFrame:
    funding = load_binance_snapshot_frame(
        config.data.snapshot_dir,
        symbol=symbol,
        dataset="funding_rates",
        verify_hash=config.data.verify_hashes,
    )
    spot = load_binance_snapshot_frame(
        config.data.snapshot_dir,
        symbol=symbol,
        dataset="spot_klines",
        verify_hash=config.data.verify_hashes,
    )
    perpetual = load_binance_snapshot_frame(
        config.data.snapshot_dir,
        symbol=symbol,
        dataset="perp_klines",
        verify_hash=config.data.verify_hashes,
    )
    for frame in (funding, spot, perpetual):
        frame.drop(frame.loc[(frame.index < config.data.start) | (frame.index >= config.data.end)].index, inplace=True)
    aligned = align_funding_with_causal_prices(
        funding,
        spot,
        perpetual,
        max_price_age_minutes=config.data.max_price_age_minutes,
    )
    return add_causal_funding_forecast(
        aligned,
        lookback_events=config.signal.lookback_events,
    )


def run_funding_carry(
    config: FundingCarryConfig,
    *,
    phase: str = "development",
    allow_locked_test: bool = False,
    cost_multiplier: float = 1.0,
) -> FundingCarryRunResult:
    """Run one or more chronological splits without touching locked data implicitly."""
    validate_snapshot_contract(config)
    selected = select_funding_carry_splits(
        config,
        phase=phase,
        allow_locked_test=allow_locked_test,
    )
    prepared = {symbol: _load_symbol_events(config, symbol) for symbol in config.data.symbols}
    segments: dict[str, FundingCarrySegmentResult] = {}
    for split in selected:
        symbol_events: dict[str, pd.DataFrame] = {}
        symbol_metrics: dict[str, dict[str, Any]] = {}
        for symbol, events in prepared.items():
            simulated = simulate_funding_carry_segment(
                events,
                signal=config.signal,
                execution=config.execution,
                start=split.start,
                end=split.end,
                cost_multiplier=cost_multiplier,
            )
            symbol_events[symbol] = simulated
            symbol_metrics[symbol] = _metrics(
                simulated,
                periods_per_year=config.research.periods_per_year,
                reporting=config.reporting,
                include_trades=True,
            )
        portfolio, portfolio_metrics = _portfolio_from_symbols(
            symbol_events,
            periods_per_year=config.research.periods_per_year,
            reporting=config.reporting,
        )
        segments[split.name] = FundingCarrySegmentResult(
            symbol_events=symbol_events,
            symbol_metrics=symbol_metrics,
            portfolio=portfolio,
            portfolio_metrics=portfolio_metrics,
        )

    return FundingCarryRunResult(
        strategy_id=config.strategy_id,
        phase=phase,
        cost_multiplier=float(cost_multiplier),
        segments=segments,
        acceptance=None,
        cost_stress=None,
    )


def evaluate_validation_acceptance(
    config: FundingCarryConfig,
    baseline: FundingCarryRunResult,
    stressed: FundingCarryRunResult,
) -> dict[str, Any]:
    split_name = config.acceptance.validation_split
    if split_name not in baseline.segments or split_name not in stressed.segments:
        raise ValueError(f"Both runs must include validation split {split_name!r}.")
    base = baseline.segments[split_name]
    stress = stressed.segments[split_name]
    checks: dict[str, bool] = {
        "baseline_portfolio_sharpe": float(base.portfolio_metrics["sharpe"])
        >= config.acceptance.min_portfolio_sharpe,
        "baseline_portfolio_return": float(base.portfolio_metrics["cumulative_return"])
        >= config.acceptance.min_portfolio_cumulative_return,
        "stressed_portfolio_return": float(stress.portfolio_metrics["cumulative_return"])
        > 0.0,
        "minimum_entries": all(
            float(metrics["entries"]) >= config.acceptance.min_entries_per_symbol
            for metrics in base.symbol_metrics.values()
        ),
    }
    if config.acceptance.require_positive_each_symbol:
        checks["positive_each_symbol_baseline"] = all(
            float(metrics["cumulative_return"]) > 0.0 for metrics in base.symbol_metrics.values()
        )
        checks["positive_each_symbol_stressed"] = all(
            float(metrics["cumulative_return"]) > 0.0 for metrics in stress.symbol_metrics.values()
        )
    return {
        "qualified": all(checks.values()),
        "split": split_name,
        "checks": checks,
        "cost_stress_multiplier": config.acceptance.cost_stress_multiplier,
        "observed": {
            "baseline_portfolio_sharpe": float(base.portfolio_metrics["sharpe"]),
            "baseline_portfolio_cumulative_return": float(
                base.portfolio_metrics["cumulative_return"]
            ),
            "stressed_portfolio_sharpe": float(stress.portfolio_metrics["sharpe"]),
            "stressed_portfolio_cumulative_return": float(
                stress.portfolio_metrics["cumulative_return"]
            ),
            "baseline_symbol_cumulative_returns": {
                symbol: float(metrics["cumulative_return"])
                for symbol, metrics in base.symbol_metrics.items()
            },
            "stressed_symbol_cumulative_returns": {
                symbol: float(metrics["cumulative_return"])
                for symbol, metrics in stress.symbol_metrics.items()
            },
            "baseline_entries": {
                symbol: int(float(metrics["entries"]))
                for symbol, metrics in base.symbol_metrics.items()
            },
        },
    }


def _jsonable_metrics(result: FundingCarryRunResult) -> dict[str, Any]:
    return {
        "strategy_id": result.strategy_id,
        "phase": result.phase,
        "cost_multiplier": result.cost_multiplier,
        "acceptance": result.acceptance,
        "cost_stress": result.cost_stress,
        "segments": {
            name: {
                "portfolio": segment.portfolio_metrics,
                "symbols": segment.symbol_metrics,
            }
            for name, segment in result.segments.items()
        },
    }


def write_funding_carry_artifacts(
    config: FundingCarryConfig,
    result: FundingCarryRunResult,
    *,
    output_dir: str | Path | None = None,
) -> Path:
    """Write auditable results to a fresh run directory and return its path."""
    if output_dir is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destination = config.artifacts.output_root / f"{config.strategy_id}_{result.phase}_{timestamp}"
    else:
        destination = _resolve_project_path(output_dir, field="output_dir")
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite funding-carry artifacts: {destination}")
    destination.mkdir(parents=True, exist_ok=False)

    summary_path = destination / "summary.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(_jsonable_metrics(result), handle, indent=2, sort_keys=True)
        handle.write("\n")
    artifacts: dict[str, str] = {"summary": str(summary_path)}
    flat_metric_rows: list[dict[str, Any]] = []
    for split_name, segment in result.segments.items():
        split_dir = destination / split_name
        split_dir.mkdir(parents=True, exist_ok=False)
        portfolio_path = split_dir / "portfolio.csv"
        segment.portfolio.to_csv(portfolio_path, index=True, index_label="timestamp")
        artifacts[f"{split_name}/portfolio"] = str(portfolio_path)
        if config.reporting.write_flat_metrics_csv:
            flat_metric_rows.extend(
                {
                    "split": split_name,
                    "scope": "portfolio",
                    **row,
                }
                for row in flatten_metrics(segment.portfolio_metrics)
            )
        portfolio_tables = build_reporting_tables(
            segment.portfolio,
            reporting=config.reporting,
            include_trades=False,
        )
        for table_name, table in portfolio_tables.items():
            table_path = split_dir / f"portfolio_{table_name}.csv"
            table.to_csv(table_path, index=True, index_label="timestamp")
            artifacts[f"{split_name}/portfolio_{table_name}"] = str(table_path)
        for symbol, frame in segment.symbol_events.items():
            if config.reporting.write_event_level_csv:
                event_path = split_dir / f"{symbol}_events.csv"
                frame.to_csv(event_path, index=True, index_label="timestamp")
                artifacts[f"{split_name}/{symbol}_events"] = str(event_path)
            if config.reporting.write_flat_metrics_csv:
                flat_metric_rows.extend(
                    {
                        "split": split_name,
                        "scope": symbol,
                        **row,
                    }
                    for row in flatten_metrics(segment.symbol_metrics[symbol])
                )
            symbol_tables = build_reporting_tables(
                frame,
                reporting=config.reporting,
                include_trades=True,
            )
            for table_name, table in symbol_tables.items():
                table_path = split_dir / f"{symbol}_{table_name}.csv"
                index_label = "timestamp" if not table.empty and isinstance(table.index, pd.DatetimeIndex) else "row"
                table.to_csv(table_path, index=True, index_label=index_label)
                artifacts[f"{split_name}/{symbol}_{table_name}"] = str(table_path)

    if config.reporting.write_flat_metrics_csv:
        flat_metrics_path = destination / "metrics_flat.csv"
        pd.DataFrame(flat_metric_rows).to_csv(flat_metrics_path, index=False)
        artifacts["metrics_flat"] = str(flat_metrics_path)
    if result.cost_stress is not None:
        stress_path = destination / "cost_stress.json"
        with stress_path.open("w", encoding="utf-8") as handle:
            json.dump(result.cost_stress, handle, indent=2, sort_keys=True)
            handle.write("\n")
        artifacts["cost_stress"] = str(stress_path)

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "strategy_id": config.strategy_id,
        "phase": result.phase,
        "cost_multiplier": result.cost_multiplier,
        "config": {
            "path": str(config.config_path),
            "sha256": config.config_sha256,
        },
        "data_manifest": {
            "path": str(config.data.snapshot_dir / "manifest.json"),
            "sha256": file_sha256(config.data.snapshot_dir / "manifest.json"),
        },
        "git": collect_git_metadata(),
        "files": {
            key: {"path": path, "sha256": file_sha256(path)}
            for key, path in sorted(artifacts.items())
        },
    }
    manifest_path = destination / "run_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
    return destination


__all__ = [
    "FundingCarryAcceptanceSpec",
    "FundingCarryArtifactSpec",
    "FundingCarryConfig",
    "FundingCarryDataSpec",
    "FundingCarryExecutionSpec",
    "FundingCarryResearchSpec",
    "FundingCarryRunResult",
    "FundingCarrySegmentResult",
    "FundingCarrySignalSpec",
    "FundingCarrySplit",
    "add_causal_funding_forecast",
    "align_funding_with_causal_prices",
    "evaluate_validation_acceptance",
    "load_funding_carry_config",
    "run_funding_carry",
    "select_funding_carry_splits",
    "simulate_funding_carry_segment",
    "validate_snapshot_contract",
    "write_funding_carry_artifacts",
]
