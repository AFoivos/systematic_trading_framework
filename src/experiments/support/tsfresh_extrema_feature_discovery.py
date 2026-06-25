from __future__ import annotations

import math
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import numpy as np
import pandas as pd

from src.evaluation.diagnostics import (
    aggregate_feature_importance,
    summarize_feature_family_counts,
    summarize_feature_importance_stability,
)
from src.evaluation.model_metrics import (
    empty_classification_metrics,
    empty_regression_metrics,
    empty_volatility_metrics,
)
from src.evaluation.time_splits import (
    assert_no_forward_label_leakage,
    build_time_splits,
    trim_train_indices_for_horizon,
)
from src.models.common.runtime import infer_feature_columns


_LABEL_BY_CODE = {
    0: "neither",
    1: "local_top",
    2: "local_bottom",
}
_CODE_BY_LABEL = {label: code for code, label in _LABEL_BY_CODE.items()}
_TSFRESH_FEATURE_PRESETS = {"minimal", "efficient", "comprehensive"}
_TSFRESH_RESEARCH_LABEL_COL = "tsfresh_extrema_label"
_TSFRESH_RESEARCH_LABEL_CODE_COL = "tsfresh_extrema_label_code"
_TSFRESH_RESEARCH_ELIGIBLE_COL = "tsfresh_extrema_eligible"


def _load_tsfresh_bindings() -> dict[str, Any]:
    try:
        from tsfresh import extract_features
        from tsfresh.feature_extraction import (
            ComprehensiveFCParameters,
            EfficientFCParameters,
            MinimalFCParameters,
        )
        from tsfresh.feature_selection import select_features
        from tsfresh.feature_selection.relevance import calculate_relevance_table
    except Exception as exc:
        raise ImportError(
            "tsfresh extrema discovery requires the optional 'tsfresh' dependency. "
            "Install tsfresh to use model.kind='tsfresh_extrema_feature_discovery'."
        ) from exc

    try:
        tsfresh_version = version("tsfresh")
    except PackageNotFoundError:
        tsfresh_version = None

    return {
        "extract_features": extract_features,
        "select_features": select_features,
        "calculate_relevance_table": calculate_relevance_table,
        "feature_preset_factories": {
            "minimal": MinimalFCParameters,
            "efficient": EfficientFCParameters,
            "comprehensive": ComprehensiveFCParameters,
        },
        "version": tsfresh_version,
    }


def _require_datetime_index(df: pd.DataFrame) -> pd.DatetimeIndex:
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("tsfresh extrema discovery requires a DatetimeIndex.")
    if not df.index.is_monotonic_increasing:
        raise ValueError("tsfresh extrema discovery requires the input index to be sorted ascending.")
    if df.index.has_duplicates:
        raise ValueError("tsfresh extrema discovery requires a unique DatetimeIndex.")
    return df.index


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or int(value) <= 0:
        raise ValueError(f"{field} must be a positive integer.")
    return int(value)


def _summarize_named_labels(labels: pd.Series) -> dict[str, Any]:
    series = pd.Series(labels, copy=False).dropna().astype(str)
    if series.empty:
        return {
            "labeled_rows": 0,
            "class_counts": {},
            "class_rates": {},
        }

    counts = series.value_counts().sort_index()
    total = int(counts.sum())
    return {
        "labeled_rows": total,
        "class_counts": {str(label): int(count) for label, count in counts.items()},
        "class_rates": {str(label): float(count / total) for label, count in counts.items()},
    }


def _build_future_extrema_labels(
    df: pd.DataFrame,
    *,
    high_col: str,
    low_col: str,
    label_horizon: int,
) -> pd.Series:
    horizon = _positive_int(label_horizon, field="label_horizon")
    for column in (high_col, low_col):
        if column not in df.columns:
            raise KeyError(f"Missing column for tsfresh extrema labels: {column}")

    high = pd.to_numeric(df[high_col], errors="coerce").astype(float)
    low = pd.to_numeric(df[low_col], errors="coerce").astype(float)
    labels = pd.Series(pd.NA, index=df.index, dtype="object")

    last_anchor = len(df) - horizon
    for anchor in range(last_anchor):
        future_high = high.iloc[anchor + 1 : anchor + horizon + 1]
        future_low = low.iloc[anchor + 1 : anchor + horizon + 1]
        current_high = float(high.iloc[anchor])
        current_low = float(low.iloc[anchor])
        if (
            not np.isfinite(current_high)
            or not np.isfinite(current_low)
            or future_high.dropna().empty
            or future_low.dropna().empty
        ):
            continue

        is_top = bool(current_high > float(future_high.max()))
        is_bottom = bool(current_low < float(future_low.min()))
        if is_top and not is_bottom:
            labels.iloc[anchor] = "local_top"
        elif is_bottom and not is_top:
            labels.iloc[anchor] = "local_bottom"
        else:
            labels.iloc[anchor] = "neither"

    return labels.rename("tsfresh_extrema_label")


def _build_pit_window_manifest(
    index: pd.DatetimeIndex,
    *,
    window_size: int,
    label_horizon: int,
) -> pd.DataFrame:
    window = _positive_int(window_size, field="window_size")
    horizon = _positive_int(label_horizon, field="label_horizon")
    if len(index) < window + horizon:
        raise ValueError(
            "Not enough rows to build tsfresh extrema discovery windows. "
            f"Need at least window_size + label_horizon = {window + horizon} rows."
        )

    rows: list[dict[str, Any]] = []
    for anchor_position in range(window - 1, len(index) - horizon):
        rows.append(
            {
                "anchor_id": int(anchor_position),
                "anchor_position": int(anchor_position),
                "anchor_timestamp": index[anchor_position],
                "feature_start_position": int(anchor_position - window + 1),
                "feature_end_position": int(anchor_position),
                "label_start_position": int(anchor_position + 1),
                "label_end_position": int(anchor_position + horizon),
            }
        )
    return pd.DataFrame(rows)


def _build_long_window_frame(
    df: pd.DataFrame,
    *,
    source_cols: list[str],
    window_manifest: pd.DataFrame,
) -> pd.DataFrame:
    numeric = df.loc[:, source_cols].apply(pd.to_numeric, errors="coerce").astype(float)
    frames: list[pd.DataFrame] = []
    for row in window_manifest.itertuples(index=False):
        sample_id = int(row.anchor_id)
        start = int(row.feature_start_position)
        end = int(row.feature_end_position) + 1
        window = numeric.iloc[start:end]
        offsets = np.arange(len(window), dtype=int)
        for column in source_cols:
            values = window[column].to_numpy(dtype=float, copy=False)
            finite_mask = np.isfinite(values)
            if not bool(finite_mask.any()):
                continue
            frames.append(
                pd.DataFrame(
                    {
                        "id": sample_id,
                        "time": offsets[finite_mask],
                        "kind": str(column),
                        "value": values[finite_mask],
                    }
                )
            )
    if not frames:
        raise ValueError("No PIT-safe rolling windows were produced for tsfresh extraction.")
    return pd.concat(frames, ignore_index=True)


def _resolve_source_feature_columns(
    df: pd.DataFrame,
    *,
    model_cfg: dict[str, Any],
    protected_cols: set[str],
    include_raw_ohlcv: bool = False,
) -> list[str]:
    if not model_cfg.get("feature_cols") and not model_cfg.get("feature_selectors"):
        source_cols = _infer_broad_numeric_source_columns(
            df,
            protected_cols=protected_cols,
        )
        if source_cols:
            return source_cols

    source_cols = infer_feature_columns(
        df,
        explicit_cols=model_cfg.get("feature_cols"),
        feature_selectors=model_cfg.get("feature_selectors"),
        exclude=protected_cols,
    )
    if not source_cols:
        raise ValueError("No numeric source feature columns resolved for tsfresh extrema discovery.")
    resolved = [str(col) for col in source_cols]
    if not include_raw_ohlcv:
        return resolved

    appended = list(resolved)
    for raw_col in ("open", "high", "low", "close", "volume"):
        if raw_col in df.columns and raw_col not in appended:
            appended.append(raw_col)
    return appended


def _infer_broad_numeric_source_columns(
    df: pd.DataFrame,
    *,
    protected_cols: set[str],
) -> list[str]:
    exclude_set = set(protected_cols)
    exclude_set.update(
        {
            "adj_close",
            _TSFRESH_RESEARCH_LABEL_COL,
            _TSFRESH_RESEARCH_LABEL_CODE_COL,
            _TSFRESH_RESEARCH_ELIGIBLE_COL,
        }
    )
    numeric_cols = list(df.select_dtypes(include=["number"]).columns)
    selected: list[str] = []
    for column in numeric_cols:
        if column in exclude_set:
            continue
        if column.startswith(("signal_", "pred_", "target_", "pre_local_")):
            continue
        if "raw_local_" in str(column):
            continue
        selected.append(str(column))
    return selected


def _resolve_fc_parameters(
    bindings: dict[str, Any],
    *,
    preset: str,
) -> Any:
    normalized = str(preset).strip().lower()
    if normalized not in _TSFRESH_FEATURE_PRESETS:
        allowed = ", ".join(sorted(_TSFRESH_FEATURE_PRESETS))
        raise ValueError(f"Unsupported tsfresh feature preset: {preset!r}. Allowed presets: {allowed}.")
    factory = dict(bindings.get("feature_preset_factories", {}) or {}).get(normalized)
    if factory is None:
        raise ValueError(f"Missing tsfresh feature preset factory for {normalized!r}.")
    return factory()


def _normalize_fc_parameter_mapping(
    raw_mapping: Any,
    *,
    field: str,
) -> dict[str, Any]:
    if raw_mapping is None:
        return {}
    if not isinstance(raw_mapping, dict):
        raise ValueError(f"{field} must be a mapping of calculator names to parameter specs.")

    normalized: dict[str, Any] = {}
    for calculator_name, raw_spec in raw_mapping.items():
        name = str(calculator_name).strip()
        if not name:
            raise ValueError(f"{field} contains an empty calculator name.")
        if raw_spec is None:
            normalized[name] = None
            continue
        if isinstance(raw_spec, dict):
            normalized[name] = [{str(key): value for key, value in raw_spec.items()}]
            continue
        if not isinstance(raw_spec, list):
            raise ValueError(
                f"{field}.{name} must be null, a mapping, or a list of mappings."
            )
        params_list: list[dict[str, Any]] = []
        for idx, item in enumerate(raw_spec):
            if not isinstance(item, dict):
                raise ValueError(f"{field}.{name}[{idx}] must be a mapping.")
            params_list.append({str(key): value for key, value in item.items()})
        normalized[name] = params_list
    return normalized


def _resolve_kind_to_fc_parameters(
    params: dict[str, Any],
) -> dict[str, Any]:
    raw_mapping = params.get("kind_to_fc_parameters")
    if raw_mapping in (None, {}):
        return {}
    if not isinstance(raw_mapping, dict):
        raise ValueError("model.params.kind_to_fc_parameters must be a mapping.")

    normalized: dict[str, Any] = {}
    for raw_kind, raw_kind_mapping in raw_mapping.items():
        kind = str(raw_kind).strip()
        if not kind:
            raise ValueError("model.params.kind_to_fc_parameters contains an empty kind name.")
        normalized[kind] = _normalize_fc_parameter_mapping(
            raw_kind_mapping,
            field=f"model.params.kind_to_fc_parameters.{kind}",
        )
    return normalized


def _split_tsfresh_feature_name(feature_name: str) -> tuple[str, str]:
    feature = str(feature_name)
    if "__" not in feature:
        return feature, ""
    kind, remainder = feature.split("__", 1)
    return kind, remainder


def _feature_detail_rows(feature_names: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for feature_name in sorted({str(name) for name in feature_names if str(name).strip()}):
        source_kind, calculator = _split_tsfresh_feature_name(feature_name)
        rows.append(
            {
                "feature": feature_name,
                "source_kind": source_kind,
                "calculator": calculator,
            }
        )
    return rows


def _project_feature_frame_to_full_index(
    feature_frame: pd.DataFrame,
    *,
    full_index: pd.DatetimeIndex,
) -> pd.DataFrame:
    if feature_frame.empty:
        return pd.DataFrame(index=full_index)
    projected = feature_frame.copy()
    anchor_positions = np.asarray(projected.index, dtype=int)
    projected.index = full_index.take(anchor_positions)
    projected.index.name = full_index.name
    return projected.reindex(full_index)


def _build_research_feature_dataset(
    df: pd.DataFrame,
    *,
    full_feature_frame: pd.DataFrame,
    eligible_labels_named: pd.Series,
    eligible_labels_code: pd.Series,
    eligible_index: pd.DatetimeIndex,
) -> pd.DataFrame:
    out = df.copy()
    out = out.join(full_feature_frame, how="left")
    out[_TSFRESH_RESEARCH_LABEL_COL] = eligible_labels_named.astype("object")
    out[_TSFRESH_RESEARCH_LABEL_CODE_COL] = eligible_labels_code.astype("float32")
    out[_TSFRESH_RESEARCH_ELIGIBLE_COL] = pd.Series(out.index.isin(eligible_index), index=out.index, dtype=bool)
    return out


def _prepare_fold_feature_matrices(
    full_feature_frame: pd.DataFrame,
    *,
    train_idx: np.ndarray,
    test_idx: np.ndarray,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    X_train = full_feature_frame.iloc[train_idx].copy()
    X_test = full_feature_frame.iloc[test_idx].copy()

    X_train = X_train.replace([np.inf, -np.inf], np.nan)
    X_test = X_test.replace([np.inf, -np.inf], np.nan)
    raw_feature_count = int(X_train.shape[1])

    non_empty_cols = [col for col in X_train.columns if bool(X_train[col].notna().any())]
    X_train = X_train.loc[:, non_empty_cols]
    X_test = X_test.loc[:, non_empty_cols]
    dropped_all_nan_cols = [str(col) for col in full_feature_frame.columns if col not in non_empty_cols]
    dropped_all_nan_count = int(raw_feature_count - len(non_empty_cols))

    constant_cols = [
        str(col)
        for col in X_train.columns
        if int(X_train[col].nunique(dropna=True)) <= 1
    ]
    if constant_cols:
        X_train = X_train.drop(columns=constant_cols)
        X_test = X_test.drop(columns=constant_cols, errors="ignore")
    dropped_constant_count = int(len(constant_cols))

    if X_train.empty:
        return X_train, X_test, {
            "raw_feature_count": raw_feature_count,
            "dropped_all_nan_count": dropped_all_nan_count,
            "dropped_constant_count": dropped_constant_count,
            "dropped_all_nan_features": dropped_all_nan_cols,
            "dropped_constant_features": constant_cols,
            "dropped_still_nan_features": [],
        }

    train_medians = X_train.median(axis=0, skipna=True)
    X_train = X_train.fillna(train_medians)
    X_test = X_test.fillna(train_medians)

    still_nan_cols = [col for col in X_train.columns if bool(X_train[col].isna().any())]
    if still_nan_cols:
        X_train = X_train.drop(columns=still_nan_cols)
        X_test = X_test.drop(columns=still_nan_cols, errors="ignore")

    return X_train.astype(float), X_test.astype(float), {
        "raw_feature_count": raw_feature_count,
        "dropped_all_nan_count": dropped_all_nan_count,
        "dropped_constant_count": dropped_constant_count + int(len(still_nan_cols)),
        "dropped_all_nan_features": dropped_all_nan_cols,
        "dropped_constant_features": constant_cols,
        "dropped_still_nan_features": [str(col) for col in still_nan_cols],
    }


def _importance_rows_from_relevance_table(
    relevance_table: pd.DataFrame,
    *,
    selected_features: set[str],
) -> list[dict[str, Any]]:
    if relevance_table.empty:
        return []

    table = relevance_table.copy()
    if "feature" not in table.columns:
        table = table.reset_index().rename(columns={table.columns[0]: "feature"})

    p_value_cols = [str(col) for col in table.columns if str(col).startswith("p_value")]
    relevant_cols = [str(col) for col in table.columns if str(col).startswith("relevant")]
    if not p_value_cols and "p_value" in table.columns:
        p_value_cols = ["p_value"]
    if not relevant_cols and "relevant" in table.columns:
        relevant_cols = ["relevant"]

    scored_rows: list[dict[str, Any]] = []
    for row in table.to_dict(orient="records"):
        feature = str(row.get("feature"))
        min_p_value = math.nan
        if p_value_cols:
            p_values = [float(row.get(col)) for col in p_value_cols if row.get(col) is not None]
            finite_p = [value for value in p_values if math.isfinite(value)]
            if finite_p:
                min_p_value = float(min(finite_p))
        importance = 0.0
        if math.isfinite(min_p_value):
            importance = float(max(0.0, -math.log10(max(min_p_value, 1.0e-300))))
        selected = feature in selected_features
        relevant = selected
        if relevant_cols:
            relevant = bool(any(bool(row.get(col)) for col in relevant_cols))
        scored_rows.append(
            {
                "feature": feature,
                "importance": importance,
                "min_p_value": min_p_value if math.isfinite(min_p_value) else None,
                "selected": bool(selected),
                "relevant": bool(relevant),
                "source": "tsfresh_relevance",
            }
        )

    scored_rows.sort(
        key=lambda item: (
            -float(item.get("importance", 0.0) or 0.0),
            float(item.get("min_p_value", 1.0) or 1.0),
            str(item.get("feature", "")),
        )
    )
    total_importance = float(sum(float(row["importance"]) for row in scored_rows))
    for rank, row in enumerate(scored_rows, start=1):
        importance = float(row["importance"])
        row["importance_normalized"] = float(importance / total_importance) if total_importance > 0.0 else 0.0
        row["rank"] = int(rank)
    return scored_rows


def _aggregate_selected_feature_details(
    folds: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    bucket: dict[str, dict[str, Any]] = {}
    eligible_folds = 0
    for fold in folds:
        selected_rows = list(fold.get("selected_features", []) or [])
        if not bool(fold.get("selection_executed", False)):
            continue
        eligible_folds += 1
        for row in selected_rows:
            feature = str(row.get("feature"))
            info = bucket.setdefault(
                feature,
                {
                    "feature": feature,
                    "selection_count": 0,
                    "importance_sum": 0.0,
                    "min_p_value_sum": 0.0,
                    "rank_sum": 0.0,
                    "best_rank": None,
                },
            )
            info["selection_count"] += 1
            info["importance_sum"] += float(row.get("importance", 0.0) or 0.0)
            if row.get("min_p_value") is not None:
                info["min_p_value_sum"] += float(row["min_p_value"])
            rank = int(row.get("rank", 0) or 0)
            info["rank_sum"] += rank
            info["best_rank"] = rank if info["best_rank"] is None else min(int(info["best_rank"]), rank)

    if not bucket:
        return []

    rows: list[dict[str, Any]] = []
    for info in bucket.values():
        selection_count = max(int(info["selection_count"]), 1)
        rows.append(
            {
                "feature": str(info["feature"]),
                "selection_count": int(selection_count),
                "selection_rate": float(selection_count / max(eligible_folds, 1)),
                "mean_importance": float(info["importance_sum"] / selection_count),
                "mean_min_p_value": float(info["min_p_value_sum"] / selection_count),
                "mean_rank": float(info["rank_sum"] / selection_count),
                "best_rank": int(info["best_rank"]) if info["best_rank"] is not None else None,
            }
        )
    rows.sort(
        key=lambda item: (
            -float(item["selection_rate"]),
            float(item["mean_rank"]),
            -float(item["mean_importance"]),
            str(item["feature"]),
        )
    )
    for rank, row in enumerate(rows, start=1):
        row["rank"] = int(rank)
    return rows


def _aggregate_dropped_feature_details(
    fold_feature_cleaning: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    drop_keys = (
        ("dropped_all_nan_features", "all_nan_in_train"),
        ("dropped_constant_features", "constant_in_train"),
        ("dropped_still_nan_features", "still_nan_after_imputation"),
    )
    bucket: dict[tuple[str, str], dict[str, Any]] = {}
    eligible_folds = max(len(fold_feature_cleaning), 1)

    for row in fold_feature_cleaning:
        fold = int(row.get("fold", 0))
        for field, reason in drop_keys:
            for feature_name in list(row.get(field, []) or []):
                feature = str(feature_name)
                key = (feature, reason)
                source_kind, calculator = _split_tsfresh_feature_name(feature)
                info = bucket.setdefault(
                    key,
                    {
                        "feature": feature,
                        "source_kind": source_kind,
                        "calculator": calculator,
                        "drop_reason": reason,
                        "drop_count": 0,
                        "folds": [],
                    },
                )
                info["drop_count"] += 1
                info["folds"].append(fold)

    if not bucket:
        return []

    rows: list[dict[str, Any]] = []
    for info in bucket.values():
        folds = sorted({int(fold) for fold in list(info.get("folds", []) or [])})
        rows.append(
            {
                "feature": str(info["feature"]),
                "source_kind": str(info["source_kind"]),
                "calculator": str(info["calculator"]),
                "drop_reason": str(info["drop_reason"]),
                "drop_count": int(info["drop_count"]),
                "drop_rate": float(int(info["drop_count"]) / eligible_folds),
                "folds": ",".join(str(fold) for fold in folds),
            }
        )
    rows.sort(
        key=lambda item: (
            str(item["drop_reason"]),
            -float(item["drop_rate"]),
            str(item["feature"]),
        )
    )
    return rows


def train_tsfresh_extrema_feature_discovery(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, None, dict[str, Any]]:
    """
    Train the registered ``tsfresh_extrema_feature_discovery`` model component.
    
    YAML declaration::
    
        model:
          kind: tsfresh_extrema_feature_discovery
          params: {}
    
    Required input columns
    ----------------------
    anchor_timestamp:
        Required dataframe column read directly by this component.
    calculate_relevance_table:
        Required dataframe column read directly by this component.
    extract_features:
        Required dataframe column read directly by this component.
    feature:
        Required dataframe column read directly by this component.
    select_features:
        Required dataframe column read directly by this component.
    test_start:
        Required dataframe column read directly by this component.
    returns_col:
        Optional input column configured by ``returns_col``; used when a value is provided.
    
    Parameters
    ----------
    model_cfg:
        Configuration mapping, usually resolved from YAML before this
        registered component is called.
    returns_col:
        Input dataframe column name consumed by the component. Default: ``None``.
    """
    del returns_col
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    index = _require_datetime_index(df)
    bindings = _load_tsfresh_bindings()

    model_cfg = dict(model_cfg or {})
    params = dict(model_cfg.get("params", {}) or {})
    high_col = str(params.get("high_col", "high"))
    low_col = str(params.get("low_col", "low"))
    window_size = _positive_int(params.get("window_size", 48), field="model.params.window_size")
    label_horizon = _positive_int(params.get("label_horizon", 8), field="model.params.label_horizon")
    feature_preset = str(params.get("feature_preset", "minimal")).strip().lower()
    n_jobs = _positive_int(params.get("n_jobs", 1), field="model.params.n_jobs")
    chunksize = params.get("chunksize")
    if chunksize is not None:
        chunksize = _positive_int(chunksize, field="model.params.chunksize")
    fdr_level = float(params.get("fdr_level", 0.05))
    if not 0.0 < fdr_level <= 1.0:
        raise ValueError("model.params.fdr_level must be in (0,1].")
    hypotheses_independent = bool(params.get("hypotheses_independent", False))
    n_significant = _positive_int(params.get("n_significant", 1), field="model.params.n_significant")
    disable_progressbar = bool(params.get("disable_progressbar", True))
    show_warnings = bool(params.get("show_warnings", False))
    include_raw_ohlcv = bool(params.get("include_raw_ohlcv", False))
    kind_to_fc_parameters = _resolve_kind_to_fc_parameters(params)

    protected_cols = {high_col, low_col, "open", "close", "volume"}
    source_cols = _resolve_source_feature_columns(
        df,
        model_cfg=model_cfg,
        protected_cols=protected_cols,
        include_raw_ohlcv=include_raw_ohlcv,
    )
    labels_named = _build_future_extrema_labels(
        df,
        high_col=high_col,
        low_col=low_col,
        label_horizon=label_horizon,
    )
    labels_code = labels_named.map(_CODE_BY_LABEL).astype("float32")

    window_manifest = _build_pit_window_manifest(
        index,
        window_size=window_size,
        label_horizon=label_horizon,
    )
    long_window_frame = _build_long_window_frame(
        df,
        source_cols=source_cols,
        window_manifest=window_manifest,
    )

    fc_parameters = _resolve_fc_parameters(bindings, preset=feature_preset)
    extracted = bindings["extract_features"](
        long_window_frame,
        column_id="id",
        column_sort="time",
        column_kind="kind",
        column_value="value",
        default_fc_parameters=fc_parameters,
        kind_to_fc_parameters=kind_to_fc_parameters or None,
        n_jobs=n_jobs,
        chunksize=chunksize,
        show_warnings=show_warnings,
        disable_progressbar=disable_progressbar,
        impute_function=None,
    )
    extracted = extracted.sort_index()
    full_feature_frame = _project_feature_frame_to_full_index(
        extracted,
        full_index=index,
    )
    if full_feature_frame.empty or full_feature_frame.shape[1] == 0:
        raise ValueError("tsfresh extraction produced no features.")
    eligible_index = pd.DatetimeIndex(window_manifest["anchor_timestamp"], tz=index.tz, name=index.name)
    eligible_mask = pd.Series(index=index, data=index.isin(eligible_index))
    eligible_labels_named = labels_named.where(eligible_mask, other=pd.NA)
    eligible_labels_code = labels_code.where(eligible_mask, other=np.nan)
    output_df = _build_research_feature_dataset(
        df,
        full_feature_frame=full_feature_frame,
        eligible_labels_named=eligible_labels_named,
        eligible_labels_code=eligible_labels_code,
        eligible_index=eligible_index,
    )

    split_cfg = dict(model_cfg.get("split", {}) or {})
    method = str(split_cfg.get("method", "time"))
    splits = build_time_splits(
        method=method,
        n_samples=len(df),
        split_cfg=split_cfg,
        target_horizon=label_horizon,
    )

    total_train_rows = 0
    total_eval_rows = 0
    total_trimmed_rows = 0
    total_rows_dropped_missing = 0
    total_dropped_all_nan = 0
    total_dropped_constant = 0
    skipped_folds_insufficient_classes = 0
    skipped_folds_no_features = 0
    fold_feature_importances: list[list[dict[str, Any]]] = []
    train_label_distributions: list[dict[str, Any]] = []
    eval_label_distributions: list[dict[str, Any]] = []
    executed_folds: list[dict[str, Any]] = []
    skipped_folds: list[dict[str, Any]] = []
    fold_feature_cleaning: list[dict[str, Any]] = []

    for split in splits:
        raw_train_idx = split.train_idx
        safe_train_idx = trim_train_indices_for_horizon(
            raw_train_idx,
            test_start=int(split.test_start),
            target_horizon=label_horizon,
        )
        assert_no_forward_label_leakage(
            safe_train_idx,
            test_start=int(split.test_start),
            target_horizon=label_horizon,
        )
        trimmed_rows = int(len(raw_train_idx) - len(safe_train_idx))
        total_trimmed_rows += trimmed_rows

        train_label_raw = labels_code.iloc[safe_train_idx]
        test_label_raw = labels_code.iloc[split.test_idx]
        eligible_train_mask = train_label_raw.notna()
        eligible_test_mask = test_label_raw.notna()
        eligible_train_idx = safe_train_idx[eligible_train_mask.to_numpy(dtype=bool)]
        eligible_test_idx = split.test_idx[eligible_test_mask.to_numpy(dtype=bool)]
        train_rows_raw = int(len(safe_train_idx))
        train_rows = int(len(eligible_train_idx))
        eval_rows = int(len(eligible_test_idx))
        total_rows_dropped_missing += int(train_rows_raw - train_rows)

        if train_rows == 0:
            skipped_folds.append(
                {
                    "fold": int(split.fold),
                    "reason": "no_train_rows_with_labels",
                }
            )
            continue

        X_train, _, cleaning_meta = _prepare_fold_feature_matrices(
            full_feature_frame,
            train_idx=eligible_train_idx,
            test_idx=eligible_test_idx,
        )
        fold_feature_cleaning.append(
            {
                "fold": int(split.fold),
                "raw_feature_count": int(cleaning_meta.get("raw_feature_count", 0) or 0),
                "dropped_all_nan_count": int(cleaning_meta.get("dropped_all_nan_count", 0) or 0),
                "dropped_constant_count": int(cleaning_meta.get("dropped_constant_count", 0) or 0),
                "dropped_all_nan_features": list(cleaning_meta.get("dropped_all_nan_features", []) or []),
                "dropped_constant_features": list(cleaning_meta.get("dropped_constant_features", []) or []),
                "dropped_still_nan_features": list(cleaning_meta.get("dropped_still_nan_features", []) or []),
            }
        )
        total_dropped_all_nan += int(cleaning_meta.get("dropped_all_nan_count", 0) or 0)
        total_dropped_constant += int(cleaning_meta.get("dropped_constant_count", 0) or 0)

        if X_train.empty:
            skipped_folds_no_features += 1
            skipped_folds.append(
                {
                    "fold": int(split.fold),
                    "reason": "no_train_features_after_cleaning",
                }
            )
            continue

        y_train = labels_code.iloc[eligible_train_idx].astype(int)
        y_test_named = labels_named.iloc[eligible_test_idx]
        y_train_named = labels_named.iloc[eligible_train_idx]
        train_label_distribution = _summarize_named_labels(y_train_named)
        eval_label_distribution = _summarize_named_labels(y_test_named)

        if int(y_train.nunique()) < 2:
            skipped_folds_insufficient_classes += 1
            skipped_folds.append(
                {
                    "fold": int(split.fold),
                    "reason": "insufficient_train_classes",
                    "train_label_distribution": train_label_distribution,
                }
            )
            continue

        selected_train = bindings["select_features"](
            X_train,
            y_train,
            ml_task="classification",
            multiclass=True,
            n_significant=n_significant,
            n_jobs=n_jobs,
            show_warnings=show_warnings,
            chunksize=chunksize,
            hypotheses_independent=hypotheses_independent,
            fdr_level=fdr_level,
        )
        selected_features = set(str(col) for col in selected_train.columns)
        relevance_table = bindings["calculate_relevance_table"](
            X_train,
            y_train,
            ml_task="classification",
            multiclass=True,
            n_significant=n_significant,
            n_jobs=n_jobs,
            show_warnings=show_warnings,
            chunksize=chunksize,
            hypotheses_independent=hypotheses_independent,
            fdr_level=fdr_level,
        )
        fold_importance = _importance_rows_from_relevance_table(
            relevance_table,
            selected_features=selected_features,
        )
        fold_feature_importances.append(fold_importance)

        selected_rows = [dict(row) for row in fold_importance if str(row.get("feature")) in selected_features]
        selected_rows.sort(
            key=lambda row: (
                int(row.get("rank", 0) or 0),
                str(row.get("feature", "")),
            )
        )

        total_train_rows += train_rows
        total_eval_rows += eval_rows
        train_label_distributions.append(train_label_distribution)
        eval_label_distributions.append(eval_label_distribution)

        fold_record = {
            "fold": int(split.fold),
            "train_start": int(split.train_start),
            "train_end": int(split.train_end),
            "effective_train_start": int(eligible_train_idx.min()) if len(eligible_train_idx) else None,
            "effective_train_end": int(eligible_train_idx.max() + 1) if len(eligible_train_idx) else None,
            "trimmed_for_horizon_rows": int(trimmed_rows),
            "test_start": int(split.test_start),
            "test_end": int(split.test_end),
            "train_rows_raw": train_rows_raw,
            "train_rows": train_rows,
            "train_rows_dropped_missing": int(train_rows_raw - train_rows),
            "test_rows": int(len(split.test_idx)),
            "test_pred_rows": 0,
            "train_label_distribution": train_label_distribution,
            "eval_label_distribution": eval_label_distribution,
            "classification_metrics": dict(empty_classification_metrics()) | {"evaluation_rows": eval_rows},
            "regression_metrics": empty_regression_metrics(),
            "volatility_metrics": empty_volatility_metrics(),
            "feature_importance": fold_importance,
            "selection_executed": True,
            "selected_features": selected_rows,
            "feature_selection": {
                "available_feature_count": int(X_train.shape[1]),
                "selected_feature_count": int(len(selected_rows)),
            },
            "feature_cleaning": {
                "raw_feature_count": int(cleaning_meta.get("raw_feature_count", X_train.shape[1]) or 0),
                "dropped_all_nan_count": int(cleaning_meta.get("dropped_all_nan_count", 0) or 0),
                "dropped_constant_count": int(cleaning_meta.get("dropped_constant_count", 0) or 0),
            },
        }
        executed_folds.append(fold_record)

    if not executed_folds:
        raise ValueError(
            "tsfresh extrema discovery could not execute any fold. "
            f"Skipped folds: {skipped_folds}"
        )

    aggregated_selected_features = _aggregate_selected_feature_details(executed_folds)
    dropped_feature_details = _aggregate_dropped_feature_details(fold_feature_cleaning)
    selected_feature_names = [str(row["feature"]) for row in aggregated_selected_features]
    extracted_feature_names = [str(col) for col in full_feature_frame.columns]
    label_distribution = {
        "train": _merge_named_label_distributions(train_label_distributions),
        "oos_evaluation": _merge_named_label_distributions(eval_label_distributions),
        "eligible_full": _summarize_named_labels(labels_named.loc[window_manifest["anchor_timestamp"]]),
    }

    feature_selection_meta = {
        "profile": None,
        "enabled_families": [],
        "family_counts": summarize_feature_family_counts(selected_feature_names),
        "source_feature_count": int(len(source_cols)),
        "source_feature_cols": list(source_cols),
        "extracted_feature_count": int(full_feature_frame.shape[1]),
        "extracted_feature_details": _feature_detail_rows(extracted_feature_names),
        "resolved_feature_count": int(full_feature_frame.shape[1]),
        "selected_feature_count": int(len(selected_feature_names)),
        "selected_features": list(selected_feature_names),
        "selected_feature_details": aggregated_selected_features,
        "dropped_feature_details": dropped_feature_details,
        "fold_feature_cleaning": fold_feature_cleaning,
        "window_size": int(window_size),
        "label_horizon": int(label_horizon),
        "feature_preset": feature_preset,
        "include_raw_ohlcv": bool(include_raw_ohlcv),
        "custom_kind_count": int(len(kind_to_fc_parameters)),
        "configured_custom_kinds": sorted(str(kind) for kind in kind_to_fc_parameters),
        "auto_apply_selected_features": False,
    }

    export_feature_dataset = bool(params.get("export_feature_dataset", False))
    export_dataset_path = params.get("export_dataset_path")
    if export_feature_dataset and not isinstance(export_dataset_path, str):
        raise ValueError("model.params.export_dataset_path must be a non-empty string when export is enabled.")

    feature_pipeline_meta = {
        "raw_feature_count": int(len(source_cols)),
        "resolved_feature_count": int(full_feature_frame.shape[1]),
        "active_feature_count": int(full_feature_frame.shape[1]),
        "selected_feature_count": int(len(selected_feature_names)),
        "model_feature_count": int(len(selected_feature_names)),
        "actual_model_feature_count": int(len(selected_feature_names)),
        "reported_feature_count": int(len(selected_feature_names)),
        "dropped_missing_count": int(total_dropped_all_nan),
        "dropped_constant_count": int(total_dropped_constant),
        "dropped_selector_count": 0,
        "final_feature_names": list(selected_feature_names),
    }

    meta = {
        "model_kind": "tsfresh_extrema_feature_discovery",
        "runtime": {
            "dependency": "tsfresh",
            "dependency_version": bindings.get("version"),
        },
        "feature_cols": list(selected_feature_names),
        "feature_selection": feature_selection_meta,
        "feature_pipeline": feature_pipeline_meta,
        "feature_family_counts": summarize_feature_family_counts(selected_feature_names),
        "split_method": method,
        "split_index": int(executed_folds[0]["test_start"]),
        "n_folds": int(len(executed_folds)),
        "folds": executed_folds,
        "skipped_folds": skipped_folds,
        "train_rows": int(total_train_rows),
        "test_pred_rows": 0,
        "oos_rows": int(total_eval_rows),
        "oos_classification_summary": {},
        "oos_regression_summary": {},
        "oos_volatility_summary": {},
        "feature_importance": aggregate_feature_importance(fold_feature_importances),
        "feature_importance_stability": summarize_feature_importance_stability(fold_feature_importances),
        "label_distribution": label_distribution,
        "prediction_diagnostics": {},
        "missing_value_diagnostics": {
            "train_rows_dropped_missing": int(total_rows_dropped_missing),
            "test_rows_missing_features": 0,
            "test_rows_not_candidates": 0,
            "test_rows_without_prediction": 0,
            "folds_with_zero_predictions": 0,
            "folds_skipped_insufficient_classes": int(skipped_folds_insufficient_classes),
            "folds_skipped_no_features": int(skipped_folds_no_features),
        },
        "target": {
            "kind": "future_extrema_multiclass",
            "label_names_by_code": dict(_LABEL_BY_CODE),
            "label_horizon": int(label_horizon),
            "high_col": high_col,
            "low_col": low_col,
            "label_distribution": dict(label_distribution.get("eligible_full", {}) or {}),
            "eligible_rows": int(len(window_manifest)),
        },
        "feature_dataset": {
            "available": True,
            "export_enabled": bool(export_feature_dataset),
            "export_dataset_path": str(export_dataset_path) if isinstance(export_dataset_path, str) else None,
            "feature_count": int(full_feature_frame.shape[1]),
            "feature_name_prefixes": list(source_cols),
            "extracted_feature_names": extracted_feature_names,
            "label_col": _TSFRESH_RESEARCH_LABEL_COL,
            "label_code_col": _TSFRESH_RESEARCH_LABEL_CODE_COL,
            "eligible_col": _TSFRESH_RESEARCH_ELIGIBLE_COL,
            "eligible_rows": int(len(eligible_index)),
        },
        "anti_leakage": {
            "window_size": int(window_size),
            "label_horizon": int(label_horizon),
            "total_trimmed_train_rows": int(total_trimmed_rows),
            "feature_window_uses_future": False,
            "label_horizon_excluded_from_feature_windows": True,
        },
    }
    return output_df, None, meta


def _merge_named_label_distributions(distributions: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    total = 0
    for distribution in distributions:
        payload = dict(distribution or {})
        total += int(payload.get("labeled_rows", 0) or 0)
        for label, count in dict(payload.get("class_counts", {}) or {}).items():
            counts[str(label)] = int(counts.get(str(label), 0)) + int(count)
    if total <= 0:
        return {
            "labeled_rows": 0,
            "class_counts": {},
            "class_rates": {},
        }
    return {
        "labeled_rows": int(total),
        "class_counts": dict(sorted(counts.items(), key=lambda item: item[0])),
        "class_rates": {
            str(label): float(count / total)
            for label, count in sorted(counts.items(), key=lambda item: item[0])
        },
    }


__all__ = [
    "_build_future_extrema_labels",
    "_build_research_feature_dataset",
    "_build_pit_window_manifest",
    "train_tsfresh_extrema_feature_discovery",
]
