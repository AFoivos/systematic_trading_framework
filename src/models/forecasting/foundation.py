from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FoundationForecastSpec:
    model_family: str
    model_id: str
    source_col: str
    source_kind: str
    source_returns_type: str
    target_kind: str
    target_returns_type: str
    prediction_length: int
    target_horizon: int
    lookback: int
    min_context: int
    quantiles: tuple[float, ...]
    normalize_by_volatility: bool
    volatility_col: str | None
    price_col: str
    volatility_floor: float
    clip: tuple[float, float] | None


def _parse_quantiles(raw: Any) -> tuple[float, ...]:
    values = [0.1, 0.5, 0.9] if raw is None else list(raw)
    quantiles = tuple(sorted(float(q) for q in values))
    if not quantiles:
        raise ValueError("model.params.quantiles must not be empty.")
    if len(set(quantiles)) != len(quantiles):
        raise ValueError("model.params.quantiles must be unique.")
    if any(not (0.0 < q < 1.0) for q in quantiles):
        raise ValueError("model.params.quantiles must be within (0, 1).")
    return quantiles


def _quantile_col(quantile: float) -> str:
    return f"pred_q{int(round(quantile * 100)):02d}"


def _target_horizon(target_cfg: dict[str, Any], model_params: dict[str, Any]) -> int:
    horizon = target_cfg.get(
        "horizon_bars",
        target_cfg.get("horizon", model_params.get("prediction_length", 1)),
    )
    horizon_int = int(horizon)
    if horizon_int <= 0:
        raise ValueError("model target horizon must be positive.")
    return horizon_int


def _resolve_source_kind(source_col: str, model_params: dict[str, Any], target_cfg: dict[str, Any]) -> str:
    raw_kind = model_params.get("source_kind")
    if raw_kind is None:
        returns_col = target_cfg.get("returns_col")
        if returns_col is not None and str(returns_col) == source_col:
            return "returns"
        lowered = source_col.lower()
        if "logret" in lowered or "log_return" in lowered:
            return "returns"
        if lowered.endswith("_ret") or "return" in lowered:
            return "returns"
        return "price"
    source_kind = str(raw_kind).strip().lower()
    if source_kind not in {"price", "returns"}:
        raise ValueError("model.params.source_kind must be one of: price, returns.")
    return source_kind


def _resolve_spec(
    full_df: pd.DataFrame,
    model_params: dict[str, Any],
    *,
    model_family: str,
    default_model_id: str,
) -> FoundationForecastSpec:
    target_cfg = dict(model_params.get("_target_cfg", {}) or {})
    target_kind = str(target_cfg.get("kind", "forward_return"))
    if target_kind not in {"forward_return", "future_return_regression"}:
        raise ValueError(
            "Foundation forecasters support target.kind='forward_return' or "
            "'future_return_regression'."
        )

    horizon = _target_horizon(target_cfg, model_params)
    prediction_length = int(model_params.get("prediction_length", horizon))
    if prediction_length < horizon:
        raise ValueError("model.params.prediction_length must be >= the target horizon.")

    price_col = str(target_cfg.get("price_col", "close"))
    source_col = str(model_params.get("source_col") or model_params.get("context_col") or price_col)
    if source_col not in full_df.columns:
        raise KeyError(f"model.params.source_col '{source_col}' not found in DataFrame.")

    source_kind = _resolve_source_kind(source_col, model_params, target_cfg)
    target_returns_type = str(target_cfg.get("returns_type", "simple"))
    source_returns_type = str(model_params.get("source_returns_type", target_returns_type))
    if source_returns_type not in {"simple", "log"}:
        raise ValueError("model.params.source_returns_type must be 'simple' or 'log'.")
    if target_returns_type not in {"simple", "log"}:
        raise ValueError("model.target.returns_type must be 'simple' or 'log'.")

    lookback = int(model_params.get("lookback", model_params.get("context_length", 256)))
    if lookback <= 1:
        raise ValueError("model.params.lookback must be > 1.")
    min_context = int(model_params.get("min_context", min(lookback, 16)))
    if min_context <= 1:
        raise ValueError("model.params.min_context must be > 1.")
    if min_context > lookback:
        raise ValueError("model.params.min_context must be <= model.params.lookback.")

    clip: tuple[float, float] | None = None
    raw_clip = target_cfg.get("clip")
    if raw_clip is not None:
        if not isinstance(raw_clip, (list, tuple)) or len(raw_clip) != 2:
            raise ValueError("model.target.clip must be a [low, high] pair.")
        clip = (float(raw_clip[0]), float(raw_clip[1]))
        if clip[0] >= clip[1]:
            raise ValueError("model.target.clip must satisfy low < high.")

    normalize_by_volatility = bool(target_cfg.get("normalize_by_volatility", False))
    volatility_col = str(target_cfg.get("volatility_col", "atr_14")) if normalize_by_volatility else None
    if volatility_col is not None and volatility_col not in full_df.columns:
        raise KeyError(f"model.target.volatility_col '{volatility_col}' not found in DataFrame.")
    if normalize_by_volatility and price_col not in full_df.columns:
        raise KeyError(f"model.target.price_col '{price_col}' not found in DataFrame.")

    return FoundationForecastSpec(
        model_family=model_family,
        model_id=str(model_params.get("model_id") or model_params.get("checkpoint") or default_model_id),
        source_col=source_col,
        source_kind=source_kind,
        source_returns_type=source_returns_type,
        target_kind=target_kind,
        target_returns_type=target_returns_type,
        prediction_length=prediction_length,
        target_horizon=horizon,
        lookback=lookback,
        min_context=min_context,
        quantiles=_parse_quantiles(model_params.get("quantiles")),
        normalize_by_volatility=normalize_by_volatility,
        volatility_col=volatility_col,
        price_col=price_col,
        volatility_floor=float(target_cfg.get("volatility_floor", 1e-12)),
        clip=clip,
    )


def _context_values(
    full_df: pd.DataFrame,
    row_idx: int,
    spec: FoundationForecastSpec,
) -> np.ndarray | None:
    values = pd.to_numeric(full_df[spec.source_col], errors="coerce").to_numpy(dtype=float)
    start = max(0, int(row_idx) - spec.lookback + 1)
    context = values[start : int(row_idx) + 1]
    finite = np.isfinite(context)
    if not finite.any():
        return None
    if not finite.all():
        last_bad = np.flatnonzero(~finite)[-1]
        context = context[last_bad + 1 :]
    if len(context) < spec.min_context:
        return None
    if spec.source_kind == "price" and (not np.isfinite(context[-1]) or abs(float(context[-1])) <= 1e-12):
        return None
    return np.asarray(context, dtype="float32")


def _as_numpy(values: Any) -> np.ndarray:
    if hasattr(values, "detach"):
        values = values.detach().cpu().numpy()
    elif hasattr(values, "numpy"):
        values = values.numpy()
    return np.asarray(values, dtype=float)


def _matrix(values: Any, *, expected_rows: int, horizon: int, name: str) -> np.ndarray:
    arr = _as_numpy(values)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    if arr.ndim != 2:
        raise ValueError(f"{name} must have shape (batch, horizon); got {arr.shape}.")
    if arr.shape[0] != expected_rows:
        raise ValueError(f"{name} batch size mismatch: expected {expected_rows}, got {arr.shape[0]}.")
    if arr.shape[1] < horizon:
        raise ValueError(f"{name} horizon is too short: expected at least {horizon}, got {arr.shape[1]}.")
    return np.asarray(arr[:, :horizon], dtype=float)


def _quantile_cube(values: Any, *, expected_rows: int, horizon: int, num_quantiles: int, name: str) -> np.ndarray:
    arr = _as_numpy(values)
    if arr.ndim != 3:
        raise ValueError(f"{name} must have shape (batch, horizon, quantiles); got {arr.shape}.")
    if arr.shape[0] != expected_rows:
        raise ValueError(f"{name} batch size mismatch: expected {expected_rows}, got {arr.shape[0]}.")
    if arr.shape[1] < horizon and arr.shape[2] >= horizon:
        arr = np.swapaxes(arr, 1, 2)
    if arr.shape[1] < horizon:
        raise ValueError(f"{name} horizon is too short: expected at least {horizon}, got {arr.shape[1]}.")
    if arr.shape[2] != num_quantiles:
        raise ValueError(
            f"{name} quantile count mismatch: expected {num_quantiles}, got {arr.shape[2]}."
        )
    return np.asarray(arr[:, :horizon, :], dtype=float)


def _forecast_values_to_return(
    forecast_values: np.ndarray,
    *,
    last_context_values: np.ndarray,
    row_positions: np.ndarray,
    full_df: pd.DataFrame,
    spec: FoundationForecastSpec,
) -> np.ndarray:
    horizon = spec.target_horizon
    values = np.asarray(forecast_values, dtype=float)
    if values.ndim != 2 or values.shape[1] < horizon:
        raise ValueError("forecast_values must have shape (batch, prediction_length).")

    if spec.source_kind == "returns":
        steps = values[:, :horizon]
        if spec.source_returns_type == "log":
            log_ret = np.nansum(steps, axis=1)
            raw_ret = log_ret if spec.target_returns_type == "log" else np.expm1(log_ret)
        else:
            simple_ret = np.nanprod(1.0 + steps, axis=1) - 1.0
            raw_ret = np.log1p(simple_ret) if spec.target_returns_type == "log" else simple_ret
    else:
        terminal = values[:, horizon - 1]
        if spec.target_returns_type == "log":
            raw_ret = np.log(terminal / last_context_values)
        else:
            raw_ret = terminal / last_context_values - 1.0

    raw_ret = np.asarray(raw_ret, dtype=float)
    raw_ret[~np.isfinite(raw_ret)] = np.nan

    if spec.normalize_by_volatility:
        assert spec.volatility_col is not None
        volatility = pd.to_numeric(full_df.iloc[row_positions][spec.volatility_col], errors="coerce").to_numpy(dtype=float)
        price = pd.to_numeric(full_df.iloc[row_positions][spec.price_col], errors="coerce").to_numpy(dtype=float)
        normalizer = volatility / np.abs(price)
        valid_normalizer = np.isfinite(normalizer) & (normalizer > spec.volatility_floor)
        raw_ret = np.where(valid_normalizer, raw_ret / normalizer, np.nan)

    if spec.clip is not None:
        raw_ret = np.clip(raw_ret, spec.clip[0], spec.clip[1])

    return raw_ret.astype("float32")


def _assemble_prediction_output(
    *,
    index: pd.Index,
    row_positions: np.ndarray,
    last_context_values: np.ndarray,
    point_forecast: np.ndarray,
    quantile_forecasts: dict[float, np.ndarray],
    full_df: pd.DataFrame,
    spec: FoundationForecastSpec,
) -> tuple[pd.Series, dict[str, pd.Series]]:
    pred_values = _forecast_values_to_return(
        point_forecast,
        last_context_values=last_context_values,
        row_positions=row_positions,
        full_df=full_df,
        spec=spec,
    )
    pred_ret = pd.Series(pred_values, index=index, dtype="float32")

    extra_cols: dict[str, pd.Series] = {}
    quantile_return_cols: dict[float, pd.Series] = {}
    for quantile, forecast_values in sorted(quantile_forecasts.items()):
        values = _forecast_values_to_return(
            forecast_values,
            last_context_values=last_context_values,
            row_positions=row_positions,
            full_df=full_df,
            spec=spec,
        )
        series = pd.Series(values, index=index, dtype="float32")
        quantile_return_cols[quantile] = series
        extra_cols[_quantile_col(quantile)] = series

    if quantile_return_cols:
        low = quantile_return_cols[min(quantile_return_cols)].astype(float)
        high = quantile_return_cols[max(quantile_return_cols)].astype(float)
        extra_cols["pred_vol"] = ((high - low).abs() / 2.0).astype("float32")

    return pred_ret, extra_cols


def _build_context_batch(
    full_df: pd.DataFrame,
    test_idx: np.ndarray,
    spec: FoundationForecastSpec,
) -> tuple[list[np.ndarray], np.ndarray, np.ndarray, pd.Index]:
    contexts: list[np.ndarray] = []
    row_positions: list[int] = []
    last_values: list[float] = []
    out_index: list[Any] = []
    for raw_idx in np.asarray(test_idx, dtype=int):
        context = _context_values(full_df, int(raw_idx), spec)
        if context is None:
            continue
        contexts.append(context)
        row_positions.append(int(raw_idx))
        last_values.append(float(context[-1]))
        out_index.append(full_df.index[int(raw_idx)])
    return (
        contexts,
        np.asarray(row_positions, dtype=int),
        np.asarray(last_values, dtype=float),
        pd.Index(out_index),
    )


def _chronos_common_meta(
    *,
    spec: FoundationForecastSpec,
    train_idx: np.ndarray,
    contexts: list[np.ndarray],
    model_params: dict[str, Any],
) -> dict[str, Any]:
    return {
        "model_family": spec.model_family,
        "model_id": spec.model_id,
        "source_col": spec.source_col,
        "source_kind": spec.source_kind,
        "lookback": spec.lookback,
        "min_context": spec.min_context,
        "prediction_length": spec.prediction_length,
        "target_horizon": spec.target_horizon,
        "quantiles": list(spec.quantiles),
        "foundation_train_rows": int(len(train_idx)),
        "foundation_test_samples": int(len(contexts)),
        "zero_shot": True,
        "batch_size": int(model_params.get("batch_size", 256)),
    }


def make_chronos_bolt_fold_predictor(
    *,
    default_model_id: str = "amazon/chronos-bolt-tiny",
) -> Callable[
    [pd.DataFrame, np.ndarray, np.ndarray, list[str], str, dict[str, Any], dict[str, Any]],
    tuple[pd.Series, dict[str, pd.Series], object, dict[str, Any]],
]:
    cache: dict[str, Any] = {}

    def _load_pipeline(model_params: dict[str, Any]) -> object:
        spec_model_id = str(model_params.get("model_id") or model_params.get("checkpoint") or default_model_id)
        cache_key = "|".join(
            [
                spec_model_id,
                str(model_params.get("device_map", "cpu")),
                str(model_params.get("torch_dtype", "auto")),
            ]
        )
        if cache_key not in cache:
            try:
                from chronos import ChronosBoltPipeline
            except Exception as exc:
                raise ImportError(
                    "Chronos-Bolt forecaster requires chronos-forecasting. "
                    "Install it with `pip install chronos-forecasting`."
                ) from exc
            cache[cache_key] = ChronosBoltPipeline.from_pretrained(
                spec_model_id,
                device_map=model_params.get("device_map", "cpu"),
                torch_dtype=model_params.get("torch_dtype", "auto"),
            )
        return cache[cache_key]

    def _predictor(
        full_df: pd.DataFrame,
        train_idx: np.ndarray,
        test_idx: np.ndarray,
        feature_cols: list[str],
        target_col: str,
        model_params: dict[str, Any],
        runtime_meta: dict[str, Any],
    ) -> tuple[pd.Series, dict[str, pd.Series], object, dict[str, Any]]:
        del feature_cols, target_col, runtime_meta
        spec = _resolve_spec(
            full_df,
            model_params,
            model_family="chronos_bolt",
            default_model_id=default_model_id,
        )
        contexts, row_positions, last_values, index = _build_context_batch(full_df, test_idx, spec)
        if not contexts:
            return (
                pd.Series(dtype="float32", index=index),
                {},
                _load_pipeline(model_params),
                _chronos_common_meta(spec=spec, train_idx=train_idx, contexts=contexts, model_params=model_params),
            )

        try:
            import torch
        except Exception as exc:
            raise ImportError("Chronos-Bolt forecaster requires torch.") from exc

        pipeline = _load_pipeline(model_params)
        tensor_contexts = [torch.tensor(context, dtype=torch.float32) for context in contexts]
        quantiles, mean = pipeline.predict_quantiles(
            inputs=tensor_contexts,
            prediction_length=spec.prediction_length,
            quantile_levels=list(spec.quantiles),
            batch_size=int(model_params.get("batch_size", 256)),
            limit_prediction_length=bool(model_params.get("limit_prediction_length", False)),
        )
        point_forecast = _matrix(mean, expected_rows=len(contexts), horizon=spec.prediction_length, name="chronos_mean")
        quantile_cube = _quantile_cube(
            quantiles,
            expected_rows=len(contexts),
            horizon=spec.prediction_length,
            num_quantiles=len(spec.quantiles),
            name="chronos_quantiles",
        )
        quantile_forecasts = {
            q: quantile_cube[:, :, q_idx]
            for q_idx, q in enumerate(spec.quantiles)
        }
        pred_ret, extra_cols = _assemble_prediction_output(
            index=index,
            row_positions=row_positions,
            last_context_values=last_values,
            point_forecast=point_forecast,
            quantile_forecasts=quantile_forecasts,
            full_df=full_df,
            spec=spec,
        )
        return (
            pred_ret,
            extra_cols,
            pipeline,
            _chronos_common_meta(spec=spec, train_idx=train_idx, contexts=contexts, model_params=model_params),
        )

    return _predictor


def make_chronos2_fold_predictor(
    *,
    default_model_id: str = "amazon/chronos-2",
) -> Callable[
    [pd.DataFrame, np.ndarray, np.ndarray, list[str], str, dict[str, Any], dict[str, Any]],
    tuple[pd.Series, dict[str, pd.Series], object, dict[str, Any]],
]:
    cache: dict[str, Any] = {}

    def _load_pipeline(model_params: dict[str, Any]) -> object:
        spec_model_id = str(model_params.get("model_id") or model_params.get("checkpoint") or default_model_id)
        cache_key = "|".join(
            [
                spec_model_id,
                str(model_params.get("device_map", "cpu")),
                str(model_params.get("torch_dtype", "auto")),
            ]
        )
        if cache_key not in cache:
            try:
                from chronos import Chronos2Pipeline
            except Exception as exc:
                raise ImportError(
                    "Chronos-2 forecaster requires chronos-forecasting. "
                    "Install it with `pip install chronos-forecasting`."
                ) from exc
            cache[cache_key] = Chronos2Pipeline.from_pretrained(
                spec_model_id,
                device_map=model_params.get("device_map", "cpu"),
                torch_dtype=model_params.get("torch_dtype", "auto"),
            )
        return cache[cache_key]

    def _predictor(
        full_df: pd.DataFrame,
        train_idx: np.ndarray,
        test_idx: np.ndarray,
        feature_cols: list[str],
        target_col: str,
        model_params: dict[str, Any],
        runtime_meta: dict[str, Any],
    ) -> tuple[pd.Series, dict[str, pd.Series], object, dict[str, Any]]:
        del feature_cols, target_col, runtime_meta
        spec = _resolve_spec(
            full_df,
            model_params,
            model_family="chronos_2",
            default_model_id=default_model_id,
        )
        contexts, row_positions, last_values, index = _build_context_batch(full_df, test_idx, spec)
        pipeline = _load_pipeline(model_params)
        if not contexts:
            return (
                pd.Series(dtype="float32", index=index),
                {},
                pipeline,
                _chronos_common_meta(spec=spec, train_idx=train_idx, contexts=contexts, model_params=model_params),
            )

        rows: list[dict[str, Any]] = []
        freq = str(model_params.get("freq", "D"))
        for item_id, context in enumerate(contexts):
            timestamps = pd.date_range("2000-01-01", periods=len(context), freq=freq)
            rows.extend(
                {"item_id": str(item_id), "timestamp": ts, "target": float(value)}
                for ts, value in zip(timestamps, context)
            )
        context_df = pd.DataFrame(rows)
        forecast_df = pipeline.predict_df(
            context_df,
            id_column="item_id",
            timestamp_column="timestamp",
            target="target",
            prediction_length=spec.prediction_length,
            quantile_levels=list(spec.quantiles),
            batch_size=int(model_params.get("batch_size", 256)),
            validate_inputs=bool(model_params.get("validate_inputs", False)),
            freq=freq,
        )
        forecast_df["item_id"] = forecast_df["item_id"].astype(str)
        point_rows: list[np.ndarray] = []
        quantile_rows: dict[float, list[np.ndarray]] = {q: [] for q in spec.quantiles}
        for item_id in range(len(contexts)):
            item = forecast_df.loc[forecast_df["item_id"] == str(item_id)].head(spec.prediction_length)
            point_rows.append(pd.to_numeric(item["predictions"], errors="coerce").to_numpy(dtype=float))
            for q in spec.quantiles:
                quantile_rows[q].append(pd.to_numeric(item[str(q)], errors="coerce").to_numpy(dtype=float))

        point_forecast = _matrix(
            np.vstack(point_rows),
            expected_rows=len(contexts),
            horizon=spec.prediction_length,
            name="chronos2_predictions",
        )
        quantile_forecasts = {
            q: _matrix(
                np.vstack(values),
                expected_rows=len(contexts),
                horizon=spec.prediction_length,
                name=f"chronos2_quantile_{q}",
            )
            for q, values in quantile_rows.items()
        }
        pred_ret, extra_cols = _assemble_prediction_output(
            index=index,
            row_positions=row_positions,
            last_context_values=last_values,
            point_forecast=point_forecast,
            quantile_forecasts=quantile_forecasts,
            full_df=full_df,
            spec=spec,
        )
        return (
            pred_ret,
            extra_cols,
            pipeline,
            _chronos_common_meta(spec=spec, train_idx=train_idx, contexts=contexts, model_params=model_params),
        )

    return _predictor


def _timesfm_quantile_forecasts(
    quantile_forecast: Any,
    *,
    quantiles: tuple[float, ...],
    expected_rows: int,
    horizon: int,
) -> dict[float, np.ndarray]:
    if quantile_forecast is None:
        return {}
    arr = _as_numpy(quantile_forecast)
    if arr.ndim != 3 or arr.shape[0] != expected_rows or arr.shape[1] < horizon:
        return {}
    arr = arr[:, :horizon, :]
    if arr.shape[2] >= 10:
        levels = [round(i / 10.0, 1) for i in range(1, 10)]
        offset = 1
    elif arr.shape[2] >= 9:
        levels = [round(i / 10.0, 1) for i in range(1, 10)]
        offset = 0
    else:
        return {}
    out: dict[float, np.ndarray] = {}
    for q in quantiles:
        nearest_idx, nearest = min(enumerate(levels), key=lambda item: abs(item[1] - q))
        if abs(nearest - q) <= 0.051:
            out[q] = arr[:, :, nearest_idx + offset]
    return out


def make_timesfm_fold_predictor(
    *,
    setup: str,
    default_model_id: str,
) -> Callable[
    [pd.DataFrame, np.ndarray, np.ndarray, list[str], str, dict[str, Any], dict[str, Any]],
    tuple[pd.Series, dict[str, pd.Series], object, dict[str, Any]],
]:
    cache: dict[str, Any] = {}

    def _load_model(model_params: dict[str, Any], spec: FoundationForecastSpec) -> object:
        cache_key = "|".join(
            [
                setup,
                spec.model_id,
                str(model_params.get("backend", "cpu")),
                str(model_params.get("max_context", spec.lookback)),
                str(model_params.get("max_horizon", spec.prediction_length)),
            ]
        )
        if cache_key in cache:
            return cache[cache_key]
        try:
            import timesfm
        except Exception as exc:
            raise ImportError(
                "TimesFM forecaster requires timesfm. Install the torch backend with "
                "`pip install 'timesfm[torch]'`."
            ) from exc

        max_context = int(model_params.get("max_context", spec.lookback))
        max_horizon = max(int(model_params.get("max_horizon", spec.prediction_length)), spec.prediction_length)
        if setup == "2p5_200m":
            try:
                cls = getattr(timesfm, "TimesFM_2p5_200M_torch")
                forecast_config_cls = getattr(timesfm, "ForecastConfig")
            except AttributeError as exc:
                raise ImportError(
                    "timesfm_2p5_200m_forecaster requires a TimesFM package that exposes "
                    "TimesFM_2p5_200M_torch and ForecastConfig."
                ) from exc
            model = cls.from_pretrained(spec.model_id)
            model.compile(
                forecast_config_cls(
                    max_context=max_context,
                    max_horizon=max_horizon,
                    normalize_inputs=bool(model_params.get("normalize_inputs", True)),
                    use_continuous_quantile_head=bool(
                        model_params.get("use_continuous_quantile_head", True)
                    ),
                    force_flip_invariance=bool(model_params.get("force_flip_invariance", True)),
                    infer_is_positive=bool(model_params.get("infer_is_positive", True)),
                    fix_quantile_crossing=bool(model_params.get("fix_quantile_crossing", True)),
                )
            )
        elif setup == "1p0_200m":
            try:
                timesfm_model_cls = getattr(timesfm, "TimesFm")
                hparams_cls = getattr(timesfm, "TimesFmHparams")
                checkpoint_cls = getattr(timesfm, "TimesFmCheckpoint")
            except AttributeError as exc:
                raise ImportError(
                    "timesfm_1p0_200m_forecaster requires the archived TimesFM 1.x API. "
                    "Install a compatible package such as `timesfm==1.3.0`."
                ) from exc
            model = timesfm_model_cls(
                hparams=hparams_cls(
                    backend=str(model_params.get("backend", "cpu")),
                    per_core_batch_size=int(model_params.get("batch_size", 32)),
                    horizon_len=max_horizon,
                    context_len=max_context,
                ),
                checkpoint=checkpoint_cls(huggingface_repo_id=spec.model_id),
            )
        else:
            raise ValueError(f"Unsupported TimesFM setup: {setup}")
        cache[cache_key] = model
        return model

    def _predictor(
        full_df: pd.DataFrame,
        train_idx: np.ndarray,
        test_idx: np.ndarray,
        feature_cols: list[str],
        target_col: str,
        model_params: dict[str, Any],
        runtime_meta: dict[str, Any],
    ) -> tuple[pd.Series, dict[str, pd.Series], object, dict[str, Any]]:
        del feature_cols, target_col, runtime_meta
        spec = _resolve_spec(
            full_df,
            model_params,
            model_family=f"timesfm_{setup}",
            default_model_id=default_model_id,
        )
        contexts, row_positions, last_values, index = _build_context_batch(full_df, test_idx, spec)
        model = _load_model(model_params, spec)
        if not contexts:
            return (
                pd.Series(dtype="float32", index=index),
                {},
                model,
                _chronos_common_meta(spec=spec, train_idx=train_idx, contexts=contexts, model_params=model_params),
            )

        if setup == "2p5_200m":
            point_forecast, quantile_forecast = model.forecast(
                horizon=spec.prediction_length,
                inputs=[np.asarray(context, dtype=float) for context in contexts],
            )
        else:
            frequency = int(model_params.get("frequency", model_params.get("freq_category", 0)))
            point_forecast, quantile_forecast = model.forecast(
                [np.asarray(context, dtype=float) for context in contexts],
                freq=[frequency] * len(contexts),
            )
        point_matrix = _matrix(
            point_forecast,
            expected_rows=len(contexts),
            horizon=spec.prediction_length,
            name="timesfm_point_forecast",
        )
        quantile_forecasts = _timesfm_quantile_forecasts(
            quantile_forecast,
            quantiles=spec.quantiles,
            expected_rows=len(contexts),
            horizon=spec.prediction_length,
        )
        pred_ret, extra_cols = _assemble_prediction_output(
            index=index,
            row_positions=row_positions,
            last_context_values=last_values,
            point_forecast=point_matrix,
            quantile_forecasts=quantile_forecasts,
            full_df=full_df,
            spec=spec,
        )
        meta = _chronos_common_meta(
            spec=spec,
            train_idx=train_idx,
            contexts=contexts,
            model_params=model_params,
        )
        meta["timesfm_setup"] = setup
        meta["timesfm_quantiles_available"] = bool(quantile_forecasts)
        return pred_ret, extra_cols, model, meta

    return _predictor


__all__ = [
    "FoundationForecastSpec",
    "make_chronos2_fold_predictor",
    "make_chronos_bolt_fold_predictor",
    "make_timesfm_fold_predictor",
]
