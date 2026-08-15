"""Real, replaceable VectorBT executor for Phase 2 discovery contracts."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
import json
from math import isfinite
from pathlib import Path
import platform
from typing import Any

import numpy as np
import pandas as pd

from src.evaluation.metrics import (
    annualized_return,
    annualized_volatility,
    equity_curve_from_returns,
    max_drawdown,
    profit_factor,
    sharpe_ratio,
)
from src.research.contracts import ResearchContractError
from src.research.discovery.contracts import (
    DiscoverySpecification,
    DiscoveryTrial,
    TrialStatus,
)
from src.research.discovery.service import TrialEvaluator
from src.utils.run_metadata import compute_config_hash

from .contracts import (
    VECTORBT_CAPABILITIES,
    VectorBTCostMapping,
    VectorBTInputError,
    VectorBTResourcePolicy,
    VectorBTRuntimeError,
    VectorBTSignalSet,
    VectorBTTimingPolicy,
    VectorBTUnsupportedSemanticsError,
)
from .optional_dependency import load_vectorbt, vectorbt_version


FrameworkSignalBuilder = Callable[
    [pd.DataFrame, Mapping[str, Any]],
    VectorBTSignalSet,
]


SCREENING_METRIC_DEFINITIONS: Mapping[str, str] = {
    "total_return": "compounded VectorBT net portfolio return",
    "gross_total_return": "compounded zero-cost VectorBT portfolio return",
    "total_cost": "terminal return drag: gross_total_return - total_return",
    "annualized_return": "STF annualized_return over VectorBT net bar returns",
    "volatility": "STF sample annualized volatility, ddof=1",
    "sharpe": "STF conventional Sharpe, arithmetic bar returns, risk-free rate 0",
    "max_drawdown": "STF peak-to-trough drawdown over VectorBT net equity",
    "bar_profit_factor": "positive net bar-return sum / absolute negative sum",
    "trade_count": "completed long entry/exit pairs after timing mapping",
    "open_trade_count": "entries without an executed exit at sample end",
    "turnover": "sum absolute changes in declared target-fraction position",
    "observation_count": "validated market-data row count",
    "oos_rows": "zero: VectorBT screening consumes DISCOVERY data only",
    "oos_coverage": "zero: no OOS evidence is claimed by screening",
    "missing_rate": "leading warmup signal rows / market-data rows",
}


@dataclass(frozen=True)
class PreparedVectorBTSignals:
    entries: pd.Series
    exits: pd.Series
    target_positions: pd.Series
    entry_timestamps: tuple[str, ...]
    exit_timestamps: tuple[str, ...]
    warmup_rows: int
    dropped_entry_signals: int
    dropped_exit_signals: int


def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def vectorbt_runtime_provenance() -> dict[str, Any]:
    """Portable runtime versions; none of these values affect candidate identity."""

    return {
        "backend_name": "vectorbt",
        "vectorbt_version": vectorbt_version(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "numba_version": _package_version("numba"),
        "metric_scope": "screening_only_not_canonical_evidence",
    }


def validate_vectorbt_market_data(data: pd.DataFrame) -> None:
    """Reject misaligned or silently repairable data before VectorBT sees it."""

    if not isinstance(data, pd.DataFrame) or data.empty:
        raise VectorBTInputError("VectorBT market data must be a non-empty DataFrame.")
    if not isinstance(data.index, pd.DatetimeIndex):
        raise VectorBTInputError("VectorBT market data requires a DatetimeIndex.")
    if data.index.tz is None:
        raise VectorBTInputError("VectorBT market-data timestamps must be timezone-aware.")
    if not data.index.is_monotonic_increasing:
        raise VectorBTInputError("VectorBT market-data timestamps must be monotonic.")
    if not data.index.is_unique:
        raise VectorBTInputError("VectorBT market-data timestamps must be unique.")
    for column in ("open", "close"):
        if column not in data.columns:
            raise VectorBTInputError(
                f"VectorBT market data is missing required column {column!r}."
            )
        values = pd.to_numeric(data[column], errors="coerce")
        numeric = values.to_numpy(dtype=float)
        if not np.isfinite(numeric).all() or bool((numeric <= 0.0).any()):
            raise VectorBTInputError(
                f"VectorBT market-data column {column!r} must be finite and positive."
            )


def _normalize_boolean_signal(
    values: pd.Series,
    *,
    index: pd.DatetimeIndex,
    field_name: str,
) -> tuple[pd.Series, int]:
    if not values.index.equals(index):
        raise VectorBTInputError(
            f"{field_name} index must exactly match validated market data."
        )
    missing = values.isna().to_numpy(dtype=bool)
    warmup_rows = 0
    if missing.any():
        last_missing = int(np.flatnonzero(missing)[-1])
        if not bool(missing[: last_missing + 1].all()):
            raise VectorBTInputError(
                f"{field_name} may contain NaN only in one leading warmup prefix."
            )
        warmup_rows = last_missing + 1
    observed = values.iloc[warmup_rows:]
    allowed = observed.map(
        lambda value: isinstance(value, (bool, np.bool_))
        or (
            isinstance(value, (int, np.integer, float, np.floating))
            and isfinite(float(value))
            and float(value) in {0.0, 1.0}
        )
    )
    if not bool(allowed.all()):
        raise VectorBTInputError(
            f"{field_name} must contain only booleans/0/1 after warmup."
        )
    normalized = values.copy()
    if warmup_rows:
        normalized.iloc[:warmup_rows] = False
    return normalized.astype(bool), warmup_rows


def prepare_vectorbt_signals(
    signal_set: VectorBTSignalSet,
    *,
    market_index: pd.DatetimeIndex,
    timing: VectorBTTimingPolicy,
) -> PreparedVectorBTSignals:
    """Apply explicit next-bar timing without forward-filling signal intent."""

    entries, entry_warmup = _normalize_boolean_signal(
        signal_set.entries,
        index=market_index,
        field_name="entries",
    )
    exits, exit_warmup = _normalize_boolean_signal(
        signal_set.exits,
        index=market_index,
        field_name="exits",
    )
    warmup_rows = max(entry_warmup, exit_warmup)
    entries.iloc[:warmup_rows] = False
    exits.iloc[:warmup_rows] = False

    dropped_entries = int(entries.iloc[-timing.entry_delay_bars :].sum())
    dropped_exits = int(exits.iloc[-timing.exit_delay_bars :].sum())
    shifted_entries = entries.shift(
        timing.entry_delay_bars,
        fill_value=False,
    ).astype(bool)
    shifted_exits = exits.shift(
        timing.exit_delay_bars,
        fill_value=False,
    ).astype(bool)
    conflicts = shifted_entries & shifted_exits
    if bool(conflicts.any()):
        first = conflicts.index[conflicts][0]
        raise VectorBTInputError(
            f"Entry and exit collide after timing mapping at {first}."
        )

    target_positions = pd.Series(
        0.0,
        index=market_index,
        name="target_position",
        dtype=float,
    )
    open_position = False
    entry_timestamps: list[str] = []
    exit_timestamps: list[str] = []
    for offset, timestamp in enumerate(market_index):
        if bool(shifted_entries.iat[offset]):
            if open_position:
                raise VectorBTInputError(
                    f"Entry while already long is unsupported at {timestamp}."
                )
            open_position = True
            entry_timestamps.append(timestamp.isoformat())
        elif bool(shifted_exits.iat[offset]):
            if not open_position:
                raise VectorBTInputError(
                    f"Exit while flat is unsupported at {timestamp}."
                )
            open_position = False
            exit_timestamps.append(timestamp.isoformat())
        target_positions.iat[offset] = (
            signal_set.target_fraction if open_position else 0.0
        )

    return PreparedVectorBTSignals(
        entries=shifted_entries,
        exits=shifted_exits,
        target_positions=target_positions,
        entry_timestamps=tuple(entry_timestamps),
        exit_timestamps=tuple(exit_timestamps),
        warmup_rows=warmup_rows,
        dropped_entry_signals=dropped_entries,
        dropped_exit_signals=dropped_exits,
    )


def _as_frame(value: Any, *, columns: Sequence[str]) -> pd.DataFrame:
    if isinstance(value, pd.Series):
        if len(columns) != 1:
            raise VectorBTRuntimeError(
                "vectorbt_runtime_error: backend returned Series for multiple trials."
            )
        return value.to_frame(name=columns[0])
    if not isinstance(value, pd.DataFrame):
        value = pd.DataFrame(value, columns=columns)
    if tuple(str(item) for item in value.columns) != tuple(columns):
        value = value.copy()
        value.columns = list(columns)
    return value


def _total_return(returns: pd.Series) -> float:
    values = returns.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise VectorBTInputError("invalid_metric: non-finite VectorBT returns.")
    result = float(np.prod(1.0 + values) - 1.0)
    if not isfinite(result):
        raise VectorBTInputError("invalid_metric: non-finite total return.")
    return result


def _validate_native_execution_records(
    portfolio: Any,
    *,
    valid: Sequence[
        tuple[
            int,
            Mapping[str, Any],
            str,
            VectorBTSignalSet,
            PreparedVectorBTSignals,
        ]
    ],
    market_open: pd.Series,
) -> None:
    """Verify that VectorBT actually executed the mapped timestamps and sides.

    Native records remain adapter-local.  Only the portable, independently
    derived timestamp summary is written to trial metadata after this check.
    """

    records = portfolio.orders.records_readable
    required_columns = {"Column", "Timestamp", "Price", "Side"}
    if not isinstance(records, pd.DataFrame) or not required_columns.issubset(
        records.columns
    ):
        raise VectorBTRuntimeError(
            "vectorbt_runtime_error: unexpected order-record schema."
        )
    for _, _, trial_id, _, prepared in valid:
        trial_records = records.loc[
            records["Column"].astype(str).eq(trial_id)
        ].reset_index(drop=True)
        expected = sorted(
            [
                (pd.Timestamp(timestamp), "Buy")
                for timestamp in prepared.entry_timestamps
            ]
            + [
                (pd.Timestamp(timestamp), "Sell")
                for timestamp in prepared.exit_timestamps
            ],
            key=lambda item: item[0],
        )
        actual = [
            (pd.Timestamp(row.Timestamp), str(row.Side))
            for row in trial_records.itertuples(index=False)
        ]
        if actual != expected:
            raise VectorBTRuntimeError(
                "vectorbt_runtime_error: native order timestamps/sides differ "
                f"from the explicit timing mapping for trial {trial_id!r}."
            )
        for row in trial_records.itertuples(index=False):
            timestamp = pd.Timestamp(row.Timestamp)
            expected_price = float(market_open.loc[timestamp])
            if not np.isclose(float(row.Price), expected_price, rtol=0.0, atol=1e-12):
                raise VectorBTRuntimeError(
                    "vectorbt_runtime_error: native gross fill price differs "
                    f"from declared open price for trial {trial_id!r} at {timestamp}."
                )


def _screening_metrics(
    *,
    net_returns: pd.Series,
    gross_returns: pd.Series,
    prepared: PreparedVectorBTSignals,
    periods_per_year: int,
    observation_count: int,
) -> dict[str, int | float]:
    net_total = _total_return(net_returns)
    gross_total = _total_return(gross_returns)
    cost_drag = gross_total - net_total
    if cost_drag < -1e-10:
        raise VectorBTInputError(
            "invalid_metric: configured costs improved terminal return."
        )
    cost_drag = max(cost_drag, 0.0)
    completed_trades = len(prepared.exit_timestamps)
    open_trades = len(prepared.entry_timestamps) - completed_trades
    turnover = float(prepared.target_positions.diff().abs().fillna(
        prepared.target_positions.abs()
    ).sum())
    metrics: dict[str, int | float] = {
        "total_return": net_total,
        "gross_total_return": gross_total,
        "total_cost": cost_drag,
        "annualized_return": annualized_return(
            net_returns,
            periods_per_year=periods_per_year,
        ),
        "volatility": annualized_volatility(
            net_returns,
            periods_per_year=periods_per_year,
        ),
        "sharpe": sharpe_ratio(
            net_returns,
            periods_per_year=periods_per_year,
            risk_free_rate=0.0,
        ),
        "max_drawdown": max_drawdown(equity_curve_from_returns(net_returns)),
        "trade_count": completed_trades,
        "open_trade_count": open_trades,
        "turnover": turnover,
        "observation_count": observation_count,
        "oos_rows": 0,
        "oos_coverage": 0.0,
        "missing_rate": prepared.warmup_rows / observation_count,
    }
    bar_profit_factor = profit_factor(net_returns)
    if isfinite(bar_profit_factor):
        metrics["bar_profit_factor"] = bar_profit_factor
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(float(value))
        for value in metrics.values()
    ):
        raise VectorBTInputError(
            "invalid_metric: metric mapping produced NaN or infinity."
        )
    return metrics


def _trial_digest(research_run_id: str, parameters: Mapping[str, Any]) -> str:
    digest, _ = compute_config_hash(
        {
            "research_run_id": research_run_id,
            "parameters": dict(parameters),
        }
    )
    return digest


def _trial_id(research_run_id: str, parameters: Mapping[str, Any]) -> str:
    return f"{research_run_id}-vectorbt-{_trial_digest(research_run_id, parameters)[:20]}"


def _trial_seed(
    base_seed: int,
    research_run_id: str,
    parameters: Mapping[str, Any],
) -> int:
    return int(base_seed) + int(_trial_digest(research_run_id, parameters)[:8], 16)


def _write_json_once(path: Path, payload: Mapping[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                payload,
                sort_keys=True,
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            )
        )
        handle.write("\n")


class VectorBTSearchExecutor:
    """Batched VectorBT screening behind the Phase 2 discovery protocol.

    Features and entry/exit intent remain framework-owned and are supplied by
    ``signal_builder``. VectorBT owns only the adapter-internal vectorized
    portfolio simulation. Every result is expanded to one portable trial.
    """

    name = "vectorbt"
    backend_name = "vectorbt"
    capabilities = VECTORBT_CAPABILITIES

    def __init__(
        self,
        market_data: pd.DataFrame,
        signal_builder: FrameworkSignalBuilder,
        *,
        timing: VectorBTTimingPolicy | None = None,
        resources: VectorBTResourcePolicy | None = None,
        periods_per_year: int,
        init_cash: float = 1.0,
        allow_approximate_spread: bool = False,
        artifact_root: str | Path | None = None,
        dependency_loader: Callable[[], Any] = load_vectorbt,
    ) -> None:
        if not callable(signal_builder):
            raise VectorBTInputError("signal_builder must be callable.")
        if (
            isinstance(periods_per_year, bool)
            or not isinstance(periods_per_year, int)
            or periods_per_year < 1
        ):
            raise VectorBTInputError("periods_per_year must be an integer >= 1.")
        if (
            isinstance(init_cash, bool)
            or not isinstance(init_cash, (int, float))
            or not isfinite(float(init_cash))
            or float(init_cash) <= 0.0
        ):
            raise VectorBTInputError("init_cash must be finite and > 0.")
        if not isinstance(allow_approximate_spread, bool):
            raise VectorBTInputError("allow_approximate_spread must be boolean.")
        validate_vectorbt_market_data(market_data)
        self.market_data = market_data.copy()
        self.signal_builder = signal_builder
        self.timing = timing or VectorBTTimingPolicy()
        self.resources = resources or VectorBTResourcePolicy()
        self.periods_per_year = periods_per_year
        self.init_cash = float(init_cash)
        self.allow_approximate_spread = allow_approximate_spread
        self.artifact_root = None if artifact_root is None else Path(artifact_root)
        self._dependency_loader = dependency_loader

    @property
    def backend_version(self) -> str:
        return vectorbt_version()

    def _artifact_references(self) -> tuple[str, ...]:
        if self.artifact_root is None:
            return ()
        return tuple(
            str(self.artifact_root / name)
            for name in (
                "vectorbt_backend.json",
                "vectorbt_timing_mapping.json",
                "vectorbt_cost_mapping.json",
                "vectorbt_search_summary.json",
            )
        )

    def _runtime_metadata(
        self,
        *,
        specification: DiscoverySpecification,
        cost_mapping: VectorBTCostMapping,
        prepared: PreparedVectorBTSignals | None,
        full_cardinality: int,
        planned_combinations: int,
        estimated_bytes: int,
        batch_index: int | None,
        signal_metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata = vectorbt_runtime_provenance()
        metadata.update(
            {
                "capabilities": sorted(self.capabilities),
                "screening_metrics_are_canonical_evidence": False,
                "timing_mapping": self.timing.to_dict(),
                "cost_mapping": cost_mapping.to_dict(),
                "metric_definitions": dict(SCREENING_METRIC_DEFINITIONS),
                "sizing_mode": "fully_invested_target_fraction",
                "target_fraction": 1.0,
                "sizing_mapping_status": "exact_for_supported_long_only_mode",
                "position_direction": "long_only",
                "multi_asset_semantics": "unsupported",
                "full_search_cardinality": full_cardinality,
                "planned_combinations": planned_combinations,
                "trial_budget": specification.trial_budget,
                "estimated_working_set_bytes": estimated_bytes,
                "resource_policy": self.resources.to_dict(),
                "batch_index": batch_index,
                "signal_metadata": dict(signal_metadata or {}),
            }
        )
        if prepared is not None:
            metadata.update(
                {
                    "entry_timestamps": list(prepared.entry_timestamps),
                    "exit_timestamps": list(prepared.exit_timestamps),
                    "warmup_rows": prepared.warmup_rows,
                    "warmup_policy": "leading_nan_to_no_signal_without_forward_fill",
                    "dropped_entry_signals_at_data_end": (
                        prepared.dropped_entry_signals
                    ),
                    "dropped_exit_signals_at_data_end": (
                        prepared.dropped_exit_signals
                    ),
                }
            )
        return metadata

    def _write_backend_artifacts(
        self,
        *,
        trials: Sequence[DiscoveryTrial],
        specification: DiscoverySpecification,
        cost_mapping: VectorBTCostMapping,
        full_cardinality: int,
        planned_combinations: int,
        estimated_bytes: int,
    ) -> None:
        if self.artifact_root is None:
            return
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        paths = [Path(item) for item in self._artifact_references()]
        existing = [str(path) for path in paths if path.exists()]
        if existing:
            raise VectorBTRuntimeError(
                f"VectorBT backend artifacts already exist: {existing}."
            )
        state_counts = Counter(trial.status.value for trial in trials)
        _write_json_once(
            paths[0],
            {
                **vectorbt_runtime_provenance(),
                "capabilities": sorted(self.capabilities),
                "unsupported_capabilities": [
                    "event_driven_execution",
                    "live_execution",
                    "ml_walk_forward",
                    "multi_asset_shared_capital",
                    "portfolio_optimization",
                    "short_screening",
                ],
            },
        )
        _write_json_once(paths[1], self.timing.to_dict())
        _write_json_once(paths[2], cost_mapping.to_dict())
        _write_json_once(
            paths[3],
            {
                "discovery_specification_hash": specification.specification_hash,
                "full_search_cardinality": full_cardinality,
                "planned_combinations": planned_combinations,
                "emitted_trials": len(trials),
                "trial_state_counts": dict(sorted(state_counts.items())),
                "estimated_working_set_bytes": estimated_bytes,
                "resource_policy": self.resources.to_dict(),
                "screening_only": True,
            },
        )

    def execute(
        self,
        specification: DiscoverySpecification,
        *,
        research_run_id: str,
        evaluator: TrialEvaluator | None = None,
    ) -> tuple[DiscoveryTrial, ...]:
        if specification.search_method != self.name:
            raise ResearchContractError(
                f"VectorBT executor cannot run {specification.search_method!r}."
            )
        if evaluator is not None:
            raise ResearchContractError(
                "VectorBT executor owns simulation; use the injected framework signal_builder."
            )
        if len(specification.assets) != 1:
            raise VectorBTUnsupportedSemanticsError(
                "Phase 3A VectorBT supports one asset per discovery run only."
            )
        if specification.model_families:
            raise VectorBTUnsupportedSemanticsError(
                "Phase 3A VectorBT supports rule-based screening, not ML walk-forward."
            )
        full_cardinality = specification.search_space.cardinality()
        if full_cardinality is None:
            raise VectorBTUnsupportedSemanticsError(
                "VectorBT requires a finite enumerable search space; use Optuna for "
                "continuous or log-scaled dimensions."
            )
        if full_cardinality < 1:
            raise VectorBTInputError("VectorBT search space cannot be empty.")
        planned_combinations = min(full_cardinality, specification.trial_budget)
        estimated_bytes = self.resources.validate(
            rows=len(self.market_data),
            combinations=planned_combinations,
        )
        cost_mapping = VectorBTCostMapping.from_stf_assumptions(
            specification.cost_assumptions,
            allow_approximate_spread=self.allow_approximate_spread,
        )
        vectorbt_module = self._dependency_loader()
        combinations = tuple(
            specification.search_space.iter_grid(limit=planned_combinations)
        )
        references = self._artifact_references()
        trials_by_position: dict[int, DiscoveryTrial] = {}

        for batch_index, batch_start in enumerate(
            range(0, len(combinations), self.resources.batch_size)
        ):
            batch = combinations[
                batch_start : batch_start + self.resources.batch_size
            ]
            valid: list[
                tuple[int, Mapping[str, Any], str, VectorBTSignalSet, PreparedVectorBTSignals]
            ] = []
            for local_offset, parameters in enumerate(batch):
                position = batch_start + local_offset
                trial_id = _trial_id(research_run_id, parameters)
                seed = _trial_seed(
                    specification.random_seed,
                    research_run_id,
                    parameters,
                )
                try:
                    signal_set = self.signal_builder(
                        self.market_data.copy(deep=False),
                        parameters,
                    )
                    if not isinstance(signal_set, VectorBTSignalSet):
                        raise VectorBTInputError(
                            "signal_builder must return VectorBTSignalSet."
                        )
                    prepared = prepare_vectorbt_signals(
                        signal_set,
                        market_index=self.market_data.index,
                        timing=self.timing,
                    )
                except VectorBTUnsupportedSemanticsError as exc:
                    trials_by_position[position] = DiscoveryTrial(
                        trial_id=trial_id,
                        research_run_id=research_run_id,
                        parameters=parameters,
                        status=TrialStatus.INVALID,
                        seed=seed,
                        failure_reason=f"unsupported_semantics: {exc}",
                        artifact_references=references,
                        runtime_metadata=self._runtime_metadata(
                            specification=specification,
                            cost_mapping=cost_mapping,
                            prepared=None,
                            full_cardinality=full_cardinality,
                            planned_combinations=planned_combinations,
                            estimated_bytes=estimated_bytes,
                            batch_index=batch_index,
                        ),
                    )
                    continue
                except VectorBTInputError as exc:
                    trials_by_position[position] = DiscoveryTrial(
                        trial_id=trial_id,
                        research_run_id=research_run_id,
                        parameters=parameters,
                        status=TrialStatus.INVALID,
                        seed=seed,
                        failure_reason=f"invalid_input: {exc}",
                        artifact_references=references,
                        runtime_metadata=self._runtime_metadata(
                            specification=specification,
                            cost_mapping=cost_mapping,
                            prepared=None,
                            full_cardinality=full_cardinality,
                            planned_combinations=planned_combinations,
                            estimated_bytes=estimated_bytes,
                            batch_index=batch_index,
                        ),
                    )
                    continue
                except Exception as exc:
                    trials_by_position[position] = DiscoveryTrial(
                        trial_id=trial_id,
                        research_run_id=research_run_id,
                        parameters=parameters,
                        status=TrialStatus.FAILED,
                        seed=seed,
                        failure_reason=(
                            f"vectorbt_runtime_error: signal builder raised "
                            f"{type(exc).__name__}: {exc}"
                        ),
                        artifact_references=references,
                        runtime_metadata=self._runtime_metadata(
                            specification=specification,
                            cost_mapping=cost_mapping,
                            prepared=None,
                            full_cardinality=full_cardinality,
                            planned_combinations=planned_combinations,
                            estimated_bytes=estimated_bytes,
                            batch_index=batch_index,
                        ),
                    )
                    continue
                valid.append((position, parameters, trial_id, signal_set, prepared))

            if not valid:
                continue
            column_names = [item[2] for item in valid]
            price_frame = pd.concat(
                [self.market_data["open"]] * len(valid),
                axis=1,
            )
            price_frame.columns = column_names
            entry_frame = pd.concat([item[4].entries for item in valid], axis=1)
            entry_frame.columns = column_names
            exit_frame = pd.concat([item[4].exits for item in valid], axis=1)
            exit_frame.columns = column_names
            size_frame = pd.DataFrame(
                {
                    item[2]: item[3].target_fraction
                    for item in valid
                },
                index=self.market_data.index,
            )
            try:
                common = {
                    "close": price_frame,
                    "entries": entry_frame,
                    "exits": exit_frame,
                    "size": size_frame,
                    "size_type": "percent",
                    "direction": "longonly",
                    "accumulate": False,
                    "init_cash": self.init_cash,
                    "cash_sharing": False,
                    "allow_partial": False,
                    "raise_reject": True,
                    "log": False,
                    "seed": specification.random_seed,
                    "max_orders": len(self.market_data) * len(valid),
                    "max_logs": 1,
                }
                gross_portfolio = vectorbt_module.Portfolio.from_signals(
                    **common,
                    fees=0.0,
                    fixed_fees=0.0,
                    slippage=0.0,
                )
                net_portfolio = vectorbt_module.Portfolio.from_signals(
                    **common,
                    fees=cost_mapping.fees,
                    fixed_fees=cost_mapping.fixed_fees,
                    slippage=cost_mapping.slippage,
                )
                gross_returns = _as_frame(
                    gross_portfolio.returns(),
                    columns=column_names,
                )
                net_returns = _as_frame(
                    net_portfolio.returns(),
                    columns=column_names,
                )
                _validate_native_execution_records(
                    gross_portfolio,
                    valid=valid,
                    market_open=self.market_data["open"],
                )
            except Exception as exc:
                for position, parameters, trial_id, signal_set, prepared in valid:
                    trials_by_position[position] = DiscoveryTrial(
                        trial_id=trial_id,
                        research_run_id=research_run_id,
                        parameters=parameters,
                        status=TrialStatus.FAILED,
                        seed=_trial_seed(
                            specification.random_seed,
                            research_run_id,
                            parameters,
                        ),
                        failure_reason=(
                            f"vectorbt_runtime_error: {type(exc).__name__}: {exc}"
                        ),
                        artifact_references=references,
                        runtime_metadata=self._runtime_metadata(
                            specification=specification,
                            cost_mapping=cost_mapping,
                            prepared=prepared,
                            full_cardinality=full_cardinality,
                            planned_combinations=planned_combinations,
                            estimated_bytes=estimated_bytes,
                            batch_index=batch_index,
                            signal_metadata=signal_set.metadata,
                        ),
                    )
                continue

            for position, parameters, trial_id, signal_set, prepared in valid:
                seed = _trial_seed(
                    specification.random_seed,
                    research_run_id,
                    parameters,
                )
                runtime_metadata = self._runtime_metadata(
                    specification=specification,
                    cost_mapping=cost_mapping,
                    prepared=prepared,
                    full_cardinality=full_cardinality,
                    planned_combinations=planned_combinations,
                    estimated_bytes=estimated_bytes,
                    batch_index=batch_index,
                    signal_metadata=signal_set.metadata,
                )
                try:
                    metrics = _screening_metrics(
                        net_returns=net_returns[trial_id],
                        gross_returns=gross_returns[trial_id],
                        prepared=prepared,
                        periods_per_year=self.periods_per_year,
                        observation_count=len(self.market_data),
                    )
                    checks = {
                        "causal_features": signal_set.checks.get(
                            "causal_features", False
                        ),
                        "target_signal_compatible": signal_set.checks.get(
                            "target_signal_compatible", False
                        ),
                        "data_quality": True,
                        "timing_mapping_supported": True,
                        "cost_mapping_supported": True,
                        "long_only_supported": True,
                        "screening_only": True,
                    }
                    checks.update(signal_set.checks)
                    trials_by_position[position] = DiscoveryTrial(
                        trial_id=trial_id,
                        research_run_id=research_run_id,
                        parameters=parameters,
                        status=TrialStatus.COMPLETED,
                        metrics=metrics,
                        checks=checks,
                        seed=seed,
                        artifact_references=references,
                        runtime_metadata=runtime_metadata,
                    )
                except VectorBTInputError as exc:
                    trials_by_position[position] = DiscoveryTrial(
                        trial_id=trial_id,
                        research_run_id=research_run_id,
                        parameters=parameters,
                        status=TrialStatus.INVALID,
                        seed=seed,
                        failure_reason=f"invalid_metric: {exc}",
                        artifact_references=references,
                        runtime_metadata=runtime_metadata,
                    )

        trials = tuple(trials_by_position[index] for index in range(len(combinations)))
        self._write_backend_artifacts(
            trials=trials,
            specification=specification,
            cost_mapping=cost_mapping,
            full_cardinality=full_cardinality,
            planned_combinations=planned_combinations,
            estimated_bytes=estimated_bytes,
        )
        return trials


__all__ = [
    "FrameworkSignalBuilder",
    "PreparedVectorBTSignals",
    "SCREENING_METRIC_DEFINITIONS",
    "VectorBTSearchExecutor",
    "prepare_vectorbt_signals",
    "validate_vectorbt_market_data",
    "vectorbt_runtime_provenance",
]
