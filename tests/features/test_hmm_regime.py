from __future__ import annotations

import numpy as np
import pytest

import src.features.hmm_regime as hmm_module
from src.features.hmm_regime import _state_order, add_hmm_regime

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


class RecordingGaussianHMM:
    fit_lengths: list[int] = []
    compute_lengths: list[int] = []
    predict_lengths: list[int] = []
    fit_values: list[np.ndarray] = []

    def __init__(self, n_components, covariance_type, n_iter, random_state):
        self.n_components = n_components
        self.means_ = np.arange(n_components, dtype=float).reshape(-1, 1)
        self.startprob_ = np.full(n_components, 1.0 / n_components, dtype=float)
        self.transmat_ = np.full((n_components, n_components), 1.0 / n_components, dtype=float)

    def fit(self, values):
        self.fit_lengths.append(len(values))
        self.fit_values.append(np.asarray(values, dtype=float).copy())
        return self

    def _compute_log_likelihood(self, values):
        self.compute_lengths.append(len(values))
        log_likelihood = np.full((len(values), self.n_components), -np.inf, dtype=float)
        log_likelihood[:, self.n_components - 1] = 0.0
        return log_likelihood

    def predict(self, values):
        self.predict_lengths.append(len(values))
        return np.full(len(values), self.n_components - 1, dtype=int)

    def predict_proba(self, values):
        probabilities = np.zeros((len(values), self.n_components), dtype=float)
        probabilities[:, self.n_components - 1] = 1.0
        return probabilities


def _patch_recording_hmm(monkeypatch) -> tuple[list[int], list[int], list[int], list[np.ndarray]]:
    fit_lengths: list[int] = []
    compute_lengths: list[int] = []
    predict_lengths: list[int] = []
    fit_values: list[np.ndarray] = []

    class PatchedRecordingGaussianHMM(RecordingGaussianHMM):
        pass

    PatchedRecordingGaussianHMM.fit_lengths = fit_lengths
    PatchedRecordingGaussianHMM.compute_lengths = compute_lengths
    PatchedRecordingGaussianHMM.predict_lengths = predict_lengths
    PatchedRecordingGaussianHMM.fit_values = fit_values
    monkeypatch.setattr(hmm_module, "_load_gaussian_hmm", lambda: PatchedRecordingGaussianHMM)
    return fit_lengths, compute_lengths, predict_lengths, fit_values


def test_hmm_regime_contract_and_numeric_sanity_static_train(monkeypatch) -> None:
    _patch_recording_hmm(monkeypatch)
    df = synthetic_ohlcv(90)
    out = add_hmm_regime(
        df,
        feature_cols=["returns"],
        mode="static_train",
        train_size=35,
        n_states=2,
        include_probabilities=True,
        output_col="hmm_custom",
    )

    assert "hmm_custom" in out.columns
    assert "hmm_regime_prob_0" in out.columns
    assert_no_mutation(
        add_hmm_regime,
        df,
        feature_cols=["returns"],
        mode="static_train",
        train_size=35,
        n_states=2,
        output_col="hmm_custom",
    )
    assert_has_finite_values(out["hmm_custom"])
    assert set(out["hmm_custom"].dropna().unique()).issubset({0.0, 1.0})


def test_hmm_regime_missing_columns() -> None:
    with pytest.raises(KeyError, match="Missing columns"):
        add_hmm_regime(synthetic_ohlcv().drop(columns=["returns"]), feature_cols=["returns"], mode="expanding")


def test_hmm_regime_invalid_params() -> None:
    with pytest.raises(ValueError, match="mode"):
        add_hmm_regime(synthetic_ohlcv(), feature_cols=["returns"], mode="bad")


def test_hmm_regime_is_causal(monkeypatch) -> None:
    _patch_recording_hmm(monkeypatch)
    assert_causal(
        add_hmm_regime,
        synthetic_ohlcv(90),
        output_cols=["hmm_regime"],
        params={
            "feature_cols": ["returns"],
            "mode": "static_train",
            "train_size": 35,
            "n_states": 2,
        },
        cutoff=60,
        mutate_cols=["returns"],
    )


def test_hmm_regime_static_train_does_not_fit_full_sample_or_write_training_regimes(monkeypatch) -> None:
    fit_lengths, compute_lengths, predict_lengths, _ = _patch_recording_hmm(monkeypatch)

    out = add_hmm_regime(
        synthetic_ohlcv(12),
        feature_cols=["returns"],
        mode="static_train",
        train_size=5,
        n_states=3,
        include_probabilities=True,
    )

    assert fit_lengths == [5]
    assert compute_lengths == [12]
    assert predict_lengths == []
    assert out["hmm_regime"].iloc[:5].isna().all()
    assert out["hmm_regime"].iloc[5:].notna().all()
    assert {"hmm_regime_prob_0", "hmm_regime_prob_1", "hmm_regime_prob_2"}.issubset(out.columns)
    assert out["hmm_regime_prob_2"].iloc[:5].isna().all()
    assert out["hmm_regime_prob_2"].iloc[5:].eq(1.0).all()


def test_hmm_regime_expanding_fits_only_observations_before_scored_row(monkeypatch) -> None:
    fit_lengths, compute_lengths, predict_lengths, _ = _patch_recording_hmm(monkeypatch)

    out = add_hmm_regime(
        synthetic_ohlcv(9),
        feature_cols=["returns"],
        mode="expanding",
        min_train_size=4,
        refit_interval=2,
        n_states=2,
    )

    assert fit_lengths == [4, 6, 8]
    assert compute_lengths == [6, 8, 9]
    assert predict_lengths == []
    assert out["hmm_regime"].iloc[:4].isna().all()
    assert out["hmm_regime"].iloc[4:].notna().all()


def test_hmm_regime_static_train_standardizes_using_train_window_only(monkeypatch) -> None:
    _, _, _, fit_values = _patch_recording_hmm(monkeypatch)
    df = synthetic_ohlcv(16)
    df["wide_feature"] = np.linspace(100.0, 900.0, len(df))
    df.loc[df.index[5]:, "wide_feature"] = 10_000.0

    add_hmm_regime(
        df,
        feature_cols=["returns", "wide_feature"],
        mode="static_train",
        train_size=5,
        n_states=2,
        standardize=True,
    )

    fitted = fit_values[0]
    np.testing.assert_allclose(fitted.mean(axis=0), np.zeros(2), atol=1e-12)
    np.testing.assert_allclose(fitted.std(axis=0), np.ones(2), atol=1e-12)


def test_hmm_regime_expanding_standardizes_each_fit_with_prior_rows_only(monkeypatch) -> None:
    _, _, _, fit_values = _patch_recording_hmm(monkeypatch)

    add_hmm_regime(
        synthetic_ohlcv(9),
        feature_cols=["returns", "ppo_hist"],
        mode="expanding",
        min_train_size=4,
        refit_interval=2,
        n_states=2,
        standardize=True,
    )

    for fitted in fit_values:
        np.testing.assert_allclose(fitted.mean(axis=0), np.zeros(fitted.shape[1]), atol=1e-12)
        np.testing.assert_allclose(fitted.std(axis=0), np.ones(fitted.shape[1]), atol=1e-12)


def test_hmm_regime_state_order_maps_raw_states_by_first_mean_column() -> None:
    class Model:
        means_ = np.asarray([[5.0], [1.0], [3.0]])

    assert _state_order(Model(), n_states=3) == {1: 0, 2: 1, 0: 2}
