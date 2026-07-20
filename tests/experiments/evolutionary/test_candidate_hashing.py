from __future__ import annotations

from src.experiments.evolutionary.genome import candidate_hash


def test_candidate_hash_is_independent_of_mapping_insertion_order() -> None:
    left = {"alpha": True, "threshold": 0.5}
    right = {"threshold": 0.5, "alpha": True}

    assert candidate_hash(
        left,
        base_config_hash="base",
        decoder_contract_hash="decoder-contract",
        decoded_config_hash="decoded-config",
    ) == candidate_hash(
        right,
        base_config_hash="base",
        decoder_contract_hash="decoder-contract",
        decoded_config_hash="decoded-config",
    )


def test_candidate_hash_changes_with_genome_or_decoding_contract() -> None:
    baseline = candidate_hash(
        {"alpha": True},
        base_config_hash="base",
        decoder_contract_hash="decoder-contract",
        decoded_config_hash="decoded-config",
    )

    assert baseline != candidate_hash(
        {"alpha": False},
        base_config_hash="base",
        decoder_contract_hash="decoder-contract",
        decoded_config_hash="decoded-config",
    )
    assert baseline != candidate_hash(
        {"alpha": True},
        base_config_hash="base",
        decoder_contract_hash="different-decoder-contract",
        decoded_config_hash="decoded-config",
    )
    assert baseline != candidate_hash(
        {"alpha": True},
        base_config_hash="different-base",
        decoder_contract_hash="decoder-contract",
        decoded_config_hash="decoded-config",
    )
    assert baseline != candidate_hash(
        {"alpha": True},
        base_config_hash="base",
        decoder_contract_hash="decoder-contract",
        decoded_config_hash="different-decoded-config",
    )
