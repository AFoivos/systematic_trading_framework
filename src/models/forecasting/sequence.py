from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SequenceScaler:
    feature_mean: np.ndarray
    feature_std: np.ndarray
    target_mean: float
    target_std: float
    scale_target: bool = True

    def transform_features(self, values: np.ndarray) -> np.ndarray:
        arr = np.asarray(values, dtype=float)
        scaled = (arr - self.feature_mean) / self.feature_std
        return scaled.astype("float32")

    def transform_target(self, values: np.ndarray) -> np.ndarray:
        arr = np.asarray(values, dtype=float)
        if not self.scale_target:
            return arr.astype("float32")
        scaled = (arr - self.target_mean) / self.target_std
        return scaled.astype("float32")

    def inverse_target(self, values: np.ndarray) -> np.ndarray:
        arr = np.asarray(values, dtype=float)
        if not self.scale_target:
            return arr.astype("float32")
        restored = arr * self.target_std + self.target_mean
        return restored.astype("float32")


@dataclass(frozen=True)
class SequenceSamples:
    x: np.ndarray
    y: np.ndarray
    index: pd.Index


def fit_sequence_scaler(
    *,
    full_df: pd.DataFrame,
    train_idx: np.ndarray,
    feature_cols: list[str],
    target_col: str,
    scale_target: bool = True,
) -> SequenceScaler:
    if not feature_cols:
        raise ValueError("Sequence scaler requires at least one feature column.")

    train_df = full_df.iloc[np.asarray(train_idx, dtype=int)]
    x_train = train_df[feature_cols].to_numpy(dtype=float)
    feat_mean = np.nanmean(x_train, axis=0)
    feat_std = np.nanstd(x_train, axis=0)
    feat_mean = np.where(np.isfinite(feat_mean), feat_mean, 0.0)
    feat_std = np.where(np.isfinite(feat_std) & (feat_std > 1e-12), feat_std, 1.0)

    y_train = train_df[target_col].to_numpy(dtype=float)
    y_train = y_train[np.isfinite(y_train)]
    if y_train.size == 0:
        target_mean = 0.0
        target_std = 1.0
    else:
        target_mean = float(np.mean(y_train))
        target_std = float(np.std(y_train))
        if not np.isfinite(target_std) or target_std <= 1e-12:
            target_std = 1.0

    return SequenceScaler(
        feature_mean=np.asarray(feat_mean, dtype="float32"),
        feature_std=np.asarray(feat_std, dtype="float32"),
        target_mean=float(target_mean),
        target_std=float(target_std),
        scale_target=bool(scale_target),
    )


def build_sequence_samples(
    *,
    full_df: pd.DataFrame,
    indices: np.ndarray,
    feature_cols: list[str],
    target_col: str,
    lookback: int,
    require_target: bool,
    scaler: SequenceScaler | None = None,
    allowed_window_indices: set[int] | None = None,
) -> SequenceSamples:
    """
    Build causal rolling windows aligned to the target row index.

    For train folds, `allowed_window_indices` should usually contain only train indices so the
    window never crosses into future rows. For test folds it can be `None`, allowing the window to
    use historical context from the train segment while still ending at the prediction timestamp.
    """
    if lookback <= 1:
        raise ValueError("lookback must be > 1 for sequence models.")
    if not feature_cols:
        raise ValueError("Sequence models require at least one feature column.")

    x_raw = full_df[feature_cols].to_numpy(dtype=float)
    y_raw = full_df[target_col].to_numpy(dtype=float)
    index_values = full_df.index

    x_rows: list[np.ndarray] = []
    y_rows: list[float] = []
    out_index: list[pd.Timestamp] = []
    for idx in np.asarray(indices, dtype=int):
        start = int(idx - lookback + 1)
        if start < 0:
            continue
        window = np.arange(start, int(idx) + 1, dtype=int)
        if allowed_window_indices is not None and any(int(w) not in allowed_window_indices for w in window):
            continue
        x_win = x_raw[window]
        if not np.isfinite(x_win).all():
            continue
        if scaler is not None:
            x_win = scaler.transform_features(x_win)
        else:
            x_win = x_win.astype("float32")

        if require_target:
            y_val = float(y_raw[int(idx)])
            if not np.isfinite(y_val):
                continue
            if scaler is not None:
                y_val = float(scaler.transform_target(np.asarray([y_val], dtype=float))[0])
            y_rows.append(y_val)

        x_rows.append(np.asarray(x_win, dtype="float32"))
        out_index.append(index_values[int(idx)])

    if not x_rows:
        return SequenceSamples(
            x=np.empty((0, lookback, len(feature_cols)), dtype="float32"),
            y=np.empty((0,), dtype="float32"),
            index=pd.Index([], dtype="datetime64[ns]"),
        )

    x_arr = np.stack(x_rows, axis=0).astype("float32")
    y_arr = np.asarray(y_rows, dtype="float32") if require_target else np.empty((len(x_rows),), dtype="float32")
    return SequenceSamples(x=x_arr, y=y_arr, index=pd.Index(out_index))


__all__ = [
    "SequenceSamples",
    "SequenceScaler",
    "build_sequence_samples",
    "fit_sequence_scaler",
]
