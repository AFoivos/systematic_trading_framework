"""Portable alpha-discovery, trial, eligibility, and ranking contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any

from ..candidate import _freeze_metrics
from ..contracts import (
    EvidenceReference,
    EvidenceStage,
    ResearchContractError,
    _freeze_json_mapping,
    _require_exact_keys,
    _require_identifier,
    _require_json_array,
    _require_non_empty,
    _require_sha256,
    _require_unique_strings,
)
from ..evidence import CheckStatus
from ..run import SelectionDirection
from .search_space import SearchSpace


class TrialStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    PRUNED = "pruned"
    INVALID = "invalid"


class RuleOperator(str, Enum):
    LT = "lt"
    LE = "le"
    GT = "gt"
    GE = "ge"
    EQ = "eq"


class SelectionMetricBasis(str, Enum):
    PREDICTION = "prediction"
    TRADING = "trading"


def _non_negative_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ResearchContractError(f"{field_name} must be an integer >= 0.")
    return value


def _optional_non_negative_int(value: object, *, field_name: str) -> int | None:
    if value is None:
        return None
    return _non_negative_int(value, field_name=field_name)


def _optional_rate(value: object, *, field_name: str) -> float | None:
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(float(value))
        or not 0.0 <= float(value) <= 1.0
    ):
        raise ResearchContractError(f"{field_name} must be null or finite in [0, 1].")
    return float(value)


def _freeze_checks(checks: Mapping[str, bool], *, field_name: str) -> Mapping[str, bool]:
    if not isinstance(checks, Mapping):
        raise ResearchContractError(f"{field_name} must be a mapping.")
    normalized: dict[str, bool] = {}
    for raw_name, value in checks.items():
        name = _require_non_empty(raw_name, field_name=f"{field_name} key")
        if not isinstance(value, bool):
            raise ResearchContractError(f"{field_name}.{name} must be boolean.")
        normalized[name] = value
    return MappingProxyType(normalized)


@dataclass(frozen=True)
class MetricPreference:
    metric: str
    direction: SelectionDirection

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "metric",
            _require_non_empty(self.metric, field_name="metric preference"),
        )
        try:
            direction = SelectionDirection(self.direction)
        except (TypeError, ValueError) as exc:
            raise ResearchContractError(str(exc)) from exc
        object.__setattr__(self, "direction", direction)

    def to_dict(self) -> dict[str, str]:
        return {"metric": self.metric, "direction": self.direction.value}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> MetricPreference:
        _require_exact_keys(
            payload,
            expected={"metric", "direction"},
            field_name="Metric preference",
        )
        return cls(
            metric=payload["metric"],
            direction=SelectionDirection(payload["direction"]),
        )


@dataclass(frozen=True)
class MinimumDataRequirements:
    minimum_observations: int | None = None
    minimum_oos_rows: int | None = None
    minimum_trades: int | None = None
    minimum_coverage: float | None = None
    maximum_missing_rate: float | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "minimum_observations",
            "minimum_oos_rows",
            "minimum_trades",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_non_negative_int(
                    getattr(self, field_name), field_name=field_name
                ),
            )
        for field_name in ("minimum_coverage", "maximum_missing_rate"):
            object.__setattr__(
                self,
                field_name,
                _optional_rate(getattr(self, field_name), field_name=field_name),
            )

    def to_dict(self) -> dict[str, int | float | None]:
        return {
            "minimum_observations": self.minimum_observations,
            "minimum_oos_rows": self.minimum_oos_rows,
            "minimum_trades": self.minimum_trades,
            "minimum_coverage": self.minimum_coverage,
            "maximum_missing_rate": self.maximum_missing_rate,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> MinimumDataRequirements:
        expected = {
            "minimum_observations",
            "minimum_oos_rows",
            "minimum_trades",
            "minimum_coverage",
            "maximum_missing_rate",
        }
        _require_exact_keys(
            payload,
            expected=expected,
            field_name="Minimum data requirements",
        )
        return cls(**{key: payload[key] for key in expected})


@dataclass(frozen=True)
class EligibilityRule:
    metric: str
    operator: RuleOperator
    threshold: int | float
    rejection_reason: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "metric",
            _require_non_empty(self.metric, field_name="eligibility metric"),
        )
        try:
            operator = RuleOperator(self.operator)
        except (TypeError, ValueError) as exc:
            raise ResearchContractError(str(exc)) from exc
        object.__setattr__(self, "operator", operator)
        if (
            isinstance(self.threshold, bool)
            or not isinstance(self.threshold, (int, float))
            or not isfinite(float(self.threshold))
        ):
            raise ResearchContractError("eligibility threshold must be finite.")
        object.__setattr__(
            self,
            "rejection_reason",
            _require_non_empty(
                self.rejection_reason, field_name="eligibility rejection_reason"
            ),
        )

    def passes(self, value: int | float) -> bool:
        left = float(value)
        right = float(self.threshold)
        return {
            RuleOperator.LT: left < right,
            RuleOperator.LE: left <= right,
            RuleOperator.GT: left > right,
            RuleOperator.GE: left >= right,
            RuleOperator.EQ: left == right,
        }[self.operator]

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "operator": self.operator.value,
            "threshold": self.threshold,
            "rejection_reason": self.rejection_reason,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> EligibilityRule:
        _require_exact_keys(
            payload,
            expected={"metric", "operator", "threshold", "rejection_reason"},
            field_name="Eligibility rule",
        )
        return cls(
            metric=payload["metric"],
            operator=RuleOperator(payload["operator"]),
            threshold=payload["threshold"],
            rejection_reason=payload["rejection_reason"],
        )


@dataclass(frozen=True)
class EligibilityPolicy:
    minimum_data: MinimumDataRequirements = field(default_factory=MinimumDataRequirements)
    metric_rules: tuple[EligibilityRule, ...] = ()
    required_checks: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.minimum_data, MinimumDataRequirements):
            raise ResearchContractError(
                "minimum_data must be MinimumDataRequirements."
            )
        if isinstance(self.metric_rules, (str, bytes, bytearray)):
            raise ResearchContractError("metric_rules must be a sequence.")
        rules = tuple(self.metric_rules)
        if any(not isinstance(rule, EligibilityRule) for rule in rules):
            raise ResearchContractError(
                "metric_rules must contain only EligibilityRule values."
            )
        signatures = tuple(
            (rule.metric, rule.operator.value, float(rule.threshold)) for rule in rules
        )
        if len(set(signatures)) != len(signatures):
            raise ResearchContractError("Eligibility rules cannot be duplicated.")
        object.__setattr__(self, "metric_rules", rules)
        object.__setattr__(
            self,
            "required_checks",
            _require_unique_strings(
                self.required_checks,
                field_name="required_checks",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "minimum_data": self.minimum_data.to_dict(),
            "metric_rules": [rule.to_dict() for rule in self.metric_rules],
            "required_checks": list(self.required_checks),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> EligibilityPolicy:
        _require_exact_keys(
            payload,
            expected={"minimum_data", "metric_rules", "required_checks"},
            field_name="Eligibility policy",
        )
        return cls(
            minimum_data=MinimumDataRequirements.from_dict(payload["minimum_data"]),
            metric_rules=tuple(
                EligibilityRule.from_dict(item)
                for item in _require_json_array(
                    payload["metric_rules"], field_name="metric_rules"
                )
            ),
            required_checks=tuple(
                _require_json_array(
                    payload["required_checks"], field_name="required_checks"
                )
            ),
        )


@dataclass(frozen=True)
class SelectionPolicy:
    primary: MetricPreference
    metric_basis: SelectionMetricBasis
    top_k: int
    tie_breakers: tuple[MetricPreference, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.primary, MetricPreference):
            raise ResearchContractError("primary must be a MetricPreference.")
        try:
            basis = SelectionMetricBasis(self.metric_basis)
        except (TypeError, ValueError) as exc:
            raise ResearchContractError(str(exc)) from exc
        object.__setattr__(self, "metric_basis", basis)
        if isinstance(self.top_k, bool) or not isinstance(self.top_k, int) or self.top_k < 1:
            raise ResearchContractError("top_k must be an integer >= 1.")
        if isinstance(self.tie_breakers, (str, bytes, bytearray)):
            raise ResearchContractError("tie_breakers must be a sequence.")
        tie_breakers = tuple(self.tie_breakers)
        if any(not isinstance(item, MetricPreference) for item in tie_breakers):
            raise ResearchContractError(
                "tie_breakers must contain only MetricPreference values."
            )
        metrics = tuple(item.metric for item in tie_breakers)
        if len(set(metrics)) != len(metrics):
            raise ResearchContractError("Tie-break metrics cannot be duplicated.")
        object.__setattr__(self, "tie_breakers", tie_breakers)

    @property
    def tie_break_rule(self) -> str:
        declared = [
            f"{item.metric}:{item.direction.value}" for item in self.tie_breakers
        ]
        declared.append("trial_id:ascending")
        return ",".join(declared)

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary": self.primary.to_dict(),
            "metric_basis": self.metric_basis.value,
            "top_k": self.top_k,
            "tie_breakers": [item.to_dict() for item in self.tie_breakers],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SelectionPolicy:
        _require_exact_keys(
            payload,
            expected={"primary", "metric_basis", "top_k", "tie_breakers"},
            field_name="Selection policy",
        )
        return cls(
            primary=MetricPreference.from_dict(payload["primary"]),
            metric_basis=SelectionMetricBasis(payload["metric_basis"]),
            top_k=payload["top_k"],
            tie_breakers=tuple(
                MetricPreference.from_dict(item)
                for item in _require_json_array(
                    payload["tie_breakers"], field_name="tie_breakers"
                )
            ),
        )


@dataclass(frozen=True)
class DiscoverySpecification:
    """Frozen, compositional description of one discovery search."""

    hypothesis_id: str
    assets: tuple[str, ...]
    timeframe: str
    feature_families: tuple[str, ...]
    target_family: str
    model_families: tuple[str, ...]
    signal_families: tuple[str, ...]
    search_method: str
    trial_budget: int
    search_space: SearchSpace
    selection: SelectionPolicy
    eligibility: EligibilityPolicy
    config_reference: str
    config_hash: str
    dataset_reference: str
    dataset_fingerprint: Mapping[str, Any]
    evidence_reference: EvidenceReference
    cost_assumptions: Mapping[str, Any]
    validation_method: str
    random_seed: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "hypothesis_id",
            _require_identifier(self.hypothesis_id, field_name="hypothesis_id"),
        )
        object.__setattr__(
            self,
            "assets",
            _require_unique_strings(self.assets, field_name="assets", allow_empty=False),
        )
        for field_name in (
            "timeframe",
            "target_family",
            "search_method",
            "config_reference",
            "dataset_reference",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_non_empty(getattr(self, field_name), field_name=field_name),
            )
        for field_name in ("feature_families", "model_families", "signal_families"):
            object.__setattr__(
                self,
                field_name,
                _require_unique_strings(
                    getattr(self, field_name), field_name=field_name
                ),
            )
        if (
            isinstance(self.trial_budget, bool)
            or not isinstance(self.trial_budget, int)
            or self.trial_budget < 1
        ):
            raise ResearchContractError("trial_budget must be an integer >= 1.")
        if not isinstance(self.search_space, SearchSpace):
            raise ResearchContractError("search_space must be a SearchSpace.")
        if not isinstance(self.selection, SelectionPolicy):
            raise ResearchContractError("selection must be a SelectionPolicy.")
        if not isinstance(self.eligibility, EligibilityPolicy):
            raise ResearchContractError("eligibility must be an EligibilityPolicy.")
        object.__setattr__(
            self,
            "config_hash",
            _require_sha256(self.config_hash, field_name="config_hash"),
        )
        fingerprint = _freeze_json_mapping(
            self.dataset_fingerprint, field_name="dataset_fingerprint"
        )
        _require_sha256(
            fingerprint.get("sha256"), field_name="dataset_fingerprint.sha256"
        )
        object.__setattr__(self, "dataset_fingerprint", fingerprint)
        if not isinstance(self.evidence_reference, EvidenceReference):
            raise ResearchContractError(
                "evidence_reference must be an EvidenceReference."
            )
        if self.evidence_reference.stage is not EvidenceStage.DEVELOPMENT:
            raise ResearchContractError(
                "DiscoverySpecification may use only development/DISCOVERY evidence."
            )
        if self.evidence_reference.sample_reference != self.dataset_reference:
            raise ResearchContractError(
                "evidence sample_reference must match dataset_reference."
            )
        costs = _freeze_json_mapping(
            self.cost_assumptions, field_name="cost_assumptions"
        )
        if self.selection.metric_basis is SelectionMetricBasis.TRADING and not costs:
            raise ResearchContractError(
                "Trading-metric discovery requires explicit cost_assumptions."
            )
        object.__setattr__(self, "cost_assumptions", costs)
        method = _require_non_empty(
            self.validation_method, field_name="validation_method"
        )
        if method != "canonical_experiment":
            raise ResearchContractError(
                "validation_method must be 'canonical_experiment'."
            )
        object.__setattr__(self, "validation_method", method)
        if (
            isinstance(self.random_seed, bool)
            or not isinstance(self.random_seed, int)
            or self.random_seed < 0
        ):
            raise ResearchContractError("random_seed must be an integer >= 0.")

    @property
    def specification_hash(self) -> str:
        """Use the framework's canonical config-hash implementation."""

        from src.utils.run_metadata import compute_config_hash

        digest, _ = compute_config_hash(self.to_dict())
        return digest

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "assets": list(self.assets),
            "timeframe": self.timeframe,
            "feature_families": list(self.feature_families),
            "target_family": self.target_family,
            "model_families": list(self.model_families),
            "signal_families": list(self.signal_families),
            "search_method": self.search_method,
            "trial_budget": self.trial_budget,
            "search_space": self.search_space.to_dict(),
            "selection": self.selection.to_dict(),
            "eligibility": self.eligibility.to_dict(),
            "config_reference": self.config_reference,
            "config_hash": self.config_hash,
            "dataset_reference": self.dataset_reference,
            "dataset_fingerprint": dict(self.dataset_fingerprint),
            "evidence_reference": self.evidence_reference.to_dict(),
            "cost_assumptions": dict(self.cost_assumptions),
            "validation_method": self.validation_method,
            "random_seed": self.random_seed,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> DiscoverySpecification:
        expected = {
            "hypothesis_id",
            "assets",
            "timeframe",
            "feature_families",
            "target_family",
            "model_families",
            "signal_families",
            "search_method",
            "trial_budget",
            "search_space",
            "selection",
            "eligibility",
            "config_reference",
            "config_hash",
            "dataset_reference",
            "dataset_fingerprint",
            "evidence_reference",
            "cost_assumptions",
            "validation_method",
            "random_seed",
        }
        _require_exact_keys(
            payload, expected=expected, field_name="Discovery specification"
        )
        return cls(
            hypothesis_id=payload["hypothesis_id"],
            assets=tuple(_require_json_array(payload["assets"], field_name="assets")),
            timeframe=payload["timeframe"],
            feature_families=tuple(
                _require_json_array(
                    payload["feature_families"], field_name="feature_families"
                )
            ),
            target_family=payload["target_family"],
            model_families=tuple(
                _require_json_array(
                    payload["model_families"], field_name="model_families"
                )
            ),
            signal_families=tuple(
                _require_json_array(
                    payload["signal_families"], field_name="signal_families"
                )
            ),
            search_method=payload["search_method"],
            trial_budget=payload["trial_budget"],
            search_space=SearchSpace.from_dict(payload["search_space"]),
            selection=SelectionPolicy.from_dict(payload["selection"]),
            eligibility=EligibilityPolicy.from_dict(payload["eligibility"]),
            config_reference=payload["config_reference"],
            config_hash=payload["config_hash"],
            dataset_reference=payload["dataset_reference"],
            dataset_fingerprint=payload["dataset_fingerprint"],
            evidence_reference=EvidenceReference.from_dict(
                payload["evidence_reference"]
            ),
            cost_assumptions=payload["cost_assumptions"],
            validation_method=payload["validation_method"],
            random_seed=payload["random_seed"],
        )


@dataclass(frozen=True)
class TrialProposal:
    trial_id: str
    research_run_id: str
    parameters: Mapping[str, Any]
    seed: int

    def __post_init__(self) -> None:
        for field_name in ("trial_id", "research_run_id"):
            object.__setattr__(
                self,
                field_name,
                _require_identifier(getattr(self, field_name), field_name=field_name),
            )
        object.__setattr__(
            self,
            "parameters",
            _freeze_json_mapping(self.parameters, field_name="parameters"),
        )
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ResearchContractError("trial seed must be an integer >= 0.")


@dataclass(frozen=True)
class TrialEvaluation:
    status: TrialStatus
    metrics: Mapping[str, int | float | None] = field(default_factory=dict)
    checks: Mapping[str, bool] = field(default_factory=dict)
    failure_reason: str | None = None
    artifact_references: tuple[str, ...] = ()
    runtime_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            status = TrialStatus(self.status)
        except (TypeError, ValueError) as exc:
            raise ResearchContractError(str(exc)) from exc
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "metrics", _freeze_metrics(self.metrics))
        object.__setattr__(
            self,
            "checks",
            _freeze_checks(self.checks, field_name="checks"),
        )
        object.__setattr__(
            self,
            "artifact_references",
            _require_unique_strings(
                self.artifact_references, field_name="artifact_references"
            ),
        )
        object.__setattr__(
            self,
            "runtime_metadata",
            _freeze_json_mapping(
                self.runtime_metadata, field_name="runtime_metadata"
            ),
        )
        if status is TrialStatus.COMPLETED:
            if self.failure_reason is not None:
                raise ResearchContractError(
                    "A completed trial cannot have failure_reason."
                )
        else:
            object.__setattr__(
                self,
                "failure_reason",
                _require_non_empty(
                    self.failure_reason, field_name="trial failure_reason"
                ),
            )


@dataclass(frozen=True)
class DiscoveryTrial:
    trial_id: str
    research_run_id: str
    parameters: Mapping[str, Any]
    status: TrialStatus
    metrics: Mapping[str, int | float | None]
    checks: Mapping[str, bool]
    seed: int
    failure_reason: str | None = None
    artifact_references: tuple[str, ...] = ()
    runtime_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        proposal = TrialProposal(
            trial_id=self.trial_id,
            research_run_id=self.research_run_id,
            parameters=self.parameters,
            seed=self.seed,
        )
        evaluation = TrialEvaluation(
            status=self.status,
            metrics=self.metrics,
            checks=self.checks,
            failure_reason=self.failure_reason,
            artifact_references=self.artifact_references,
            runtime_metadata=self.runtime_metadata,
        )
        for field_name in ("trial_id", "research_run_id", "parameters", "seed"):
            object.__setattr__(self, field_name, getattr(proposal, field_name))
        for field_name in (
            "status",
            "metrics",
            "checks",
            "failure_reason",
            "artifact_references",
            "runtime_metadata",
        ):
            object.__setattr__(self, field_name, getattr(evaluation, field_name))

    def to_dict(self) -> dict[str, Any]:
        return {
            "trial_id": self.trial_id,
            "research_run_id": self.research_run_id,
            "parameters": dict(self.parameters),
            "status": self.status.value,
            "metrics": dict(self.metrics),
            "checks": dict(self.checks),
            "seed": self.seed,
            "failure_reason": self.failure_reason,
            "artifact_references": list(self.artifact_references),
            "runtime_metadata": dict(self.runtime_metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> DiscoveryTrial:
        expected = {
            "trial_id",
            "research_run_id",
            "parameters",
            "status",
            "metrics",
            "checks",
            "seed",
            "failure_reason",
            "artifact_references",
            "runtime_metadata",
        }
        _require_exact_keys(payload, expected=expected, field_name="Discovery trial")
        return cls(
            trial_id=payload["trial_id"],
            research_run_id=payload["research_run_id"],
            parameters=payload["parameters"],
            status=TrialStatus(payload["status"]),
            metrics=payload["metrics"],
            checks=payload["checks"],
            seed=payload["seed"],
            failure_reason=payload["failure_reason"],
            artifact_references=tuple(
                _require_json_array(
                    payload["artifact_references"], field_name="artifact_references"
                )
            ),
            runtime_metadata=payload["runtime_metadata"],
        )


@dataclass(frozen=True)
class RankingEntry:
    trial_id: str
    trial_status: TrialStatus
    eligible: bool
    rank: int | None
    score: int | float | None
    rejection_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "trial_id",
            _require_identifier(self.trial_id, field_name="trial_id"),
        )
        try:
            status = TrialStatus(self.trial_status)
        except (TypeError, ValueError) as exc:
            raise ResearchContractError(str(exc)) from exc
        object.__setattr__(self, "trial_status", status)
        if not isinstance(self.eligible, bool):
            raise ResearchContractError("eligible must be boolean.")
        if self.rank is not None and (
            isinstance(self.rank, bool) or not isinstance(self.rank, int) or self.rank < 1
        ):
            raise ResearchContractError("rank must be null or an integer >= 1.")
        if self.score is not None and (
            isinstance(self.score, bool)
            or not isinstance(self.score, (int, float))
            or not isfinite(float(self.score))
        ):
            raise ResearchContractError("score must be finite or null.")
        reasons = _require_unique_strings(
            self.rejection_reasons, field_name="rejection_reasons"
        )
        object.__setattr__(self, "rejection_reasons", reasons)
        if self.eligible and (self.rank is None or self.score is None or reasons):
            raise ResearchContractError(
                "Eligible ranking entries require rank/score and forbid rejection reasons."
            )
        if not self.eligible and (self.rank is not None or not reasons):
            raise ResearchContractError(
                "Ineligible ranking entries require reasons and cannot have rank."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "trial_id": self.trial_id,
            "trial_status": self.trial_status.value,
            "eligible": self.eligible,
            "rank": self.rank,
            "score": self.score,
            "rejection_reasons": list(self.rejection_reasons),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RankingEntry:
        required = {
            "trial_id",
            "trial_status",
            "eligible",
            "rank",
            "score",
            "rejection_reasons",
        }
        _require_exact_keys(payload, expected=required, field_name="ranking_entry")
        return cls(
            trial_id=payload["trial_id"],
            trial_status=payload["trial_status"],
            eligible=payload["eligible"],
            rank=payload["rank"],
            score=payload["score"],
            rejection_reasons=tuple(
                _require_json_array(
                    payload["rejection_reasons"],
                    field_name="rejection_reasons",
                )
            ),
        )


@dataclass(frozen=True)
class CandidateRanking:
    selection_metric: str
    selection_direction: SelectionDirection
    tie_break_rule: str
    entries: tuple[RankingEntry, ...]
    total_trial_count: int
    completed_trial_count: int
    eligible_candidate_count: int
    rejection_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "selection_metric",
            _require_non_empty(self.selection_metric, field_name="selection_metric"),
        )
        try:
            direction = SelectionDirection(self.selection_direction)
        except (TypeError, ValueError) as exc:
            raise ResearchContractError(str(exc)) from exc
        object.__setattr__(self, "selection_direction", direction)
        object.__setattr__(
            self,
            "tie_break_rule",
            _require_non_empty(self.tie_break_rule, field_name="tie_break_rule"),
        )
        entries = tuple(self.entries)
        if any(not isinstance(item, RankingEntry) for item in entries):
            raise ResearchContractError(
                "ranking entries must contain only RankingEntry values."
            )
        trial_ids = tuple(item.trial_id for item in entries)
        if len(set(trial_ids)) != len(trial_ids):
            raise ResearchContractError("ranking trial IDs must be unique.")
        object.__setattr__(self, "entries", entries)
        for field_name in (
            "total_trial_count",
            "completed_trial_count",
            "eligible_candidate_count",
        ):
            _non_negative_int(getattr(self, field_name), field_name=field_name)
        if self.total_trial_count != len(entries):
            raise ResearchContractError("total_trial_count must equal entries length.")
        if self.completed_trial_count != sum(
            item.trial_status is TrialStatus.COMPLETED for item in entries
        ):
            raise ResearchContractError(
                "completed_trial_count must match completed entries."
            )
        eligible = tuple(item for item in entries if item.eligible)
        if self.eligible_candidate_count != len(eligible):
            raise ResearchContractError(
                "eligible_candidate_count must match eligible entries."
            )
        if sorted(item.rank for item in eligible) != list(
            range(1, len(eligible) + 1)
        ):
            raise ResearchContractError("Eligible ranks must be contiguous from 1.")
        if not isinstance(self.rejection_counts, Mapping):
            raise ResearchContractError("rejection_counts must be a mapping.")
        counts: dict[str, int] = {}
        for raw_reason, count in self.rejection_counts.items():
            reason = _require_non_empty(
                raw_reason, field_name="rejection_counts key"
            )
            counts[reason] = _non_negative_int(
                count, field_name=f"rejection_counts.{reason}"
            )
        object.__setattr__(self, "rejection_counts", MappingProxyType(counts))

    def entry_for(self, trial_id: str) -> RankingEntry:
        match = next((item for item in self.entries if item.trial_id == trial_id), None)
        if match is None:
            raise ResearchContractError(f"Unknown ranked trial {trial_id!r}.")
        return match

    def to_dict(self) -> dict[str, Any]:
        return {
            "selection_metric": self.selection_metric,
            "selection_direction": self.selection_direction.value,
            "tie_break_rule": self.tie_break_rule,
            "entries": [entry.to_dict() for entry in self.entries],
            "total_trial_count": self.total_trial_count,
            "completed_trial_count": self.completed_trial_count,
            "eligible_candidate_count": self.eligible_candidate_count,
            "rejection_counts": dict(self.rejection_counts),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> CandidateRanking:
        required = {
            "selection_metric",
            "selection_direction",
            "tie_break_rule",
            "entries",
            "total_trial_count",
            "completed_trial_count",
            "eligible_candidate_count",
            "rejection_counts",
        }
        _require_exact_keys(payload, expected=required, field_name="candidate_ranking")
        entries = _require_json_array(payload["entries"], field_name="entries")
        if any(not isinstance(item, Mapping) for item in entries):
            raise ResearchContractError("entries must contain JSON objects.")
        rejection_counts = payload["rejection_counts"]
        if not isinstance(rejection_counts, Mapping):
            raise ResearchContractError("rejection_counts must be a JSON object.")
        return cls(
            selection_metric=payload["selection_metric"],
            selection_direction=payload["selection_direction"],
            tie_break_rule=payload["tie_break_rule"],
            entries=tuple(RankingEntry.from_dict(item) for item in entries),
            total_trial_count=payload["total_trial_count"],
            completed_trial_count=payload["completed_trial_count"],
            eligible_candidate_count=payload["eligible_candidate_count"],
            rejection_counts=rejection_counts,
        )


@dataclass(frozen=True)
class ParameterNeighborhoodStability:
    candidate_trial_id: str
    parameter_name: str
    selection_metric: str
    direction: SelectionDirection
    configured_max_degradation: float
    neighbor_scores: Mapping[str, int | float]
    status: CheckStatus
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("candidate_trial_id",):
            object.__setattr__(
                self,
                field_name,
                _require_identifier(getattr(self, field_name), field_name=field_name),
            )
        for field_name in ("parameter_name", "selection_metric"):
            object.__setattr__(
                self,
                field_name,
                _require_non_empty(getattr(self, field_name), field_name=field_name),
            )
        try:
            direction = SelectionDirection(self.direction)
            status = CheckStatus(self.status)
        except (TypeError, ValueError) as exc:
            raise ResearchContractError(str(exc)) from exc
        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "status", status)
        if (
            isinstance(self.configured_max_degradation, bool)
            or not isinstance(self.configured_max_degradation, (int, float))
            or not isfinite(float(self.configured_max_degradation))
            or float(self.configured_max_degradation) < 0.0
        ):
            raise ResearchContractError(
                "configured_max_degradation must be finite and >= 0."
            )
        frozen_scores = _freeze_metrics(self.neighbor_scores)
        if any(value is None for value in frozen_scores.values()):
            raise ResearchContractError("neighbor_scores cannot contain null values.")
        object.__setattr__(self, "neighbor_scores", frozen_scores)
        object.__setattr__(
            self,
            "details",
            _freeze_json_mapping(self.details, field_name="details"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_trial_id": self.candidate_trial_id,
            "parameter_name": self.parameter_name,
            "selection_metric": self.selection_metric,
            "direction": self.direction.value,
            "configured_max_degradation": float(self.configured_max_degradation),
            "neighbor_scores": dict(self.neighbor_scores),
            "status": self.status.value,
            "details": dict(self.details),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ParameterNeighborhoodStability:
        required = {
            "candidate_trial_id",
            "parameter_name",
            "selection_metric",
            "direction",
            "configured_max_degradation",
            "neighbor_scores",
            "status",
            "details",
        }
        _require_exact_keys(
            payload,
            expected=required,
            field_name="parameter_neighborhood_stability",
        )
        neighbor_scores = payload["neighbor_scores"]
        details = payload["details"]
        if not isinstance(neighbor_scores, Mapping):
            raise ResearchContractError("neighbor_scores must be a JSON object.")
        if not isinstance(details, Mapping):
            raise ResearchContractError("details must be a JSON object.")
        return cls(
            candidate_trial_id=payload["candidate_trial_id"],
            parameter_name=payload["parameter_name"],
            selection_metric=payload["selection_metric"],
            direction=payload["direction"],
            configured_max_degradation=payload["configured_max_degradation"],
            neighbor_scores=neighbor_scores,
            status=payload["status"],
            details=details,
        )


__all__ = [
    "CandidateRanking",
    "DiscoverySpecification",
    "DiscoveryTrial",
    "EligibilityPolicy",
    "EligibilityRule",
    "MetricPreference",
    "MinimumDataRequirements",
    "ParameterNeighborhoodStability",
    "RankingEntry",
    "RuleOperator",
    "SelectionMetricBasis",
    "SelectionPolicy",
    "TrialEvaluation",
    "TrialProposal",
    "TrialStatus",
]
