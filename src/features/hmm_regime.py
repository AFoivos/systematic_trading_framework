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
    standardize: bool = False,
    standardize_eps: float = 1e-12,
) -> pd.DataFrame:
    """Add Hidden Markov Model regimes without full-sample fitting.

    ``mode='expanding'`` fits on observations strictly before the row being
    scored. ``mode='static_train'`` fits once on the first ``train_size`` valid
    observations and only scores later rows. If ``standardize=True``,
    normalization statistics are estimated from the HMM training window only.
    The ``hmmlearn`` package is required at runtime.
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
    if not isinstance(standardize, bool):
        raise ValueError("standardize must be boolean.")
    _validate_positive_float(standardize_eps, name="standardize_eps")

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
        model_features = (
            _standardize_features(valid_features, fit_end_pos=train_size, eps=float(standardize_eps))
            if standardize
            else valid_features
        )
        model = _fit_model(
            GaussianHMM,
            model_features.iloc[:train_size].to_numpy(dtype=float),
            n_states=n_states,
            covariance_type=covariance_type,
            n_iter=n_iter,
            random_state=random_state,
        )
        state_order = _state_order(model, n_states=n_states)
        states, proba = _score_sequence_endpoints(
            model,
            model_features.to_numpy(dtype=float),
            state_order,
        )
        scored_index = valid_features.index[train_size:]
        regimes.loc[scored_index] = states[train_size:].astype(float)
        if probabilities is not None and proba is not None:
            probabilities.loc[scored_index, probabilities.columns] = proba[train_size:]
    else:
        model = None
        state_order: dict[int, int] | None = None
        last_fit_pos = -refit_interval
        obs_pos = 0
        while obs_pos < len(valid_features):
            if obs_pos < min_size:
                obs_pos += 1
                continue
            if model is None or obs_pos - last_fit_pos >= refit_interval:
                model_features = (
                    _standardize_features(valid_features, fit_end_pos=obs_pos, eps=float(standardize_eps))
                    if standardize
                    else valid_features
                )
                model = _fit_model(
                    GaussianHMM,
                    model_features.iloc[:obs_pos].to_numpy(dtype=float),
                    n_states=n_states,
                    covariance_type=covariance_type,
                    n_iter=n_iter,
                    random_state=random_state,
                )
                state_order = _state_order(model, n_states=n_states)
                last_fit_pos = obs_pos
            segment_end = min(len(valid_features), obs_pos + refit_interval)
            states, proba = _score_sequence_endpoints(
                model,
                model_features.iloc[:segment_end].to_numpy(dtype=float),
                state_order or {state: state for state in range(n_states)},
            )
            scored_index = valid_features.index[obs_pos:segment_end]
            regimes.loc[scored_index] = states[obs_pos:segment_end].astype(float)
            if probabilities is not None and proba is not None:
                probabilities.loc[scored_index, probabilities.columns] = proba[obs_pos:segment_end]
            obs_pos = segment_end

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
        raise ImportError("hmmlearn is required for add_hmm_regime. Install project requirements to use HMM regimes.") from exc
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


def _standardize_features(features: pd.DataFrame, *, fit_end_pos: int, eps: float) -> pd.DataFrame:
    if fit_end_pos <= 0:
        raise ValueError("standardization requires at least one training observation.")
    fit_window = features.iloc[:fit_end_pos].astype(float)
    mean = fit_window.mean(axis=0)
    std = fit_window.std(axis=0, ddof=0)
    std = std.mask(std <= eps, 1.0)
    return (features.astype(float) - mean) / std


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


def _score_sequence_endpoints(
    model: object,
    values: np.ndarray,
    state_order: dict[int, int],
) -> tuple[np.ndarray, np.ndarray | None]:
    """
    Return causal endpoint states/probabilities for every prefix of ``values``.

    For a fixed fitted model, this is equivalent to repeatedly scoring each
    prefix endpoint, but it computes one forward/Viterbi pass instead of
    re-scanning the full prefix for every row.
    """
    log_likelihood_fn = getattr(model, "_compute_log_likelihood", None)
    startprob = getattr(model, "startprob_", None)
    transmat = getattr(model, "transmat_", None)
    if not callable(log_likelihood_fn) or startprob is None or transmat is None:
        return _score_sequence_endpoints_slow(model, values, state_order)

    log_likelihood = np.asarray(log_likelihood_fn(values), dtype=float)
    if log_likelihood.ndim != 2 or log_likelihood.shape[0] != len(values):
        return _score_sequence_endpoints_slow(model, values, state_order)

    n_samples, n_states = log_likelihood.shape
    log_startprob = _safe_log(np.asarray(startprob, dtype=float))
    log_transmat = _safe_log(np.asarray(transmat, dtype=float))
    if log_startprob.shape != (n_states,) or log_transmat.shape != (n_states, n_states):
        return _score_sequence_endpoints_slow(model, values, state_order)

    log_alpha = np.empty((n_samples, n_states), dtype=float)
    log_delta = np.empty((n_samples, n_states), dtype=float)
    raw_states = np.empty(n_samples, dtype=int)
    raw_probabilities = np.empty((n_samples, n_states), dtype=float)

    log_alpha[0] = log_startprob + log_likelihood[0]
    log_delta[0] = log_alpha[0]
    raw_states[0] = int(np.argmax(log_delta[0]))
    raw_probabilities[0] = _normalize_log_probabilities(log_alpha[0])

    for obs_pos in range(1, n_samples):
        alpha_candidates = log_alpha[obs_pos - 1][:, np.newaxis] + log_transmat
        delta_candidates = log_delta[obs_pos - 1][:, np.newaxis] + log_transmat
        log_alpha[obs_pos] = log_likelihood[obs_pos] + _logsumexp(alpha_candidates, axis=0)
        log_delta[obs_pos] = log_likelihood[obs_pos] + np.max(delta_candidates, axis=0)
        raw_states[obs_pos] = int(np.argmax(log_delta[obs_pos]))
        raw_probabilities[obs_pos] = _normalize_log_probabilities(log_alpha[obs_pos])

    mapped_states = np.asarray([state_order[int(raw_state)] for raw_state in raw_states], dtype=int)
    mapped_probabilities = np.empty_like(raw_probabilities)
    for raw_state, ordered_state in state_order.items():
        mapped_probabilities[:, ordered_state] = raw_probabilities[:, raw_state]
    return mapped_states, mapped_probabilities


def _score_sequence_endpoints_slow(
    model: object,
    values: np.ndarray,
    state_order: dict[int, int],
) -> tuple[np.ndarray, np.ndarray | None]:
    states: list[int] = []
    probabilities: list[np.ndarray] = []
    saw_probabilities = True
    for obs_pos in range(len(values)):
        state, proba = _score_endpoint(model, values[: obs_pos + 1], state_order)
        states.append(state)
        if proba is None:
            saw_probabilities = False
        elif saw_probabilities:
            probabilities.append(proba)
    if not saw_probabilities:
        return np.asarray(states, dtype=int), None
    return np.asarray(states, dtype=int), np.vstack(probabilities)


def _safe_log(values: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.log(values)


def _logsumexp(values: np.ndarray, *, axis: int) -> np.ndarray:
    max_values = np.max(values, axis=axis, keepdims=True)
    finite = np.isfinite(max_values)
    shifted = np.where(finite, values - max_values, -np.inf)
    summed = np.sum(np.exp(shifted), axis=axis, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = max_values + np.log(summed)
    out = np.where(finite, out, -np.inf)
    return np.squeeze(out, axis=axis)


def _normalize_log_probabilities(log_probabilities: np.ndarray) -> np.ndarray:
    normalizer = _logsumexp(log_probabilities, axis=0)
    if not np.isfinite(normalizer):
        return np.full_like(log_probabilities, np.nan, dtype=float)
    return np.exp(log_probabilities - normalizer)


def _validate_columns(df: pd.DataFrame, columns: list[str], *, feature: str) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for {feature}: {missing}")


def _validate_positive_int(value: int, *, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Integral) or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")


def _validate_positive_float(value: float, *, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite positive number.")
    if float(value) <= 0.0:
        raise ValueError(f"{name} must be a finite positive number.")


def _resolve_output_col(output_col: str | None, default: str) -> str:
    if output_col is None:
        return default
    if not isinstance(output_col, str) or not output_col.strip():
        raise ValueError("output_col must be a non-empty string.")
    return output_col


__all__ = [
    "add_hmm_regime",
]
