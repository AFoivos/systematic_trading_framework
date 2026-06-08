from __future__ import annotations

from collections.abc import Sequence
from numbers import Integral

import numpy as np
import pandas as pd


def add_hmm_regime(
    df: pd.DataFrame,
    feature_cols: Sequence[str] | None = None,
    price_col: str = "close",
    returns_col: str | None = None,
    n_states: int = 2,
    mode: str = "expanding",
    train_size: int | None = None,
    min_train_size: int | None = None,
    refit_interval: int = 1,
    covariance_type: str = "diag",
    n_iter: int = 100,
    random_state: int = 0,
    output_col: str | None = None,
    include_probabilities: bool = False,
    probability_prefix: str = "hmm_regime_prob",
) -> pd.DataFrame:
    """Add Hidden Markov Model regimes without full-sample fitting.

    ``mode='expanding'`` fits on observations strictly before the row being
    scored. ``mode='static_train'`` fits once on the first ``train_size`` valid
    observations and only scores later rows. The optional ``hmmlearn`` package is
    required at runtime.
    """
    _validate_positive_int(n_states, name="n_states")
    if n_states < 2:
        raise ValueError("n_states must be at least 2.")
    if mode not in {"expanding", "static_train"}:
        raise ValueError("mode must be one of: expanding, static_train.")
    _validate_positive_int(refit_interval, name="refit_interval")
    _validate_positive_int(n_iter, name="n_iter")
    col = _resolve_output_col(output_col, "hmm_regime")
    if include_probabilities and (not isinstance(probability_prefix, str) or not probability_prefix.strip()):
        raise ValueError("probability_prefix must be a non-empty string.")

    out = df.copy()
    features = _resolve_feature_frame(out, feature_cols=feature_cols, price_col=price_col, returns_col=returns_col)
    valid_features = features.replace([np.inf, -np.inf], np.nan).dropna()

    regimes = pd.Series(np.nan, index=out.index, dtype="float64")
    probabilities = pd.DataFrame(index=out.index) if include_probabilities else None
    if include_probabilities:
        for state in range(n_states):
            probabilities[f"{probability_prefix}_{state}"] = np.nan

    if len(valid_features) <= n_states:
        out[col] = regimes
        if probabilities is not None:
            out = out.join(probabilities)
        return out

    GaussianHMM = _load_gaussian_hmm()
    min_size = min_train_size if min_train_size is not None else max(30, n_states * 10)
    _validate_positive_int(min_size, name="min_train_size")
    if mode == "static_train":
        if train_size is None:
            raise ValueError("train_size is required for mode='static_train'.")
        _validate_positive_int(train_size, name="train_size")
        if train_size >= len(valid_features):
            raise ValueError("train_size must be smaller than the number of valid observations.")
        model = _fit_model(
            GaussianHMM,
            valid_features.iloc[:train_size].to_numpy(dtype=float),
            n_states=n_states,
            covariance_type=covariance_type,
            n_iter=n_iter,
            random_state=random_state,
        )
        state_order = _state_order(model, n_states=n_states)
        for obs_pos in range(train_size, len(valid_features)):
            state, proba = _score_endpoint(model, valid_features.iloc[: obs_pos + 1].to_numpy(dtype=float), state_order)
            row_index = valid_features.index[obs_pos]
            regimes.loc[row_index] = state
            if probabilities is not None and proba is not None:
                probabilities.loc[row_index, probabilities.columns] = proba
    else:
        model = None
        state_order: dict[int, int] | None = None
        last_fit_pos = -refit_interval
        for obs_pos in range(len(valid_features)):
            if obs_pos < min_size:
                continue
            if model is None or obs_pos - last_fit_pos >= refit_interval:
                model = _fit_model(
                    GaussianHMM,
                    valid_features.iloc[:obs_pos].to_numpy(dtype=float),
                    n_states=n_states,
                    covariance_type=covariance_type,
                    n_iter=n_iter,
                    random_state=random_state,
                )
                state_order = _state_order(model, n_states=n_states)
                last_fit_pos = obs_pos
            state, proba = _score_endpoint(
                model,
                valid_features.iloc[: obs_pos + 1].to_numpy(dtype=float),
                state_order or {state: state for state in range(n_states)},
            )
            row_index = valid_features.index[obs_pos]
            regimes.loc[row_index] = state
            if probabilities is not None and proba is not None:
                probabilities.loc[row_index, probabilities.columns] = proba

    out[col] = regimes
    if probabilities is not None:
        out = out.join(probabilities)
    return out


def _resolve_feature_frame(
    df: pd.DataFrame,
    *,
    feature_cols: Sequence[str] | None,
    price_col: str,
    returns_col: str | None,
) -> pd.DataFrame:
    if feature_cols is not None:
        columns = list(feature_cols)
        if not columns:
            raise ValueError("feature_cols must not be empty.")
        _validate_columns(df, columns, feature="HMM regime")
        return df[columns].astype(float)
    if returns_col is not None:
        _validate_columns(df, [returns_col], feature="HMM regime")
        return pd.DataFrame({returns_col: df[returns_col].astype(float)}, index=df.index)
    _validate_columns(df, [price_col], feature="HMM regime")
    returns = df[price_col].astype(float).pct_change()
    return pd.DataFrame({"hmm_return": returns}, index=df.index)


def _load_gaussian_hmm() -> object:
    try:
        from hmmlearn.hmm import GaussianHMM
    except ImportError as exc:
        raise ImportError("hmmlearn is required for add_hmm_regime; install it to use HMM regimes.") from exc
    return GaussianHMM


def _fit_model(
    GaussianHMM: object,
    values: np.ndarray,
    *,
    n_states: int,
    covariance_type: str,
    n_iter: int,
    random_state: int,
) -> object:
    model = GaussianHMM(
        n_components=n_states,
        covariance_type=covariance_type,
        n_iter=n_iter,
        random_state=random_state,
    )
    model.fit(values)
    return model


def _state_order(model: object, *, n_states: int) -> dict[int, int]:
    means = np.asarray(model.means_, dtype=float)
    order = np.argsort(means[:, 0])
    return {int(raw_state): int(ordered_state) for ordered_state, raw_state in enumerate(order[:n_states])}


def _score_endpoint(model: object, values: np.ndarray, state_order: dict[int, int]) -> tuple[int, np.ndarray | None]:
    raw_states = model.predict(values)
    raw_state = int(raw_states[-1])
    mapped_state = state_order[raw_state]
    try:
        raw_proba = np.asarray(model.predict_proba(values)[-1], dtype=float)
    except (AttributeError, ValueError):
        raw_proba = None
    if raw_proba is None:
        return mapped_state, None
    mapped = np.empty_like(raw_proba)
    for raw, ordered in state_order.items():
        mapped[ordered] = raw_proba[raw]
    return mapped_state, mapped


def _validate_columns(df: pd.DataFrame, columns: list[str], *, feature: str) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for {feature}: {missing}")


def _validate_positive_int(value: int, *, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Integral) or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")


def _resolve_output_col(output_col: str | None, default: str) -> str:
    if output_col is None:
        return default
    if not isinstance(output_col, str) or not output_col.strip():
        raise ValueError("output_col must be a non-empty string.")
    return output_col


__all__ = [
    "add_hmm_regime",
]
