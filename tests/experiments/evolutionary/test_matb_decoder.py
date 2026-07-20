from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from src.experiments.evolutionary.decoders import decode_candidate
from src.experiments.evolutionary.genome import GenomeValidationError
from src.experiments.evolutionary.schemas import load_evolutionary_spec
from src.utils.config import load_experiment_config


SPEC_PATH = Path("config/evolutionary/matb/ga_matb_asset_module_v1.yaml")


def _inputs():
    spec = load_evolutionary_spec(SPEC_PATH)
    base = load_experiment_config(spec.base_config_path)
    seeds = {seed.name: dict(seed.genome) for seed in spec.genome.seed_candidates}
    return spec, base, seeds


def test_selected_assets_synchronize_all_required_config_branches() -> None:
    spec, base, seeds = _inputs()
    decoded = decode_candidate(base, seeds["diversified_non_crypto"], spec).config
    expected = ["SPX500", "XAUUSD", "USOIL", "EURUSD"]

    assert decoded["data"]["symbols"] == expected
    assert list(decoded["data"]["storage"]["load_paths"]) == expected
    assert list(decoded["backtest"]["asset_params"]) == expected
    assert list(decoded["portfolio"]["asset_groups"]) == expected


def test_removed_asset_has_no_stale_entries() -> None:
    spec, base, seeds = _inputs()
    decoded = decode_candidate(base, seeds["diversified_non_crypto"], spec).config

    for branch in (
        decoded["data"]["storage"]["load_paths"],
        decoded["backtest"]["asset_params"],
        decoded["portfolio"]["asset_groups"],
    ):
        assert "ETHUSD" not in branch


def test_small_universe_is_rejected_but_four_asset_single_group_is_valid() -> None:
    spec, base, seeds = _inputs()
    small = dict(seeds["full_deterministic_baseline"])
    for name in spec.genome.decoder_params["asset_genes"].values():
        small[name] = False
    small["include_spx500"] = True
    small["include_us100"] = True

    with pytest.raises(GenomeValidationError, match="below minimum"):
        decode_candidate(base, small, spec)

    equity_only = dict(small)
    equity_only["include_ger40"] = True
    equity_only["include_nikkei225"] = True

    decoded = decode_candidate(base, equity_only, spec)

    assert decoded.config["data"]["symbols"] == [
        "SPX500",
        "US100",
        "GER40",
        "NIKKEI225",
    ]


def test_high_volatility_module_is_added_exactly_once() -> None:
    spec, base, seeds = _inputs()
    decoded = decode_candidate(base, seeds["equity_high_vol_exact"], spec).config
    module_steps = [
        step
        for step in decoded["features"]
        if step["step"] == "volatility_regime"
        and step["params"].get("output_col") == "matb_volatility_regime"
    ]

    assert len(module_steps) == 1
    assert decoded["signals"]["kind"] == "regime_filtered"
    assert decoded["signals"]["params"]["active_value"] == 2.0


def test_high_vol_disabled_removes_only_matb_specific_module() -> None:
    spec, base, seeds = _inputs()
    augmented = deepcopy(base)
    augmented["features"].append(
        {
            "step": "volatility_regime",
            "params": {
                "price_col": "close",
                "vol_window": 20,
                "regime_window": 100,
                "method": "ratio",
                "output_col": "unrelated_volatility_regime",
            },
        }
    )

    decoded = decode_candidate(augmented, seeds["full_deterministic_baseline"], spec).config

    output_columns = [
        step["params"].get("output_col")
        for step in decoded["features"]
        if step["step"] == "volatility_regime"
    ]
    assert output_columns == ["unrelated_volatility_regime"]
    assert decoded["signals"]["kind"] == "matb_candidate"


def test_baseline_and_equity_high_vol_seeds_decode_and_base_is_immutable() -> None:
    spec, base, seeds = _inputs()
    before = deepcopy(base)

    baseline = decode_candidate(base, seeds["full_deterministic_baseline"], spec)
    high_vol = decode_candidate(base, seeds["equity_high_vol_exact"], spec)

    assert baseline.config["data"]["symbols"] == base["data"]["symbols"]
    assert high_vol.config["data"]["symbols"] == [
        "SPX500",
        "US100",
        "GER40",
        "NIKKEI225",
    ]
    assert high_vol.context["use_high_volatility_regime_filter"] is True
    assert base == before
