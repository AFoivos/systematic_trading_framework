from __future__ import annotations

import ast
import builtins
import importlib
import json
from pathlib import Path
import sys

import pytest

from src.pipelines.canonical_pipeline import run_canonical_pipeline
from src.pipelines.registry import get_pipeline_fn
from src.research import (
    CandidateStatus,
    EvidenceReference,
    EvidenceStage,
    ResearchCandidate,
    ResearchRequest,
    ResearchResult,
)
from src.research.backends.base import ResearchBackend
from src.research.contracts import ResearchContractError
from src.src_data.research_roles import EvidenceRole


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_canonical_pipeline_contract_is_unchanged() -> None:
    assert get_pipeline_fn("canonical_experiment") is run_canonical_pipeline


def test_research_package_imports_without_optional_backends(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocked = {"vectorbt", "pybroker", "qlib", "skfolio", "nautilus_trader"}
    original_import = builtins.__import__

    def guarded_import(name: str, *args: object, **kwargs: object) -> object:
        if name.split(".", maxsplit=1)[0] in blocked:
            raise AssertionError(f"Phase 0 imported optional backend {name!r}")
        return original_import(name, *args, **kwargs)

    for name in tuple(sys.modules):
        if name.split(".", maxsplit=1)[0] in blocked or name == "src.research" or name.startswith(
            "src.research."
        ):
            monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setattr(builtins, "__import__", guarded_import)

    importlib.import_module("src.research.backends.base")


def test_evidence_stages_reuse_immutable_existing_roles() -> None:
    development = EvidenceReference(
        stage=EvidenceStage.DEVELOPMENT,
        evidence_role=EvidenceRole.DISCOVERY,
        artifact_reference="artifacts/dev/manifest.json",
        sample_reference="ETHUSD-30m-development-v1",
    )
    assert development.evidence_role is EvidenceRole.DISCOVERY

    with pytest.raises(
        ResearchContractError,
        match="requires role 'PROSPECTIVE_FINAL'",
    ):
        EvidenceReference(
            stage=EvidenceStage.FINAL_HOLDOUT,
            evidence_role=EvidenceRole.HISTORICAL_PSEUDO_OOS,
            artifact_reference="artifacts/locked/manifest.json",
            sample_reference="inspected-history",
        )


def test_backend_contract_exchanges_only_framework_owned_values() -> None:
    request = ResearchRequest(
        request_id="screen-001",
        config_reference="config/research/screen-001.yaml#sha256:abc",
        assets=("ETHUSD",),
        timeframe="30m",
        parameters={"grid": {"lookback": [12, 24]}},
    )
    candidate = ResearchCandidate(
        candidate_id="candidate-001",
        strategy_name="trend-screen",
        backend="dummy",
        config_reference=request.config_reference,
        assets=request.assets,
        timeframe=request.timeframe,
        sample_reference="snapshot:development-v1",
        metrics={"conventional_sharpe": 0.7, "trade_count": 42},
        cost_assumptions={"spread_bps": 1.5, "commission_bps": 0.5},
        search_metadata={"parameter_set": 3},
        status=CandidateStatus.SCREENED,
    )

    class DummyBackend:
        name = "dummy"
        capabilities = frozenset({"vectorized_screening"})

        def run(self, backend_request: ResearchRequest) -> ResearchResult:
            return ResearchResult(
                request_id=backend_request.request_id,
                backend=self.name,
                candidates=(candidate,),
                artifact_references=("artifacts/dummy/screen-001.json",),
            )

    backend: ResearchBackend = DummyBackend()
    result = backend.run(request)

    assert result.candidates == (candidate,)
    assert result.candidates[0].status is CandidateStatus.SCREENED
    serialized = json.loads(json.dumps(result.to_dict(), allow_nan=False))
    assert serialized["candidates"][0]["candidate_id"] == "candidate-001"


def test_candidate_rejects_non_serializable_backend_objects_and_non_finite_metrics() -> None:
    common = {
        "candidate_id": "candidate-002",
        "strategy_name": "portable-contract",
        "backend": "dummy",
        "config_reference": "config.yaml#sha256:def",
        "assets": ("ETHUSD",),
        "timeframe": "30m",
        "sample_reference": "snapshot:dev-v2",
    }
    with pytest.raises(ResearchContractError, match="finite number"):
        ResearchCandidate(**common, metrics={"sharpe": float("nan")})
    with pytest.raises(ResearchContractError, match="JSON-compatible"):
        ResearchCandidate(**common, search_metadata={"native_result": object()})


def _imported_modules(package: str) -> set[str]:
    modules: set[str] = set()
    for path in sorted((REPO_ROOT / "src" / package).rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
    return modules


@pytest.mark.parametrize(
    ("package", "forbidden_prefixes"),
    [
        ("features", ("src.experiments",)),
        ("targets", ("src.execution",)),
        ("models", ("src.experiments.runner",)),
        ("signals", ("src.src_data.loaders",)),
        ("portfolio", ("src.execution",)),
        ("research", ("src.experiments", "src.execution")),
    ],
)
def test_important_dependency_boundaries(
    package: str,
    forbidden_prefixes: tuple[str, ...],
) -> None:
    violations = sorted(
        module
        for module in _imported_modules(package)
        if any(
            module == prefix or module.startswith(f"{prefix}.")
            for prefix in forbidden_prefixes
        )
    )
    assert not violations, f"src/{package} crosses an Architecture V2 boundary: {violations}"


def test_direct_vectorbt_imports_are_confined_to_the_approved_adapter() -> None:
    approved_root = REPO_ROOT / "src" / "research" / "backends" / "vectorbt"
    violations: list[str] = []
    for path in sorted((REPO_ROOT / "src").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports_vectorbt = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports_vectorbt = imports_vectorbt or any(
                    alias.name.split(".", maxsplit=1)[0] == "vectorbt"
                    for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports_vectorbt = imports_vectorbt or (
                    node.module.split(".", maxsplit=1)[0] == "vectorbt"
                )
        if imports_vectorbt and not path.is_relative_to(approved_root):
            violations.append(str(path.relative_to(REPO_ROOT)))
    assert not violations, (
        "Direct VectorBT imports escaped the approved research-adapter boundary: "
        f"{violations}"
    )


def test_direct_pybroker_imports_are_confined_to_the_approved_adapter() -> None:
    approved_root = REPO_ROOT / "src" / "research" / "backends" / "pybroker"
    violations: list[str] = []
    for path in sorted((REPO_ROOT / "src").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports_pybroker = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports_pybroker = imports_pybroker or any(
                    alias.name.split(".", maxsplit=1)[0] == "pybroker"
                    for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports_pybroker = imports_pybroker or (
                    node.module.split(".", maxsplit=1)[0] == "pybroker"
                )
        if imports_pybroker and not path.is_relative_to(approved_root):
            violations.append(str(path.relative_to(REPO_ROOT)))
    assert not violations, (
        "Direct PyBroker imports escaped the approved research-adapter boundary: "
        f"{violations}"
    )
