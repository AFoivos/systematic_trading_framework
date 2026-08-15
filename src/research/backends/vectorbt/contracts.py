"""Explicit timing, cost, signal, and resource contracts for VectorBT screening."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType
from typing import Any, Literal

import pandas as pd

from src.research.contracts import (
    ResearchContractError,
    _freeze_json_mapping,
    _require_non_empty,
)


VECTORBT_CAPABILITIES = frozenset(
    {
        "vectorized_screening",
        "parameter_grid_search",
        "rule_based_strategy_screening",
    }
)


class VectorBTBackendError(ResearchContractError):
    """Base error for fail-closed VectorBT adapter contracts."""


class VectorBTUnsupportedSemanticsError(VectorBTBackendError):
    """Raised when requested semantics cannot be represented faithfully."""


class VectorBTInputError(VectorBTBackendError):
    """Raised for invalid market-data or signal inputs."""


class VectorBTResourceLimitError(VectorBTBackendError):
    """Raised before allocating a search that exceeds explicit resource limits."""


class VectorBTRuntimeError(VectorBTBackendError):
    """Raised when the optional backend fails after validated input mapping."""


def _non_negative_rate(value: object, *, field_name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(float(value))
        or float(value) < 0.0
    ):
        raise VectorBTInputError(f"{field_name} must be finite and >= 0.")
    return float(value)


def _positive_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise VectorBTInputError(f"{field_name} must be an integer >= 1.")
    return value


@dataclass(frozen=True)
class VectorBTTimingPolicy:
    """The deliberately narrow Phase 3A bar-timing mapping.

    Close-derived framework signals are shifted before entering VectorBT. Only
    next-or-later bar open fills are supported, so same-close execution cannot
    be selected accidentally.
    """

    signal_timestamp: Literal["bar_close"] = "bar_close"
    entry_delay_bars: int = 1
    entry_price_source: Literal["open"] = "open"
    exit_delay_bars: int = 1
    exit_price_source: Literal["open"] = "open"

    def __post_init__(self) -> None:
        if self.signal_timestamp != "bar_close":
            raise VectorBTUnsupportedSemanticsError(
                "Phase 3A VectorBT supports only signals known at bar close."
            )
        if self.entry_price_source != "open" or self.exit_price_source != "open":
            raise VectorBTUnsupportedSemanticsError(
                "Phase 3A VectorBT supports only open-price entry and exit fills."
            )
        if (
            isinstance(self.entry_delay_bars, bool)
            or not isinstance(self.entry_delay_bars, int)
            or self.entry_delay_bars < 1
        ):
            raise VectorBTUnsupportedSemanticsError(
                "entry_delay_bars must be an integer >= 1; same-close fills are forbidden."
            )
        if (
            isinstance(self.exit_delay_bars, bool)
            or not isinstance(self.exit_delay_bars, int)
            or self.exit_delay_bars < 1
        ):
            raise VectorBTUnsupportedSemanticsError(
                "exit_delay_bars must be an integer >= 1; same-close fills are forbidden."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_timestamp": self.signal_timestamp,
            "entry_delay_bars": self.entry_delay_bars,
            "entry_price_source": self.entry_price_source,
            "exit_delay_bars": self.exit_delay_bars,
            "exit_price_source": self.exit_price_source,
            "same_close_execution": False,
            "mapping_status": "exact_for_declared_bar_model",
        }


@dataclass(frozen=True)
class VectorBTCostMapping:
    """Normalized STF-to-VectorBT order-cost mapping.

    ``fees`` and ``slippage`` are fractions per executed side, as expected by
    ``Portfolio.from_signals``. A scalar midpoint spread is only available as
    an explicitly opted-in approximation; quote-path and holding costs remain
    unsupported.
    """

    fees: float = 0.0
    slippage: float = 0.0
    fixed_fees: float = 0.0
    normalized_assumptions: Mapping[str, Any] = field(default_factory=dict)
    component_status: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("fees", "slippage", "fixed_fees"):
            object.__setattr__(
                self,
                field_name,
                _non_negative_rate(getattr(self, field_name), field_name=field_name),
            )
        object.__setattr__(
            self,
            "normalized_assumptions",
            _freeze_json_mapping(
                self.normalized_assumptions,
                field_name="normalized_assumptions",
            ),
        )
        statuses: dict[str, str] = {}
        if not isinstance(self.component_status, Mapping):
            raise VectorBTInputError("component_status must be a mapping.")
        for raw_name, raw_status in self.component_status.items():
            name = _require_non_empty(raw_name, field_name="cost component")
            statuses[name] = _require_non_empty(
                raw_status,
                field_name=f"cost component status {name}",
            )
        object.__setattr__(self, "component_status", MappingProxyType(statuses))

    @classmethod
    def from_stf_assumptions(
        cls,
        assumptions: Mapping[str, Any],
        *,
        allow_approximate_spread: bool = False,
    ) -> VectorBTCostMapping:
        if not isinstance(assumptions, Mapping):
            raise VectorBTInputError("cost assumptions must be a mapping.")
        allowed = {
            "cost_per_turnover",
            "commission_bps_per_side",
            "slippage_per_turnover",
            "slippage_bps_per_side",
            "spread_bps_per_side",
            "fixed_fee_per_order",
            "holding_cost_per_exposed_bar",
        }
        unexpected = sorted(set(assumptions).difference(allowed))
        if unexpected:
            raise VectorBTUnsupportedSemanticsError(
                "Unsupported or ambiguous VectorBT cost assumptions: "
                f"{unexpected}. Use explicit per-turnover or per-side keys."
            )

        def value(name: str) -> float:
            return _non_negative_rate(assumptions.get(name, 0.0), field_name=name)

        cost_per_turnover = value("cost_per_turnover")
        commission_bps = value("commission_bps_per_side")
        if cost_per_turnover and commission_bps:
            raise VectorBTInputError(
                "Specify either cost_per_turnover or commission_bps_per_side, not both."
            )
        slippage_per_turnover = value("slippage_per_turnover")
        slippage_bps = value("slippage_bps_per_side")
        if slippage_per_turnover and slippage_bps:
            raise VectorBTInputError(
                "Specify either slippage_per_turnover or slippage_bps_per_side, not both."
            )
        spread_bps = value("spread_bps_per_side")
        if spread_bps and not allow_approximate_spread:
            raise VectorBTUnsupportedSemanticsError(
                "Scalar spread mapping is approximate. Set allow_approximate_spread=True "
                "explicitly or use the canonical bid/ask engine."
            )
        holding_cost = value("holding_cost_per_exposed_bar")
        if holding_cost:
            raise VectorBTUnsupportedSemanticsError(
                "holding_cost_per_exposed_bar is unsupported by the Phase 3A VectorBT adapter."
            )

        fees = cost_per_turnover or commission_bps / 10_000.0
        base_slippage = slippage_per_turnover or slippage_bps / 10_000.0
        spread_slippage = spread_bps / 10_000.0
        fixed_fees = value("fixed_fee_per_order")
        normalized = {
            "cost_per_turnover": fees,
            "slippage_per_turnover": base_slippage,
            "spread_bps_per_side": spread_bps,
            "fixed_fee_per_order": fixed_fees,
            "holding_cost_per_exposed_bar": 0.0,
        }
        statuses = {
            "commission": (
                "screening_equivalent_with_cross_engine_tolerance"
                if cost_per_turnover
                else (
                    "exact_percentage_of_executed_order_value"
                    if commission_bps
                    else "not_configured"
                )
            ),
            "slippage": (
                "screening_equivalent_with_cross_engine_tolerance"
                if slippage_per_turnover
                else (
                    "exact_vectorbt_adverse_price_fraction"
                    if slippage_bps
                    else "not_configured"
                )
            ),
            "fixed_fee": (
                "exact_currency_amount_per_executed_order"
                if fixed_fees
                else "not_configured"
            ),
            "holding_cost": "not_configured",
            "spread": (
                "approximate_scalar_midpoint_adverse_price_fraction"
                if spread_bps
                else "not_configured"
            ),
        }
        return cls(
            fees=fees,
            slippage=base_slippage + spread_slippage,
            fixed_fees=fixed_fees,
            normalized_assumptions=normalized,
            component_status=statuses,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "vectorbt_parameters": {
                "fees": self.fees,
                "slippage": self.slippage,
                "fixed_fees": self.fixed_fees,
            },
            "normalized_assumptions": dict(self.normalized_assumptions),
            "component_status": dict(self.component_status),
            "cross_engine_parity": (
                "synthetic_fixture_required_with_explicit_tolerance"
            ),
        }


@dataclass(frozen=True)
class VectorBTResourcePolicy:
    max_combinations: int = 10_000
    batch_size: int = 256
    max_estimated_bytes: int = 512 * 1024 * 1024
    estimated_bytes_per_bar_combination: int = 96

    def __post_init__(self) -> None:
        for field_name in (
            "max_combinations",
            "batch_size",
            "max_estimated_bytes",
            "estimated_bytes_per_bar_combination",
        ):
            object.__setattr__(
                self,
                field_name,
                _positive_int(getattr(self, field_name), field_name=field_name),
            )
        if self.batch_size > self.max_combinations:
            raise VectorBTInputError(
                "batch_size cannot exceed max_combinations."
            )

    def estimate_bytes(self, *, rows: int, combinations: int) -> int:
        return (
            _positive_int(rows, field_name="rows")
            * _positive_int(combinations, field_name="combinations")
            * self.estimated_bytes_per_bar_combination
        )

    def validate(self, *, rows: int, combinations: int) -> int:
        if combinations > self.max_combinations:
            raise VectorBTResourceLimitError(
                "resource_limit: planned combination count "
                f"{combinations} exceeds max_combinations={self.max_combinations}."
            )
        concurrent_combinations = min(combinations, self.batch_size)
        estimated = self.estimate_bytes(
            rows=rows,
            combinations=concurrent_combinations,
        )
        if estimated > self.max_estimated_bytes:
            raise VectorBTResourceLimitError(
                "resource_limit: estimated vectorized working set "
                f"{estimated} bytes exceeds max_estimated_bytes="
                f"{self.max_estimated_bytes}."
            )
        return estimated

    def to_dict(self) -> dict[str, int]:
        return {
            "max_combinations": self.max_combinations,
            "batch_size": self.batch_size,
            "max_estimated_bytes": self.max_estimated_bytes,
            "estimated_bytes_per_bar_combination": (
                self.estimated_bytes_per_bar_combination
            ),
        }


@dataclass(frozen=True)
class VectorBTSignalSet:
    """Framework-produced long-only signals supplied to the adapter."""

    entries: pd.Series
    exits: pd.Series
    target_fraction: float = 1.0
    checks: Mapping[str, bool] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.entries, pd.Series) or not isinstance(
            self.exits, pd.Series
        ):
            raise VectorBTInputError("entries and exits must be pandas Series.")
        fraction = _non_negative_rate(
            self.target_fraction,
            field_name="target_fraction",
        )
        if fraction != 1.0:
            raise VectorBTUnsupportedSemanticsError(
                "Phase 3A supports only fully invested target_fraction=1.0. "
                "Partial target weights, fixed units, and volatility-adjusted sizing "
                "require separate capital-semantics parity coverage."
            )
        object.__setattr__(self, "target_fraction", fraction)
        if not isinstance(self.checks, Mapping):
            raise VectorBTInputError("signal checks must be a mapping.")
        normalized_checks: dict[str, bool] = {}
        for raw_name, raw_value in self.checks.items():
            name = _require_non_empty(raw_name, field_name="signal check")
            if not isinstance(raw_value, bool):
                raise VectorBTInputError(f"signal check {name!r} must be boolean.")
            normalized_checks[name] = raw_value
        object.__setattr__(self, "checks", MappingProxyType(normalized_checks))
        object.__setattr__(
            self,
            "metadata",
            _freeze_json_mapping(self.metadata, field_name="signal metadata"),
        )


__all__ = [
    "VECTORBT_CAPABILITIES",
    "VectorBTBackendError",
    "VectorBTCostMapping",
    "VectorBTInputError",
    "VectorBTResourceLimitError",
    "VectorBTResourcePolicy",
    "VectorBTRuntimeError",
    "VectorBTSignalSet",
    "VectorBTTimingPolicy",
    "VectorBTUnsupportedSemanticsError",
]
