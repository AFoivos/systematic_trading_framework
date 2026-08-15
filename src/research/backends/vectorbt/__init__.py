"""Optional VectorBT research adapter; importing this package is dependency-safe."""

from .adapter import (
    FrameworkSignalBuilder,
    PreparedVectorBTSignals,
    SCREENING_METRIC_DEFINITIONS,
    VectorBTSearchExecutor,
    prepare_vectorbt_signals,
    validate_vectorbt_market_data,
    vectorbt_runtime_provenance,
)
from .contracts import (
    VECTORBT_CAPABILITIES,
    VectorBTBackendError,
    VectorBTCostMapping,
    VectorBTInputError,
    VectorBTResourceLimitError,
    VectorBTResourcePolicy,
    VectorBTRuntimeError,
    VectorBTSignalSet,
    VectorBTTimingPolicy,
    VectorBTUnsupportedSemanticsError,
)
from .optional_dependency import (
    VECTORBT_DISTRIBUTION,
    VECTORBT_PIN,
    VectorBTDependencyError,
    load_vectorbt,
    vectorbt_version,
)

__all__ = [
    "FrameworkSignalBuilder",
    "PreparedVectorBTSignals",
    "SCREENING_METRIC_DEFINITIONS",
    "VECTORBT_CAPABILITIES",
    "VECTORBT_DISTRIBUTION",
    "VECTORBT_PIN",
    "VectorBTBackendError",
    "VectorBTCostMapping",
    "VectorBTDependencyError",
    "VectorBTInputError",
    "VectorBTResourceLimitError",
    "VectorBTResourcePolicy",
    "VectorBTRuntimeError",
    "VectorBTSearchExecutor",
    "VectorBTSignalSet",
    "VectorBTTimingPolicy",
    "VectorBTUnsupportedSemanticsError",
    "load_vectorbt",
    "prepare_vectorbt_signals",
    "validate_vectorbt_market_data",
    "vectorbt_runtime_provenance",
    "vectorbt_version",
]
