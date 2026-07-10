from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
import warnings

import numpy as np
import pandas as pd

from src.features.helpers.rolling_linear_regression import compute_rolling_linear_regression


PRIMARY_FORECAST_FEATURES = [
    "pred_ret",
    "abs_pred_ret",
    "primary_candidate_strength",
    "primary_candidate_threshold_distance",
    "pred_ret_diff_1",
    "pred_ret_diff_2",
    "pred_ret_rolling_mean_4",
    "pred_ret_rolling_std_8",
    "pred_ret_rolling_zscore_192",
    "forecast_same_side_count_2",
    "forecast_same_side_count_4",
]

ORIENTED_FEATURE_SOURCES = [
    "ema_trend_48_192",
    "mama_minus_fama_over_atr",
    "roofing_filter_over_atr",
    "instantaneous_trendline_slope_over_atr",
    "decycler_slope_over_atr",
    "frama_slope_over_atr",
    "supersmoother_slope_over_atr",
    "distance_from_ema24_atr",
    "distance_from_ema96_atr",
    "macd_hist",
    "close_location",
]

ORIENTED_FEATURES = [f"oriented_{name}" for name in ORIENTED_FEATURE_SOURCES]

REGIME_FEATURES = [
    "atr_over_price_48",
    "atr_pct_rank_192",
    "vol_rolling_24",
    "vol_rolling_48",
    "vol_rolling_96",
    "vol_rolling_192",
    "vol_ratio_24_192",
    "bollinger_bandwidth",
    "bollinger_bandwidth_rank_192",
    "bollinger_percent_b",
    "range_to_atr",
    "dominant_cycle_period",
    "dominant_cycle_phase_normalized",
]

CANDLE_PATH_RISK_FEATURES = [
    "body_ratio",
    "upper_wick_ratio",
    "lower_wick_ratio",
    "close_location",
    "distance_from_ema24_atr",
    "distance_from_ema96_atr",
    "close_over_bb_upper_192",
    "close_over_bb_mid_192",
]

TREND_QUALITY_FEATURES = [
    "rolling_price_slope_48_atr",
    "rolling_price_r2_48",
    "rolling_price_slope_96_atr",
    "rolling_price_r2_96",
    "signed_trend_quality_48",
    "signed_trend_quality_96",
]

DEFAULT_META_FEATURE_COLS = list(
    dict.fromkeys(
        [
            *PRIMARY_FORECAST_FEATURES,
            "primary_candidate_side",
            *ORIENTED_FEATURES,
            *REGIME_FEATURES,
            *CANDLE_PATH_RISK_FEATURES,
            *TREND_QUALITY_FEATURES,
        ]
    )
)

FORBIDDEN_FEATURE_PREFIXES = ("meta_",)
FORBIDDEN_FEATURE_EXACT = {
    "meta_candidate",
    "meta_side",
    "meta_entry_price",
    "meta_exit_price",
    "meta_exit_reason",
    "meta_hit_type",
    "meta_hit_step",
    "meta_holding_bars",
    "meta_gross_return",
    "meta_net_return",
    "meta_gross_r",
    "meta_net_r",
    "meta_mfe_r",
    "meta_mae_r",
}


@dataclass
class FoldArtifact:
    fold: int
    model_kind: str
    model: Any
    feature_cols: list[str]
    impute_values: np.ndarray
    center: np.ndarray
    scale: np.ndarray
    scaler: str
    calibrator: Any | None
    train_indices: np.ndarray
    model_train_indices: np.ndarray
    calibration_indices: np.ndarray
    test_indices: np.ndarray
    train_rows: int
    model_train_rows: int
    calibration_rows: int
    test_rows: int
    train_max_pos: int | None
    test_start_pos: int
    purge_bars: int
    calibration_applied: bool


@dataclass
class MetaStackingResult:
    frame: pd.DataFrame
    feature_cols: list[str]
    fold_diagnostics: list[dict[str, Any]]
    artifacts: list[FoldArtifact] = field(default_factory=list)
    model_kind: str = ""
    label_col: str = ""
    calibration_method: str = "none"
    final_test_fold: int | float | str | None = None


@dataclass
class ConstantProbabilityModel:
    probability: float

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        p = float(np.clip(self.probability, 1e-6, 1.0 - 1e-6))
        return np.column_stack([np.full(len(x), 1.0 - p), np.full(len(x), p)])


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)


def _group_transform(
    frame: pd.DataFrame,
    series: pd.Series,
    *,
    group_col: str | None,
    fn: Any,
) -> pd.Series:
    if group_col and group_col in frame.columns:
        return series.groupby(frame[group_col], sort=False, group_keys=False).transform(fn)
    return fn(series)


def _group_rolling_linear(
    frame: pd.DataFrame,
    *,
    price_col: str,
    group_col: str | None,
    window: int,
) -> tuple[pd.Series, pd.Series]:
    if group_col and group_col in frame.columns:
        slope_parts: list[pd.Series] = []
        r2_parts: list[pd.Series] = []
        for _, group in frame.groupby(group_col, sort=False):
            slope, _, r2 = compute_rolling_linear_regression(_numeric(group[price_col]), window=window)
            slope_parts.append(pd.Series(slope.to_numpy(dtype=float), index=group.index))
            r2_parts.append(pd.Series(r2.to_numpy(dtype=float), index=group.index))
        slope_all = pd.concat(slope_parts).sort_index()
        r2_all = pd.concat(r2_parts).sort_index()
        return slope_all.reindex(frame.index), r2_all.reindex(frame.index)
    slope, _, r2 = compute_rolling_linear_regression(_numeric(frame[price_col]), window=window)
    return pd.Series(slope.to_numpy(dtype=float), index=frame.index), pd.Series(r2.to_numpy(dtype=float), index=frame.index)


def build_causal_meta_features(
    df: pd.DataFrame,
    *,
    pred_col: str = "pred_ret",
    side_col: str = "primary_candidate_side",
    price_col: str = "close",
    volatility_col: str = "atr_over_price_48",
    group_col: str | None = "asset",
) -> pd.DataFrame:
    """
    Build the controlled causal feature set used by the ETHUSD stacked trade filter.
    """
    required = [pred_col, side_col, price_col, volatility_col]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for meta features: {missing}")

    out = df.copy()
    pred = _numeric(out[pred_col])
    side = np.sign(_numeric(out[side_col]).fillna(0.0).clip(lower=-1.0, upper=1.0))
    out["abs_pred_ret"] = pred.abs().astype("float32")
    out["pred_ret_diff_1"] = _group_transform(out, pred, group_col=group_col, fn=lambda s: s.diff(1)).astype("float32")
    out["pred_ret_diff_2"] = _group_transform(out, pred, group_col=group_col, fn=lambda s: s.diff(2)).astype("float32")
    out["pred_ret_rolling_mean_4"] = _group_transform(
        out,
        pred,
        group_col=group_col,
        fn=lambda s: s.rolling(4, min_periods=2).mean(),
    ).astype("float32")
    out["pred_ret_rolling_std_8"] = _group_transform(
        out,
        pred,
        group_col=group_col,
        fn=lambda s: s.rolling(8, min_periods=2).std(ddof=0),
    ).astype("float32")
    rolling_mean_192 = _group_transform(
        out,
        pred,
        group_col=group_col,
        fn=lambda s: s.rolling(192, min_periods=20).mean(),
    )
    rolling_std_192 = _group_transform(
        out,
        pred,
        group_col=group_col,
        fn=lambda s: s.rolling(192, min_periods=20).std(ddof=0),
    )
    out["pred_ret_rolling_zscore_192"] = (
        (pred - rolling_mean_192) / rolling_std_192.replace(0.0, np.nan)
    ).astype("float32")

    forecast_side = np.sign(pred.fillna(0.0))
    same_side = pd.Series((forecast_side == side) & side.ne(0.0), index=out.index, dtype=float)
    out["forecast_same_side_count_2"] = _group_transform(
        out,
        same_side,
        group_col=group_col,
        fn=lambda s: s.shift(1).rolling(2, min_periods=1).sum(),
    ).fillna(0.0).astype("float32")
    out["forecast_same_side_count_4"] = _group_transform(
        out,
        same_side,
        group_col=group_col,
        fn=lambda s: s.shift(1).rolling(4, min_periods=1).sum(),
    ).fillna(0.0).astype("float32")

    for source_col in ORIENTED_FEATURE_SOURCES:
        source = _numeric(out[source_col]) if source_col in out.columns else pd.Series(np.nan, index=out.index)
        out[f"oriented_{source_col}"] = (side * source).astype("float32")

    if "vol_rolling_24" in out.columns and "vol_rolling_192" in out.columns:
        denom = _numeric(out["vol_rolling_192"]).replace(0.0, np.nan)
        out["vol_ratio_24_192"] = (_numeric(out["vol_rolling_24"]) / denom).astype("float32")
    else:
        out["vol_ratio_24_192"] = np.nan

    atr_price = (_numeric(out[price_col]) * _numeric(out[volatility_col])).replace(0.0, np.nan)
    for window in (48, 96):
        slope, r2 = _group_rolling_linear(out, price_col=price_col, group_col=group_col, window=window)
        slope_atr_col = f"rolling_price_slope_{window}_atr"
        r2_col = f"rolling_price_r2_{window}"
        quality_col = f"signed_trend_quality_{window}"
        out[slope_atr_col] = (slope / atr_price).astype("float32")
        out[r2_col] = r2.astype("float32")
        out[quality_col] = (side * out[slope_atr_col].astype(float) * out[r2_col].astype(float)).astype("float32")

    for col in DEFAULT_META_FEATURE_COLS:
        if col not in out.columns:
            out[col] = np.nan
    return out


def validate_meta_feature_columns(feature_cols: list[str]) -> None:
    """
    Reject outcome, label, prediction, and path metadata columns from the meta-feature matrix.
    """
    bad: list[str] = []
    for col in feature_cols:
        name = str(col)
        if name in FORBIDDEN_FEATURE_EXACT or any(name.startswith(prefix) for prefix in FORBIDDEN_FEATURE_PREFIXES):
            bad.append(name)
    if bad:
        raise ValueError(f"Target/meta outcome columns are not allowed as meta features: {bad}")


def _finite_binary_labels(values: pd.Series) -> pd.Series:
    labels = pd.to_numeric(values, errors="coerce")
    valid = labels.dropna().astype(float)
    if not valid.isin([0.0, 1.0]).all():
        raise ValueError("Meta target labels must be binary 0/1 values.")
    return labels


def _fit_preprocessor(x_train: pd.DataFrame, *, scaler: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = x_train.astype(float).replace([np.inf, -np.inf], np.nan).to_numpy(dtype=float)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="All-NaN slice encountered", category=RuntimeWarning)
        impute = np.nanmedian(x, axis=0)
    impute = np.where(np.isfinite(impute), impute, 0.0)
    x_imp = np.where(np.isfinite(x), x, impute)
    if scaler == "none":
        center = np.zeros(x_imp.shape[1], dtype=float)
        scale = np.ones(x_imp.shape[1], dtype=float)
    elif scaler == "standard":
        center = x_imp.mean(axis=0)
        scale = x_imp.std(axis=0)
    elif scaler == "robust":
        center = np.median(x_imp, axis=0)
        q75 = np.quantile(x_imp, 0.75, axis=0)
        q25 = np.quantile(x_imp, 0.25, axis=0)
        scale = q75 - q25
    else:
        raise ValueError("scaler must be one of: none, standard, robust.")
    scale = np.where(np.isfinite(scale) & (np.abs(scale) > 1e-12), scale, 1.0)
    return impute.astype(float), center.astype(float), scale.astype(float)


def _transform_features(
    x_frame: pd.DataFrame,
    *,
    impute_values: np.ndarray,
    center: np.ndarray,
    scale: np.ndarray,
) -> np.ndarray:
    x = x_frame.astype(float).replace([np.inf, -np.inf], np.nan).to_numpy(dtype=float)
    x = np.where(np.isfinite(x), x, impute_values)
    return (x - center) / scale


def _model_default_params(model_kind: str, *, random_state: int) -> dict[str, Any]:
    if model_kind == "logistic_regression_clf":
        return {
            "C": 0.5,
            "class_weight": "balanced",
            "max_iter": 1000,
            "solver": "lbfgs",
            "random_state": random_state,
        }
    if model_kind == "lightgbm_clf":
        return {
            "n_estimators": 120,
            "learning_rate": 0.04,
            "num_leaves": 15,
            "max_depth": 4,
            "min_child_samples": 30,
            "subsample": 0.90,
            "colsample_bytree": 0.80,
            "reg_alpha": 0.10,
            "reg_lambda": 1.00,
            "random_state": random_state,
            "n_jobs": 1,
            "verbose": -1,
        }
    raise ValueError("model_kind must be one of: logistic_regression_clf, lightgbm_clf.")


def _fit_model(
    x_train: np.ndarray,
    y_train: np.ndarray,
    *,
    model_kind: str,
    params: dict[str, Any],
) -> Any:
    classes = np.unique(y_train.astype(int))
    if len(classes) < 2:
        return ConstantProbabilityModel(float(classes[0]) if len(classes) else 0.5)
    if model_kind == "logistic_regression_clf":
        from sklearn.linear_model import LogisticRegression

        model = LogisticRegression(**params)
    elif model_kind == "lightgbm_clf":
        from lightgbm import LGBMClassifier

        model = LGBMClassifier(**params)
    else:
        raise ValueError("Unsupported model_kind.")
    model.fit(x_train, y_train.astype(int))
    return model


def _predict_raw_prob(model: Any, x: np.ndarray) -> np.ndarray:
    if len(x) == 0:
        return np.asarray([], dtype=float)
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="X does not have valid feature names, but LGBMClassifier was fitted with feature names",
            category=UserWarning,
        )
        proba = model.predict_proba(x)
    if proba.ndim != 2:
        raise ValueError("Classifier predict_proba must return a 2D array.")
    if proba.shape[1] == 1:
        return np.full(len(x), float(proba[0, 0]))
    return np.asarray(proba[:, 1], dtype=float)


def _logit(prob: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(prob, dtype=float), 1e-6, 1.0 - 1e-6)
    return np.log(p / (1.0 - p))


def _fit_sigmoid_calibrator(raw_prob: np.ndarray, y: np.ndarray) -> Any | None:
    if len(raw_prob) == 0 or len(np.unique(y.astype(int))) < 2:
        return None
    from sklearn.linear_model import LogisticRegression

    calibrator = LogisticRegression(C=1e6, max_iter=1000, solver="lbfgs")
    calibrator.fit(_logit(raw_prob).reshape(-1, 1), y.astype(int))
    return calibrator


def _apply_calibrator(raw_prob: np.ndarray, calibrator: Any | None) -> np.ndarray:
    raw = np.clip(np.asarray(raw_prob, dtype=float), 1e-6, 1.0 - 1e-6)
    if calibrator is None:
        return raw
    return np.asarray(calibrator.predict_proba(_logit(raw).reshape(-1, 1))[:, 1], dtype=float)


def _split_model_and_calibration_indices(
    train_indices: np.ndarray,
    *,
    calibration_method: str,
    calibration_fraction: float,
    calibration_min_rows: int,
) -> tuple[np.ndarray, np.ndarray]:
    if calibration_method == "none":
        return train_indices, np.asarray([], dtype=int)
    if calibration_method != "sigmoid":
        raise ValueError("calibration_method must be one of: none, sigmoid.")
    if not 0.0 < float(calibration_fraction) < 0.5:
        raise ValueError("calibration_fraction must be in (0, 0.5).")
    if len(train_indices) < max(int(calibration_min_rows) * 2, 20):
        return train_indices, np.asarray([], dtype=int)
    calibration_rows = max(int(round(len(train_indices) * float(calibration_fraction))), int(calibration_min_rows))
    calibration_rows = min(calibration_rows, len(train_indices) - int(calibration_min_rows))
    if calibration_rows <= 0:
        return train_indices, np.asarray([], dtype=int)
    return train_indices[:-calibration_rows], train_indices[-calibration_rows:]


def _feature_importance(model: Any, feature_cols: list[str]) -> dict[str, float]:
    if hasattr(model, "feature_importances_"):
        values = np.asarray(getattr(model, "feature_importances_"), dtype=float)
    elif hasattr(model, "coef_"):
        values = np.abs(np.asarray(getattr(model, "coef_"), dtype=float)).reshape(-1)
    else:
        values = np.zeros(len(feature_cols), dtype=float)
    if len(values) != len(feature_cols):
        values = np.resize(values, len(feature_cols))
    return {feature: float(value) for feature, value in zip(feature_cols, values)}


def train_stacked_meta_filter(
    df: pd.DataFrame,
    *,
    label_col: str = "meta_label_min_0_50r",
    model_kind: Literal["logistic_regression_clf", "lightgbm_clf"] = "lightgbm_clf",
    feature_cols: list[str] | None = None,
    fold_col: str = "walk_forward_fold",
    candidate_col: str = "primary_candidate",
    side_col: str = "primary_candidate_side",
    primary_oos_col: str = "pred_is_oos",
    pred_col: str = "pred_ret",
    purge_bars: int = 24,
    embargo_bars: int = 24,
    min_train_candidates: int = 100,
    scaler: Literal["none", "standard", "robust"] | None = None,
    calibration_method: Literal["none", "sigmoid"] = "none",
    calibration_fraction: float = 0.20,
    calibration_min_rows: int = 50,
    model_params: dict[str, Any] | None = None,
    random_state: int = 7,
    raw_prob_col: str = "meta_pred_raw_prob",
    prob_col: str = "meta_pred_prob",
    meta_oos_col: str = "meta_pred_is_oos",
    meta_fold_col: str = "meta_fold",
) -> MetaStackingResult:
    """
    Train a sequential, leak-free meta-filter on completed primary candidate rows.
    """
    required = [label_col, fold_col, candidate_col, side_col, primary_oos_col, pred_col]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for stacked meta-filter: {missing}")
    if int(purge_bars) < 0 or int(embargo_bars) < 0:
        raise ValueError("purge_bars and embargo_bars must be >= 0.")

    out = df.copy()
    features = list(feature_cols or DEFAULT_META_FEATURE_COLS)
    validate_meta_feature_columns(features)
    missing_features = [col for col in features if col not in out.columns]
    if missing_features:
        raise KeyError(f"Missing meta feature columns: {missing_features}")

    labels = _finite_binary_labels(out[label_col])
    candidate_mask = pd.to_numeric(out[candidate_col], errors="coerce").fillna(0.0).gt(0.0)
    side_mask = pd.to_numeric(out[side_col], errors="coerce").fillna(0.0).ne(0.0)
    primary_oos = out[primary_oos_col].fillna(False).astype(bool)
    pred_available = pd.to_numeric(out[pred_col], errors="coerce").notna()
    candidate_rows = candidate_mask & side_mask
    bad_primary = candidate_rows & (~primary_oos | ~pred_available)
    if bool(bad_primary.any()):
        examples = ", ".join(str(idx) for idx in out.index[bad_primary][:5])
        raise ValueError(f"Candidate rows must use OOS primary predictions only. Examples: {examples}")

    completed_candidate = candidate_rows & labels.notna() & primary_oos & pred_available
    row_pos = pd.Series(np.arange(len(out), dtype=int), index=out.index)
    folds = pd.Series(out[fold_col], index=out.index)
    unique_folds = [fold for fold in pd.unique(folds.dropna())]
    unique_folds = sorted(unique_folds, key=lambda value: float(value) if str(value).replace(".", "", 1).isdigit() else str(value))

    out[raw_prob_col] = np.nan
    out[prob_col] = np.nan
    out[meta_oos_col] = False
    out[meta_fold_col] = np.nan

    resolved_scaler = scaler or ("robust" if model_kind == "logistic_regression_clf" else "none")
    params = _model_default_params(model_kind, random_state=random_state)
    params.update(dict(model_params or {}))
    diagnostics: list[dict[str, Any]] = []
    artifacts: list[FoldArtifact] = []

    for fold in unique_folds:
        fold_mask = folds.eq(fold)
        fold_positions = row_pos.loc[fold_mask].to_numpy(dtype=int)
        if fold_positions.size == 0:
            continue
        test_start_pos = int(fold_positions.min())
        train_cutoff = test_start_pos - int(purge_bars)
        train_mask = completed_candidate & row_pos.lt(train_cutoff)
        test_mask = candidate_rows & primary_oos & pred_available & fold_mask
        train_indices = np.flatnonzero(train_mask.to_numpy(dtype=bool))
        test_indices = np.flatnonzero(test_mask.to_numpy(dtype=bool))
        if len(test_indices) == 0:
            continue
        if len(train_indices) < int(min_train_candidates):
            diagnostics.append(
                {
                    "fold": fold,
                    "status": "skipped_min_train",
                    "train_rows": int(len(train_indices)),
                    "test_rows": int(len(test_indices)),
                    "test_start_pos": test_start_pos,
                    "purge_bars": int(purge_bars),
                    "embargo_bars": int(embargo_bars),
                }
            )
            continue

        model_train_indices, calibration_indices = _split_model_and_calibration_indices(
            train_indices,
            calibration_method=calibration_method,
            calibration_fraction=calibration_fraction,
            calibration_min_rows=calibration_min_rows,
        )
        y_all = labels.iloc[train_indices].to_numpy(dtype=int)
        y_model = labels.iloc[model_train_indices].to_numpy(dtype=int)
        impute, center, scale = _fit_preprocessor(out.iloc[model_train_indices][features], scaler=resolved_scaler)
        x_model = _transform_features(out.iloc[model_train_indices][features], impute_values=impute, center=center, scale=scale)
        model = _fit_model(x_model, y_model, model_kind=model_kind, params=params)

        calibrator = None
        if len(calibration_indices) > 0:
            x_cal = _transform_features(out.iloc[calibration_indices][features], impute_values=impute, center=center, scale=scale)
            raw_cal = _predict_raw_prob(model, x_cal)
            y_cal = labels.iloc[calibration_indices].to_numpy(dtype=int)
            calibrator = _fit_sigmoid_calibrator(raw_cal, y_cal)

        x_test = _transform_features(out.iloc[test_indices][features], impute_values=impute, center=center, scale=scale)
        raw_prob = _predict_raw_prob(model, x_test)
        prob = _apply_calibrator(raw_prob, calibrator)
        out.iloc[test_indices, out.columns.get_loc(raw_prob_col)] = raw_prob
        out.iloc[test_indices, out.columns.get_loc(prob_col)] = prob
        out.iloc[test_indices, out.columns.get_loc(meta_oos_col)] = True
        out.iloc[test_indices, out.columns.get_loc(meta_fold_col)] = fold

        artifact = FoldArtifact(
            fold=int(fold) if isinstance(fold, (int, np.integer, float, np.floating)) and float(fold).is_integer() else fold,
            model_kind=model_kind,
            model=model,
            feature_cols=features,
            impute_values=impute,
            center=center,
            scale=scale,
            scaler=resolved_scaler,
            calibrator=calibrator,
            train_indices=train_indices,
            model_train_indices=model_train_indices,
            calibration_indices=calibration_indices,
            test_indices=test_indices,
            train_rows=int(len(train_indices)),
            model_train_rows=int(len(model_train_indices)),
            calibration_rows=int(len(calibration_indices)),
            test_rows=int(len(test_indices)),
            train_max_pos=int(train_indices.max()) if len(train_indices) else None,
            test_start_pos=test_start_pos,
            purge_bars=int(purge_bars),
            calibration_applied=calibrator is not None,
        )
        artifacts.append(artifact)
        diagnostics.append(
            {
                "fold": fold,
                "status": "fit",
                "train_rows": int(len(train_indices)),
                "model_train_rows": int(len(model_train_indices)),
                "calibration_rows": int(len(calibration_indices)),
                "test_rows": int(len(test_indices)),
                "positive_rate_train": float(np.mean(y_all)) if len(y_all) else None,
                "positive_rate_test": float(labels.iloc[test_indices].dropna().mean())
                if labels.iloc[test_indices].notna().any()
                else None,
                "test_start_pos": test_start_pos,
                "train_max_pos": int(train_indices.max()) if len(train_indices) else None,
                "purge_bars": int(purge_bars),
                "embargo_bars": int(embargo_bars),
                "scaler": resolved_scaler,
                "calibration_method": calibration_method,
                "calibration_applied": calibrator is not None,
                "feature_importance": _feature_importance(model, features),
            }
        )

    final_test_fold = unique_folds[-1] if unique_folds else None
    return MetaStackingResult(
        frame=out,
        feature_cols=features,
        fold_diagnostics=diagnostics,
        artifacts=artifacts,
        model_kind=model_kind,
        label_col=label_col,
        calibration_method=calibration_method,
        final_test_fold=final_test_fold,
    )


def build_meta_filtered_signal(
    df: pd.DataFrame,
    *,
    threshold: float,
    prob_col: str = "meta_pred_prob",
    meta_oos_col: str = "meta_pred_is_oos",
    candidate_col: str = "primary_candidate",
    side_col: str = "primary_candidate_side",
    signal_col: str = "signal_meta_filtered",
) -> pd.Series:
    """
    Gate existing candidate sides by an OOS meta probability threshold.
    """
    if not 0.0 < float(threshold) < 1.0:
        raise ValueError("threshold must be in (0, 1).")
    for col in [prob_col, meta_oos_col, candidate_col, side_col]:
        if col not in df.columns:
            raise KeyError(f"Missing column for meta-filtered signal: {col}")
    side = np.sign(pd.to_numeric(df[side_col], errors="coerce").fillna(0.0).clip(lower=-1.0, upper=1.0))
    active = (
        df[meta_oos_col].fillna(False).astype(bool)
        & pd.to_numeric(df[candidate_col], errors="coerce").fillna(0.0).gt(0.0)
        & pd.to_numeric(df[prob_col], errors="coerce").ge(float(threshold))
        & side.ne(0.0)
    )
    signal = pd.Series(0.0, index=df.index, name=signal_col, dtype=float)
    signal.loc[active] = side.loc[active].astype(float)
    return signal


def _binary_metrics(y_true: np.ndarray, prob: np.ndarray) -> dict[str, Any]:
    valid = np.isfinite(y_true) & np.isfinite(prob)
    y = y_true[valid].astype(int)
    p = np.clip(prob[valid].astype(float), 1e-6, 1.0 - 1e-6)
    if len(y) == 0:
        return {
            "rows": 0,
            "brier_score": None,
            "log_loss": None,
            "roc_auc": None,
            "pr_auc": None,
            "calibration_slope": None,
            "calibration_intercept": None,
        }
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score

    metrics = {
        "rows": int(len(y)),
        "brier_score": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, p, labels=[0, 1])),
        "roc_auc": float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else None,
        "pr_auc": float(average_precision_score(y, p)) if len(np.unique(y)) == 2 else None,
        "calibration_slope": None,
        "calibration_intercept": None,
    }
    if len(np.unique(y)) == 2:
        cal = LogisticRegression(C=1e6, max_iter=1000, solver="lbfgs")
        cal.fit(_logit(p).reshape(-1, 1), y)
        metrics["calibration_intercept"] = float(cal.intercept_[0])
        metrics["calibration_slope"] = float(cal.coef_[0][0])
    return metrics


def reliability_table(
    df: pd.DataFrame,
    *,
    label_col: str,
    prob_col: str,
    r_col: str = "meta_net_r",
    bins: int = 10,
) -> pd.DataFrame:
    valid = df[[label_col, prob_col, r_col]].copy()
    valid[label_col] = pd.to_numeric(valid[label_col], errors="coerce")
    valid[prob_col] = pd.to_numeric(valid[prob_col], errors="coerce")
    valid[r_col] = pd.to_numeric(valid[r_col], errors="coerce")
    valid = valid.dropna(subset=[label_col, prob_col])
    if valid.empty:
        return pd.DataFrame(
            columns=["bucket", "candidate_count", "avg_predicted_probability", "realized_success_rate", "average_net_r"]
        )
    bucket = pd.cut(valid[prob_col].clip(0.0, 1.0), bins=np.linspace(0.0, 1.0, int(bins) + 1), include_lowest=True)
    grouped = valid.groupby(bucket, observed=False)
    out = grouped.agg(
        candidate_count=(label_col, "size"),
        avg_predicted_probability=(prob_col, "mean"),
        realized_success_rate=(label_col, "mean"),
        average_net_r=(r_col, "mean"),
    ).reset_index(names="bucket")
    out["bucket"] = out["bucket"].astype(str)
    return out


def compute_probability_diagnostics(
    df: pd.DataFrame,
    *,
    label_cols: list[str],
    prob_col: str = "meta_pred_prob",
    meta_oos_col: str = "meta_pred_is_oos",
    r_col: str = "meta_net_r",
    bins: int = 10,
) -> dict[str, Any]:
    mask = df[meta_oos_col].fillna(False).astype(bool) if meta_oos_col in df.columns else pd.Series(True, index=df.index)
    scoped = df.loc[mask].copy()
    metrics: dict[str, Any] = {}
    reliability: dict[str, pd.DataFrame] = {}
    for label_col in label_cols:
        y = pd.to_numeric(scoped[label_col], errors="coerce").to_numpy(dtype=float)
        p = pd.to_numeric(scoped[prob_col], errors="coerce").to_numpy(dtype=float)
        metrics[label_col] = _binary_metrics(y, p)
        reliability[label_col] = reliability_table(scoped, label_col=label_col, prob_col=prob_col, r_col=r_col, bins=bins)
    return {"metrics": metrics, "reliability": reliability}


def _predict_with_artifact(artifact: FoldArtifact, frame: pd.DataFrame) -> np.ndarray:
    x = _transform_features(
        frame[artifact.feature_cols],
        impute_values=artifact.impute_values,
        center=artifact.center,
        scale=artifact.scale,
    )
    return _apply_calibrator(_predict_raw_prob(artifact.model, x), artifact.calibrator)


def permutation_importance(
    result: MetaStackingResult,
    *,
    label_col: str | None = None,
    prob_col: str = "meta_pred_prob",
    max_features: int = 20,
    random_state: int = 7,
) -> pd.DataFrame:
    """
    Compute fold-local permutation importance as OOS log-loss deterioration.
    """
    label = label_col or result.label_col
    if not result.artifacts:
        return pd.DataFrame(columns=["feature", "mean_log_loss_delta", "fold_count"])
    from sklearn.metrics import log_loss

    rng = np.random.default_rng(int(random_state))
    base_frame = result.frame
    candidates = []
    importances = []
    for row in _aggregate_importance(result.fold_diagnostics).head(max_features).itertuples(index=False):
        candidates.append(str(row.feature))
    if not candidates:
        candidates = result.feature_cols[:max_features]

    for feature in candidates:
        deltas: list[float] = []
        for artifact in result.artifacts:
            fold_frame = base_frame.iloc[artifact.test_indices].copy()
            y = pd.to_numeric(fold_frame[label], errors="coerce").to_numpy(dtype=float)
            valid = np.isfinite(y)
            if valid.sum() == 0 or len(np.unique(y[valid].astype(int))) < 2:
                continue
            p_base = pd.to_numeric(fold_frame[prob_col], errors="coerce").to_numpy(dtype=float)
            baseline = log_loss(y[valid].astype(int), np.clip(p_base[valid], 1e-6, 1.0 - 1e-6), labels=[0, 1])
            shuffled = fold_frame.copy()
            values = shuffled[feature].to_numpy(copy=True)
            rng.shuffle(values)
            shuffled[feature] = values
            p_perm = _predict_with_artifact(artifact, shuffled)
            permuted = log_loss(y[valid].astype(int), np.clip(p_perm[valid], 1e-6, 1.0 - 1e-6), labels=[0, 1])
            deltas.append(float(permuted - baseline))
        importances.append(
            {
                "feature": feature,
                "mean_log_loss_delta": float(np.mean(deltas)) if deltas else 0.0,
                "fold_count": int(len(deltas)),
            }
        )
    return pd.DataFrame(importances).sort_values("mean_log_loss_delta", ascending=False).reset_index(drop=True)


def _aggregate_importance(fold_diagnostics: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for diag in fold_diagnostics:
        importance = dict(diag.get("feature_importance", {}) or {})
        for feature, value in importance.items():
            rows.append({"feature": feature, "importance": float(value), "fold": diag.get("fold")})
    if not rows:
        return pd.DataFrame(columns=["feature", "importance"])
    frame = pd.DataFrame(rows)
    return (
        frame.groupby("feature", as_index=False)
        .agg(importance=("importance", "mean"), fold_count=("fold", "nunique"))
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )


__all__ = [
    "DEFAULT_META_FEATURE_COLS",
    "MetaStackingResult",
    "build_causal_meta_features",
    "build_meta_filtered_signal",
    "compute_probability_diagnostics",
    "permutation_importance",
    "reliability_table",
    "train_stacked_meta_filter",
    "validate_meta_feature_columns",
]
