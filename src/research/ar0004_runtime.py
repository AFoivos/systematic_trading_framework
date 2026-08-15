"""Cloud-scale, discovery-only AR-0004 cross-asset ML tournament.

The runtime searches model parameters only on the frozen tuning folds, then
evaluates the top frozen alternatives on later screening folds.  Every model
is refit per fold with a target-horizon purge.  Screening predictions are never
backfilled and no validation, portfolio, backtest, or execution state is used.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import floor, isfinite, sqrt
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from src.experiments.alpha_discovery_statistics import (
    adjust_pvalues,
    newey_west_conditional_mean_summary,
    segmented_moving_block_bootstrap_summary,
    stable_hypothesis_seed,
)
from src.models.forecasting.lightgbm import create_lightgbm_regressor_estimator
from src.research.ar0003_runtime import (
    BAR_DELTA,
    FEATURE_COLUMNS,
    _load_one_source,
    build_ar0003_asset_features_and_targets,
)
from src.research.dataset import compute_research_dataset_fingerprint
from src.utils.run_metadata import compute_config_hash


class AR0004RuntimeError(RuntimeError):
    """Raised when AR-0004 cannot preserve its frozen research contract."""


@dataclass(frozen=True)
class AR0004BuiltPanel:
    frame: pd.DataFrame
    dataset_fingerprint: Mapping[str, Any]
    source_quality: Mapping[str, Any]


@dataclass(frozen=True)
class FoldEvaluation:
    fold_id: str
    train_start: str
    model_fit_end: str
    test_start: str
    test_end: str
    train_rows: int
    eligible_test_rows: int
    oos_prediction_rows: int
    rank_ic_periods: int
    mean_rank_ic: float | None
    rmse: float | None
    stressed_top_bottom_return: float | None

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class CandidateEvaluation:
    identity: str
    parameters: dict[str, Any]
    status: str
    failure_reason: str | None
    fold_metrics: list[FoldEvaluation]
    rank_ic_timeline: pd.DataFrame
    metrics: dict[str, Any]
    predictions: pd.DataFrame | None = None


BASE_FEATURES = tuple(FEATURE_COLUMNS)
CS_FEATURES = (
    "cs_z_log_return_16",
    "cs_z_log_return_32",
    "cs_z_log_return_64",
    "cs_rank_path_efficiency_16",
    "cs_rank_path_efficiency_32",
    "cs_rank_path_efficiency_48",
    "cs_rank_volatility_ratio_32_192",
)


def _same_timestamp_rank(values: pd.Series, timestamps: pd.Series, minimum: int) -> pd.Series:
    count = values.notna().groupby(timestamps).transform("sum")
    return values.groupby(timestamps).rank(method="average", pct=True).where(count >= minimum)


def _add_cross_sectional_features(frame: pd.DataFrame, *, minimum_assets: int) -> pd.DataFrame:
    out = frame.copy()
    timestamp = out["timestamp"]
    for column in ("log_return_16", "log_return_32", "log_return_64"):
        grouped = out[column].groupby(timestamp)
        count = out[column].notna().groupby(timestamp).transform("sum")
        mean = grouped.transform("mean")
        std = grouped.transform(lambda item: item.std(ddof=0))
        out[f"cs_z_{column}"] = ((out[column] - mean) / std.where(std > 0.0)).where(
            count >= minimum_assets
        )
    for column in (
        "path_efficiency_16",
        "path_efficiency_32",
        "path_efficiency_48",
        "volatility_ratio_32_192",
    ):
        out[f"cs_rank_{column}"] = _same_timestamp_rank(
            out[column], timestamp, minimum_assets
        )
    return out


def build_ar0004_panel(cfg: Mapping[str, Any], *, project_root: Path) -> AR0004BuiltPanel:
    """Verify all frozen source hashes and build one causal long-form panel."""

    universe = cfg["asset_universe"]
    start = pd.Timestamp(universe["sample_start_inclusive"])
    end = pd.Timestamp(universe["sample_end_exclusive"])
    frames: list[pd.DataFrame] = []
    quality: list[dict[str, Any]] = []
    for asset in universe["asset_ids"]:
        source, report = _load_one_source(
            asset,
            universe["source_files"][asset],
            project_root=project_root,
            start=start,
            end=end,
        )
        frames.append(build_ar0003_asset_features_and_targets(source))
        quality.append(report)
    panel = pd.concat(frames, ignore_index=True).sort_values(
        ["timestamp", "asset_id"], kind="mergesort"
    ).reset_index(drop=True)
    resources = cfg["resource_policy"]
    if len(panel) > int(resources["max_rows"]):
        raise AR0004RuntimeError(
            f"AR-0004 row cap exceeded: {len(panel)}>{resources['max_rows']}."
        )
    if panel["asset_id"].nunique() > int(resources["max_assets"]):
        raise AR0004RuntimeError("AR-0004 asset cap exceeded.")
    panel = _add_cross_sectional_features(
        panel, minimum_assets=int(universe["minimum_assets_per_timestamp"])
    )
    fingerprint_columns = [
        "timestamp",
        "asset_id",
        *BASE_FEATURES,
        *CS_FEATURES,
        "future_executable_return_h16",
        "future_executable_return_h32",
    ]
    fingerprint = compute_research_dataset_fingerprint(panel[fingerprint_columns])
    return AR0004BuiltPanel(
        frame=panel,
        dataset_fingerprint=fingerprint,
        source_quality={
            "contract": "FROZEN_SHA256_CAUSAL_PANEL_NO_DENSIFICATION",
            "asset_count": len(quality),
            "row_count": int(len(panel)),
            "first_timestamp": panel["timestamp"].min().isoformat(),
            "last_timestamp": panel["timestamp"].max().isoformat(),
            "gaps_filled": False,
            "rows_densified": False,
            "sources": quality,
        },
    )


def _feature_columns(cfg: Mapping[str, Any], name: str) -> tuple[str, ...]:
    variants = cfg["features"]["feature_sets"]
    if name not in variants:
        raise AR0004RuntimeError(f"Unknown frozen feature set: {name!r}.")
    columns = tuple(str(value) for value in variants[name])
    if not columns or len(set(columns)) != len(columns):
        raise AR0004RuntimeError(f"Invalid feature set: {name!r}.")
    return columns


def _model_parameters(parameters: Mapping[str, Any], *, seed: int, threads: int) -> dict[str, Any]:
    return {
        "n_estimators": int(parameters["n_estimators"]),
        "learning_rate": float(parameters["learning_rate"]),
        "num_leaves": int(parameters["num_leaves"]),
        "max_depth": int(parameters["max_depth"]),
        "min_child_samples": int(parameters["min_child_samples"]),
        "subsample": float(parameters["subsample"]),
        "subsample_freq": 1,
        "colsample_bytree": float(parameters["colsample_bytree"]),
        "reg_alpha": float(parameters["reg_alpha"]),
        "reg_lambda": float(parameters["reg_lambda"]),
        "objective": "regression_l2",
        "random_state": int(seed),
        "n_jobs": int(threads),
        "verbosity": -1,
        "deterministic": True,
        "force_col_wise": True,
    }


def _fold_rows(
    frame: pd.DataFrame,
    *,
    test_start: pd.Timestamp,
    test_end: pd.Timestamp,
    horizon: int,
    features: Sequence[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp, int]:
    target = f"future_executable_return_h{horizon}"
    safe_end = test_start - (horizon + 1) * BAR_DELTA
    train_mask = frame["timestamp"].lt(safe_end)
    test_mask = frame["timestamp"].ge(test_start) & frame["timestamp"].lt(test_end)
    required = [*features, target]
    train = frame.loc[train_mask].dropna(subset=required)
    eligible_test = frame.loc[test_mask].dropna(subset=[target])
    test = eligible_test.dropna(subset=list(features))
    if train.empty or test.empty:
        raise AR0004RuntimeError("Fold has no complete train or test rows.")
    if train["timestamp"].max() >= test_start:
        raise AR0004RuntimeError("Target purge failed to separate train and test.")
    return train, test, safe_end, int(len(eligible_test))


def _rank_ic_rows(
    frame: pd.DataFrame, *, minimum_assets: int
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for timestamp, group in frame.groupby("timestamp", sort=True):
        sample = group[["prediction", "target"]].dropna()
        if len(sample) < minimum_assets:
            continue
        pred_rank = sample["prediction"].rank(method="average")
        target_rank = sample["target"].rank(method="average")
        value = pred_rank.corr(target_rank)
        if value is not None and isfinite(float(value)):
            rows.append({"timestamp": timestamp, "rank_ic": float(value)})
    return pd.DataFrame(rows, columns=["timestamp", "rank_ic"])


def _directional_tail_return(
    frame: pd.DataFrame,
    *,
    horizon: int,
    quantile_fraction: float,
) -> float | None:
    values: list[float] = []
    long_column = f"long_return_h{horizon}_cost_1_5"
    short_column = f"short_return_h{horizon}_cost_1_5"
    for _, group in frame.groupby("timestamp", sort=True):
        sample = group.dropna(subset=["prediction", long_column, short_column]).sort_values(
            ["prediction", "asset_id"], kind="mergesort"
        )
        count = floor(len(sample) * quantile_fraction)
        if count < 1:
            continue
        top = sample.tail(count)[long_column].mean()
        bottom = sample.head(count)[short_column].mean()
        if isfinite(float(top)) and isfinite(float(bottom)):
            values.append(float(top + bottom))
    return float(np.mean(values)) if values else None


def _evaluate_folds(
    cfg: Mapping[str, Any],
    frame: pd.DataFrame,
    parameters: Mapping[str, Any],
    folds: Sequence[Mapping[str, Any]],
    *,
    seed: int,
    identity: str,
    retain_predictions: bool,
) -> CandidateEvaluation:
    features = _feature_columns(cfg, str(parameters["feature_set"]))
    horizon = int(parameters["horizon_bars"])
    target = f"future_executable_return_h{horizon}"
    minimum_assets = int(cfg["screening_evaluation"]["minimum_assets_per_timestamp"])
    fraction = float(cfg["screening_evaluation"]["top_fraction"])
    fold_metrics: list[FoldEvaluation] = []
    timelines: list[pd.DataFrame] = []
    prediction_parts: list[pd.DataFrame] = []
    try:
        for fold_index, fold in enumerate(folds):
            test_start = pd.Timestamp(fold["test_start"])
            test_end = pd.Timestamp(fold["test_end"])
            train, test, _, eligible_test_rows = _fold_rows(
                frame,
                test_start=test_start,
                test_end=test_end,
                horizon=horizon,
                features=features,
            )
            model_seed = stable_hypothesis_seed(seed + fold_index, identity)
            estimator = create_lightgbm_regressor_estimator(
                _model_parameters(
                    parameters,
                    seed=model_seed,
                    threads=int(cfg["model_search"]["threads_per_model"]),
                )
            )
            estimator.fit(train.loc[:, features], train[target].astype(float))
            prediction = np.asarray(estimator.predict(test.loc[:, features]), dtype=float)
            if prediction.shape != (len(test),) or not np.isfinite(prediction).all():
                raise AR0004RuntimeError("LightGBM emitted non-finite or misaligned predictions.")
            scored = test[
                [
                    "timestamp",
                    "asset_id",
                    target,
                    f"long_return_h{horizon}_cost_1_5",
                    f"short_return_h{horizon}_cost_1_5",
                ]
            ].copy()
            scored = scored.rename(columns={target: "target"})
            scored["prediction"] = prediction
            scored["fold_id"] = str(fold["fold_id"])
            scored["trained_without_this_row"] = True
            scored["is_oos"] = True
            scored["model_fit_end_timestamp"] = train["timestamp"].max()
            rank_rows = _rank_ic_rows(scored, minimum_assets=minimum_assets)
            rank_rows["fold_id"] = str(fold["fold_id"])
            timelines.append(rank_rows)
            rmse = sqrt(float(np.mean(np.square(scored["prediction"] - scored["target"]))))
            fold_metrics.append(
                FoldEvaluation(
                    fold_id=str(fold["fold_id"]),
                    train_start=train["timestamp"].min().isoformat(),
                    model_fit_end=train["timestamp"].max().isoformat(),
                    test_start=test_start.isoformat(),
                    test_end=test_end.isoformat(),
                    train_rows=int(len(train)),
                    eligible_test_rows=eligible_test_rows,
                    oos_prediction_rows=int(len(scored)),
                    rank_ic_periods=int(len(rank_rows)),
                    mean_rank_ic=(float(rank_rows["rank_ic"].mean()) if len(rank_rows) else None),
                    rmse=rmse,
                    stressed_top_bottom_return=_directional_tail_return(
                        scored, horizon=horizon, quantile_fraction=fraction
                    ),
                )
            )
            if retain_predictions:
                prediction_parts.append(scored)
        fold_ics = [
            float(item.mean_rank_ic)
            for item in fold_metrics
            if item.mean_rank_ic is not None and isfinite(float(item.mean_rank_ic))
        ]
        if len(fold_ics) != len(folds):
            raise AR0004RuntimeError("A fold has no finite cross-sectional rank IC.")
        worst = min(fold_ics)
        mean_ic = float(np.mean(fold_ics))
        dispersion = float(np.std(fold_ics, ddof=0))
        objective = mean_ic - 0.50 * dispersion - 0.25 * max(0.0, -worst)
        tail_values = [
            float(item.stressed_top_bottom_return)
            for item in fold_metrics
            if item.stressed_top_bottom_return is not None
        ]
        all_predictions = pd.concat(prediction_parts, ignore_index=True) if prediction_parts else None
        timeline = pd.concat(timelines, ignore_index=True)
        total_rows = int(sum(item.eligible_test_rows for item in fold_metrics))
        predicted_rows = int(sum(item.oos_prediction_rows for item in fold_metrics))
        return CandidateEvaluation(
            identity=identity,
            parameters=dict(parameters),
            status="COMPLETED",
            failure_reason=None,
            fold_metrics=fold_metrics,
            rank_ic_timeline=timeline,
            metrics={
                "objective": objective,
                "mean_rank_correlation": mean_ic,
                "median_fold_rank_correlation": float(np.median(fold_ics)),
                "worst_fold_rank_correlation": worst,
                "fold_rank_dispersion": dispersion,
                "positive_fold_count": int(sum(value > 0.0 for value in fold_ics)),
                "rmse": float(np.mean([item.rmse for item in fold_metrics if item.rmse is not None])),
                "stressed_top_bottom_return": float(np.mean(tail_values)) if tail_values else None,
                "observation_count": total_rows,
                "oos_rows": predicted_rows,
                "oos_coverage": float(predicted_rows / total_rows) if total_rows else 0.0,
                "missing_rate": float(1.0 - predicted_rows / total_rows) if total_rows else 1.0,
            },
            predictions=all_predictions,
        )
    except Exception as exc:
        return CandidateEvaluation(
            identity=identity,
            parameters=dict(parameters),
            status="INVALID",
            failure_reason=f"{type(exc).__name__}:{exc}",
            fold_metrics=fold_metrics,
            rank_ic_timeline=pd.DataFrame(columns=["timestamp", "rank_ic", "fold_id"]),
            metrics={},
            predictions=None,
        )


def _suggest_parameters(trial: Any, cfg: Mapping[str, Any]) -> dict[str, Any]:
    space = cfg["model_search"]["space"]
    return {
        "candidate_kind": "model",
        "source_trial_number": int(trial.number),
        "feature_set": trial.suggest_categorical("feature_set", space["feature_set"]),
        "horizon_bars": trial.suggest_categorical("horizon_bars", space["horizon_bars"]),
        "n_estimators": trial.suggest_int("n_estimators", **space["n_estimators"]),
        "learning_rate": trial.suggest_float("learning_rate", **space["learning_rate"]),
        "num_leaves": trial.suggest_int("num_leaves", **space["num_leaves"]),
        "max_depth": trial.suggest_categorical("max_depth", space["max_depth"]),
        "min_child_samples": trial.suggest_int("min_child_samples", **space["min_child_samples"]),
        "subsample": trial.suggest_float("subsample", **space["subsample"]),
        "colsample_bytree": trial.suggest_float("colsample_bytree", **space["colsample_bytree"]),
        "reg_alpha": trial.suggest_float("reg_alpha", **space["reg_alpha"]),
        "reg_lambda": trial.suggest_float("reg_lambda", **space["reg_lambda"]),
    }


def run_tuning_search(
    cfg: Mapping[str, Any],
    built: AR0004BuiltPanel,
    *,
    storage_path: Path,
) -> tuple[Any, pd.DataFrame]:
    """Run or resume the frozen Optuna tuning study without screening access."""

    try:
        import optuna
    except ModuleNotFoundError as exc:
        raise AR0004RuntimeError(
            "AR-0004 requires optuna from requirements.lock.txt; install the core requirements."
        ) from exc
    search = cfg["model_search"]
    sampler_cfg = search["sampler"]
    sampler = optuna.samplers.TPESampler(
        seed=int(sampler_cfg["seed"]),
        multivariate=bool(sampler_cfg["multivariate"]),
        group=bool(sampler_cfg["group"]),
        n_startup_trials=int(sampler_cfg["startup_trials"]),
    )
    pruning_cfg = search["pruning"]
    pruner = optuna.pruners.MedianPruner(
        n_startup_trials=int(pruning_cfg["startup_trials"]),
        n_warmup_steps=int(pruning_cfg["warmup_folds"]),
    )
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    study = optuna.create_study(
        study_name=f"AR-0004-{cfg['specification_hash'][:16]}",
        direction="maximize",
        sampler=sampler,
        pruner=pruner,
        storage=f"sqlite:///{storage_path.resolve()}",
        load_if_exists=True,
    )

    def objective(trial: Any) -> float:
        parameters = _suggest_parameters(trial, cfg)
        fold_metrics: list[FoldEvaluation] = []
        for step, fold_spec in enumerate(cfg["walk_forward"]["tuning_folds"]):
            partial = _evaluate_folds(
                cfg,
                built.frame,
                parameters,
                [fold_spec],
                seed=int(sampler_cfg["seed"]),
                identity=(
                    f"tuning-trial-{trial.number:06d}-"
                    f"{fold_spec['fold_id']}"
                ),
                retain_predictions=False,
            )
            if partial.status != "COMPLETED":
                raise AR0004RuntimeError(partial.failure_reason or "invalid tuning fold")
            fold_metrics.extend(partial.fold_metrics)
            trial.report(float(partial.fold_metrics[0].mean_rank_ic), step=step)
            if bool(pruning_cfg["enabled"]) and trial.should_prune():
                raise optuna.TrialPruned()
        fold_ics = [float(item.mean_rank_ic) for item in fold_metrics]
        worst = min(fold_ics)
        metrics = {
            "objective": (
                float(np.mean(fold_ics))
                - 0.50 * float(np.std(fold_ics, ddof=0))
                - 0.25 * max(0.0, -worst)
            ),
            "mean_rank_correlation": float(np.mean(fold_ics)),
            "median_fold_rank_correlation": float(np.median(fold_ics)),
            "worst_fold_rank_correlation": worst,
            "fold_rank_dispersion": float(np.std(fold_ics, ddof=0)),
            "positive_fold_count": sum(value > 0.0 for value in fold_ics),
            "rmse": float(np.mean([item.rmse for item in fold_metrics])),
            "stressed_top_bottom_return": float(
                np.mean([item.stressed_top_bottom_return for item in fold_metrics])
            ),
            "observation_count": sum(item.eligible_test_rows for item in fold_metrics),
            "oos_rows": sum(item.oos_prediction_rows for item in fold_metrics),
        }
        metrics["oos_coverage"] = float(
            metrics["oos_rows"] / metrics["observation_count"]
        )
        metrics["missing_rate"] = 1.0 - metrics["oos_coverage"]
        for name, value in metrics.items():
            if value is not None and isinstance(value, (int, float)) and isfinite(float(value)):
                trial.set_user_attr(name, value)
        trial.set_user_attr("fold_metrics", [item.to_dict() for item in fold_metrics])
        trial.set_user_attr("candidate_parameters", parameters)
        return float(metrics["objective"])

    target_trials = int(search["trials"])
    finished = sum(
        trial.state.name in {"COMPLETE", "PRUNED", "FAIL"} for trial in study.trials
    )
    remaining = max(0, target_trials - finished)
    if remaining:
        study.optimize(
            objective,
            n_trials=remaining,
            n_jobs=int(search["parallel_jobs"]),
            catch=(AR0004RuntimeError, ValueError),
            gc_after_trial=True,
        )
    rows: list[dict[str, Any]] = []
    for trial in study.trials:
        candidate = dict(trial.user_attrs.get("candidate_parameters", {}) or {})
        rows.append(
            {
                "trial_number": int(trial.number),
                "state": trial.state.name,
                "objective": trial.value,
                **candidate,
                "fold_metrics": trial.user_attrs.get("fold_metrics"),
            }
        )
    return study, pd.DataFrame(rows)


def _top_screening_parameters(study: Any, *, count: int) -> list[dict[str, Any]]:
    complete = [
        trial
        for trial in study.trials
        if trial.state.name == "COMPLETE" and trial.value is not None and isfinite(float(trial.value))
    ]
    complete.sort(key=lambda trial: (-float(trial.value), int(trial.number)))
    if len(complete) < count:
        raise AR0004RuntimeError(
            f"Only {len(complete)} completed tuning trials; {count} are required."
        )
    return [dict(trial.user_attrs["candidate_parameters"]) for trial in complete[:count]]


def _ensemble_evaluation(
    cfg: Mapping[str, Any], members: Sequence[CandidateEvaluation]
) -> CandidateEvaluation:
    if not members or any(member.predictions is None for member in members):
        raise AR0004RuntimeError("AR-0004 ensemble members require retained OOS predictions.")
    horizon = int(members[0].parameters["horizon_bars"])
    if any(int(member.parameters["horizon_bars"]) != horizon for member in members):
        raise AR0004RuntimeError("AR-0004 ensemble members must share one horizon.")
    identity_columns = ["timestamp", "asset_id", "fold_id"]
    first = members[0].predictions.copy()
    assert first is not None
    values = first[identity_columns + ["target"]].copy()
    prediction_columns: list[str] = []
    for index, member in enumerate(members):
        assert member.predictions is not None
        name = f"prediction_{index}"
        prediction_columns.append(name)
        part = member.predictions[identity_columns + ["prediction"]].rename(
            columns={"prediction": name}
        )
        values = values.merge(part, on=identity_columns, how="inner", validate="one_to_one")
    values["prediction"] = values[prediction_columns].mean(axis=1)
    source = members[0].predictions
    assert source is not None
    extra = source[
        identity_columns
        + [
            f"long_return_h{horizon}_cost_1_5",
            f"short_return_h{horizon}_cost_1_5",
            "trained_without_this_row",
            "is_oos",
            "model_fit_end_timestamp",
        ]
    ]
    values = values.merge(extra, on=identity_columns, how="inner", validate="one_to_one")
    fold_metrics: list[FoldEvaluation] = []
    timelines: list[pd.DataFrame] = []
    for fold_id, group in values.groupby("fold_id", sort=True):
        rank_rows = _rank_ic_rows(
            group,
            minimum_assets=int(cfg["screening_evaluation"]["minimum_assets_per_timestamp"]),
        )
        rank_rows["fold_id"] = fold_id
        timelines.append(rank_rows)
        member_fold = next(
            item for item in members[0].fold_metrics if item.fold_id == fold_id
        )
        fold_metrics.append(
            FoldEvaluation(
                fold_id=fold_id,
                train_start=member_fold.train_start,
                model_fit_end=member_fold.model_fit_end,
                test_start=member_fold.test_start,
                test_end=member_fold.test_end,
                train_rows=sum(
                    next(item for item in member.fold_metrics if item.fold_id == fold_id).train_rows
                    for member in members
                ),
                eligible_test_rows=int(len(group)),
                oos_prediction_rows=int(len(group)),
                rank_ic_periods=int(len(rank_rows)),
                mean_rank_ic=float(rank_rows["rank_ic"].mean()),
                rmse=sqrt(float(np.mean(np.square(group["prediction"] - group["target"])))),
                stressed_top_bottom_return=_directional_tail_return(
                    group,
                    horizon=horizon,
                    quantile_fraction=float(cfg["screening_evaluation"]["top_fraction"]),
                ),
            )
        )
    fold_ics = [float(item.mean_rank_ic) for item in fold_metrics]
    tail = [float(item.stressed_top_bottom_return) for item in fold_metrics]
    parameters = dict(members[0].parameters)
    parameters.update(
        {
            "candidate_kind": "ensemble",
            "source_trial_number": -1,
            "ensemble_member_trials": [
                int(member.parameters["source_trial_number"]) for member in members
            ],
        }
    )
    return CandidateEvaluation(
        identity="screening-ensemble-top-k",
        parameters=parameters,
        status="COMPLETED",
        failure_reason=None,
        fold_metrics=fold_metrics,
        rank_ic_timeline=pd.concat(timelines, ignore_index=True),
        metrics={
            "mean_rank_correlation": float(np.mean(fold_ics)),
            "median_fold_rank_correlation": float(np.median(fold_ics)),
            "worst_fold_rank_correlation": min(fold_ics),
            "fold_rank_dispersion": float(np.std(fold_ics, ddof=0)),
            "positive_fold_count": sum(value > 0.0 for value in fold_ics),
            "rmse": float(np.mean([item.rmse for item in fold_metrics])),
            "stressed_top_bottom_return": float(np.mean(tail)),
            "observation_count": int(len(values)),
            "oos_rows": int(len(values)),
            "oos_coverage": 1.0,
            "missing_rate": 0.0,
        },
        predictions=values,
    )


def _apply_screening_inference(
    cfg: Mapping[str, Any], evaluations: Sequence[CandidateEvaluation]
) -> None:
    inference = cfg["inference"]
    raw_p: list[float] = []
    for evaluation in evaluations:
        if evaluation.status != "COMPLETED" or evaluation.rank_ic_timeline.empty:
            raw_p.append(1.0)
            continue
        observed = evaluation.rank_ic_timeline.sort_values("timestamp")
        fold_specs = cfg["walk_forward"]["screening_folds"]
        timeline = pd.DataFrame(
            {
                "timestamp": pd.date_range(
                    start=fold_specs[0]["test_start"],
                    end=pd.Timestamp(fold_specs[-1]["test_end"]) - BAR_DELTA,
                    freq="30min",
                    tz="UTC",
                )
            }
        )
        timeline["fold_id"] = ""
        for fold in fold_specs:
            mask = timeline["timestamp"].ge(pd.Timestamp(fold["test_start"])) & timeline[
                "timestamp"
            ].lt(pd.Timestamp(fold["test_end"]))
            timeline.loc[mask, "fold_id"] = str(fold["fold_id"])
        timeline = timeline.merge(
            observed[["timestamp", "rank_ic"]],
            on="timestamp",
            how="left",
            validate="one_to_one",
        )
        values = timeline["rank_ic"].to_numpy(dtype=float)
        eligible = np.isfinite(values)
        fold_codes = pd.Categorical(timeline["fold_id"]).codes.astype(int)
        years = pd.to_datetime(timeline["timestamp"], utc=True).dt.year.to_numpy(dtype=int)
        try:
            hac = newey_west_conditional_mean_summary(
                values,
                condition=np.ones(len(values), dtype=bool),
                eligible=eligible,
                continuity_segment_ids=fold_codes,
                stratum_ids=years,
                lag_bars=int(inference["hac_lag_bars"]),
            )
            bootstrap_cfg = inference["bootstrap"]
            bootstrap = segmented_moving_block_bootstrap_summary(
                values,
                condition=np.ones(len(values), dtype=bool),
                eligible=eligible,
                continuity_segment_ids=fold_codes,
                stratum_ids=years,
                block_length_bars=int(bootstrap_cfg["block_length_bars"]),
                resamples=int(bootstrap_cfg["resamples"]),
                confidence_level=float(bootstrap_cfg["confidence_level"]),
                minimum_valid_resample_fraction=float(
                    bootstrap_cfg["minimum_valid_resample_fraction"]
                ),
                seed=stable_hypothesis_seed(int(bootstrap_cfg["seed"]), evaluation.identity),
            )
            evaluation.metrics["hac_p_value"] = float(hac.p_value)
            evaluation.metrics["bootstrap_confidence_lower"] = float(bootstrap.confidence_lower)
            evaluation.metrics["bootstrap_confidence_upper"] = float(bootstrap.confidence_upper)
            raw_p.append(float(hac.p_value))
        except Exception as exc:
            evaluation.status = "INVALID"
            evaluation.failure_reason = f"inference_failure:{type(exc).__name__}:{exc}"
            raw_p.append(1.0)
    adjusted = adjust_pvalues(
        raw_p,
        method="BY",
        total_hypotheses=int(inference["screening_family_size"]),
        missing_hypothesis_p_value=1.0,
    )
    for evaluation, value in zip(evaluations, adjusted):
        evaluation.metrics["global_by_p_value"] = float(value)


def run_ar0004_tournament(
    cfg: Mapping[str, Any], built: AR0004BuiltPanel, *, study_storage: Path
) -> dict[str, Any]:
    """Tune without screening access, freeze finalists, then screen them once."""

    study, tuning_rows = run_tuning_search(cfg, built, storage_path=study_storage)
    top_parameters = _top_screening_parameters(
        study, count=int(cfg["model_search"]["top_trials_for_screening"])
    )
    best_horizon = int(top_parameters[0]["horizon_bars"])
    ensemble_parameters = [
        parameters for parameters in top_parameters if int(parameters["horizon_bars"]) == best_horizon
    ][: int(cfg["model_search"]["ensemble_top_k_same_horizon"])]
    if len(ensemble_parameters) != int(cfg["model_search"]["ensemble_top_k_same_horizon"]):
        raise AR0004RuntimeError("Insufficient same-horizon finalists for the frozen ensemble.")
    ensemble_numbers = {int(item["source_trial_number"]) for item in ensemble_parameters}
    evaluations: list[CandidateEvaluation] = []
    ensemble_members: list[CandidateEvaluation] = []
    for index, parameters in enumerate(top_parameters):
        retain = int(parameters["source_trial_number"]) in ensemble_numbers
        evaluation = _evaluate_folds(
            cfg,
            built.frame,
            parameters,
            cfg["walk_forward"]["screening_folds"],
            seed=int(cfg["model_search"]["sampler"]["seed"]),
            identity=f"screening-model-{index:02d}-trial-{parameters['source_trial_number']}",
            retain_predictions=retain,
        )
        evaluations.append(evaluation)
        if retain:
            ensemble_members.append(evaluation)
    evaluations.append(_ensemble_evaluation(cfg, ensemble_members))
    if len(evaluations) != int(cfg["inference"]["screening_family_size"]):
        raise AR0004RuntimeError("AR-0004 screening family cardinality drifted.")
    _apply_screening_inference(cfg, evaluations)
    breadth = {
        "requested_tuning_trials": int(cfg["model_search"]["trials"]),
        "tuning_trials_recorded": int(len(study.trials)),
        "tuning_completed": sum(trial.state.name == "COMPLETE" for trial in study.trials),
        "tuning_pruned": sum(trial.state.name == "PRUNED" for trial in study.trials),
        "tuning_failed": sum(trial.state.name == "FAIL" for trial in study.trials),
        "screening_alternatives": len(evaluations),
        "screening_completed": sum(item.status == "COMPLETED" for item in evaluations),
        "screening_invalid": sum(item.status != "COMPLETED" for item in evaluations),
        "ensemble_members": len(ensemble_members),
    }
    return {
        "study": study,
        "tuning_rows": tuning_rows,
        "evaluations": evaluations,
        "search_breadth": breadth,
        "study_storage": study_storage,
    }


def trial_identity(parameters: Mapping[str, Any]) -> str:
    digest, _ = compute_config_hash(dict(parameters))
    return f"ar0004-trial-{digest[:20]}"


def materialize_screening_predictions(
    cfg: Mapping[str, Any],
    built: AR0004BuiltPanel,
    evaluation: CandidateEvaluation,
) -> pd.DataFrame:
    """Deterministically reproduce OOS rows only for a selected alternative."""

    if evaluation.predictions is not None:
        return evaluation.predictions.copy()
    reproduced = _evaluate_folds(
        cfg,
        built.frame,
        evaluation.parameters,
        cfg["walk_forward"]["screening_folds"],
        seed=int(cfg["model_search"]["sampler"]["seed"]),
        identity=evaluation.identity,
        retain_predictions=True,
    )
    if reproduced.status != "COMPLETED" or reproduced.predictions is None:
        raise AR0004RuntimeError(
            "Selected AR-0004 predictions could not be reproduced: "
            f"{reproduced.failure_reason}"
        )
    return reproduced.predictions


__all__ = [
    "AR0004BuiltPanel",
    "AR0004RuntimeError",
    "CandidateEvaluation",
    "FoldEvaluation",
    "build_ar0004_panel",
    "materialize_screening_predictions",
    "run_ar0004_tournament",
    "trial_identity",
]
