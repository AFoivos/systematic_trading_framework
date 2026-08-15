"""Optional PyBroker research adapter; imports remain dependency-safe."""

from .adapter import (
    PyBrokerLoader,
    PyBrokerSearchExecutor,
    SCREENING_METRIC_GROUPS,
    pybroker_runtime_provenance,
)
from .contracts import (
    PYBROKER_CAPABILITIES,
    PyBrokerBackendError,
    PyBrokerCostMapping,
    PyBrokerFoldPolicy,
    PyBrokerInputError,
    PyBrokerParameterMapping,
    PyBrokerPreprocessingPolicy,
    PyBrokerResearchData,
    PyBrokerResourceLimitError,
    PyBrokerResourcePolicy,
    PyBrokerRuntimeError,
    PyBrokerSignalPolicy,
    PyBrokerTimingPolicy,
    PyBrokerUnsupportedSemanticsError,
)
from .optional_dependency import (
    PYBROKER_DISTRIBUTION,
    PYBROKER_IMPORT_NAME,
    PYBROKER_PIN,
    PyBrokerDependencyError,
    load_pybroker,
    pybroker_version,
)

__all__ = [
    "PYBROKER_CAPABILITIES",
    "PYBROKER_DISTRIBUTION",
    "PYBROKER_IMPORT_NAME",
    "PYBROKER_PIN",
    "PyBrokerBackendError",
    "PyBrokerCostMapping",
    "PyBrokerDependencyError",
    "PyBrokerFoldPolicy",
    "PyBrokerInputError",
    "PyBrokerLoader",
    "PyBrokerParameterMapping",
    "PyBrokerPreprocessingPolicy",
    "PyBrokerResearchData",
    "PyBrokerResourceLimitError",
    "PyBrokerResourcePolicy",
    "PyBrokerRuntimeError",
    "PyBrokerSearchExecutor",
    "PyBrokerSignalPolicy",
    "PyBrokerTimingPolicy",
    "PyBrokerUnsupportedSemanticsError",
    "SCREENING_METRIC_GROUPS",
    "load_pybroker",
    "pybroker_runtime_provenance",
    "pybroker_version",
]
