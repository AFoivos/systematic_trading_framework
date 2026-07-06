from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from src.evaluation.diagnostics import summarize_numeric_distribution


def _numeric_series(frame: pd.DataFrame, column: str | None) -> pd.Series:
    if not column or column not in frame.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").astype(float)


def _finite_frame(frame: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    cols = [col for col in columns if col in frame.columns]
    if not cols:
        return pd.DataFrame(index=frame.index)
    out = frame.loc[:, cols].apply(pd.to_numeric, errors="coerce")
    return out.replace([np.inf, -np.inf], np.nan)


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if np.isfinite(out) else None


def _sample_frame(frame: pd.DataFrame, *, max_rows: int, random_state: int) -> pd.DataFrame:
    if max_rows <= 0 or len(frame) <= max_rows:
        return frame.copy()
    return frame.sample(n=max_rows, random_state=random_state).sort_index()


def prediction_autocorrelation(series: pd.Series, *, lags: Sequence[int] = (1, 2, 4, 8, 16)) -> pd.DataFrame:
    values = pd.to_numeric(series, errors="coerce").dropna().astype(float)
    rows: list[dict[str, Any]] = []
    for lag in lags:
        lag_int = int(lag)
        if lag_int <= 0 or len(values) <= lag_int:
            corr = None
        else:
            corr = _safe_float(values.corr(values.shift(lag_int)))
        rows.append({"lag": lag_int, "autocorrelation": corr})
    return pd.DataFrame(rows)


def prediction_realized_metrics(prediction: pd.Series, realized: pd.Series) -> dict[str, Any]:
    frame = pd.DataFrame({"prediction": prediction, "realized": realized}).replace([np.inf, -np.inf], np.nan).dropna()
    if frame.empty:
        return {
            "evaluation_rows": 0,
            "correlation": None,
            "spearman_rank_correlation": None,
            "calibration_slope": None,
            "calibration_intercept": None,
            "directional_accuracy": None,
            "mean_prediction": None,
            "mean_realized": None,
        }

    pred = frame["prediction"].astype(float)
    real = frame["realized"].astype(float)
    pred_var = float(pred.var(ddof=1)) if len(pred) >= 2 else 0.0
    slope = None
    intercept = None
    if len(pred) >= 2 and pred_var > 1e-12:
        cov = float(np.cov(pred.to_numpy(dtype=float), real.to_numpy(dtype=float), ddof=1)[0, 1])
        slope = float(cov / pred_var)
        intercept = float(real.mean() - slope * pred.mean())

    corr = _safe_float(pred.corr(real)) if len(frame) >= 2 else None
    spearman = _safe_float(pred.corr(real, method="spearman")) if len(frame) >= 2 else None
    return {
        "evaluation_rows": int(len(frame)),
        "correlation": corr,
        "spearman_rank_correlation": spearman,
        "calibration_slope": slope,
        "calibration_intercept": intercept,
        "directional_accuracy": float((np.sign(pred) == np.sign(real)).mean()),
        "mean_prediction": float(pred.mean()),
        "mean_realized": float(real.mean()),
    }


def prediction_quantile_table(
    prediction: pd.Series,
    realized: pd.Series,
    *,
    expected_net_return: pd.Series | None = None,
    turnover: pd.Series | None = None,
    costs: pd.Series | None = None,
    quantiles: int = 10,
) -> pd.DataFrame:
    frame = pd.DataFrame({"prediction": prediction, "realized": realized})
    if expected_net_return is not None:
        frame["expected_net_return"] = expected_net_return
    if turnover is not None:
        frame["turnover"] = turnover
    if costs is not None:
        frame["cost"] = costs
    frame = frame.replace([np.inf, -np.inf], np.nan).dropna(subset=["prediction", "realized"])
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "quantile",
                "rows",
                "prediction_mean",
                "realized_mean",
                "realized_sharpe",
                "hit_rate",
                "turnover_mean",
                "cost_mean",
                "net_return_mean",
            ]
        )

    q_count = max(2, int(quantiles))
    try:
        frame["quantile"] = pd.qcut(frame["prediction"], q=min(q_count, len(frame)), labels=False, duplicates="drop")
    except ValueError:
        frame["quantile"] = 0
    rows: list[dict[str, Any]] = []
    for quantile, group in frame.groupby("quantile", sort=True):
        realized_values = group["realized"].astype(float)
        realized_std = float(realized_values.std(ddof=1)) if len(realized_values) >= 2 else 0.0
        cost_mean = float(group["cost"].mean()) if "cost" in group.columns else 0.0
        net_return = realized_values - group["cost"].fillna(0.0).astype(float) if "cost" in group.columns else realized_values
        rows.append(
            {
                "quantile": int(quantile),
                "rows": int(len(group)),
                "prediction_mean": float(group["prediction"].mean()),
                "expected_net_return_mean": (
                    float(group["expected_net_return"].mean()) if "expected_net_return" in group.columns else None
                ),
                "realized_mean": float(realized_values.mean()),
                "realized_sharpe": float(realized_values.mean() / realized_std) if realized_std > 1e-12 else None,
                "hit_rate": float((np.sign(group["prediction"]) == np.sign(realized_values)).mean()),
                "turnover_mean": float(group["turnover"].mean()) if "turnover" in group.columns else None,
                "cost_mean": cost_mean if "cost" in group.columns else None,
                "net_return_mean": float(net_return.mean()),
            }
        )
    return pd.DataFrame(rows)


def quantile_monotonicity(quantile_table: pd.DataFrame) -> dict[str, Any]:
    if quantile_table.empty or "realized_mean" not in quantile_table.columns:
        return {"monotonicity": None, "monotonic_increasing_steps": 0, "quantile_count": 0}
    ordered = quantile_table.sort_values("quantile")
    realized = pd.to_numeric(ordered["realized_mean"], errors="coerce")
    valid = realized.notna()
    if int(valid.sum()) < 2:
        return {"monotonicity": None, "monotonic_increasing_steps": 0, "quantile_count": int(valid.sum())}
    ranks = pd.Series(np.arange(int(valid.sum())), index=realized.loc[valid].index, dtype=float)
    monotonicity = _safe_float(ranks.corr(realized.loc[valid], method="spearman"))
    diffs = realized.loc[valid].diff().dropna()
    return {
        "monotonicity": monotonicity,
        "monotonic_increasing_steps": int((diffs > 0.0).sum()),
        "quantile_count": int(valid.sum()),
    }


def residual_diagnostics(
    prediction: pd.Series,
    realized: pd.Series,
    *,
    volatility: pd.Series | None = None,
    forecast_abs: pd.Series | None = None,
) -> dict[str, Any]:
    frame = pd.DataFrame({"prediction": prediction, "realized": realized}).replace([np.inf, -np.inf], np.nan).dropna()
    if frame.empty:
        return {"rows": 0, "distribution": summarize_numeric_distribution([]), "autocorrelation": []}
    residual = frame["realized"].astype(float) - frame["prediction"].astype(float)
    out = {
        "rows": int(len(residual)),
        "distribution": summarize_numeric_distribution(residual),
        "autocorrelation": prediction_autocorrelation(residual, lags=(1, 2, 4, 8)).to_dict(orient="records"),
        "residual_vs_forecast_abs_correlation": None,
        "residual_vs_volatility_correlation": None,
    }
    if forecast_abs is not None:
        abs_series = pd.to_numeric(forecast_abs, errors="coerce").reindex(residual.index).abs()
        out["residual_vs_forecast_abs_correlation"] = _safe_float(residual.corr(abs_series))
    if volatility is not None:
        vol = pd.to_numeric(volatility, errors="coerce").reindex(residual.index)
        out["residual_vs_volatility_correlation"] = _safe_float(residual.corr(vol))
    return out


def compute_regime_diagnostics(
    frame: pd.DataFrame,
    *,
    prediction_col: str,
    realized_col: str,
    expected_net_return_col: str | None = None,
    volatility_col: str | None = None,
    adx_col: str | None = "adx_14",
    turnover: pd.Series | None = None,
    costs: pd.Series | None = None,
) -> pd.DataFrame:
    prediction = _numeric_series(frame, prediction_col)
    realized = _numeric_series(frame, realized_col)
    expected = _numeric_series(frame, expected_net_return_col) if expected_net_return_col else pd.Series(dtype=float)
    work = pd.DataFrame({"prediction": prediction, "realized": realized}, index=frame.index)
    if not expected.empty:
        work["expected_net_return"] = expected
    if turnover is not None:
        work["turnover"] = pd.to_numeric(turnover, errors="coerce").reindex(frame.index)
    if costs is not None:
        work["cost"] = pd.to_numeric(costs, errors="coerce").reindex(frame.index)

    regimes: dict[str, pd.Series] = {}
    vol = _numeric_series(frame, volatility_col)
    if not vol.empty and vol.notna().sum() >= 4:
        low_cut = float(vol.quantile(0.33))
        high_cut = float(vol.quantile(0.67))
        regimes["low_volatility"] = vol <= low_cut
        regimes["high_volatility"] = vol >= high_cut
    adx = _numeric_series(frame, adx_col)
    if not adx.empty and adx.notna().sum() >= 4:
        regimes["trending"] = adx >= 25.0
        regimes["mean_reverting"] = adx < 18.0
    if not regimes:
        regimes["all"] = pd.Series(True, index=frame.index)

    rows: list[dict[str, Any]] = []
    for regime, mask in regimes.items():
        subset = work.loc[mask.reindex(work.index).fillna(False).astype(bool)].dropna(subset=["prediction", "realized"])
        if subset.empty:
            rows.append({"regime": regime, "rows": 0})
            continue
        metrics = prediction_realized_metrics(subset["prediction"], subset["realized"])
        realized_values = subset["realized"].astype(float)
        std = float(realized_values.std(ddof=1)) if len(realized_values) >= 2 else 0.0
        rows.append(
            {
                "regime": regime,
                "rows": int(len(subset)),
                "realized_mean": float(realized_values.mean()),
                "sharpe": float(realized_values.mean() / std) if std > 1e-12 else None,
                "hit_rate": metrics.get("directional_accuracy"),
                "calibration_slope": metrics.get("calibration_slope"),
                "prediction_correlation": metrics.get("correlation"),
                "turnover_mean": float(subset["turnover"].mean()) if "turnover" in subset.columns else None,
                "cost_mean": float(subset["cost"].mean()) if "cost" in subset.columns else None,
            }
        )
    return pd.DataFrame(rows)


def compute_lightgbm_importance(model: Any, feature_cols: Sequence[str]) -> dict[str, list[dict[str, Any]]]:
    booster = getattr(model, "booster_", None)
    if booster is None or not feature_cols:
        return {"gain": [], "split": []}
    rows: dict[str, list[dict[str, Any]]] = {}
    for importance_type in ("gain", "split"):
        try:
            values = np.asarray(booster.feature_importance(importance_type=importance_type), dtype=float)
        except Exception:
            rows[importance_type] = []
            continue
        order = np.argsort(np.abs(values))[::-1]
        total = float(np.sum(np.abs(values)))
        rows[importance_type] = [
            {
                "rank": int(rank),
                "feature": str(feature_cols[int(idx)]),
                "importance": float(values[int(idx)]),
                "importance_normalized": float(abs(values[int(idx)]) / total) if total > 0.0 else 0.0,
                "importance_type": importance_type,
            }
            for rank, idx in enumerate(order, start=1)
        ]
    return rows


def compute_lightgbm_shap_diagnostics(
    *,
    model: Any,
    features: pd.DataFrame,
    predictions: pd.Series,
    realized: pd.Series,
    feature_cols: Sequence[str],
    cfg: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    shap_cfg = dict(cfg or {})
    enabled = bool(shap_cfg.get("enabled", True))
    if not enabled:
        return {"enabled": False, "available": False, "reason": "disabled"}

    max_rows = int(shap_cfg.get("max_rows", 200) or 200)
    top_n = int(shap_cfg.get("top_n_features", 12) or 12)
    random_state = int(shap_cfg.get("random_state", 42) or 42)

    if features.empty or not feature_cols:
        return {"enabled": True, "available": False, "reason": "empty feature sample"}

    try:
        import shap  # type: ignore
    except Exception as exc:
        return {"enabled": True, "available": False, "reason": f"shap unavailable: {exc}"}

    x = _finite_frame(features, list(feature_cols)).dropna()
    if x.empty:
        return {"enabled": True, "available": False, "reason": "no complete rows for SHAP"}
    x = _sample_frame(x, max_rows=max_rows, random_state=random_state)

    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(x)
    except Exception as exc:
        return {"enabled": True, "available": False, "reason": f"TreeExplainer failed: {exc}"}

    if isinstance(shap_values, list):
        shap_values = shap_values[0]
    shap_array = np.asarray(shap_values, dtype=float)
    if shap_array.ndim != 2 or shap_array.shape[1] != len(feature_cols):
        return {"enabled": True, "available": False, "reason": "unexpected SHAP value shape"}

    mean_abs = np.nanmean(np.abs(shap_array), axis=0)
    order = np.argsort(mean_abs)[::-1]
    summary_rows = [
        {
            "rank": int(rank),
            "feature": str(feature_cols[int(idx)]),
            "mean_abs_shap": float(mean_abs[int(idx)]),
        }
        for rank, idx in enumerate(order, start=1)
    ]
    top_indices = list(order[: max(1, min(top_n, len(order)))])
    x_top = x.iloc[:, top_indices]
    shap_top = shap_array[:, top_indices]
    sample_rows: list[dict[str, Any]] = []
    for row_pos, index_value in enumerate(x.index):
        pred = _safe_float(predictions.reindex([index_value]).iloc[0]) if index_value in predictions.index else None
        truth = _safe_float(realized.reindex([index_value]).iloc[0]) if index_value in realized.index else None
        for local_idx, feature in enumerate(x_top.columns):
            sample_rows.append(
                {
                    "row_id": str(index_value),
                    "feature": str(feature),
                    "feature_value": _safe_float(x_top.iloc[row_pos, local_idx]),
                    "shap_value": _safe_float(shap_top[row_pos, local_idx]),
                    "prediction": pred,
                    "realized": truth,
                }
            )

    per_prediction = _per_prediction_shap_rows(
        x=x,
        shap_array=shap_array,
        predictions=predictions.reindex(x.index),
        realized=realized.reindex(x.index),
        feature_cols=list(feature_cols),
        top_k=int(shap_cfg.get("per_prediction_top_k", 5) or 5),
        row_limit=int(shap_cfg.get("per_prediction_row_limit", 3) or 3),
    )
    return {
        "enabled": True,
        "available": True,
        "sample_size": int(len(x)),
        "feature_count": int(len(feature_cols)),
        "summary": summary_rows,
        "sample_values": sample_rows,
        "per_prediction": per_prediction,
    }


def _per_prediction_shap_rows(
    *,
    x: pd.DataFrame,
    shap_array: np.ndarray,
    predictions: pd.Series,
    realized: pd.Series,
    feature_cols: list[str],
    top_k: int,
    row_limit: int,
) -> list[dict[str, Any]]:
    frame = pd.DataFrame({"prediction": predictions, "realized": realized}, index=x.index)
    frame["abs_prediction"] = frame["prediction"].abs()
    frame["loss_key"] = -frame["realized"]
    buckets = {
        "top_ranked_predictions": frame.sort_values("prediction", ascending=False).head(row_limit).index,
        "worst_predictions": frame.sort_values("prediction", ascending=True).head(row_limit).index,
        "largest_losses": frame.sort_values("loss_key", ascending=False).head(row_limit).index,
        "largest_gains": frame.sort_values("realized", ascending=False).head(row_limit).index,
    }
    index_to_pos = {idx: pos for pos, idx in enumerate(x.index)}
    rows: list[dict[str, Any]] = []
    for bucket, indices in buckets.items():
        for idx in indices:
            pos = index_to_pos.get(idx)
            if pos is None:
                continue
            shap_row = shap_array[pos, :]
            top_features = np.argsort(np.abs(shap_row))[::-1][: max(1, top_k)]
            for rank, feature_idx in enumerate(top_features, start=1):
                rows.append(
                    {
                        "bucket": bucket,
                        "row_id": str(idx),
                        "rank": int(rank),
                        "feature": str(feature_cols[int(feature_idx)]),
                        "feature_value": _safe_float(x.iloc[pos, int(feature_idx)]),
                        "shap_value": _safe_float(shap_row[int(feature_idx)]),
                        "prediction": _safe_float(frame.loc[idx, "prediction"]),
                        "realized": _safe_float(frame.loc[idx, "realized"]),
                    }
                )
    return rows


def collect_shap_diagnostics(model_meta: Mapping[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    sample_rows: list[dict[str, Any]] = []
    per_prediction_rows: list[dict[str, Any]] = []
    per_asset = dict(model_meta.get("per_asset", {}) or {})
    if not per_asset:
        per_asset = {"asset": dict(model_meta)}
    for asset, meta in sorted(per_asset.items()):
        for fold in list(dict(meta or {}).get("folds", []) or []):
            fold_id = int(dict(fold).get("fold", 0) or 0)
            shap_payload = dict(dict(fold).get("shap", {}) or {})
            for row in list(shap_payload.get("summary", []) or []):
                summary_rows.append(dict(row) | {"asset": asset, "fold": fold_id})
            for row in list(shap_payload.get("sample_values", []) or []):
                sample_rows.append(dict(row) | {"asset": asset, "fold": fold_id})
            for row in list(shap_payload.get("per_prediction", []) or []):
                per_prediction_rows.append(dict(row) | {"asset": asset, "fold": fold_id})
    return (
        pd.DataFrame(summary_rows),
        pd.DataFrame(sample_rows),
        pd.DataFrame(per_prediction_rows),
    )


def collect_shap_status(model_meta: Mapping[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    per_asset = dict(model_meta.get("per_asset", {}) or {})
    if not per_asset:
        per_asset = {"asset": dict(model_meta)}
    for asset, meta in sorted(per_asset.items()):
        for fold in list(dict(meta or {}).get("folds", []) or []):
            fold_id = int(dict(fold).get("fold", 0) or 0)
            payload = dict(dict(fold).get("shap", {}) or {})
            if not payload:
                continue
            rows.append(
                {
                    "asset": asset,
                    "fold": fold_id,
                    "enabled": bool(payload.get("enabled", False)),
                    "available": bool(payload.get("available", False)),
                    "reason": payload.get("reason"),
                    "sample_size": payload.get("sample_size"),
                    "feature_count": payload.get("feature_count"),
                }
            )
    return pd.DataFrame(rows)


def collect_lightgbm_importance(model_meta: Mapping[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    per_asset = dict(model_meta.get("per_asset", {}) or {})
    if not per_asset:
        per_asset = {"asset": dict(model_meta)}
    for asset, meta in sorted(per_asset.items()):
        for fold in list(dict(meta or {}).get("folds", []) or []):
            fold_id = int(dict(fold).get("fold", 0) or 0)
            payload = dict(dict(fold).get("lightgbm_importance", {}) or {})
            for importance_type, values in payload.items():
                for row in list(values or []):
                    rows.append(dict(row) | {"asset": asset, "fold": fold_id, "importance_type": importance_type})
    return pd.DataFrame(rows)


def build_dense_forecast_diagnostic_frames(
    asset_frames: Mapping[str, pd.DataFrame],
    *,
    model_meta: Mapping[str, Any],
    portfolio_weights: pd.DataFrame | None,
    net_returns: pd.Series | None,
    gross_returns: pd.Series | None,
    costs: pd.Series | None,
    turnover: pd.Series | None,
    cfg: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cfg_dict = dict(cfg or {})
    model_meta_dict = dict(model_meta or {})
    model_cfg = dict(cfg_dict.get("model", {}) or {})
    signals_cfg = dict(cfg_dict.get("signals", {}) or {})
    signal_params = dict(signals_cfg.get("params", {}) or {})
    diagnostics_cfg = dict(cfg_dict.get("diagnostics", {}) or {})
    forecast_cfg = dict(diagnostics_cfg.get("forecast", {}) or {})

    prediction_col = str(model_meta_dict.get("pred_ret_col") or model_cfg.get("pred_ret_col") or "pred_ret")
    expected_col = str(
        signal_params.get("expected_net_return_col")
        or dict(cfg_dict.get("portfolio", {}) or {}).get("expected_return_col")
        or "expected_net_return"
    )
    target_col = str(model_meta_dict.get("fwd_col") or dict(model_meta_dict.get("target", {}) or {}).get("label_col") or "target_future_return_v2")
    oos_col = str(model_meta_dict.get("pred_is_oos_col") or "pred_is_oos")
    volatility_col = str(forecast_cfg.get("volatility_col") or "atr_pct_rank_100")
    quantiles = int(forecast_cfg.get("quantiles", 10) or 10)
    lags = tuple(int(x) for x in list(forecast_cfg.get("autocorrelation_lags", [1, 2, 4, 8, 16]) or []))

    prediction_rows: list[pd.DataFrame] = []
    quantile_rows: list[pd.DataFrame] = []
    metrics_rows: list[dict[str, Any]] = []
    autocorr_rows: list[pd.DataFrame] = []
    residual_payload: dict[str, Any] = {}
    regime_rows: list[pd.DataFrame] = []

    for asset, frame in sorted(asset_frames.items()):
        if prediction_col not in frame.columns or target_col not in frame.columns:
            continue
        mask = frame[oos_col].astype(bool) if oos_col in frame.columns else pd.Series(True, index=frame.index)
        work = frame.loc[mask].copy()
        pred = _numeric_series(work, prediction_col)
        expected = _numeric_series(work, expected_col)
        realized = _numeric_series(work, target_col)
        cost_est = _numeric_series(work, signal_params.get("estimated_cost_col", "estimated_round_trip_cost"))
        asset_turnover = None
        if portfolio_weights is not None and asset in portfolio_weights.columns:
            asset_turnover = portfolio_weights[asset].astype(float).diff().abs().reindex(work.index)

        pred_frame = pd.DataFrame(
            {
                "asset": asset,
                "prediction": pred,
                "expected_net_return": expected if not expected.empty else np.nan,
                "realized": realized,
                "residual": realized - pred,
            },
            index=work.index,
        ).replace([np.inf, -np.inf], np.nan)
        for quantile_col in sorted(
            col
            for col in work.columns
            if str(col).startswith("pred_q")
        ):
            pred_frame[str(quantile_col)] = _numeric_series(work, str(quantile_col))
        pred_frame.index.name = "timestamp"
        prediction_rows.append(pred_frame.reset_index())

        metrics = prediction_realized_metrics(pred, realized)
        quantile_table = prediction_quantile_table(
            pred,
            realized,
            expected_net_return=expected if not expected.empty else None,
            turnover=asset_turnover,
            costs=cost_est if not cost_est.empty else None,
            quantiles=quantiles,
        )
        metrics.update(quantile_monotonicity(quantile_table))
        metrics_rows.append({"asset": asset, **metrics})
        if not quantile_table.empty:
            quantile_rows.append(quantile_table.assign(asset=asset))
        auto = prediction_autocorrelation(pred, lags=lags).assign(asset=asset)
        autocorr_rows.append(auto)
        residual_payload[asset] = residual_diagnostics(
            pred,
            realized,
            volatility=_numeric_series(work, volatility_col),
            forecast_abs=pred.abs(),
        )
        regime = compute_regime_diagnostics(
            work,
            prediction_col=prediction_col,
            realized_col=target_col,
            expected_net_return_col=expected_col if expected_col in work.columns else None,
            volatility_col=volatility_col if volatility_col in work.columns else None,
            adx_col="adx_14",
            turnover=asset_turnover,
            costs=cost_est if not cost_est.empty else None,
        )
        if not regime.empty:
            regime_rows.append(regime.assign(asset=asset))

    prediction_frame = pd.concat(prediction_rows, ignore_index=True) if prediction_rows else pd.DataFrame()
    quantile_frame = pd.concat(quantile_rows, ignore_index=True) if quantile_rows else pd.DataFrame()
    autocorr_frame = pd.concat(autocorr_rows, ignore_index=True) if autocorr_rows else pd.DataFrame()
    regime_frame = pd.concat(regime_rows, ignore_index=True) if regime_rows else pd.DataFrame()
    metrics_frame = pd.DataFrame(metrics_rows)
    summary = {
        "prediction_distribution": summarize_numeric_distribution(prediction_frame["prediction"] if "prediction" in prediction_frame.columns else []),
        "expected_net_return_distribution": summarize_numeric_distribution(
            prediction_frame["expected_net_return"] if "expected_net_return" in prediction_frame.columns else []
        ),
        "prediction_vs_realized": (
            prediction_realized_metrics(prediction_frame["prediction"], prediction_frame["realized"])
            if {"prediction", "realized"}.issubset(prediction_frame.columns)
            else prediction_realized_metrics(pd.Series(dtype=float), pd.Series(dtype=float))
        ),
        "quantile_monotonicity": quantile_monotonicity(
            quantile_frame.groupby("quantile", as_index=False)["realized_mean"].mean()
            if not quantile_frame.empty and "quantile" in quantile_frame.columns
            else pd.DataFrame()
        ),
        "residuals": residual_payload,
    }
    turnover_cost = turnover_cost_diagnostics(
        net_returns=net_returns,
        gross_returns=gross_returns,
        costs=costs,
        turnover=turnover,
    )
    return {
        "prediction_frame": prediction_frame,
        "prediction_metrics": metrics_frame,
        "prediction_quantiles": quantile_frame,
        "prediction_autocorrelation": autocorr_frame,
        "residual_diagnostics": residual_payload,
        "regime_diagnostics": regime_frame,
        "summary": summary,
        "turnover_cost": turnover_cost,
        "shap": collect_shap_diagnostics(model_meta_dict),
        "shap_status": collect_shap_status(model_meta_dict),
        "lightgbm_importance": collect_lightgbm_importance(model_meta_dict),
    }


def turnover_cost_diagnostics(
    *,
    net_returns: pd.Series | None,
    gross_returns: pd.Series | None,
    costs: pd.Series | None,
    turnover: pd.Series | None,
) -> dict[str, Any]:
    frame = pd.DataFrame(
        {
            "net_return": pd.Series(dtype=float) if net_returns is None else pd.to_numeric(net_returns, errors="coerce"),
            "gross_return": pd.Series(dtype=float) if gross_returns is None else pd.to_numeric(gross_returns, errors="coerce"),
            "cost": pd.Series(dtype=float) if costs is None else pd.to_numeric(costs, errors="coerce"),
            "turnover": pd.Series(dtype=float) if turnover is None else pd.to_numeric(turnover, errors="coerce"),
        }
    ).replace([np.inf, -np.inf], np.nan)
    if frame.empty:
        return {"summary": {}, "timeseries": pd.DataFrame()}
    frame["rolling_turnover_mean"] = frame["turnover"].rolling(48, min_periods=4).mean()
    frame["cumulative_cost"] = frame["cost"].fillna(0.0).cumsum()
    frame["cumulative_gross_pnl"] = frame["gross_return"].fillna(0.0).cumsum()
    frame["cumulative_net_pnl"] = frame["net_return"].fillna(0.0).cumsum()
    gross_abs = float(frame["gross_return"].abs().sum())
    total_cost = float(frame["cost"].sum())
    summary = {
        "rows": int(len(frame)),
        "total_turnover": float(frame["turnover"].sum()),
        "avg_turnover": float(frame["turnover"].mean()),
        "rebalance_frequency": float((frame["turnover"].fillna(0.0) > 0.0).mean()),
        "churn_frequency": float((frame["turnover"].fillna(0.0) > frame["turnover"].fillna(0.0).median()).mean()),
        "total_cost": total_cost,
        "gross_pnl": float(frame["gross_return"].sum()),
        "net_pnl": float(frame["net_return"].sum()),
        "cost_to_abs_gross_pnl": float(total_cost / gross_abs) if gross_abs > 1e-12 else None,
        "turnover_vs_net_pnl_correlation": _safe_float(frame["turnover"].corr(frame["net_return"])),
    }
    return {"summary": summary, "timeseries": frame}


def write_dense_diagnostic_plots(diagnostics_dir: Path, frames: Mapping[str, Any]) -> dict[str, Path]:
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    import matplotlib

    mpl_dir = diagnostics_dir / ".mplconfig"
    mpl_dir.mkdir(parents=True, exist_ok=True)
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    paths: dict[str, Path] = {}
    prediction_frame = frames.get("prediction_frame")
    if isinstance(prediction_frame, pd.DataFrame) and not prediction_frame.empty:
        time_sample = prediction_frame.copy()
        if "timestamp" in time_sample.columns:
            time_sample["timestamp"] = pd.to_datetime(time_sample["timestamp"], errors="coerce")
            time_sample = time_sample.dropna(subset=["timestamp"])
        if {"timestamp", "prediction", "realized"}.issubset(time_sample.columns) and not time_sample.empty:
            path = diagnostics_dir / "prediction_timeseries.png"
            assets = (
                time_sample["asset"].dropna().astype(str).drop_duplicates().head(4).tolist()
                if "asset" in time_sample.columns
                else ["asset"]
            )
            fig, axes = plt.subplots(
                len(assets),
                1,
                figsize=(12, max(4, 3.2 * len(assets))),
                sharex=False,
                squeeze=False,
            )
            quantile_cols = sorted(
                col
                for col in time_sample.columns
                if str(col).startswith("pred_q")
                and pd.to_numeric(time_sample[col], errors="coerce").notna().any()
            )
            for row_idx, asset in enumerate(assets):
                ax = axes[row_idx][0]
                asset_frame = (
                    time_sample.loc[time_sample["asset"].astype(str) == asset].copy()
                    if "asset" in time_sample.columns
                    else time_sample.copy()
                )
                asset_frame = asset_frame.sort_values("timestamp")
                if len(asset_frame) > 2000:
                    take_idx = np.linspace(0, len(asset_frame) - 1, 2000).astype(int)
                    asset_frame = asset_frame.iloc[take_idx]
                x = asset_frame["timestamp"]
                realized = pd.to_numeric(asset_frame["realized"], errors="coerce")
                prediction = pd.to_numeric(asset_frame["prediction"], errors="coerce")
                ax.plot(x, realized, linewidth=1.0, alpha=0.75, label="realized")
                ax.plot(x, prediction, linewidth=1.1, alpha=0.9, label="prediction")
                if len(quantile_cols) >= 2:
                    low = pd.to_numeric(asset_frame[quantile_cols[0]], errors="coerce")
                    high = pd.to_numeric(asset_frame[quantile_cols[-1]], errors="coerce")
                    ax.fill_between(x, low, high, alpha=0.16, label=f"{quantile_cols[0]}-{quantile_cols[-1]}")
                ax.axhline(0.0, color="black", linewidth=0.8, alpha=0.55)
                ax.set_title(f"Forecast Time Series: {asset}")
                ax.set_ylabel("Forward return")
                ax.grid(alpha=0.25)
                ax.legend(loc="best")
            fig.tight_layout()
            fig.savefig(path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            paths["prediction_timeseries"] = path

        path = diagnostics_dir / "prediction_histogram.png"
        fig, ax = plt.subplots(figsize=(10, 4))
        for column in ("prediction", "expected_net_return"):
            if column in prediction_frame.columns:
                values = pd.to_numeric(prediction_frame[column], errors="coerce").dropna()
                if not values.empty:
                    ax.hist(values.to_numpy(dtype=float), bins=50, alpha=0.55, label=column)
        ax.set_title("Prediction Distribution")
        ax.set_xlabel("Return forecast")
        ax.set_ylabel("Count")
        ax.grid(alpha=0.25)
        ax.legend(loc="best")
        fig.tight_layout()
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        paths["prediction_histogram"] = path

        path = diagnostics_dir / "prediction_vs_realized.png"
        sample = prediction_frame.dropna(subset=["prediction", "realized"])
        if not sample.empty:
            if len(sample) > 5000:
                sample = sample.sample(5000, random_state=42)
            fig, ax = plt.subplots(figsize=(6, 5))
            ax.scatter(sample["prediction"], sample["realized"], s=8, alpha=0.35)
            ax.axhline(0.0, color="black", linewidth=0.8)
            ax.axvline(0.0, color="black", linewidth=0.8)
            ax.set_title("Predicted vs Realized Return")
            ax.set_xlabel("Predicted return")
            ax.set_ylabel("Future realized return")
            ax.grid(alpha=0.25)
            fig.tight_layout()
            fig.savefig(path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            paths["prediction_vs_realized"] = path

        path = diagnostics_dir / "residual_histogram.png"
        residual = (
            pd.to_numeric(prediction_frame["residual"], errors="coerce").dropna()
            if "residual" in prediction_frame.columns
            else pd.Series(dtype=float)
        )
        if not residual.empty:
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.hist(residual.to_numpy(dtype=float), bins=50, alpha=0.75)
            ax.set_title("Residual Distribution")
            ax.set_xlabel("realized - predicted")
            ax.set_ylabel("Count")
            ax.grid(alpha=0.25)
            fig.tight_layout()
            fig.savefig(path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            paths["residual_histogram"] = path

    quantiles = frames.get("prediction_quantiles")
    if isinstance(quantiles, pd.DataFrame) and not quantiles.empty:
        path = diagnostics_dir / "prediction_quantiles.png"
        grouped = quantiles.groupby("quantile", as_index=False)[["realized_mean", "net_return_mean"]].mean()
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.plot(grouped["quantile"], grouped["realized_mean"], marker="o", label="realized")
        ax.plot(grouped["quantile"], grouped["net_return_mean"], marker="o", label="net")
        ax.set_title("Prediction Quantile Realized Return")
        ax.set_xlabel("Prediction quantile")
        ax.set_ylabel("Return")
        ax.grid(alpha=0.25)
        ax.legend(loc="best")
        fig.tight_layout()
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        paths["prediction_quantiles"] = path

    autocorr = frames.get("prediction_autocorrelation")
    if isinstance(autocorr, pd.DataFrame) and not autocorr.empty:
        path = diagnostics_dir / "prediction_autocorrelation.png"
        grouped = autocorr.groupby("lag", as_index=False)["autocorrelation"].mean()
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(grouped["lag"].astype(str), grouped["autocorrelation"])
        ax.set_title("Prediction Autocorrelation")
        ax.set_xlabel("Lag")
        ax.set_ylabel("Correlation")
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        paths["prediction_autocorrelation"] = path

    turnover_cost = dict(frames.get("turnover_cost", {}) or {})
    turnover_ts = turnover_cost.get("timeseries")
    if isinstance(turnover_ts, pd.DataFrame) and not turnover_ts.empty:
        path = diagnostics_dir / "turnover_timeseries.png"
        fig, ax = plt.subplots(figsize=(11, 4))
        ax.plot(turnover_ts.index, turnover_ts["turnover"], linewidth=1.2, label="turnover")
        ax.plot(turnover_ts.index, turnover_ts["rolling_turnover_mean"], linewidth=1.8, label="rolling mean")
        ax.set_title("Turnover Time Series")
        ax.set_ylabel("Turnover")
        ax.grid(alpha=0.25)
        ax.legend(loc="best")
        fig.tight_layout()
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        paths["turnover_timeseries"] = path

        path = diagnostics_dir / "cost_vs_gross_pnl.png"
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.scatter(turnover_ts["gross_return"], turnover_ts["cost"], s=10, alpha=0.4)
        ax.set_title("Cost vs Gross PnL")
        ax.set_xlabel("Gross return")
        ax.set_ylabel("Cost")
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        paths["cost_vs_gross_pnl"] = path

        path = diagnostics_dir / "turnover_vs_net_pnl.png"
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.scatter(turnover_ts["turnover"], turnover_ts["net_return"], s=10, alpha=0.4)
        ax.set_title("Turnover vs Net PnL")
        ax.set_xlabel("Turnover")
        ax.set_ylabel("Net return")
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        paths["turnover_vs_net_pnl"] = path

    _write_shap_plots(diagnostics_dir, frames, plt, paths)
    _write_lightgbm_importance_plots(diagnostics_dir, frames, plt, paths)
    return paths


def _write_shap_plots(diagnostics_dir: Path, frames: Mapping[str, Any], plt: Any, paths: dict[str, Path]) -> None:
    _, shap_sample, _ = frames.get("shap", (pd.DataFrame(), pd.DataFrame(), pd.DataFrame()))
    if not isinstance(shap_sample, pd.DataFrame) or shap_sample.empty:
        return
    sample = shap_sample.dropna(subset=["feature", "shap_value", "feature_value"])
    if sample.empty:
        return
    feature_order = (
        sample.assign(abs_shap=sample["shap_value"].abs())
        .groupby("feature")["abs_shap"]
        .mean()
        .sort_values(ascending=False)
        .head(20)
        .index.tolist()
    )
    path = diagnostics_dir / "shap_summary.png"
    fig, ax = plt.subplots(figsize=(10, max(4, 0.35 * len(feature_order))))
    for y_pos, feature in enumerate(feature_order):
        sub = sample.loc[sample["feature"] == feature]
        ax.scatter(sub["shap_value"], np.full(len(sub), y_pos), c=sub["feature_value"], cmap="viridis", s=8, alpha=0.55)
    ax.set_yticks(np.arange(len(feature_order)))
    ax.set_yticklabels(feature_order)
    ax.set_title("SHAP Summary")
    ax.set_xlabel("SHAP value")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    paths["shap_summary"] = path

    preferred_tokens = ("rsi", "adx", "macd", "atr", "vol", "roc", "ema")
    dependence_features = [
        feature
        for feature in feature_order
        if any(token in str(feature).lower() for token in preferred_tokens)
    ][:6]
    for feature in dependence_features:
        sub = sample.loc[sample["feature"] == feature]
        if sub.empty:
            continue
        safe_name = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(feature))[:80]
        path = diagnostics_dir / f"shap_dependence_{safe_name}.png"
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.scatter(sub["feature_value"], sub["shap_value"], s=10, alpha=0.45)
        ax.set_title(f"SHAP Dependence: {feature}")
        ax.set_xlabel(str(feature))
        ax.set_ylabel("SHAP value")
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        paths[f"shap_dependence_{safe_name}"] = path


def _write_lightgbm_importance_plots(
    diagnostics_dir: Path,
    frames: Mapping[str, Any],
    plt: Any,
    paths: dict[str, Path],
) -> None:
    importance = frames.get("lightgbm_importance")
    if not isinstance(importance, pd.DataFrame) or importance.empty:
        return
    for importance_type in ("gain", "split"):
        sub = importance.loc[importance["importance_type"] == importance_type]
        if sub.empty:
            continue
        grouped = sub.groupby("feature", as_index=False)["importance"].mean()
        grouped = grouped.assign(abs_importance=grouped["importance"].abs()).sort_values("abs_importance", ascending=False).head(20)
        path = diagnostics_dir / f"lgbm_{importance_type}_importance.png"
        fig, ax = plt.subplots(figsize=(10, max(4, 0.35 * len(grouped))))
        ax.barh(grouped["feature"], grouped["importance"])
        ax.invert_yaxis()
        ax.set_title(f"LightGBM {importance_type.title()} Importance")
        ax.set_xlabel("Importance")
        ax.grid(axis="x", alpha=0.25)
        fig.tight_layout()
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        paths[f"lgbm_{importance_type}_importance"] = path


__all__ = [
    "build_dense_forecast_diagnostic_frames",
    "collect_lightgbm_importance",
    "collect_shap_diagnostics",
    "collect_shap_status",
    "compute_lightgbm_importance",
    "compute_lightgbm_shap_diagnostics",
    "compute_regime_diagnostics",
    "prediction_autocorrelation",
    "prediction_quantile_table",
    "prediction_realized_metrics",
    "quantile_monotonicity",
    "residual_diagnostics",
    "turnover_cost_diagnostics",
    "write_dense_diagnostic_plots",
]
