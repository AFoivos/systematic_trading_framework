"""Library-independent search-space contracts for alpha discovery."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from itertools import islice, product
import json
from math import isfinite
from typing import Any

from ..contracts import (
    ResearchContractError,
    _require_exact_keys,
    _require_json_array,
    _require_json_compatible,
    _require_non_empty,
)


class ParameterKind(str, Enum):
    CATEGORICAL = "categorical"
    INTEGER = "integer"
    FLOAT = "float"
    FIXED = "fixed"


def _finite_number(value: object, *, field_name: str) -> int | float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(float(value))
    ):
        raise ResearchContractError(f"{field_name} must be a finite number.")
    return value


def _value_identity(value: Any) -> str:
    _require_json_compatible(value, field_name="parameter value")
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


@dataclass(frozen=True)
class ParameterSpec:
    """One portable parameter dimension.

    ``path`` is optional at the research-contract level. Existing config-based
    engines such as the repository Optuna implementation require it in their
    adapter, while manual or backend-native proposal generators may use only
    the stable parameter ``name``.
    """

    name: str
    kind: ParameterKind
    path: str | None = None
    low: int | float | None = None
    high: int | float | None = None
    step: int | float | None = None
    log: bool = False
    values: tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "name",
            _require_non_empty(self.name, field_name="parameter name"),
        )
        try:
            kind = ParameterKind(self.kind)
        except (TypeError, ValueError) as exc:
            raise ResearchContractError(str(exc)) from exc
        object.__setattr__(self, "kind", kind)
        if self.path is not None:
            object.__setattr__(
                self,
                "path",
                _require_non_empty(self.path, field_name=f"parameter {self.name} path"),
            )
        if not isinstance(self.log, bool):
            raise ResearchContractError(f"parameter {self.name} log must be boolean.")
        if isinstance(self.values, (str, bytes, bytearray)):
            raise ResearchContractError(
                f"parameter {self.name} values must be a sequence."
            )
        values = tuple(deepcopy(tuple(self.values)))
        identities = tuple(_value_identity(value) for value in values)
        if len(set(identities)) != len(identities):
            raise ResearchContractError(
                f"parameter {self.name} values cannot contain duplicates."
            )
        object.__setattr__(self, "values", values)

        if kind in {ParameterKind.CATEGORICAL, ParameterKind.FIXED}:
            expected_count = 1 if kind is ParameterKind.FIXED else None
            if not values or (expected_count is not None and len(values) != expected_count):
                requirement = "exactly one value" if expected_count else "at least one value"
                raise ResearchContractError(
                    f"parameter {self.name} requires {requirement}."
                )
            if any(value is not None for value in (self.low, self.high, self.step)):
                raise ResearchContractError(
                    f"parameter {self.name} {kind.value} values cannot define ranges."
                )
            if self.log:
                raise ResearchContractError(
                    f"parameter {self.name} {kind.value} values cannot be log-scaled."
                )
            return

        if values:
            raise ResearchContractError(
                f"parameter {self.name} range cannot also define categorical values."
            )
        if self.low is None or self.high is None:
            raise ResearchContractError(
                f"parameter {self.name} requires low and high."
            )
        low = _finite_number(self.low, field_name=f"parameter {self.name} low")
        high = _finite_number(self.high, field_name=f"parameter {self.name} high")
        if float(low) >= float(high):
            raise ResearchContractError(
                f"parameter {self.name} must satisfy low < high."
            )
        if kind is ParameterKind.INTEGER:
            if not isinstance(low, int) or not isinstance(high, int):
                raise ResearchContractError(
                    f"parameter {self.name} integer bounds must be integers."
                )
            if self.step is not None and (
                isinstance(self.step, bool)
                or not isinstance(self.step, int)
                or self.step <= 0
            ):
                raise ResearchContractError(
                    f"parameter {self.name} integer step must be a positive integer."
                )
        elif self.step is not None:
            step = _finite_number(
                self.step,
                field_name=f"parameter {self.name} step",
            )
            if float(step) <= 0.0:
                raise ResearchContractError(
                    f"parameter {self.name} float step must be positive."
                )
        if self.log:
            if float(low) <= 0.0:
                raise ResearchContractError(
                    f"parameter {self.name} log-scaled range requires low > 0."
                )
            if self.step is not None:
                raise ResearchContractError(
                    f"parameter {self.name} cannot combine log scaling with a step."
                )

    def grid_values(self) -> tuple[Any, ...]:
        """Return deterministic grid values or fail for a continuous range."""

        if self.kind in {ParameterKind.CATEGORICAL, ParameterKind.FIXED}:
            return tuple(deepcopy(self.values))
        if self.log:
            raise ResearchContractError(
                f"parameter {self.name} is continuous/log-scaled and cannot form a grid."
            )
        if self.kind is ParameterKind.INTEGER:
            step = int(self.step or 1)
            return tuple(range(int(self.low), int(self.high) + 1, step))
        if self.step is None:
            raise ResearchContractError(
                f"parameter {self.name} float grid requires an explicit step."
            )
        low = Decimal(str(self.low))
        high = Decimal(str(self.high))
        step = Decimal(str(self.step))
        values: list[float] = []
        current = low
        while current <= high:
            values.append(float(current))
            current += step
        return tuple(values)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind.value,
            "path": self.path,
            "low": self.low,
            "high": self.high,
            "step": self.step,
            "log": self.log,
            "values": list(deepcopy(self.values)),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ParameterSpec:
        _require_exact_keys(
            payload,
            expected={"name", "kind", "path", "low", "high", "step", "log", "values"},
            field_name="Parameter specification",
        )
        return cls(
            name=payload["name"],
            kind=ParameterKind(payload["kind"]),
            path=payload["path"],
            low=payload["low"],
            high=payload["high"],
            step=payload["step"],
            log=payload["log"],
            values=tuple(
                _require_json_array(payload["values"], field_name="parameter values")
            ),
        )


@dataclass(frozen=True)
class SearchSpace:
    parameters: tuple[ParameterSpec, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.parameters, (str, bytes, bytearray)):
            raise ResearchContractError("parameters must be a sequence.")
        parameters = tuple(self.parameters)
        if any(not isinstance(item, ParameterSpec) for item in parameters):
            raise ResearchContractError(
                "parameters must contain only ParameterSpec values."
            )
        names = tuple(item.name for item in parameters)
        if len(set(names)) != len(names):
            raise ResearchContractError("Search-space parameter names must be unique.")
        object.__setattr__(self, "parameters", parameters)

    @property
    def parameter_names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.parameters)

    def cardinality(self) -> int | None:
        total = 1
        for parameter in self.parameters:
            try:
                total *= len(parameter.grid_values())
            except ResearchContractError:
                return None
        return total

    def iter_grid(self, *, limit: int | None = None) -> Iterator[dict[str, Any]]:
        if limit is not None and (
            isinstance(limit, bool) or not isinstance(limit, int) or limit < 1
        ):
            raise ResearchContractError("grid limit must be null or an integer >= 1.")
        value_sets = tuple(parameter.grid_values() for parameter in self.parameters)
        combinations = product(*value_sets)
        if limit is not None:
            combinations = islice(combinations, limit)
        for combination in combinations:
            yield {
                parameter.name: deepcopy(value)
                for parameter, value in zip(self.parameters, combination)
            }

    def to_dict(self) -> dict[str, Any]:
        return {"parameters": [item.to_dict() for item in self.parameters]}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SearchSpace:
        _require_exact_keys(
            payload,
            expected={"parameters"},
            field_name="Search space",
        )
        return cls(
            parameters=tuple(
                ParameterSpec.from_dict(item)
                for item in _require_json_array(
                    payload["parameters"], field_name="search-space parameters"
                )
            )
        )


__all__ = ["ParameterKind", "ParameterSpec", "SearchSpace"]
