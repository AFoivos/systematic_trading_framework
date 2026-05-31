from __future__ import annotations

import inspect
import math
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Callable, Mapping

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

from src.features import (  # noqa: E402
    add_adx_features,
    add_atr_features,
    add_bollinger_features,
    add_close_returns,
    add_feature_transforms,
    add_lagged_features,
    add_macd_features,
    add_macro_context_features,
    add_mfi_features,
    add_multi_timeframe_features,
    add_opening_range_breakout_features,
    add_ppo_features,
    add_price_momentum_features,
    add_regime_context_features,
    add_return_momentum_features,
    add_roc_features,
    add_rsi_features,
    add_session_context_features,
    add_shock_context_features,
    add_stochastic_features,
    add_stochastic_rsi_features,
    add_support_resistance_features,
    add_support_resistance_v2_features,
    add_vol_normalized_momentum_features,
    add_volatility_features,
    add_volume_features,
    add_vwap_features,
    swing_extrema_context,
)
from src.features.technical.trend import add_trend_features, add_trend_regime_features  # noqa: E402
from src.signals import (  # noqa: E402
    conviction_sizing_signal,
    ema_stoch_rsi_pullback_signal,
    forecast_threshold_signal,
    forecast_vol_adjusted_signal,
    manual_long_model_filter_signal,
    meta_probability_side_signal,
    momentum_strategy,
    orb_candidate_side_signal,
    probability_vol_adjusted_signal,
    probabilistic_signal,
    roc_long_only_conditions_signal,
    rsi_strategy,
    stochastic_strategy,
    trend_state_signal,
    volatility_regime_strategy,
)
from src.targets.classifier import build_classifier_target  # noqa: E402
from src.targets.forward_return import build_forward_return_target  # noqa: E402
from src.targets.r_multiple import build_r_multiple_target  # noqa: E402
from src.targets.triple_barrier import build_triple_barrier_target  # noqa: E402


BuilderFn = Callable[..., Any]
FeatureFn = Callable[..., pd.DataFrame]
SignalFn = Callable[..., pd.DataFrame | pd.Series]

FEATURE_REGISTRY: Mapping[str, FeatureFn] = {
    "returns": add_close_returns,
    "volatility": add_volatility_features,
    "trend": add_trend_features,
    "trend_regime": add_trend_regime_features,
    "lags": add_lagged_features,
    "bollinger": add_bollinger_features,
    "macd": add_macd_features,
    "ppo": add_ppo_features,
    "roc": add_roc_features,
    "atr": add_atr_features,
    "adx": add_adx_features,
    "volume_features": add_volume_features,
    "vwap": add_vwap_features,
    "mfi": add_mfi_features,
    "rsi": add_rsi_features,
    "stochastic": add_stochastic_features,
    "stochastic_rsi": add_stochastic_rsi_features,
    "price_momentum": add_price_momentum_features,
    "return_momentum": add_return_momentum_features,
    "vol_normalized_momentum": add_vol_normalized_momentum_features,
    "session_context": add_session_context_features,
    "regime_context": add_regime_context_features,
    "shock_context": add_shock_context_features,
    "support_resistance": add_support_resistance_features,
    "support_resistance_v2": add_support_resistance_v2_features,
    "macro_context": add_macro_context_features,
    "feature_transforms": add_feature_transforms,
    "multi_timeframe": add_multi_timeframe_features,
    "opening_range_breakout": add_opening_range_breakout_features,
    "swing_extrema_context": swing_extrema_context,
    "roc_long_only_conditions": roc_long_only_conditions_signal,
    "ema_stoch_rsi_pullback": ema_stoch_rsi_pullback_signal,
}

SIGNAL_REGISTRY: Mapping[str, SignalFn] = {
    "trend_state": trend_state_signal,
    "probability_threshold": probabilistic_signal,
    "probability_conviction": conviction_sizing_signal,
    "probability_vol_adjusted": probability_vol_adjusted_signal,
    "meta_probability_side": meta_probability_side_signal,
    "orb_candidate_side": orb_candidate_side_signal,
    "roc_long_only_conditions": roc_long_only_conditions_signal,
    "ema_stoch_rsi_pullback": ema_stoch_rsi_pullback_signal,
    "manual_long_model_filter": manual_long_model_filter_signal,
    "forecast_threshold": forecast_threshold_signal,
    "forecast_vol_adjusted": forecast_vol_adjusted_signal,
    "rsi": rsi_strategy,
    "momentum": momentum_strategy,
    "stochastic": stochastic_strategy,
    "volatility_regime": volatility_regime_strategy,
}

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


def get_feature_fn(name: str) -> FeatureFn:
    if name not in FEATURE_REGISTRY:
        raise KeyError(f"Unknown feature step: {name}")
    return FEATURE_REGISTRY[name]


def get_signal_fn(name: str) -> SignalFn:
    if name not in SIGNAL_REGISTRY:
        raise KeyError(f"Unknown signal kind: {name}")
    return SIGNAL_REGISTRY[name]


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


def _apply_output_mapping(
    df: pd.DataFrame,
    outputs: dict[str, Any] | None,
    *,
    owner: str,
    ignore_missing_keys: set[str] | None = None,
) -> pd.DataFrame:
    if not outputs:
        return df
    if not isinstance(outputs, dict):
        raise TypeError(f"{owner}.outputs must be a mapping when provided.")

    rename_map: dict[str, str] = {}
    ignored = set(ignore_missing_keys or set())
    for source_col, target_col in outputs.items():
        if not isinstance(source_col, str) or not source_col.strip():
            raise ValueError(f"{owner}.outputs keys must be non-empty strings.")
        if not isinstance(target_col, str) or not target_col.strip():
            raise ValueError(f"{owner}.outputs values must be non-empty strings.")
        if source_col not in df.columns:
            if source_col in ignored:
                continue
            raise KeyError(
                f"{owner}.outputs refers to source column '{source_col}' which was not emitted by the step."
            )
        rename_map[source_col] = target_col

    renamed = df.rename(columns=rename_map)
    if len(set(renamed.columns)) != len(renamed.columns):
        duplicates = renamed.columns[renamed.columns.duplicated()].unique().tolist()
        raise ValueError(
            f"{owner}.outputs resolves to duplicate column names after renaming: {duplicates}."
        )
    return renamed


def _call_feature_fn(fn: FeatureFn, df: pd.DataFrame, params: dict[str, Any], *, asset: str | None) -> pd.DataFrame:
    call_params = dict(params)
    if asset is not None and "asset" not in call_params:
        try:
            accepts_asset = "asset" in inspect.signature(fn).parameters
        except (TypeError, ValueError):
            accepts_asset = False
        if accepts_asset:
            call_params["asset"] = asset
    return fn(df, **call_params)


def apply_feature_steps(
    df: pd.DataFrame,
    steps: list[dict[str, Any]],
    *,
    asset: str | None = None,
) -> pd.DataFrame:
    out = df
    for idx, step in enumerate(steps):
        if "step" not in step:
            raise ValueError("Each feature step must include a 'step' key.")
        if step.get("enabled", True) is False:
            continue
        name = step["step"]
        params = step.get("params", {}) or {}
        fn = get_feature_fn(name)
        out = _call_feature_fn(fn, out, params, asset=asset)
        out = _apply_output_mapping(out, step.get("outputs"), owner=f"features[{idx}]")
    return out


def apply_signal_step(df: pd.DataFrame, signals_cfg: dict[str, Any]) -> pd.DataFrame:
    kind = signals_cfg.get("kind", "none")
    if kind == "none":
        params = signals_cfg.get("params", {}) or {}
        signal_col = params.get("signal_col")
        if signal_col not in (None, ""):
            frame = df.copy()
            frame[str(signal_col)] = 0.0
            return _apply_output_mapping(
                frame,
                signals_cfg.get("outputs"),
                owner="signals",
                ignore_missing_keys={"signal_col"},
            )
        return df
    params = signals_cfg.get("params", {}) or {}
    fn = get_signal_fn(kind)
    out = fn(df, **params)
    if isinstance(out, pd.DataFrame):
        return _apply_output_mapping(
            out,
            signals_cfg.get("outputs"),
            owner="signals",
            ignore_missing_keys={"signal_col"},
        )
    if isinstance(out, pd.Series):
        frame = df.copy()
        frame[out.name] = out
        return _apply_output_mapping(
            frame,
            signals_cfg.get("outputs"),
            owner="signals",
            ignore_missing_keys={"signal_col"},
        )
    raise TypeError(f"Signal function for kind='{kind}' returned unsupported type: {type(out)}")


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


def _apply_feature_step(frame: pd.DataFrame, step: TransformStepConfig, *, asset: str | None) -> tuple[pd.DataFrame, list[str]]:
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
    effective_asset = payload.asset or (dataset.assets[0] if len(dataset.assets) == 1 else None)
    step_results: list[TransformStepResult] = []
    selected: list[tuple[str, list[str]]] = []

    for step in payload.features:
        if not step.enabled:
            continue
        working, columns = _apply_feature_step(working, step, asset=effective_asset)
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
