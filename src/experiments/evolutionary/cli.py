from __future__ import annotations

"""Command-line entrypoint for validation and evolutionary search execution."""

import argparse
from pathlib import Path
from typing import Sequence

from src.experiments.evolutionary.runner import (
    run_evolutionary_search,
    validate_evolutionary_spec,
)


def _print_validation_summary(spec_path: str | Path) -> None:
    spec, _, seeds = validate_evolutionary_spec(spec_path)
    print("Evolutionary spec validation passed")
    print(f"Search: {spec.search.name}")
    print(f"Family: {spec.search.family}")
    print(f"Backend: {spec.search.backend}")
    print(f"Decoder: {spec.genome.decoder} v{spec.genome.decoder_version}")
    print(f"Genes: {len(spec.genome.genes)}")
    print(f"Seed candidates: {len(seeds)}")
    print(f"Base experiment: {spec.base_config_path}")
    print("No experiment or evolutionary search was executed.")


def _print_study_summary(study: object) -> None:
    print("Evolutionary search completed")
    print(f"Study: {getattr(study, 'study_name', 'n/a')}")
    print(f"Trials: {len(list(getattr(study, 'trials', []) or []))}")
    try:
        best = getattr(study, "best_trial")
    except Exception:
        best = None
    if best is not None:
        print(f"Best trial: {getattr(best, 'number', 'n/a')}")
        print(f"Best fitness: {getattr(best, 'value', 'n/a')}")
        print(f"Candidate hash: {dict(getattr(best, 'user_attrs', {}) or {}).get('candidate_hash', 'n/a')}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate or run a repository evolutionary-search YAML spec."
    )
    parser.add_argument("--spec", required=True, help="Path to an evolutionary YAML spec.")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate schema, base config, genes, decoder, and seeds without evaluating candidates.",
    )
    args = parser.parse_args(argv)
    if args.validate_only:
        _print_validation_summary(args.spec)
        return 0
    study = run_evolutionary_search(args.spec)
    _print_study_summary(study)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
