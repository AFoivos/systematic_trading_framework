from __future__ import annotations

"""Structured, family-specific genome decoders for full experiment configs."""

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from src.experiments.evolutionary.contracts import (
    decoder_contract_hash as compute_decoder_contract_hash,
    search_contract_hash as compute_search_contract_hash,
)
from src.experiments.evolutionary.genome import candidate_hash, validate_genome
from src.experiments.evolutionary.schemas import EvolutionarySpec
from src.features.registry import FEATURE_KINDS
from src.signals.registry import SIGNAL_KINDS
from src.utils.config_validation import validate_resolved_config
from src.utils.run_metadata import compute_config_hash


_DISABLED = "disabled"

_MATB_BASELINE_SIGNAL = {
    "kind": "matb_candidate",
    "params": {
        "candidate_col": "matb_candidate",
        "side_col": "matb_side",
        "mode": "long_short",
        "signal_col": "signal_side",
    },
}
_MATB_HIGH_VOL_STEP = {
    "step": "volatility_regime",
    "params": {
        "vol_col": "matb_vol_short",
        "regime_window": 2880,
        "method": "percentile",
        "lower_quantile": 0.33,
        "upper_quantile": 0.67,
        "output_col": "matb_volatility_regime",
    },
}
_MATB_HIGH_VOL_SIGNAL = {
    "kind": "regime_filtered",
    "params": {
        "base_signal_col": "matb_side",
        "regime_col": "matb_volatility_regime",
        "active_value": 2.0,
        "signal_col": "signal_side",
    },
}


@dataclass(frozen=True)
class DecodedCandidate:
    config: dict[str, Any]
    genome: dict[str, Any]
    candidate_hash: str
    base_config_hash: str
    decoded_config_hash: str
    decoder_contract_hash: str
    search_contract_hash: str
    decoder: str
    decoder_version: int
    seed: int
    generation: int
    parent_ids: tuple[int, ...]
    context: dict[str, Any]

    def provenance(self) -> dict[str, Any]:
        return {
            "base_config_hash": self.base_config_hash,
            "candidate_hash": self.candidate_hash,
            "decoded_config_hash": self.decoded_config_hash,
            "decoder_contract_hash": self.decoder_contract_hash,
            "decoder": self.decoder,
            "decoder_version": self.decoder_version,
            "generation": self.generation,
            "genome": dict(self.genome),
            "parent_ids": list(self.parent_ids),
            "search_contract_hash": self.search_contract_hash,
            "seed": self.seed,
        }


def _require_mapping(config: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = config.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"Base experiment requires mapping {key!r}.")
    return dict(value)


def _require_child_mapping(
    parent: Mapping[str, Any], key: str, *, field: str
) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"Base experiment requires mapping {field!r}.")
    return dict(value)


def _candidate_metadata(
    cfg: dict[str, Any],
    *,
    candidate_id: str,
    base_config_hash: str,
    decoded_config_hash: str,
    decoder_contract_hash: str,
    search_contract_hash: str,
    spec: EvolutionarySpec,
    genome: Mapping[str, Any],
    generation: int,
    parent_ids: Sequence[int],
) -> None:
    metadata = dict(cfg.get("research_metadata", {}) or {})
    metadata["evolutionary_candidate"] = {
        "base_config_hash": base_config_hash,
        "candidate_hash": candidate_id,
        "decoded_config_hash": decoded_config_hash,
        "decoder_contract_hash": decoder_contract_hash,
        "decoder": spec.genome.decoder,
        "decoder_version": spec.genome.decoder_version,
        "generation": int(generation),
        "genome": dict(genome),
        "parent_ids": [int(value) for value in parent_ids],
        "search_name": spec.search.name,
        "search_contract_hash": search_contract_hash,
        "seed": int(spec.search.seed),
    }
    cfg["research_metadata"] = metadata


def _configure_candidate_logging(
    cfg: dict[str, Any],
    *,
    spec: EvolutionarySpec,
    candidate_id: str,
) -> None:
    logging_cfg = dict(cfg.get("logging", {}) or {})
    logging_cfg["enabled"] = bool(spec.execution.logging_enabled)
    if spec.execution.logging_enabled:
        logging_cfg["run_name"] = f"{spec.search.name}_{candidate_id[:12]}"
    cfg["logging"] = logging_cfg


def _decode_ethusd(
    base_config: Mapping[str, Any],
    genome: Mapping[str, Any],
    spec: EvolutionarySpec,
) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg = deepcopy(dict(base_config))
    params = spec.genome.decoder_params
    families = {
        str(name): [str(column) for column in columns]
        for name, columns in dict(params["feature_families"]).items()
    }
    family_genes = {
        str(name): str(gene) for name, gene in dict(params["family_genes"]).items()
    }
    model = _require_mapping(cfg, "model")
    baseline_features = list(model.get("feature_cols", []) or [])
    if not baseline_features or any(not isinstance(column, str) for column in baseline_features):
        raise ValueError("ETHUSD decoder requires a non-empty base model.feature_cols list[str].")
    if len(set(baseline_features)) != len(baseline_features):
        raise ValueError("Base ETHUSD model.feature_cols contains duplicates.")
    grouped_features = [column for columns in families.values() for column in columns]
    if len(set(grouped_features)) != len(grouped_features):
        raise ValueError("ETHUSD feature-family definitions contain duplicate columns.")
    if set(grouped_features) != set(baseline_features):
        missing = sorted(set(baseline_features) - set(grouped_features))
        unknown = sorted(set(grouped_features) - set(baseline_features))
        raise ValueError(
            "ETHUSD feature families must exactly partition base model.feature_cols; "
            f"missing={missing}, unknown={unknown}."
        )

    enabled_families = [
        family for family in families if bool(genome[family_genes[family]])
    ]
    selected_columns = {
        column for family in enabled_families for column in families[family]
    }
    decoded_features = [column for column in baseline_features if column in selected_columns]
    if not decoded_features:
        raise ValueError("ETHUSD decoder cannot produce an empty feature subset.")
    if len(set(decoded_features)) != len(decoded_features):
        raise ValueError("ETHUSD decoder produced duplicate feature columns.")
    model["feature_cols"] = decoded_features
    cfg["model"] = model

    signals = _require_mapping(cfg, "signals")
    signal_params = _require_child_mapping(signals, "params", field="signals.params")
    if signals.get("kind") != "forecast_threshold":
        raise ValueError("ETHUSD feature/gate v1 requires signals.kind='forecast_threshold'.")
    if signal_params.get("mode") != "long_short":
        raise ValueError("ETHUSD feature/gate v1 requires signals.params.mode='long_short'.")
    threshold_genes = dict(params["threshold_genes"])
    signal_params["upper"] = float(genome[str(threshold_genes["upper"])])
    signal_params["lower"] = float(genome[str(threshold_genes["lower"])])

    gate_genes = dict(params["gate_genes"])
    gate_definitions = (
        ("atr_lower", "atr_pct_rank_192", "ge"),
        ("atr_upper", "atr_pct_rank_192", "le"),
        ("range_to_atr_lower", "range_to_atr", "ge"),
        (
            "bollinger_bandwidth_rank_lower",
            "bollinger_bandwidth_rank_192",
            "ge",
        ),
    )
    activation_filters: list[dict[str, Any]] = []
    enabled_gates: list[str] = []
    for gate_name, column, operator in gate_definitions:
        raw_value = genome[str(gate_genes[gate_name])]
        if raw_value == _DISABLED:
            continue
        activation_filters.append(
            {"col": column, "op": operator, "value": float(raw_value)}
        )
        enabled_gates.append(gate_name)
    signal_params["activation_filters"] = activation_filters
    signals["params"] = signal_params
    cfg["signals"] = signals
    context = {
        "baseline_feature_count": len(baseline_features),
        "complexity": float(len(decoded_features) / len(baseline_features)),
        "enabled_feature_families": enabled_families,
        "enabled_gates": enabled_gates,
        "feature_count": len(decoded_features),
        "family_count": len(enabled_families),
    }
    return cfg, context


def _is_matb_high_vol_step(raw_step: Any) -> bool:
    if not isinstance(raw_step, Mapping) or raw_step.get("step") != "volatility_regime":
        return False
    params = dict(raw_step.get("params", {}) or {})
    return params.get("output_col") == "matb_volatility_regime"


def _filter_group_mapping(
    mapping: Mapping[str, Any], selected_groups: set[str]
) -> dict[str, Any]:
    return {
        str(group): deepcopy(value)
        for group, value in mapping.items()
        if str(group) in selected_groups
    }


def _decode_matb(
    base_config: Mapping[str, Any],
    genome: Mapping[str, Any],
    spec: EvolutionarySpec,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if "volatility_regime" not in FEATURE_KINDS:
        raise ValueError("MATB decoder requires registered feature 'volatility_regime'.")
    for signal_name in ("matb_candidate", "regime_filtered"):
        if signal_name not in SIGNAL_KINDS:
            raise ValueError(f"MATB decoder requires registered signal {signal_name!r}.")

    cfg = deepcopy(dict(base_config))
    params = spec.genome.decoder_params
    asset_genes = {
        str(asset): str(gene) for asset, gene in dict(params["asset_genes"]).items()
    }
    declared_groups = {
        str(asset): str(group) for asset, group in dict(params["asset_groups"]).items()
    }
    data = _require_mapping(cfg, "data")
    baseline_symbols = [str(symbol) for symbol in list(data.get("symbols", []) or [])]
    if baseline_symbols != list(asset_genes):
        raise ValueError(
            "MATB decoder asset_genes must follow and exactly match base data.symbols order."
        )
    selected_assets = [
        asset for asset in baseline_symbols if bool(genome[asset_genes[asset]])
    ]
    if not selected_assets:
        raise ValueError("MATB decoder cannot produce an empty asset universe.")
    selected_groups = {declared_groups[asset] for asset in selected_assets}

    storage = _require_child_mapping(data, "storage", field="data.storage")
    baseline_load_paths = _require_child_mapping(
        storage, "load_paths", field="data.storage.load_paths"
    )
    missing_load_paths = [asset for asset in baseline_symbols if asset not in baseline_load_paths]
    if missing_load_paths:
        raise ValueError(f"Base MATB load_paths is missing assets: {missing_load_paths}.")
    data["symbols"] = selected_assets
    storage["load_paths"] = {
        asset: baseline_load_paths[asset] for asset in selected_assets
    }
    data["storage"] = storage
    cfg["data"] = data

    backtest = _require_mapping(cfg, "backtest")
    baseline_asset_params = _require_child_mapping(
        backtest, "asset_params", field="backtest.asset_params"
    )
    missing_asset_params = [asset for asset in baseline_symbols if asset not in baseline_asset_params]
    if missing_asset_params:
        raise ValueError(f"Base MATB backtest.asset_params is missing assets: {missing_asset_params}.")
    backtest["asset_params"] = {
        asset: deepcopy(baseline_asset_params[asset]) for asset in selected_assets
    }
    cfg["backtest"] = backtest

    portfolio = _require_mapping(cfg, "portfolio")
    baseline_asset_groups = _require_child_mapping(
        portfolio, "asset_groups", field="portfolio.asset_groups"
    )
    if any(baseline_asset_groups.get(asset) != declared_groups[asset] for asset in baseline_symbols):
        raise ValueError("MATB decoder asset_groups do not match base portfolio.asset_groups.")
    portfolio["asset_groups"] = {
        asset: declared_groups[asset] for asset in selected_assets
    }
    portfolio_constraints = _require_child_mapping(
        portfolio, "constraints", field="portfolio.constraints"
    )
    group_exposure = _require_child_mapping(
        portfolio_constraints,
        "group_max_exposure",
        field="portfolio.constraints.group_max_exposure",
    )
    portfolio_constraints["group_max_exposure"] = _filter_group_mapping(
        group_exposure, selected_groups
    )
    portfolio["constraints"] = portfolio_constraints
    cfg["portfolio"] = portfolio

    risk = _require_mapping(cfg, "risk")
    portfolio_guard = _require_child_mapping(
        risk, "portfolio_guard", field="risk.portfolio_guard"
    )
    group_open_trades = _require_child_mapping(
        portfolio_guard,
        "group_max_open_trades",
        field="risk.portfolio_guard.group_max_open_trades",
    )
    portfolio_guard["group_max_open_trades"] = _filter_group_mapping(
        group_open_trades, selected_groups
    )
    risk["portfolio_guard"] = portfolio_guard
    cfg["risk"] = risk

    module_enabled = bool(genome[str(params["module_gene"])])
    features = [
        deepcopy(dict(step))
        for step in list(cfg.get("features", []) or [])
        if not _is_matb_high_vol_step(step)
    ]
    if module_enabled:
        matb_positions = [
            index
            for index, step in enumerate(features)
            if step.get("step") == "multi_asset_trend_breakout"
        ]
        if len(matb_positions) != 1:
            raise ValueError("MATB decoder requires exactly one multi_asset_trend_breakout step.")
        features.insert(matb_positions[0] + 1, deepcopy(_MATB_HIGH_VOL_STEP))
        cfg["signals"] = deepcopy(_MATB_HIGH_VOL_SIGNAL)
    else:
        cfg["signals"] = deepcopy(_MATB_BASELINE_SIGNAL)
    cfg["features"] = features

    group_counts = {
        group: sum(declared_groups[asset] == group for asset in selected_assets)
        for group in sorted(selected_groups)
    }
    maximum_group_asset_share = max(group_counts.values()) / len(selected_assets)
    context = {
        "asset_count": len(selected_assets),
        "baseline_asset_count": len(baseline_symbols),
        "group_count": len(selected_groups),
        "baseline_group_count": len(set(declared_groups.values())),
        "maximum_group_asset_share": float(maximum_group_asset_share),
        "module_count": int(module_enabled),
        "selected_assets": selected_assets,
        "selected_groups": sorted(selected_groups),
        "use_high_volatility_regime_filter": module_enabled,
    }
    return cfg, context


def decode_candidate(
    base_config: Mapping[str, Any],
    genome: Mapping[str, Any],
    spec: EvolutionarySpec,
    *,
    generation: int = 0,
    parent_ids: Sequence[int] = (),
) -> DecodedCandidate:
    """Decode one genome into an independently validated experiment config."""
    canonical = validate_genome(genome, spec.genome)
    base_config_hash, _ = compute_config_hash(base_config)
    resolved_decoder_contract_hash = compute_decoder_contract_hash(spec)
    resolved_search_contract_hash = compute_search_contract_hash(
        spec,
        base_config_hash=base_config_hash,
        resolved_decoder_contract_hash=resolved_decoder_contract_hash,
    )
    if spec.genome.decoder == "ethusd_feature_gate_v1":
        cfg, context = _decode_ethusd(base_config, canonical, spec)
    elif spec.genome.decoder == "matb_asset_module_v1":
        cfg, context = _decode_matb(base_config, canonical, spec)
    else:  # Schema validation should make this unreachable.
        raise ValueError(f"Unsupported decoder: {spec.genome.decoder!r}.")

    validate_genome(canonical, spec.genome, decoded_config=cfg)
    clean_config = validate_resolved_config(deepcopy(cfg))
    decoded_config_hash, _ = compute_config_hash(clean_config)
    identity = candidate_hash(
        canonical,
        base_config_hash=base_config_hash,
        decoder_contract_hash=resolved_decoder_contract_hash,
        decoded_config_hash=decoded_config_hash,
    )
    candidate_config = deepcopy(clean_config)
    _candidate_metadata(
        candidate_config,
        candidate_id=identity,
        base_config_hash=base_config_hash,
        decoded_config_hash=decoded_config_hash,
        decoder_contract_hash=resolved_decoder_contract_hash,
        search_contract_hash=resolved_search_contract_hash,
        spec=spec,
        genome=canonical,
        generation=generation,
        parent_ids=parent_ids,
    )
    _configure_candidate_logging(candidate_config, spec=spec, candidate_id=identity)
    validated = validate_resolved_config(candidate_config)
    return DecodedCandidate(
        config=validated,
        genome=canonical,
        candidate_hash=identity,
        base_config_hash=base_config_hash,
        decoded_config_hash=decoded_config_hash,
        decoder_contract_hash=resolved_decoder_contract_hash,
        search_contract_hash=resolved_search_contract_hash,
        decoder=spec.genome.decoder,
        decoder_version=spec.genome.decoder_version,
        seed=spec.search.seed,
        generation=int(generation),
        parent_ids=tuple(int(value) for value in parent_ids),
        context=context,
    )


__all__ = ["DecodedCandidate", "decode_candidate"]
