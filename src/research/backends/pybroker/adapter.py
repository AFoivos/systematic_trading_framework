"""Optional PyBroker executor over STF-owned purged walk-forward folds."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
import json
from math import isfinite
from pathlib import Path
import platform
from types import ModuleType
from typing import Any
import warnings

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning

from src.evaluation.time_splits import (
    TimeSplit,
    assert_no_forward_label_leakage,
    build_time_splits,
)
from src.models.classification.base import _apply_fold_feature_preprocessing
from src.models.classification.logistic_regression import (
    create_logistic_regression_estimator,
)
from src.research.contracts import (
    ResearchContractError,
    _freeze_json_mapping,
)
from src.research.discovery.contracts import (
    DiscoverySpecification,
    DiscoveryTrial,
    TrialStatus,
)
from src.research.discovery.service import TrialEvaluator
from src.utils.run_metadata import compute_config_hash

from .contracts import (
    PYBROKER_CAPABILITIES,
    PyBrokerCostMapping,
    PyBrokerFoldPolicy,
    PyBrokerInputError,
    PyBrokerParameterMapping,
    PyBrokerPreprocessingPolicy,
    PyBrokerResearchData,
    PyBrokerResourcePolicy,
    PyBrokerRuntimeError,
    PyBrokerSignalPolicy,
    PyBrokerTimingPolicy,
    PyBrokerUnsupportedSemanticsError,
)
from .diagnostics import (
    aggregate_trading_diagnostics,
    fold_stability_diagnostics,
    fold_trading_diagnostics,
    framework_long_flat_signal,
    predictive_metrics,
    sanitize_metrics,
)
from .optional_dependency import load_pybroker, pybroker_version


PyBrokerLoader = Callable[[], ModuleType]


SCREENING_METRIC_GROUPS: Mapping[str, tuple[str, ...]] = {
    "predictive": (
        "evaluation_rows",
        "positive_rate",
        "accuracy",
        "brier",
        "roc_auc",
        "log_loss",
    ),
    "trading": (
        "total_return",
        "net_return",
        "gross_total_return",
        "total_cost",
        "annualized_return",
        "volatility",
        "sharpe",
        "net_sharpe",
        "max_drawdown",
        "bar_profit_factor",
        "profit_factor",
        "trade_count",
        "turnover",
    ),
}


@dataclass(frozen=True)
class _FoldOutcome:
    split: TimeSplit
    probability: pd.Series
    predictive: Mapping[str, int | float | None]
    trading: Mapping[str, int | float | None]
    trading_ledger: pd.DataFrame
    metadata: Mapping[str, Any]
    provenance: tuple[Mapping[str, Any], ...]


class _InvalidFoldError(PyBrokerInputError):
    """Known fold invalidity that should become an auditable invalid trial."""


def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def pybroker_runtime_provenance() -> dict[str, Any]:
    """Portable runtime versions; never part of candidate identity."""

    return {
        "backend_name": "pybroker",
        "pybroker_distribution": "lib-pybroker",
        "pybroker_version": pybroker_version(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "scikit_learn_version": _package_version("scikit-learn"),
        "numba_version": _package_version("numba"),
        "metric_scope": "discovery_oos_screening_not_canonical_evidence",
    }


def _trial_identity(research_run_id: str, parameters: Mapping[str, Any]) -> str:
    digest, _ = compute_config_hash(
        {
            "research_run_id": research_run_id,
            "parameters": dict(parameters),
        }
    )
    return f"{research_run_id}-pybroker-{digest[:24]}"


def _trial_seed(
    base_seed: int,
    research_run_id: str,
    parameters: Mapping[str, Any],
) -> int:
    digest, _ = compute_config_hash(
        {
            "base_seed": base_seed,
            "research_run_id": research_run_id,
            "parameters": dict(parameters),
        }
    )
    return int(digest[:8], 16) % (2**31 - 1)


def _timestamp(value: object) -> str:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        raise PyBrokerInputError("Prediction provenance timestamps require timezone.")
    return timestamp.isoformat()


def _write_json_once(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        raise PyBrokerRuntimeError(
            f"PyBroker backend artifact already exists: {path}."
        )
    path.write_text(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_jsonl_once(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if path.exists():
        raise PyBrokerRuntimeError(
            f"PyBroker backend artifact already exists: {path}."
        )
    text = "".join(
        json.dumps(
            row,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
        for row in rows
    )
    path.write_text(text, encoding="utf-8")


def _frame_from_values(
    values: pd.DataFrame | np.ndarray,
    *,
    index: pd.Index,
    columns: Sequence[str],
) -> pd.DataFrame:
    if isinstance(values, pd.DataFrame):
        frame = values.copy(deep=False)
        frame.index = index
        frame.columns = list(columns)
        return frame
    array = np.asarray(values, dtype=float)
    return pd.DataFrame(array, index=index, columns=list(columns))


def _predict_positive_probability(
    estimator: object,
    features: pd.DataFrame,
) -> np.ndarray:
    if not hasattr(estimator, "predict_proba"):
        raise PyBrokerRuntimeError(
            "Framework classifier does not expose predict_proba."
        )
    raw = np.asarray(estimator.predict_proba(features), dtype=float)
    classes = np.asarray(getattr(estimator, "classes_", []))
    if raw.ndim != 2 or raw.shape[0] != len(features):
        raise PyBrokerRuntimeError(
            "PyBroker model callback returned an invalid probability shape."
        )
    positive = np.flatnonzero(classes == 1)
    if len(positive) != 1 or raw.shape[1] != len(classes):
        raise PyBrokerRuntimeError(
            "PyBroker model callback cannot identify binary positive-class probability."
        )
    probability = raw[:, int(positive[0])]
    if (
        not np.isfinite(probability).all()
        or bool(((probability < 0.0) | (probability > 1.0)).any())
    ):
        raise PyBrokerRuntimeError(
            "PyBroker model callback produced non-finite or out-of-range probabilities."
        )
    return probability


class PyBrokerSearchExecutor:
    """Finite ML screening executor using STF folds and PyBroker callbacks.

    PyBroker's native equal-window splitter is intentionally not authoritative.
    The executor builds purged/embargoed folds with ``src.evaluation`` and uses
    PyBroker's public ``ModelTrainer`` callback boundary once per fold.  Only
    predictions on the corresponding test indices are stored.
    """

    name = "pybroker"
    backend_name = "pybroker"
    capabilities = PYBROKER_CAPABILITIES

    def __init__(
        self,
        data: PyBrokerResearchData,
        *,
        folds: PyBrokerFoldPolicy,
        signal: PyBrokerSignalPolicy,
        parameter_mapping: PyBrokerParameterMapping | None = None,
        preprocessing: PyBrokerPreprocessingPolicy | None = None,
        timing: PyBrokerTimingPolicy | None = None,
        base_model_parameters: Mapping[str, Any] | None = None,
        periods_per_year: int,
        resources: PyBrokerResourcePolicy | None = None,
        artifact_root: str | Path | None = None,
        allow_approximate_spread: bool = False,
        dependency_loader: PyBrokerLoader = load_pybroker,
    ) -> None:
        if not isinstance(data, PyBrokerResearchData):
            raise PyBrokerInputError("data must be PyBrokerResearchData.")
        if not isinstance(folds, PyBrokerFoldPolicy):
            raise PyBrokerInputError("folds must be PyBrokerFoldPolicy.")
        if not isinstance(signal, PyBrokerSignalPolicy):
            raise PyBrokerInputError("signal must be PyBrokerSignalPolicy.")
        if isinstance(periods_per_year, bool) or not isinstance(
            periods_per_year, int
        ) or periods_per_year < 1:
            raise PyBrokerInputError("periods_per_year must be an integer >= 1.")
        if not isinstance(allow_approximate_spread, bool):
            raise PyBrokerInputError("allow_approximate_spread must be boolean.")
        self.data = data
        self.folds = folds
        self.signal = signal
        self.parameter_mapping = parameter_mapping or PyBrokerParameterMapping()
        self.preprocessing = preprocessing or PyBrokerPreprocessingPolicy()
        self.timing = timing or PyBrokerTimingPolicy()
        self.base_model_parameters = _freeze_json_mapping(
            base_model_parameters or {}, field_name="base_model_parameters"
        )
        self.periods_per_year = periods_per_year
        self.resources = resources or PyBrokerResourcePolicy()
        self.artifact_root = (
            Path(artifact_root) if artifact_root is not None else None
        )
        self.allow_approximate_spread = allow_approximate_spread
        self._dependency_loader = dependency_loader

    @property
    def backend_version(self) -> str:
        return pybroker_version()

    def _validate_specification(
        self,
        specification: DiscoverySpecification,
    ) -> tuple[tuple[TimeSplit, ...], int, int]:
        if specification.search_method != self.name:
            raise ResearchContractError(
                f"PyBroker executor cannot run {specification.search_method!r}."
            )
        if specification.assets != (self.data.asset,):
            raise PyBrokerUnsupportedSemanticsError(
                "Phase 3B supports exactly one asset matching PyBrokerResearchData."
            )
        if specification.timeframe != self.data.timeframe:
            raise PyBrokerInputError(
                "Discovery timeframe differs from PyBrokerResearchData."
            )
        if specification.target_family != self.data.target_family:
            raise PyBrokerInputError(
                "Discovery target_family differs from framework target metadata."
            )
        if specification.model_families != ("logistic_regression_clf",):
            raise PyBrokerUnsupportedSemanticsError(
                "Phase 3B initially supports exactly model_families="
                "('logistic_regression_clf',)."
            )
        if specification.signal_families != (self.signal.signal_family,):
            raise PyBrokerInputError(
                "Discovery signal_families must contain exactly the configured "
                "framework signal family."
            )
        self.parameter_mapping.validate_dimensions(
            specification.search_space.parameter_names,
            signal_policy=self.signal,
        )
        cardinality = specification.search_space.cardinality()
        if cardinality is None:
            raise PyBrokerUnsupportedSemanticsError(
                "PyBroker requires a finite enumerable Phase 2 search space; "
                "use ExistingOptunaSearchExecutor for adaptive/continuous search."
            )
        if cardinality < 1:
            raise PyBrokerInputError("PyBroker search space cannot be empty.")
        planned = min(cardinality, specification.trial_budget)
        self.resources.validate(rows=len(self.data.frame), combinations=planned)

        split_cfg = self.folds.to_dict(
            target_horizon=self.data.target_horizon
        )
        splits = tuple(
            build_time_splits(
                method="purged",
                n_samples=len(self.data.frame),
                split_cfg=split_cfg,
                target_horizon=self.data.target_horizon,
            )
        )
        assignment_count = np.zeros(len(self.data.frame), dtype=np.int32)
        for split in splits:
            assignment_count[split.test_idx] += 1
            assert_no_forward_label_leakage(
                split.train_idx,
                test_start=int(split.test_start),
                target_horizon=self.data.target_horizon,
            )
        if bool((assignment_count > 1).any()):
            raise PyBrokerInputError(
                "Overlapping test folds are unsupported; OOS predictions must be assigned once."
            )
        return splits, cardinality, planned

    def _artifact_references(self) -> tuple[str, ...]:
        if self.artifact_root is None:
            return ()
        return tuple(
            str(self.artifact_root / name)
            for name in (
                "pybroker_backend.json",
                "pybroker_fold_diagnostics.json",
                "pybroker_oos_predictions.jsonl",
                "pybroker_search_summary.json",
            )
        )

    def _fit_predict_fold(
        self,
        *,
        pybroker_module: ModuleType,
        split: TimeSplit,
        parameters: Mapping[str, Any],
        trial_id: str,
        trial_seed: int,
        threshold: float,
        cost_mapping: PyBrokerCostMapping,
    ) -> _FoldOutcome:
        frame = self.data.frame
        train = frame.iloc[split.train_idx]
        test = frame.iloc[split.test_idx]
        train_complete = train.loc[:, self.data.feature_columns].notna().all(axis=1)
        train_labeled = train[self.data.target_column].notna()
        train_fit = train.loc[train_complete & train_labeled]
        dropped_train_rows = int(len(train) - len(train_fit))
        if len(train_fit) < self.folds.minimum_train_rows:
            raise _InvalidFoldError(
                f"fold={split.fold}:insufficient_training_rows:"
                f"{len(train_fit)}<{self.folds.minimum_train_rows}"
            )
        labels = train_fit[self.data.target_column].astype(int)
        if int(labels.nunique()) < 2:
            raise _InvalidFoldError(
                f"fold={split.fold}:single_target_class"
            )

        test_complete = test.loc[:, self.data.feature_columns].notna().all(axis=1)
        test_predict = test.loc[test_complete]
        X_train, X_test, preprocessing_meta = _apply_fold_feature_preprocessing(
            train_fit.loc[:, self.data.feature_columns],
            test_predict.loc[:, self.data.feature_columns],
            preprocessing_cfg={"scaler": self.preprocessing.scaler},
        )
        native_train = _frame_from_values(
            X_train,
            index=train_fit.index,
            columns=self.data.feature_columns,
        )
        native_train[self.data.target_column] = labels.to_numpy(dtype=int)
        native_test = _frame_from_values(
            X_test,
            index=test_predict.index,
            columns=self.data.feature_columns,
        )
        model_parameters = self.parameter_mapping.resolve_model_parameters(
            parameters,
            base_parameters=self.base_model_parameters,
            seed=trial_seed,
        )

        def train_fn(
            symbol: str,
            train_data: pd.DataFrame,
            test_data: pd.DataFrame,
        ) -> object:
            if symbol != self.data.asset:
                raise PyBrokerRuntimeError("PyBroker callback symbol mismatch.")
            estimator = create_logistic_regression_estimator(model_parameters)
            with warnings.catch_warnings():
                warnings.simplefilter("error", ConvergenceWarning)
                estimator.fit(
                    train_data.loc[:, self.data.feature_columns],
                    train_data[self.data.target_column].astype(int),
                )
            return estimator

        def input_data_fn(input_frame: pd.DataFrame) -> pd.DataFrame:
            return input_frame.loc[:, self.data.feature_columns]

        model_name = f"stf-{trial_id}-fold-{split.fold:04d}"
        try:
            model_source = pybroker_module.ModelTrainer(
                name=model_name,
                train_fn=train_fn,
                indicator_names=(),
                input_data_fn=input_data_fn,
                predict_fn=_predict_positive_probability,
                kwargs={},
            )
            estimator = model_source(
                self.data.asset,
                native_train,
                native_test,
            )
            prediction_input = model_source.prepare_input_data(native_test)
            raw_probability = _predict_positive_probability(
                estimator,
                prediction_input,
            )
        except _InvalidFoldError:
            raise
        except ConvergenceWarning as exc:
            raise PyBrokerRuntimeError(
                f"fold={split.fold}:convergence_failure:{exc}"
            ) from exc
        except Exception as exc:
            raise PyBrokerRuntimeError(
                f"fold={split.fold}:model_exception:{type(exc).__name__}:{exc}"
            ) from exc

        probability = pd.Series(
            np.nan,
            index=test.index,
            name="pred_prob",
            dtype=float,
        )
        probability.loc[test_predict.index] = raw_probability
        fold_oos_mask = pd.Series(True, index=test.index, dtype=bool)
        fold_predictive = predictive_metrics(
            target=test[self.data.target_column],
            probability=probability,
        )
        signal = framework_long_flat_signal(
            probability=probability,
            oos_mask=fold_oos_mask,
            policy=self.signal,
            threshold=threshold,
        )
        fold_trading, trading_ledger = fold_trading_diagnostics(
            open_prices=test["open"].astype(float),
            signal=signal,
            cost_mapping=cost_mapping,
            periods_per_year=self.periods_per_year,
        )

        model_fit_end = train_fit.index[-1]
        provenance: list[Mapping[str, Any]] = []
        for timestamp, value in probability.dropna().items():
            position = int(frame.index.get_loc(timestamp))
            if position in set(split.train_idx.tolist()):
                raise PyBrokerRuntimeError(
                    "A prediction row was also present in its training fold."
                )
            if not pd.Timestamp(model_fit_end) < pd.Timestamp(timestamp):
                raise PyBrokerRuntimeError(
                    "model_fit_end_timestamp must precede every OOS prediction."
                )
            earliest_execution = (
                frame.index[position + self.timing.entry_delay_bars]
                if position + self.timing.entry_delay_bars < split.test_end
                else None
            )
            provenance.append(
                {
                    "trial_id": trial_id,
                    "fold_id": int(split.fold),
                    "prediction_timestamp": _timestamp(timestamp),
                    "prediction_information_time": "bar_close",
                    "model_fit_end_timestamp": _timestamp(model_fit_end),
                    "trained_without_this_row": True,
                    "is_oos": True,
                    "probability": float(value),
                    "earliest_execution_timestamp": (
                        _timestamp(earliest_execution)
                        if earliest_execution is not None
                        else None
                    ),
                    "execution_price_source": "open",
                }
            )

        fold_metadata = {
            "fold_id": int(split.fold),
            "train_start": int(split.train_start),
            "train_end": int(split.train_end),
            "test_start": int(split.test_start),
            "test_end": int(split.test_end),
            "train_start_timestamp": _timestamp(train.index[0]),
            "train_end_timestamp": _timestamp(train.index[-1]),
            "model_fit_end_timestamp": _timestamp(model_fit_end),
            "test_start_timestamp": _timestamp(test.index[0]),
            "test_end_timestamp": _timestamp(test.index[-1]),
            "purge_bars": self.folds.resolved_purge_bars(
                target_horizon=self.data.target_horizon
            ),
            "embargo_bars": self.folds.embargo_bars,
            "expanding": self.folds.expanding,
            "train_rows_raw": int(len(train)),
            "train_rows_fit": int(len(train_fit)),
            "train_rows_dropped_missing_or_unlabeled": dropped_train_rows,
            "test_rows": int(len(test)),
            "oos_prediction_rows": int(probability.notna().sum()),
            "missing_oos_rows": int(probability.isna().sum()),
            "oos_coverage": float(probability.notna().mean()),
            "preprocessing": {
                **preprocessing_meta,
                "policy": self.preprocessing.to_dict(),
                "training_feature_means": {
                    column: float(
                        train_fit[column].astype(float).mean()
                    )
                    for column in self.data.feature_columns
                },
            },
            "model_seed": trial_seed,
            "model_parameters": dict(model_parameters),
            "predictive_metrics": dict(fold_predictive),
            "trading_screening_metrics": dict(fold_trading),
            "prediction_callback": "pybroker_model_trainer_predict_proba",
            "refit_per_fold": True,
        }
        return _FoldOutcome(
            split=split,
            probability=probability,
            predictive=fold_predictive,
            trading=fold_trading,
            trading_ledger=trading_ledger,
            metadata=_freeze_json_mapping(
                fold_metadata, field_name="fold metadata"
            ),
            provenance=tuple(
                _freeze_json_mapping(row, field_name="prediction provenance")
                for row in provenance
            ),
        )

    def _completed_trial(
        self,
        *,
        specification: DiscoverySpecification,
        research_run_id: str,
        pybroker_module: ModuleType,
        splits: Sequence[TimeSplit],
        parameters: Mapping[str, Any],
        cost_mapping: PyBrokerCostMapping,
        full_cardinality: int,
        planned_combinations: int,
        artifact_references: tuple[str, ...],
    ) -> DiscoveryTrial:
        trial_id = _trial_identity(research_run_id, parameters)
        seed = _trial_seed(
            specification.random_seed,
            research_run_id,
            parameters,
        )
        threshold = self.signal.resolve_threshold(parameters)
        outcomes = tuple(
            self._fit_predict_fold(
                pybroker_module=pybroker_module,
                split=split,
                parameters=parameters,
                trial_id=trial_id,
                trial_seed=seed,
                threshold=threshold,
                cost_mapping=cost_mapping,
            )
            for split in splits
        )
        frame = self.data.frame
        probability = pd.Series(np.nan, index=frame.index, dtype=float)
        oos_mask = pd.Series(False, index=frame.index, dtype=bool)
        assignment_count = pd.Series(0, index=frame.index, dtype="int32")
        for outcome in outcomes:
            test_index = frame.index[outcome.split.test_idx]
            probability.loc[test_index] = outcome.probability
            oos_mask.loc[test_index] = True
            assignment_count.loc[test_index] += 1
        if bool((assignment_count > 1).any()):
            raise PyBrokerRuntimeError(
                "OOS prediction rows were assigned by more than one fold."
            )
        if bool((probability.notna() & ~oos_mask).any()):
            raise PyBrokerRuntimeError(
                "Non-OOS predictions were emitted by the PyBroker adapter."
            )
        oos_rows = int(oos_mask.sum())
        prediction_rows = int((oos_mask & probability.notna()).sum())
        if prediction_rows == 0:
            raise _InvalidFoldError("no_oos_predictions")
        missing_oos_rows = int(oos_rows - prediction_rows)
        aggregate_predictive = predictive_metrics(
            target=frame.loc[oos_mask, self.data.target_column],
            probability=probability.loc[oos_mask],
        )
        aggregate_trading = aggregate_trading_diagnostics(
            fold_ledgers=tuple(outcome.trading_ledger for outcome in outcomes),
            periods_per_year=self.periods_per_year,
        )
        trial_metrics: dict[str, int | float | None] = {
            **aggregate_predictive,
            **aggregate_trading,
            "observation_count": int(len(frame)),
            "total_rows": int(len(frame)),
            "eligible_prediction_rows": oos_rows,
            "oos_rows": oos_rows,
            "prediction_rows": prediction_rows,
            "oos_prediction_rows": prediction_rows,
            "missing_oos_rows": missing_oos_rows,
            "oos_coverage": float(prediction_rows / max(oos_rows, 1)),
            "missing_rate": float(missing_oos_rows / max(oos_rows, 1)),
            "fold_count": int(len(outcomes)),
        }
        fold_combined_metrics = [
            {**dict(outcome.predictive), **dict(outcome.trading)}
            for outcome in outcomes
        ]
        stability = fold_stability_diagnostics(
            fold_combined_metrics,
            metric_name=specification.selection.primary.metric,
            direction=specification.selection.primary.direction,
        )
        for name in (
            "mean_fold_metric",
            "median_fold_metric",
            "worst_fold_metric",
            "positive_fold_count",
            "fold_dispersion",
        ):
            trial_metrics[name] = _finite_metric_or_none(stability.get(name))
        metrics = sanitize_metrics(trial_metrics)
        provenance_rows = tuple(
            dict(row) for outcome in outcomes for row in outcome.provenance
        )
        runtime_metadata = {
            **pybroker_runtime_provenance(),
            "capabilities": sorted(self.capabilities),
            "model": {
                "kind": "logistic_regression_clf",
                "task_type": "binary_classification",
                "base_parameters": dict(self.base_model_parameters),
                "trial_parameters": {
                    model_parameter: parameters[dimension]
                    for dimension, model_parameter in self.parameter_mapping.model_parameters.items()
                },
                "refit_per_fold": True,
                "refit_frequency": "per_fold",
                "shuffle": False,
                "calibration": "unsupported",
                "feature_selection": "unsupported",
            },
            "feature_set": {
                "families": list(specification.feature_families),
                "columns": list(self.data.feature_columns),
                "owner": "stf_feature_registry_upstream",
            },
            "target": {
                "family": self.data.target_family,
                "column": self.data.target_column,
                "horizon": self.data.target_horizon,
                "owner": "stf_target_registry_upstream",
            },
            "signal": self.signal.to_dict(threshold=threshold),
            "fold_policy": self.folds.to_dict(
                target_horizon=self.data.target_horizon
            ),
            "folds": [dict(outcome.metadata) for outcome in outcomes],
            "fold_stability": stability,
            "prediction_coverage": {
                "total_rows": int(len(frame)),
                "eligible_prediction_rows": oos_rows,
                "oos_prediction_rows": prediction_rows,
                "missing_oos_rows": missing_oos_rows,
                "oos_coverage": float(prediction_rows / max(oos_rows, 1)),
                "non_oos_prediction_rows": 0,
                "first_oos_prediction_timestamp": (
                    _timestamp(probability.dropna().index[0])
                    if prediction_rows
                    else None
                ),
                "last_oos_prediction_timestamp": (
                    _timestamp(probability.dropna().index[-1])
                    if prediction_rows
                    else None
                ),
            },
            "oos_prediction_provenance": list(provenance_rows),
            "predictive_metrics": dict(aggregate_predictive),
            "trading_screening_metrics": dict(aggregate_trading),
            "metric_groups": {
                name: list(values) for name, values in SCREENING_METRIC_GROUPS.items()
            },
            "timing_mapping": self.timing.to_dict(),
            "cost_mapping": cost_mapping.to_dict(),
            "parameter_mapping": self.parameter_mapping.to_dict(),
            "trial_seed": seed,
            "framework_config_hash": specification.config_hash,
            "discovery_specification_hash": specification.specification_hash,
            "dataset_fingerprint": dict(specification.dataset_fingerprint),
            "full_search_cardinality": full_cardinality,
            "planned_combinations": planned_combinations,
            "resource_policy": self.resources.to_dict(),
            "screening_stage": "DISCOVERY",
            "screening_metrics_are_canonical_evidence": False,
            "pybroker_oos_predictions_are_untouched_final_holdout": False,
            "canonical_validation_required": True,
            "native_objects_serialized": False,
        }
        checks = {
            "causal_features": self.data.checks.get("causal_features", False),
            "target_signal_compatible": self.data.checks.get(
                "target_signal_compatible", False
            ),
            "fold_safe_preprocessing": True,
            "oos_predictions": True,
            "chronological_folds": True,
            "purge_applied": True,
            "embargo_preserved": True,
            "data_quality": True,
            "timing_mapping_supported": True,
            "cost_mapping_supported": True,
            "screening_only": True,
        }
        checks.update(self.data.checks)
        return DiscoveryTrial(
            trial_id=trial_id,
            research_run_id=research_run_id,
            parameters=parameters,
            status=TrialStatus.COMPLETED,
            metrics=metrics,
            checks=checks,
            seed=seed,
            artifact_references=artifact_references,
            runtime_metadata=runtime_metadata,
        )

    def _failed_trial(
        self,
        *,
        specification: DiscoverySpecification,
        research_run_id: str,
        parameters: Mapping[str, Any],
        splits: Sequence[TimeSplit],
        cost_mapping: PyBrokerCostMapping,
        status: TrialStatus,
        reason: str,
        artifact_references: tuple[str, ...],
        full_cardinality: int,
        planned_combinations: int,
    ) -> DiscoveryTrial:
        seed = _trial_seed(
            specification.random_seed,
            research_run_id,
            parameters,
        )
        planned_folds = [
            {
                "fold_id": int(split.fold),
                "train_start": int(split.train_start),
                "train_end": int(split.train_end),
                "test_start": int(split.test_start),
                "test_end": int(split.test_end),
                "train_start_timestamp": _timestamp(
                    self.data.frame.index[int(split.train_idx[0])]
                ),
                "train_end_timestamp": _timestamp(
                    self.data.frame.index[int(split.train_idx[-1])]
                ),
                "test_start_timestamp": _timestamp(
                    self.data.frame.index[int(split.test_idx[0])]
                ),
                "test_end_timestamp": _timestamp(
                    self.data.frame.index[int(split.test_idx[-1])]
                ),
                "purge_bars": self.folds.resolved_purge_bars(
                    target_horizon=self.data.target_horizon
                ),
                "embargo_bars": self.folds.embargo_bars,
                "expanding": self.folds.expanding,
            }
            for split in splits
        ]
        threshold = (
            self.signal.fixed_threshold
            if self.signal.fixed_threshold is not None
            else parameters.get(self.signal.threshold_parameter)
        )
        return DiscoveryTrial(
            trial_id=_trial_identity(research_run_id, parameters),
            research_run_id=research_run_id,
            parameters=parameters,
            status=status,
            metrics={},
            checks={},
            seed=seed,
            failure_reason=reason,
            artifact_references=artifact_references,
            runtime_metadata={
                **pybroker_runtime_provenance(),
                "capabilities": sorted(self.capabilities),
                "model": {
                    "kind": "logistic_regression_clf",
                    "task_type": "binary_classification",
                    "base_parameters": dict(self.base_model_parameters),
                    "trial_parameters": {
                        model_parameter: parameters[dimension]
                        for dimension, model_parameter in self.parameter_mapping.model_parameters.items()
                    },
                    "refit_per_fold": True,
                    "refit_frequency": "per_fold",
                    "shuffle": False,
                    "calibration": "unsupported",
                    "feature_selection": "unsupported",
                },
                "feature_set": {
                    "families": list(specification.feature_families),
                    "columns": list(self.data.feature_columns),
                    "owner": "stf_feature_registry_upstream",
                },
                "target": {
                    "family": self.data.target_family,
                    "column": self.data.target_column,
                    "horizon": self.data.target_horizon,
                    "owner": "stf_target_registry_upstream",
                },
                "signal": {
                    "signal_family": self.signal.signal_family,
                    "rule": self.signal.rule,
                    "direction": self.signal.direction,
                    "threshold": threshold,
                    "threshold_parameter": self.signal.threshold_parameter,
                },
                "fold_policy": self.folds.to_dict(
                    target_horizon=self.data.target_horizon
                ),
                "planned_folds": planned_folds,
                "cost_mapping": cost_mapping.to_dict(),
                "parameter_mapping": self.parameter_mapping.to_dict(),
                "trial_seed": seed,
                "framework_config_hash": specification.config_hash,
                "discovery_specification_hash": specification.specification_hash,
                "dataset_fingerprint": dict(specification.dataset_fingerprint),
                "full_search_cardinality": full_cardinality,
                "planned_combinations": planned_combinations,
                "screening_stage": "DISCOVERY",
                "screening_metrics_are_canonical_evidence": False,
                "canonical_validation_required": True,
                "native_objects_serialized": False,
            },
        )

    def _write_artifacts(
        self,
        *,
        specification: DiscoverySpecification,
        trials: Sequence[DiscoveryTrial],
        full_cardinality: int,
        planned_combinations: int,
        cost_mapping: PyBrokerCostMapping,
    ) -> None:
        if self.artifact_root is None:
            return
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        paths = [Path(value) for value in self._artifact_references()]
        existing = [str(path) for path in paths if path.exists()]
        if existing:
            raise PyBrokerRuntimeError(
                f"PyBroker backend artifacts already exist: {existing}."
            )
        _write_json_once(
            paths[0],
            {
                **pybroker_runtime_provenance(),
                "capabilities": sorted(self.capabilities),
                "unsupported_capabilities": [
                    "canonical_validation",
                    "event_driven_execution",
                    "live_execution",
                    "multi_asset_shared_capital",
                    "online_learning",
                    "portfolio_optimization",
                    "reinforcement_learning",
                    "vectorized_rule_screening",
                ],
                "screening_only": True,
            },
        )
        _write_json_once(
            paths[1],
            {
                "fold_policy": self.folds.to_dict(
                    target_horizon=self.data.target_horizon
                ),
                "trials": [
                    {
                        "trial_id": trial.trial_id,
                        "status": trial.status.value,
                        "folds": list(trial.runtime_metadata.get("folds", [])),
                        "fold_stability": dict(
                            trial.runtime_metadata.get("fold_stability", {})
                        ),
                    }
                    for trial in trials
                ],
            },
        )
        prediction_rows = [
            dict(row)
            for trial in trials
            for row in trial.runtime_metadata.get(
                "oos_prediction_provenance", []
            )
        ]
        _write_jsonl_once(paths[2], prediction_rows)
        counts = Counter(trial.status.value for trial in trials)
        _write_json_once(
            paths[3],
            {
                "discovery_specification_hash": specification.specification_hash,
                "full_search_cardinality": full_cardinality,
                "planned_combinations": planned_combinations,
                "emitted_trials": len(trials),
                "trial_state_counts": dict(sorted(counts.items())),
                "cost_mapping": cost_mapping.to_dict(),
                "resource_policy": self.resources.to_dict(),
                "model_search_dimensions": dict(
                    self.parameter_mapping.model_parameters
                ),
                "signal_threshold_dimension": self.signal.threshold_parameter,
                "screening_only": True,
                "canonical_validation_required": True,
            },
        )

    def execute(
        self,
        specification: DiscoverySpecification,
        *,
        research_run_id: str,
        evaluator: TrialEvaluator | None = None,
    ) -> tuple[DiscoveryTrial, ...]:
        if evaluator is not None:
            raise ResearchContractError(
                "PyBroker executor owns fold training; evaluator injection is unsupported."
            )
        splits, full_cardinality, planned_combinations = (
            self._validate_specification(specification)
        )
        cost_mapping = PyBrokerCostMapping.from_stf_assumptions(
            specification.cost_assumptions,
            allow_approximate_spread=self.allow_approximate_spread,
        )
        pybroker_module = self._dependency_loader()
        if not hasattr(pybroker_module, "ModelTrainer"):
            raise PyBrokerRuntimeError(
                "Installed PyBroker does not expose the required ModelTrainer API."
            )
        parameters_list = tuple(
            specification.search_space.iter_grid(limit=planned_combinations)
        )
        references = self._artifact_references()
        trials: list[DiscoveryTrial] = []
        for parameters in parameters_list:
            try:
                trial = self._completed_trial(
                    specification=specification,
                    research_run_id=research_run_id,
                    pybroker_module=pybroker_module,
                    splits=splits,
                    parameters=parameters,
                    cost_mapping=cost_mapping,
                    full_cardinality=full_cardinality,
                    planned_combinations=planned_combinations,
                    artifact_references=references,
                )
            except PyBrokerUnsupportedSemanticsError as exc:
                trial = self._failed_trial(
                    specification=specification,
                    research_run_id=research_run_id,
                    parameters=parameters,
                    splits=splits,
                    cost_mapping=cost_mapping,
                    status=TrialStatus.INVALID,
                    reason=f"unsupported_semantics:{exc}",
                    artifact_references=references,
                    full_cardinality=full_cardinality,
                    planned_combinations=planned_combinations,
                )
            except _InvalidFoldError as exc:
                trial = self._failed_trial(
                    specification=specification,
                    research_run_id=research_run_id,
                    parameters=parameters,
                    splits=splits,
                    cost_mapping=cost_mapping,
                    status=TrialStatus.INVALID,
                    reason=f"invalid_fold:{exc}",
                    artifact_references=references,
                    full_cardinality=full_cardinality,
                    planned_combinations=planned_combinations,
                )
            except PyBrokerInputError as exc:
                trial = self._failed_trial(
                    specification=specification,
                    research_run_id=research_run_id,
                    parameters=parameters,
                    splits=splits,
                    cost_mapping=cost_mapping,
                    status=TrialStatus.INVALID,
                    reason=f"invalid_input:{exc}",
                    artifact_references=references,
                    full_cardinality=full_cardinality,
                    planned_combinations=planned_combinations,
                )
            except PyBrokerRuntimeError as exc:
                trial = self._failed_trial(
                    specification=specification,
                    research_run_id=research_run_id,
                    parameters=parameters,
                    splits=splits,
                    cost_mapping=cost_mapping,
                    status=TrialStatus.FAILED,
                    reason=f"pybroker_runtime_error:{exc}",
                    artifact_references=references,
                    full_cardinality=full_cardinality,
                    planned_combinations=planned_combinations,
                )
            except Exception as exc:
                trial = self._failed_trial(
                    specification=specification,
                    research_run_id=research_run_id,
                    parameters=parameters,
                    splits=splits,
                    cost_mapping=cost_mapping,
                    status=TrialStatus.FAILED,
                    reason=(
                        "pybroker_runtime_error:"
                        f"{type(exc).__name__}:{exc}"
                    ),
                    artifact_references=references,
                    full_cardinality=full_cardinality,
                    planned_combinations=planned_combinations,
                )
            trials.append(trial)
        result = tuple(trials)
        self._write_artifacts(
            specification=specification,
            trials=result,
            full_cardinality=full_cardinality,
            planned_combinations=planned_combinations,
            cost_mapping=cost_mapping,
        )
        return result


def _finite_metric_or_none(value: object) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PyBrokerInputError("Fold stability metric must be numeric or null.")
    return value if isfinite(float(value)) else None


__all__ = [
    "PyBrokerLoader",
    "PyBrokerSearchExecutor",
    "SCREENING_METRIC_GROUPS",
    "pybroker_runtime_provenance",
]
