"""Validation for the fail-closed AR-0003 cross-sectional research contract."""

from __future__ import annotations

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


AR0003_MOMENTUM_COLUMNS = (
    "log_return_16",
    "log_return_32",
    "log_return_64",
)
AR0003_PATH_EFFICIENCY_COLUMNS = (
    "path_efficiency_16",
    "path_efficiency_32",
    "path_efficiency_48",
)
AR0003_PRIMARY_HORIZON = 32
AR0003_ROBUSTNESS_VARIANTS = 12

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
    "dataset_contract",
    "features",
    "primary_score",
    "regime_policy",
    "target",
    "cross_sectional_evaluation",
    "temporal_stability",
    "cost_policy",
    "robustness_family",
    "multiple_testing",
    "secondary_lightgbm",
    "resource_policy",
    "promotion_gates",
    "artifacts",
    "runtime",
    "blockers",
    "config_path",
}


def _require_exact(payload: Any, expected: Mapping[str, Any], *, field: str) -> None:
    resolved = _mapping(payload, field=field)
    if resolved != dict(expected):
        raise AlphaDiscoveryConfigError(f"{field} violates the frozen AR-0003 contract.")


def _validate_approval(cfg: dict[str, Any]) -> AlphaDiscoveryStatus:
    try:
        status = AlphaDiscoveryStatus(cfg["status"])
    except (KeyError, ValueError) as exc:
        raise AlphaDiscoveryConfigError("Invalid AR-0003 status.") from exc
    approval = _mapping(cfg["approval"], field="approval")
    _exact_keys(
        approval,
        {
            "approved_to_run",
            "approved_by",
            "approved_at",
            "approved_specification_hash",
        },
        field="approval",
    )
    approved = _bool(approval["approved_to_run"], field="approval.approved_to_run")
    metadata = ("approved_by", "approved_at", "approved_specification_hash")
    if status is AlphaDiscoveryStatus.SPECIFICATION_ONLY:
        if approved or any(approval[name] is not None for name in metadata):
            raise AlphaDiscoveryConfigError(
                "AR-0003 SPECIFICATION_ONLY approval must remain false and null."
            )
    else:
        if not approved:
            raise AlphaDiscoveryConfigError(
                "AR-0003 APPROVED_TO_RUN requires approved_to_run=true."
            )
        for name in metadata:
            _non_empty_string(approval[name], field=f"approval.{name}")
        _timezone_aware_timestamp(approval["approved_at"], field="approval.approved_at")
    return status


def _validate_asset_and_dataset_contracts(
    cfg: dict[str, Any], *, status: AlphaDiscoveryStatus
) -> None:
    universe = _mapping(cfg["asset_universe"], field="asset_universe")
    _exact_keys(
        universe,
        {
            "reference",
            "asset_ids",
            "timeframe",
            "timezone",
            "status",
            "minimum_assets_per_timestamp",
            "missing_observation_policy",
        },
        field="asset_universe",
    )
    if universe["timeframe"] != "30m" or universe["timezone"] != "UTC":
        raise AlphaDiscoveryConfigError("AR-0003 is frozen to 30m UTC research data.")
    if universe["minimum_assets_per_timestamp"] != 5:
        raise AlphaDiscoveryConfigError(
            "AR-0003 minimum cross-sectional asset count must remain 5."
        )
    if universe["missing_observation_policy"] != "PRESERVE_ABSENCE_NO_DENSIFICATION":
        raise AlphaDiscoveryConfigError("AR-0003 cannot densify missing panel rows.")
    assets = universe["asset_ids"]
    if not isinstance(assets, list) or any(
        not isinstance(asset, str) or not asset.strip() for asset in assets
    ):
        raise AlphaDiscoveryConfigError("asset_universe.asset_ids must be a string list.")
    if len(set(assets)) != len(assets) or assets != sorted(assets):
        raise AlphaDiscoveryConfigError(
            "asset_universe.asset_ids must be unique and lexicographically sorted."
        )
    if universe["status"] == "UNRESOLVED":
        if assets or universe["reference"] != "CANONICAL_MULTI_ASSET_UNIVERSE_UNRESOLVED":
            raise AlphaDiscoveryConfigError(
                "An unresolved AR-0003 universe cannot contain invented asset IDs."
            )
    elif universe["status"] == "READY":
        if len(assets) < 5:
            raise AlphaDiscoveryConfigError(
                "A ready AR-0003 universe requires at least five canonical assets."
            )
        _non_empty_string(universe["reference"], field="asset_universe.reference")
    else:
        raise AlphaDiscoveryConfigError("asset_universe.status must be UNRESOLVED or READY.")

    dataset = _mapping(cfg["dataset_contract"], field="dataset_contract")
    _exact_keys(
        dataset,
        {
            "contract_kind",
            "dataset_id",
            "metadata_path",
            "data_path",
            "dataset_sha256",
            "source_snapshot_fingerprints",
            "evidence_role",
            "required_segments",
            "row_identity",
            "prediction_eligibility_required",
            "status",
        },
        field="dataset_contract",
    )
    frozen = {
        "contract_kind": "PanelResearchDataset",
        "evidence_role": "DISCOVERY",
        "required_segments": ["TRAINING", "TUNING", "SCREENING"],
        "row_identity": ["timestamp", "asset_id"],
        "prediction_eligibility_required": True,
    }
    if any(dataset[name] != value for name, value in frozen.items()):
        raise AlphaDiscoveryConfigError(
            "AR-0003 must use the STF R1 DISCOVERY panel contract."
        )
    if dataset["status"] == "UNAVAILABLE":
        nullable = ("dataset_id", "metadata_path", "data_path", "dataset_sha256")
        if any(dataset[name] is not None for name in nullable):
            raise AlphaDiscoveryConfigError(
                "An unavailable AR-0003 panel cannot claim dataset bindings."
            )
        if dataset["source_snapshot_fingerprints"] != {}:
            raise AlphaDiscoveryConfigError(
                "An unavailable AR-0003 panel cannot claim snapshot fingerprints."
            )
    elif dataset["status"] == "READY":
        for name in ("dataset_id", "metadata_path", "data_path"):
            _non_empty_string(dataset[name], field=f"dataset_contract.{name}")
        _sha256(dataset["dataset_sha256"], field="dataset_contract.dataset_sha256")
        fingerprints = _mapping(
            dataset["source_snapshot_fingerprints"],
            field="dataset_contract.source_snapshot_fingerprints",
        )
        if not fingerprints:
            raise AlphaDiscoveryConfigError(
                "A ready AR-0003 panel requires source snapshot fingerprints."
            )
        for name, value in fingerprints.items():
            _non_empty_string(name, field="source snapshot reference")
            _sha256(value, field=f"source_snapshot_fingerprints.{name}")
    else:
        raise AlphaDiscoveryConfigError(
            "dataset_contract.status must be UNAVAILABLE or READY."
        )
    if status is AlphaDiscoveryStatus.APPROVED_TO_RUN and (
        universe["status"] != "READY" or dataset["status"] != "READY"
    ):
        raise AlphaDiscoveryConfigError(
            "AR-0003 cannot be approved until universe and panel dataset are READY."
        )


def _validate_scientific_core(cfg: dict[str, Any]) -> None:
    hypothesis = _mapping(cfg["hypothesis"], field="hypothesis")
    _exact_keys(
        hypothesis,
        {
            "statement",
            "primary_horizon_bars",
            "directionality",
            "prior_results_role",
            "prior_results_are_validation",
        },
        field="hypothesis",
    )
    _non_empty_string(hypothesis["statement"], field="hypothesis.statement")
    if hypothesis["primary_horizon_bars"] != AR0003_PRIMARY_HORIZON:
        raise AlphaDiscoveryConfigError("AR-0003 primary horizon must remain 32 bars.")
    if hypothesis["directionality"] != "SAME_DIRECTION":
        raise AlphaDiscoveryConfigError("AR-0003 directionality drifted.")
    if (
        hypothesis["prior_results_role"] != "POST_HOC_HYPOTHESIS_GENERATION_ONLY"
        or hypothesis["prior_results_are_validation"] is not False
    ):
        raise AlphaDiscoveryConfigError(
            "Previous conditional effects cannot be AR-0003 validation evidence."
        )

    prior = _mapping(cfg["prior_research_context"], field="prior_research_context")
    expected_prior = {
        "source_research_ids": ["AR-0001"],
        "source_specification_hashes": {
            "AR-0001": "38547ee331f5efe7f3dabbe7f5895974b454bf52e4fde92a0b2b6908ab725c1c"
        },
        "evidence_role": "DISCOVERY",
        "use": "POST_HOC_HYPOTHESIS_GENERATION_ONLY",
        "contamination_statement": (
            "PREVIOUS_CONDITIONAL_EFFECTS_ARE_NOT_INDEPENDENT_VALIDATION"
        ),
    }
    if prior != expected_prior:
        raise AlphaDiscoveryConfigError("AR-0003 prior-evidence boundary drifted.")
    _require_exact(
        cfg["scientific_contract"],
        {
            "role_assignment": "IMMUTABLE_PER_SNAPSHOT",
            "material_change_policy": "NEW_RESEARCH_CYCLE_AND_NEW_HASH",
            "candidate_ceiling": "PENDING_CANONICAL_VALIDATION",
            "canonical_validation_owner": "STF_CANONICAL_EXPERIMENT",
            "automatic_promotion": "FORBIDDEN",
        },
        field="scientific_contract",
    )

    features = _mapping(cfg["features"], field="features")
    _exact_keys(
        features,
        {
            "owner",
            "available_at",
            "missing_value_policy",
            "momentum",
            "path_efficiency",
            "realized_volatility",
            "volatility_ratio",
        },
        field="features",
    )
    expected_features = {
        "owner": "STF_FEATURE_REGISTRY",
        "available_at": {"bar_offset": 0, "event": "CLOSE"},
        "missing_value_policy": "PRESERVE_AND_MARK_INELIGIBLE",
        "momentum": {
            "kind": "log_return",
            "windows": [16, 32, 64],
            "output_columns": list(AR0003_MOMENTUM_COLUMNS),
        },
        "path_efficiency": {
            "kind": "path_efficiency",
            "windows": [16, 32, 48],
            "output_columns": list(AR0003_PATH_EFFICIENCY_COLUMNS),
        },
        "realized_volatility": {
            "kind": "realized_volatility",
            "windows": [16, 32, 64, 192],
            "primary_columns": [
                "realized_volatility_32",
                "realized_volatility_192",
            ],
            "secondary_model_columns": [
                "realized_volatility_16",
                "realized_volatility_32",
                "realized_volatility_64",
                "realized_volatility_192",
            ],
        },
        "volatility_ratio": {
            "numerator": "realized_volatility_32",
            "denominator": "realized_volatility_192",
            "output_column": "volatility_ratio_32_192",
            "zero_denominator_policy": "MISSING",
        },
    }
    if features != expected_features:
        raise AlphaDiscoveryConfigError("AR-0003 feature definitions drifted.")

    score = _mapping(cfg["primary_score"], field="primary_score")
    if score != {
        "model_kind": "DETERMINISTIC_INTERPRETABLE_SCORE",
        "trend_agreement": {
            "minimum_same_direction_horizons": 2,
            "zero_return_direction": "NEUTRAL",
        },
        "cross_sectional_zscore": {
            "grouping": "SAME_TIMESTAMP_OBSERVED_ASSETS",
            "ddof": 0,
            "minimum_assets": 5,
            "constant_cross_section_policy": "MISSING",
        },
        "trend_score": {
            "aggregation": "MEDIAN",
            "inputs": [
                "cross_sectional_zscore(log_return_16)",
                "cross_sectional_zscore(log_return_32)",
                "cross_sectional_zscore(log_return_64)",
            ],
        },
        "quality_score": {
            "aggregation": "MEDIAN",
            "inputs": list(AR0003_PATH_EFFICIENCY_COLUMNS),
        },
        "alpha_score": {"formula": "trend_score * quality_score"},
        "primary_test_must_precede_robustness": True,
    }:
        raise AlphaDiscoveryConfigError("AR-0003 primary score formula drifted.")

    _require_exact(
        cfg["regime_policy"],
        {
            "percentile_method": "CROSS_SECTIONAL_AVERAGE_RANK_AT_SAME_TIMESTAMP",
            "causal": True,
            "inclusive_boundaries": True,
            "path_efficiency_input": "quality_score",
            "path_efficiency_min_percentile": 0.70,
            "volatility_input": "volatility_ratio_32_192",
            "volatility_percentile_interval": [0.20, 0.80],
            "minimum_assets": 5,
            "future_rows_used": False,
        },
        field="regime_policy",
    )
    _require_exact(
        cfg["target"],
        {
            "owner": "STF_TARGET_REGISTRY",
            "kind": "executable_return",
            "horizon_bars": 32,
            "direction": "SAME_AS_ALPHA_SCORE",
            "information_time": "CLOSE_T",
            "entry_boundary": "OPEN_T_PLUS_1",
            "exit_boundary": "OPEN_T_PLUS_H_PLUS_1",
            "observed_bid_ask_required": True,
            "zero_cost_fallback": "FORBIDDEN",
            "panel_mapping_status": "UNAVAILABLE",
        },
        field="target",
    )
    _require_exact(
        cfg["cross_sectional_evaluation"],
        {
            "prediction_scope": "ELIGIBLE_SCREENING_ROWS_ONLY",
            "rank_by": "alpha_score",
            "top_fraction": 0.20,
            "bottom_fraction": 0.20,
            "tie_breaker": "asset_id",
            "preserve_individual_asset_predictions": True,
            "primary_metrics": [
                "mean_rank_ic",
                "median_rank_ic",
                "rank_ic_dispersion",
                "positive_ic_period_ratio",
                "top_tail_mean_executable_return",
                "bottom_tail_mean_executable_return",
                "top_minus_bottom_executable_return_spread",
                "per_asset_coverage",
                "per_asset_predictive_metrics",
                "temporal_stability",
            ],
            "top_bottom_interpretation": (
                "DIAGNOSTIC_ONLY_NOT_A_PORTFOLIO_BACKTEST"
            ),
        },
        field="cross_sectional_evaluation",
    )
    _require_exact(
        cfg["temporal_stability"],
        {
            "partition": "EXPLICIT_EXISTING_SEGMENTS_THEN_CALENDAR_YEAR",
            "report_fields": [
                "n",
                "mean_executable_return",
                "rank_ic",
                "coverage",
                "hit_rate",
            ],
            "aggregate_positive_is_not_sufficient": True,
            "minimum_period_threshold": "NOT_HARDCODED_PENDING_DATA_CONTRACT",
        },
        field="temporal_stability",
    )


def _validate_search_and_safety(cfg: dict[str, Any], *, status: AlphaDiscoveryStatus) -> None:
    robustness = _mapping(cfg["robustness_family"], field="robustness_family")
    expected_robustness = {
        "evaluation_order": "AFTER_PRIMARY_ONLY",
        "path_efficiency_percentiles": [0.60, 0.70, 0.80],
        "volatility_percentile_intervals": [[0.10, 0.90], [0.20, 0.80]],
        "forward_horizons_bars": [16, 32],
        "total_variants": AR0003_ROBUSTNESS_VARIANTS,
        "includes_primary_variant": True,
    }
    if robustness != expected_robustness:
        raise AlphaDiscoveryConfigError("AR-0003 robustness family drifted.")
    cardinality = (
        len(robustness["path_efficiency_percentiles"])
        * len(robustness["volatility_percentile_intervals"])
        * len(robustness["forward_horizons_bars"])
    )
    if cardinality != AR0003_ROBUSTNESS_VARIANTS:
        raise AlphaDiscoveryConfigError("AR-0003 robustness cardinality must be 12.")

    multiple = _mapping(cfg["multiple_testing"], field="multiple_testing")
    _exact_keys(
        multiple,
        {
            "deterministic_family_size",
            "family_dimensions",
            "primary_variant",
            "failed_or_invalid_alternatives_retained",
            "binding_method",
            "secondary_model_family_separate",
        },
        field="multiple_testing",
    )
    if multiple["deterministic_family_size"] != cardinality:
        raise AlphaDiscoveryConfigError(
            "AR-0003 multiple-testing family must include all 12 variants."
        )
    if multiple["failed_or_invalid_alternatives_retained"] is not True:
        raise AlphaDiscoveryConfigError(
            "AR-0003 failed alternatives must remain in search breadth."
        )
    if multiple["secondary_model_family_separate"] is not True:
        raise AlphaDiscoveryConfigError(
            "AR-0003 LightGBM breadth must remain a separate family."
        )
    if multiple["family_dimensions"] != [
        "path_efficiency_percentile",
        "volatility_percentile_interval",
        "forward_horizon_bars",
    ] or multiple["primary_variant"] != {
        "path_efficiency_percentile": 0.70,
        "volatility_percentile_interval": [0.20, 0.80],
        "forward_horizon_bars": 32,
    }:
        raise AlphaDiscoveryConfigError(
            "AR-0003 multiple-testing dimensions or primary member drifted."
        )
    if status is AlphaDiscoveryStatus.APPROVED_TO_RUN and multiple[
        "binding_method"
    ] == "UNRESOLVED_PENDING_STATISTICAL_DESIGN":
        raise AlphaDiscoveryConfigError(
            "AR-0003 cannot be approved before a binding multiple-testing method is frozen."
        )

    secondary = _mapping(cfg["secondary_lightgbm"], field="secondary_lightgbm")
    expected_secondary = {
        "enabled": False,
        "role": "OPTIONAL_DISCOVERY_ONLY",
        "executor": "MultiAssetSearchExecutor",
        "model_kind": "lightgbm_regressor",
        "preprocessing": "TRAIN_ONLY",
        "predictions": "TRUE_OOS_SCREENING_ONLY",
        "replaces_primary_test": False,
        "separate_search_breadth_required": True,
        "feature_columns": [
            "log_return_16",
            "log_return_32",
            "log_return_64",
            "path_efficiency_16",
            "path_efficiency_32",
            "path_efficiency_48",
            "realized_volatility_16",
            "realized_volatility_32",
            "realized_volatility_64",
            "realized_volatility_192",
            "volatility_ratio_32_192",
            "cross_sectional_rank_features",
        ],
    }
    if secondary != expected_secondary:
        raise AlphaDiscoveryConfigError("AR-0003 secondary model boundary drifted.")

    _require_exact(
        cfg["cost_policy"],
        {
            "base": "OBSERVED_BID_ASK_ONLY_WHERE_CANONICALLY_SUPPORTED",
            "stress_multipliers": [1.0, 1.25, 1.5],
            "stress_status": "BLOCKED_PENDING_CANONICAL_PANEL_COST_MAPPING",
            "unsupported_synthetic_costs": "FORBIDDEN",
            "turnover_diagnostic": (
                "ONLY_IF_SUPPORTED_NO_PORTFOLIO_INTERPRETATION"
            ),
        },
        field="cost_policy",
    )
    _require_exact(
        cfg["resource_policy"],
        {
            "preflight_required": True,
            "max_assets": 100,
            "max_rows": 1_000_000,
            "max_deterministic_variants": 12,
            "max_secondary_trials": 32,
            "estimate_status": "BLOCKED_UNTIL_DATASET_AND_UNIVERSE_ARE_BOUND",
            "estimated_primary_model_fits": 0,
            "estimated_secondary_model_fits": None,
        },
        field="resource_policy",
    )

    target = _mapping(cfg["target"], field="target")
    costs = _mapping(cfg["cost_policy"], field="cost_policy")
    if status is AlphaDiscoveryStatus.APPROVED_TO_RUN and (
        target["panel_mapping_status"] != "READY"
        or costs["stress_status"]
        == "BLOCKED_PENDING_CANONICAL_PANEL_COST_MAPPING"
    ):
        raise AlphaDiscoveryConfigError(
            "AR-0003 cannot be approved before executable target/cost mapping is READY."
        )

    runtime = _mapping(cfg["runtime"], field="runtime")
    expected_runtime_keys = {
        "perform_alpha_calculation",
        "run_backtests",
        "access_validation",
        "access_historical_pseudo_oos",
        "access_prospective_final",
        "paper_demo_live_execution",
        "construct_portfolio",
        "auto_promote_candidate",
    }
    _exact_keys(runtime, expected_runtime_keys, field="runtime")
    for name, value in runtime.items():
        _bool(value, field=f"runtime.{name}")
    forbidden = expected_runtime_keys.difference({"perform_alpha_calculation"})
    if any(runtime[name] for name in forbidden):
        raise AlphaDiscoveryConfigError(
            "AR-0003 cannot enable backtest, held-out access, execution, portfolio, or promotion."
        )
    if status is AlphaDiscoveryStatus.SPECIFICATION_ONLY and runtime[
        "perform_alpha_calculation"
    ]:
        raise AlphaDiscoveryConfigError(
            "AR-0003 SPECIFICATION_ONLY cannot calculate alpha."
        )
    if status is AlphaDiscoveryStatus.APPROVED_TO_RUN and not runtime[
        "perform_alpha_calculation"
    ]:
        raise AlphaDiscoveryConfigError(
            "AR-0003 APPROVED_TO_RUN requires perform_alpha_calculation=true."
        )


def validate_alpha_discovery_v3_config(cfg: dict[str, Any]) -> None:
    """Validate the frozen AR-0003 specification and fail closed on readiness."""

    if not isinstance(cfg, dict):
        raise AlphaDiscoveryConfigError("AR-0003 configuration must be a mapping.")
    _exact_keys(cfg, _TOP_LEVEL_KEYS, field="AR-0003 configuration")
    if cfg["schema_version"] != 4:
        raise AlphaDiscoveryConfigError("AR-0003 schema_version must be 4.")
    if cfg["pipeline"] != {
        "kind": "alpha_discovery_v3",
        "stage": "CROSS_SECTIONAL_DISCOVERY",
    }:
        raise AlphaDiscoveryConfigError("AR-0003 pipeline selector drifted.")
    if cfg["research_id"] != "AR-0003":
        raise AlphaDiscoveryConfigError("research_id must be AR-0003.")
    if cfg["title"] != "Multi-Horizon Trend Quality x Volatility Regime":
        raise AlphaDiscoveryConfigError("AR-0003 title drifted.")
    status = _validate_approval(cfg)
    _validate_asset_and_dataset_contracts(cfg, status=status)
    _validate_scientific_core(cfg)
    _validate_search_and_safety(cfg, status=status)

    gates = _mapping(cfg["promotion_gates"], field="promotion_gates")
    expected_gates = {
        "specification_complete",
        "canonical_universe_bound",
        "panel_dataset_validated",
        "leakage_and_timing",
        "resource_preflight",
        "approval_hash_bound",
        "execution_cost_mapping",
        "multiple_testing",
        "canonical_validation",
    }
    if set(gates) != expected_gates or any(
        value != "NOT_EVALUATED" for value in gates.values()
    ):
        raise AlphaDiscoveryConfigError(
            "AR-0003 promotion gates must remain unevaluated in the specification."
        )
    artifacts = _mapping(cfg["artifacts"], field="artifacts")
    planned_artifacts = [
        "run_manifest.json",
        "contracts/resolved_specification.yaml",
        "datasets/panel_dataset_metadata.json",
        "predictions/primary_score_predictions.jsonl",
        "reports/cross_sectional_diagnostics.json",
        "reports/per_asset_diagnostics.json",
        "reports/temporal_stability.json",
        "reports/robustness_family.json",
        "reports/search_breadth.json",
    ]
    if (
        artifacts.get("output_root") != "logs/experiments/alpha_discovery/AR-0003"
        or artifacts.get("layout_version") != 1
        or artifacts.get("write_mode") != "IMMUTABLE_RUN_DIRECTORY"
        or artifacts.get("planned") != planned_artifacts
    ):
        raise AlphaDiscoveryConfigError("AR-0003 artifact contract drifted.")

    blockers = cfg["blockers"]
    if not isinstance(blockers, list) or any(
        not isinstance(value, str) or not value.strip() for value in blockers
    ):
        raise AlphaDiscoveryConfigError("AR-0003 blockers must be non-empty strings.")
    if status is AlphaDiscoveryStatus.SPECIFICATION_ONLY and not blockers:
        raise AlphaDiscoveryConfigError("AR-0003 SPECIFICATION_ONLY must state blockers.")
    if status is AlphaDiscoveryStatus.APPROVED_TO_RUN and blockers:
        raise AlphaDiscoveryConfigError("Approved AR-0003 cannot retain blockers.")

    declared_hash = _sha256(cfg["specification_hash"], field="specification_hash")
    computed_hash = compute_alpha_specification_hash(cfg)
    if declared_hash != computed_hash:
        raise AlphaDiscoveryConfigError(
            f"specification_hash mismatch: declared={declared_hash}, computed={computed_hash}."
        )
    if status is AlphaDiscoveryStatus.APPROVED_TO_RUN:
        approved_hash = _sha256(
            cfg["approval"]["approved_specification_hash"],
            field="approval.approved_specification_hash",
        )
        if approved_hash != computed_hash:
            raise AlphaDiscoveryConfigError(
                "AR-0003 approval is bound to a different specification hash."
            )


__all__ = [
    "AR0003_MOMENTUM_COLUMNS",
    "AR0003_PATH_EFFICIENCY_COLUMNS",
    "AR0003_PRIMARY_HORIZON",
    "AR0003_ROBUSTNESS_VARIANTS",
    "validate_alpha_discovery_v3_config",
]
