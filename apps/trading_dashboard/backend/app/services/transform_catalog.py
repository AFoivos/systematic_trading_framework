from __future__ import annotations

import inspect
import math
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from app.core.paths import get_paths
from app.schemas.market import NamedSeries
from app.schemas.transforms import (
    BuilderDefinition,
    ParameterDefinition,
    TransformSeriesRequest,
    TransformSeriesResponse,
    TransformStepConfig,
    TransformStepResult,
)
from app.services.data_loader import DataLoader
from app.services.schema_mapper import frame_to_series


PROJECT_ROOT = get_paths().project_root
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.experiments.orchestration.feature_stage import apply_feature_steps, apply_signal_step  # noqa: E402
from src.experiments.registry import FEATURE_REGISTRY, SIGNAL_REGISTRY, get_feature_fn, get_signal_fn  # noqa: E402
from src.targets.classifier import build_classifier_target  # noqa: E402
from src.targets.forward_return import build_forward_return_target  # noqa: E402
from src.targets.r_multiple import build_r_multiple_target  # noqa: E402
from src.targets.triple_barrier import build_triple_barrier_target  # noqa: E402


BuilderFn = Callable[..., Any]

TARGET_REGISTRY: dict[str, Callable[[pd.DataFrame, dict[str, Any] | None], tuple[pd.DataFrame, str, str, dict[str, Any]]]] = {
    "forward_return": build_forward_return_target,
    "triple_barrier": build_triple_barrier_target,
    "r_multiple": build_r_multiple_target,
    "classifier": build_classifier_target,
}

TARGET_PARAM_DEFAULTS: dict[str, dict[str, Any]] = {
    "forward_return": {
        "price_col": "close",
        "returns_col": None,
        "returns_type": "simple",
        "horizon": 1,
        "fwd_col": "target_fwd_1",
        "label_col": "label",
        "threshold": 0.0,
        "quantiles": None,
    },
    "triple_barrier": {
        "price_col": "close",
        "open_col": "open",
        "high_col": "high",
        "low_col": "low",
        "returns_col": None,
        "volatility_col": None,
        "label_col": "label",
        "event_ret_col": "tb_event_ret",
        "max_holding": 24,
        "upper_mult": 2.0,
        "lower_mult": 2.0,
        "neutral_label": "drop",
        "tie_break": "closest_to_open",
        "vol_window": 24,
        "min_vol": 1e-4,
        "side_col": None,
        "candidate_col": None,
        "candidate_mode": "all_nonzero",
        "entry_price_mode": "current_close",
        "label_mode": None,
        "add_r_multiple": False,
        "r_col": "tb_event_r",
        "oriented_r_col": "tb_oriented_r",
        "r_clip": None,
    },
    "r_multiple": {
        "candidate_col": "manual_long_signal",
        "label_col": "label",
        "fwd_col": "r_target_event_ret",
        "candidate_out_col": "r_target_candidate",
        "price_col": "close",
        "open_col": "open",
        "high_col": "high",
        "low_col": "low",
        "volatility_col": "vol_rolling_24",
        "entry_price_mode": "next_open",
        "side": "long_only",
        "target_r_min": 1.0,
        "take_profit_r": 2.0,
        "stop_loss_r": 1.0,
        "max_holding_bars": 16,
        "stop_mode": "volatility_stop",
        "stop_loss_return": 0.005,
        "take_profit_return": 0.010,
        "tie_break": "conservative",
        "allow_partial_horizon": False,
        "diagnostic_feature_cols": None,
    },
    "classifier": {
        "kind": "forward_return",
        "price_col": "close",
        "returns_col": None,
        "returns_type": "simple",
        "horizon": 1,
        "fwd_col": "target_fwd_1",
        "label_col": "label",
        "threshold": 0.0,
        "quantiles": None,
    },
}

PARAM_OPTIONS: dict[str, list[Any]] = {
    "returns_type": ["simple", "log"],
    "method": ["wilder", "sma", "ema"],
    "mode": ["long_short_hold", "long_short"],
    "neutral_label": ["drop", "lower", "upper"],
    "tie_break": ["closest_to_open", "upper", "lower", "conservative", "take_profit", "stop_loss"],
    "candidate_mode": ["all_nonzero", "side_change"],
    "entry_price_mode": ["current_close", "next_open"],
    "label_mode": ["binary", "ternary", "meta"],
    "side": ["long_only"],
    "stop_mode": ["volatility_stop", "fixed_return"],
    "kind": ["forward_return", "triple_barrier", "r_multiple"],
    "timestamp_convention": ["bar_close", "bar_start"],
}

SKIPPED_RUNTIME_PARAMETERS = {"df"}


def _safe_value(value: Any) -> Any:
    if value is inspect._empty:
        return None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [_safe_value(item) for item in value]
    if isinstance(value, list):
        return [_safe_value(item) for item in value]
    if isinstance(value, set):
        return sorted(_safe_value(item) for item in value)
    if isinstance(value, dict):
        return {str(key): _safe_value(item) for key, item in value.items()}
    if hasattr(value, "item"):
        return _safe_value(value.item())
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _annotation_text(annotation: Any) -> str | None:
    if annotation is inspect._empty:
        return None
    if isinstance(annotation, str):
        return annotation
    return getattr(annotation, "__name__", str(annotation))


def _infer_kind(default: Any, annotation: Any) -> str:
    if default is not inspect._empty and default is not None:
        if isinstance(default, bool):
            return "boolean"
        if isinstance(default, int) and not isinstance(default, bool):
            return "integer"
        if isinstance(default, float):
            return "number"
        if isinstance(default, str):
            return "string"
        if isinstance(default, (list, tuple, set)):
            return "list"
        if isinstance(default, dict):
            return "object"

    annotation_lower = (_annotation_text(annotation) or "").lower()
    if "mapping" in annotation_lower or "dict" in annotation_lower:
        return "object"
    if "sequence" in annotation_lower or "iterable" in annotation_lower or "list" in annotation_lower or "tuple" in annotation_lower:
        return "list"
    if "bool" in annotation_lower:
        return "boolean"
    if "int" in annotation_lower:
        return "integer"
    if "float" in annotation_lower:
        return "number"
    if "str" in annotation_lower:
        return "string"
    return "any"


def _callable_import_path(fn: BuilderFn) -> str | None:
    module = getattr(fn, "__module__", None)
    name = getattr(fn, "__qualname__", getattr(fn, "__name__", None))
    if not module or not name:
        return None
    return f"{module}.{name}"


def _parameter_definitions(fn: BuilderFn) -> list[ParameterDefinition]:
    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):
        return []
    parameters: list[ParameterDefinition] = []
    for name, param in signature.parameters.items():
        if name in SKIPPED_RUNTIME_PARAMETERS:
            continue
        default = param.default
        parameters.append(
            ParameterDefinition(
                name=name,
                kind=_infer_kind(default, param.annotation),
                required=default is inspect._empty,
                default_value=_safe_value(default),
                annotation=_annotation_text(param.annotation),
                options=PARAM_OPTIONS.get(name),
            )
        )
    return parameters


def _target_parameter_definitions(name: str) -> list[ParameterDefinition]:
    params = TARGET_PARAM_DEFAULTS.get(name, {})
    definitions: list[ParameterDefinition] = []
    for key, default in params.items():
        definitions.append(
            ParameterDefinition(
                name=key,
                kind=_infer_kind(default, inspect._empty),
                required=False,
                default_value=_safe_value(default),
                options=PARAM_OPTIONS.get(key),
            )
        )
    return definitions


def _docstring(fn: BuilderFn) -> str | None:
    raw = inspect.getdoc(fn)
    if not raw:
        return None
    return raw.strip()


def _definitions_from_registry(
    *,
    registry: dict[str, Any],
    source_type: str,
    resolver: Callable[[str], BuilderFn],
) -> list[BuilderDefinition]:
    definitions: list[BuilderDefinition] = []
    for name in sorted(registry):
        fn = resolver(name)
        definitions.append(
            BuilderDefinition(
                name=name,
                source_type=source_type,  # type: ignore[arg-type]
                import_path=_callable_import_path(fn),
                parameters=_parameter_definitions(fn),
                docstring=_docstring(fn),
            )
        )
    return definitions


def feature_builders() -> list[BuilderDefinition]:
    return _definitions_from_registry(
        registry=FEATURE_REGISTRY,
        source_type="feature",
        resolver=get_feature_fn,
    )


def signal_builders() -> list[BuilderDefinition]:
    return _definitions_from_registry(
        registry=SIGNAL_REGISTRY,
        source_type="signal",
        resolver=get_signal_fn,
    )


def target_builders() -> list[BuilderDefinition]:
    definitions: list[BuilderDefinition] = []
    for name in sorted(TARGET_REGISTRY):
        fn = TARGET_REGISTRY[name]
        definitions.append(
            BuilderDefinition(
                name=name,
                source_type="target",
                import_path=_callable_import_path(fn),
                parameters=_target_parameter_definitions(name),
                docstring=_docstring(fn),
            )
        )
    return definitions


def _new_columns(before: Iterable[str], after: Iterable[str]) -> list[str]:
    before_set = set(before)
    return [str(column) for column in after if column not in before_set]


def _configured_output_columns(
    *,
    before: Iterable[str],
    after: Iterable[str],
    outputs: dict[str, str] | None,
    meta: dict[str, Any] | None = None,
    preferred: Iterable[str] = (),
) -> list[str]:
    after_list = [str(column) for column in after]
    candidates: list[str] = []
    if outputs:
        candidates.extend(str(value) for value in outputs.values())
    if meta:
        raw_outputs = meta.get("output_cols")
        if isinstance(raw_outputs, list):
            candidates.extend(str(value) for value in raw_outputs)
        for key in ("label_col", "fwd_col", "event_ret_col", "candidate_col", "oriented_r_col", "r_col"):
            value = meta.get(key)
            if value is not None:
                candidates.append(str(value))
    candidates.extend(str(value) for value in preferred)
    candidates.extend(_new_columns(before, after_list))
    seen: set[str] = set()
    selected: list[str] = []
    for column in candidates:
        if column in seen or column not in after_list:
            continue
        selected.append(column)
        seen.add(column)
    return selected


def _numeric_columns(frame: pd.DataFrame, columns: Iterable[str]) -> list[str]:
    numeric: list[str] = []
    for column in columns:
        if column not in frame.columns:
            continue
        if pd.api.types.is_numeric_dtype(frame[column]) or pd.api.types.is_bool_dtype(frame[column]):
            numeric.append(column)
    return numeric


def _series_response_items(frame: pd.DataFrame, source_type: str, columns: list[str]) -> list[NamedSeries]:
    numeric_columns = _numeric_columns(frame, columns)
    payload = frame_to_series(frame, numeric_columns) if numeric_columns else {}
    return [
        NamedSeries(series_id=name, source_type=source_type, points=points)
        for name, points in payload.items()
    ]


def _step_dict(step: TransformStepConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "step": step.step,
        "params": step.params,
        "enabled": step.enabled,
    }
    if step.outputs:
        payload["outputs"] = step.outputs
    return payload


def _signal_step_dict(step: TransformStepConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": step.step,
        "params": step.params,
        "enabled": step.enabled,
    }
    if step.outputs:
        payload["outputs"] = step.outputs
    return payload


def _apply_feature_step(frame: pd.DataFrame, step: TransformStepConfig, *, asset: str) -> tuple[pd.DataFrame, list[str]]:
    before = list(frame.columns)
    out = apply_feature_steps(frame, [_step_dict(step)], asset=asset)
    columns = _configured_output_columns(before=before, after=out.columns, outputs=step.outputs)
    return out, _numeric_columns(out, columns)


def _apply_signal(frame: pd.DataFrame, step: TransformStepConfig) -> tuple[pd.DataFrame, list[str]]:
    before = list(frame.columns)
    out = apply_signal_step(frame, _signal_step_dict(step))
    columns = _configured_output_columns(before=before, after=out.columns, outputs=step.outputs)
    return out, _numeric_columns(out, columns)


def _apply_target(frame: pd.DataFrame, step: TransformStepConfig) -> tuple[pd.DataFrame, list[str], dict[str, Any]]:
    if step.step not in TARGET_REGISTRY:
        raise KeyError(f"Unknown target builder: {step.step}")
    before = list(frame.columns)
    out, label_col, fwd_col, meta = TARGET_REGISTRY[step.step](frame, dict(step.params))
    columns = _configured_output_columns(
        before=before,
        after=out.columns,
        outputs=step.outputs,
        meta=meta,
        preferred=[label_col, fwd_col],
    )
    return out, _numeric_columns(out, columns), meta


def run_transform_series(payload: TransformSeriesRequest) -> TransformSeriesResponse:
    frame, dataset = DataLoader().load_frame(
        asset=payload.asset,
        timeframe=payload.timeframe,
        source=payload.source,
        dataset_id=payload.dataset_id,
        start=payload.start,
        end=payload.end,
        require_ohlcv=True,
    )

    working = frame
    step_results: list[TransformStepResult] = []
    selected: list[tuple[str, list[str]]] = []

    for step in payload.features:
        if not step.enabled:
            continue
        working, columns = _apply_feature_step(working, step, asset=payload.asset)
        selected.append(("feature", columns))
        step_results.append(TransformStepResult(source_type="feature", step=step.step, output_columns=columns))

    for step in payload.signals:
        if not step.enabled:
            continue
        working, columns = _apply_signal(working, step)
        selected.append(("signal", columns))
        step_results.append(TransformStepResult(source_type="signal", step=step.step, output_columns=columns))

    for step in payload.targets:
        if not step.enabled:
            continue
        working, columns, meta = _apply_target(working, step)
        selected.append(("target", columns))
        step_results.append(
            TransformStepResult(source_type="target", step=step.step, output_columns=columns, metadata=meta)
        )

    response_frame = working.tail(payload.limit) if payload.limit else working
    series: list[NamedSeries] = []
    for source_type, columns in selected:
        series.extend(_series_response_items(response_frame, source_type, columns))

    return TransformSeriesResponse(
        series=series,
        steps=step_results,
        metadata={
            "dataset_id": dataset.id,
            "rows_loaded": int(len(frame)),
            "rows_returned": int(len(response_frame)),
        },
    )
