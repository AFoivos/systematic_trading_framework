"""Validation for the hash-bound AR-0004 cloud ML discovery contract."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from src.utils.alpha_discovery_config import (
    AlphaDiscoveryConfigError,
    AlphaDiscoveryStatus,
    _bool,
    _exact_keys,
    _mapping,
    _non_empty_string,
    _sha256,
    _timezone_aware_timestamp,
    compute_alpha_specification_hash,
)
from src.utils.alpha_discovery_v3_config import AR0003_ASSETS, AR0003_SOURCE_SHA256


AR0004_TUNING_FOLDS = (
    ("TUNE-2023-H1", "2023-01-01T00:00:00Z", "2023-07-01T00:00:00Z"),
    ("TUNE-2023-H2", "2023-07-01T00:00:00Z", "2024-01-01T00:00:00Z"),
    ("TUNE-2024-H1", "2024-01-01T00:00:00Z", "2024-07-01T00:00:00Z"),
    ("TUNE-2024-H2", "2024-07-01T00:00:00Z", "2025-01-01T00:00:00Z"),
)
AR0004_SCREENING_FOLDS = (
    ("SCREEN-2025-H1", "2025-01-01T00:00:00Z", "2025-07-01T00:00:00Z"),
    ("SCREEN-2025-H2", "2025-07-01T00:00:00Z", "2026-01-01T00:00:00Z"),
    ("SCREEN-2026-Q1", "2026-01-01T00:00:00Z", "2026-04-28T00:00:00Z"),
)
AR0004_SCREENING_FAMILY_SIZE = 25

_TOP_LEVEL_KEYS = {
    "schema_version",
    "pipeline",
    "research_id",
    "title",
    "status",
    "specification_hash",
    "approval",
    "hypothesis",
    "prior_research_context",
    "scientific_contract",
    "asset_universe",
    "features",
    "target",
    "walk_forward",
    "model_search",
    "screening_evaluation",
    "cost_policy",
    "inference",
    "candidate_gates",
    "resource_policy",
    "artifacts",
    "runtime",
    "blockers",
    "config_path",
}


def _iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _validate_approval(cfg: dict[str, Any]) -> AlphaDiscoveryStatus:
    try:
        status = AlphaDiscoveryStatus(cfg["status"])
    except (KeyError, ValueError) as exc:
        raise AlphaDiscoveryConfigError("Invalid AR-0004 status.") from exc
    approval = _mapping(cfg["approval"], field="approval")
    _exact_keys(
        approval,
        {"approved_to_run", "approved_by", "approved_at", "approved_specification_hash"},
        field="approval",
    )
    approved = _bool(approval["approved_to_run"], field="approval.approved_to_run")
    metadata = ("approved_by", "approved_at", "approved_specification_hash")
    if status is AlphaDiscoveryStatus.SPECIFICATION_ONLY:
        if approved or any(approval[name] is not None for name in metadata):
            raise AlphaDiscoveryConfigError(
                "AR-0004 SPECIFICATION_ONLY approval must remain false and null."
            )
    else:
        if not approved:
            raise AlphaDiscoveryConfigError(
                "AR-0004 APPROVED_TO_RUN requires approved_to_run=true."
            )
        for name in metadata:
            _non_empty_string(approval[name], field=f"approval.{name}")
        _timezone_aware_timestamp(approval["approved_at"], field="approval.approved_at")
    return status


def _validate_universe(cfg: dict[str, Any]) -> None:
    universe = _mapping(cfg["asset_universe"], field="asset_universe")
    assets = universe.get("asset_ids")
    if tuple(assets or ()) != AR0003_ASSETS:
        raise AlphaDiscoveryConfigError("AR-0004 requires the frozen 15-asset universe.")
    if universe.get("timeframe") != "30m" or universe.get("timezone") != "UTC":
        raise AlphaDiscoveryConfigError("AR-0004 is frozen to 30m UTC data.")
    if universe.get("minimum_assets_per_timestamp") != 5:
        raise AlphaDiscoveryConfigError("AR-0004 minimum cross-sectional assets must be 5.")
    if universe.get("missing_observation_policy") != "PRESERVE_ABSENCE_NO_DENSIFICATION":
        raise AlphaDiscoveryConfigError("AR-0004 cannot densify the observed panel.")
    if universe.get("source_bar_policy") != "OBSERVED_PROVIDER_30M_BARS_NO_MINUTE_RECONSTRUCTION":
        raise AlphaDiscoveryConfigError("AR-0004 source-bar policy drifted.")
    sources = _mapping(universe.get("source_files"), field="asset_universe.source_files")
    if tuple(sorted(sources)) != AR0003_ASSETS:
        raise AlphaDiscoveryConfigError("AR-0004 sources must match the frozen universe.")
    for asset in AR0003_ASSETS:
        source = _mapping(sources[asset], field=f"source_files.{asset}")
        if source != {
            "path": f"data/raw/dukascopy_30m_clean/{asset.lower()}_30m.csv",
            "sha256": AR0003_SOURCE_SHA256[asset],
        }:
            raise AlphaDiscoveryConfigError(f"AR-0004 source binding drifted for {asset}.")


def _validate_folds(cfg: dict[str, Any]) -> None:
    policy = _mapping(cfg["walk_forward"], field="walk_forward")
    if policy.get("kind") != "EXPANDING" or policy.get("random_shuffle") is not False:
        raise AlphaDiscoveryConfigError("AR-0004 requires expanding chronological folds.")
    if policy.get("refit_per_fold") is not True or policy.get("embargo_bars") != 0:
        raise AlphaDiscoveryConfigError("AR-0004 refit/embargo policy drifted.")
    for name, expected in (
        ("tuning_folds", AR0004_TUNING_FOLDS),
        ("screening_folds", AR0004_SCREENING_FOLDS),
    ):
        rows = policy.get(name)
        if not isinstance(rows, list) or len(rows) != len(expected):
            raise AlphaDiscoveryConfigError(f"AR-0004 {name} cardinality drifted.")
        normalized = tuple(
            (row.get("fold_id"), row.get("test_start"), row.get("test_end"))
            for row in rows
            if isinstance(row, Mapping)
        )
        if normalized != expected:
            raise AlphaDiscoveryConfigError(f"AR-0004 {name} boundaries drifted.")
        if any(_iso(start) >= _iso(end) for _, start, end in normalized):
            raise AlphaDiscoveryConfigError(f"AR-0004 {name} has invalid chronology.")


def _validate_search(cfg: dict[str, Any]) -> None:
    search = _mapping(cfg["model_search"], field="model_search")
    expected = {
        "owner": "STF_MODEL_REGISTRY",
        "model_kind": "lightgbm_regressor",
        "method": "OPTUNA_TPE",
        "trials": 384,
        "top_trials_for_screening": 24,
        "ensemble_top_k_same_horizon": 5,
        "parallel_jobs": 4,
        "threads_per_model": 1,
        "objective": "STABILITY_ADJUSTED_MEAN_RANK_IC",
    }
    for field, value in expected.items():
        if search.get(field) != value:
            raise AlphaDiscoveryConfigError(f"AR-0004 model_search.{field} drifted.")
    space = _mapping(search.get("space"), field="model_search.space")
    if space.get("feature_set") != [
        "trend", "trend_quality", "trend_quality_volatility", "full_cross_sectional"
    ] or space.get("horizon_bars") != [16, 32]:
        raise AlphaDiscoveryConfigError("AR-0004 feature/horizon search family drifted.")
    inference = _mapping(cfg["inference"], field="inference")
    if (
        inference.get("screening_family_size") != AR0004_SCREENING_FAMILY_SIZE
        or inference.get("includes_ensemble") is not True
        or inference.get("binding_method") != "GLOBAL_BENJAMINI_YEKUTIELI"
        or inference.get("false_discovery_rate") != 0.05
        or inference.get("failed_or_invalid_alternatives_retained_as_p1") is not True
    ):
        raise AlphaDiscoveryConfigError("AR-0004 binding inference family drifted.")
    if int(search["top_trials_for_screening"]) + 1 != AR0004_SCREENING_FAMILY_SIZE:
        raise AlphaDiscoveryConfigError("AR-0004 screening family must include 24 models plus ensemble.")


def _validate_safety(cfg: dict[str, Any], *, status: AlphaDiscoveryStatus) -> None:
    target = _mapping(cfg["target"], field="target")
    if target.get("horizons_bars") != [16, 32]:
        raise AlphaDiscoveryConfigError("AR-0004 target horizons drifted.")
    if any(
        target.get(name) != expected
        for name, expected in {
            "information_time": "CLOSE_T",
            "entry": "OPEN_T_PLUS_1",
            "exit": "OPEN_T_PLUS_H_PLUS_1",
            "observed_bid_ask_required": True,
            "zero_cost_fallback": "FORBIDDEN",
            "target_overlap_purge_bars": "HORIZON_PLUS_ONE",
        }.items()
    ):
        raise AlphaDiscoveryConfigError("AR-0004 target timing/cost contract drifted.")
    costs = _mapping(cfg["cost_policy"], field="cost_policy")
    if costs.get("stress_multiplier") != 1.50 or costs.get("unsupported_cost_fallback") != "FORBIDDEN":
        raise AlphaDiscoveryConfigError("AR-0004 stress-cost contract drifted.")
    runtime = _mapping(cfg["runtime"], field="runtime")
    forbidden = (
        "access_validation", "access_historical_pseudo_oos", "access_prospective_final",
        "run_canonical_backtest", "construct_portfolio", "paper_demo_live_execution",
        "auto_promote_candidate",
    )
    if any(runtime.get(name) is not False for name in forbidden):
        raise AlphaDiscoveryConfigError("AR-0004 runtime safety must remain fail-closed.")
    if status is AlphaDiscoveryStatus.SPECIFICATION_ONLY and runtime.get("perform_alpha_calculation") is not False:
        raise AlphaDiscoveryConfigError("SPECIFICATION_ONLY AR-0004 cannot calculate alpha.")
    if status is AlphaDiscoveryStatus.APPROVED_TO_RUN and runtime.get("perform_alpha_calculation") is not True:
        raise AlphaDiscoveryConfigError("Approved AR-0004 must explicitly enable calculation.")
    blockers = cfg["blockers"]
    if status is AlphaDiscoveryStatus.SPECIFICATION_ONLY and blockers != [
        "HUMAN_APPROVAL_OF_EXACT_SPECIFICATION_HASH_REQUIRED"
    ]:
        raise AlphaDiscoveryConfigError("AR-0004 SPECIFICATION_ONLY blocker drifted.")
    if status is AlphaDiscoveryStatus.APPROVED_TO_RUN and blockers:
        raise AlphaDiscoveryConfigError("Approved AR-0004 cannot retain blockers.")


def validate_alpha_discovery_v4_config(cfg: dict[str, Any]) -> None:
    """Validate schema-critical, scientific, approval, and safety invariants."""

    if not isinstance(cfg, dict):
        raise AlphaDiscoveryConfigError("AR-0004 config must be a mapping.")
    _exact_keys(cfg, _TOP_LEVEL_KEYS, field="AR-0004 top level")
    if cfg.get("schema_version") != 5 or cfg.get("pipeline") != {
        "kind": "alpha_discovery_v4", "stage": "CLOUD_ML_DISCOVERY"
    }:
        raise AlphaDiscoveryConfigError("AR-0004 pipeline/schema drifted.")
    if cfg.get("research_id") != "AR-0004" or cfg.get("title") != "Cross-Asset Walk-Forward Alpha Tournament":
        raise AlphaDiscoveryConfigError("AR-0004 identity drifted.")
    status = _validate_approval(cfg)
    _validate_universe(cfg)
    _validate_folds(cfg)
    _validate_search(cfg)
    _validate_safety(cfg, status=status)
    declared = _sha256(cfg["specification_hash"], field="specification_hash")
    computed = compute_alpha_specification_hash(cfg)
    if declared != computed:
        raise AlphaDiscoveryConfigError(
            f"specification_hash mismatch: declared={declared}, computed={computed}."
        )
    if status is AlphaDiscoveryStatus.APPROVED_TO_RUN:
        approved = _sha256(
            cfg["approval"]["approved_specification_hash"],
            field="approval.approved_specification_hash",
        )
        if approved != computed:
            raise AlphaDiscoveryConfigError("AR-0004 approval hash does not match the specification.")


__all__ = [
    "AR0004_SCREENING_FAMILY_SIZE",
    "AR0004_SCREENING_FOLDS",
    "AR0004_TUNING_FOLDS",
    "validate_alpha_discovery_v4_config",
]
