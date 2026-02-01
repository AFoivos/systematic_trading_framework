from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from src.features.lags import add_lagged_features


def default_feature_columns(df: pd.DataFrame) -> list[str]:
    """Select a reasonable feature set if the notebook does not override.

    Expects the upstream feature pipeline to have produced:
    - close_ret (simple returns)
    - vol_rolling_20, vol_rolling_60, vol_ewma_20
    - close_over_sma_20/50, close_over_ema_20
    - momentum / oscillators (optional, handled if present)
    """

    candidates = [
        "lag_close_ret_1",
        "lag_close_ret_2",
        "lag_close_ret_5",
        "vol_rolling_20",
        "vol_rolling_60",
        "vol_ewma_20",
        "close_over_sma_20",
        "close_over_sma_50",
        "close_over_ema_20",
        "close_logret_mom_5",
        "close_logret_mom_20",
        "close_logret_norm_mom_20",
        "close_rsi_14",
        "close_stoch_k_14",
        "close_stoch_d_14",
    ]
    return [c for c in candidates if c in df.columns]


@dataclass
class LGBMBaselineConfig:
    n_estimators: int = 400
    learning_rate: float = 0.03
    max_depth: int = 4
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    min_child_samples: int = 40
    random_state: int = 7


def train_regressor(
    train_df: pd.DataFrame,
    feature_cols: Sequence[str],
    target_col: str,
    cfg: LGBMBaselineConfig | None = None,
) -> LGBMRegressor:
    """Fit a LightGBM regressor on the provided split."""

    if cfg is None:
        cfg = LGBMBaselineConfig()

    X = train_df[feature_cols]
    y = train_df[target_col].astype(float)

    model = LGBMRegressor(
        n_estimators=cfg.n_estimators,
        learning_rate=cfg.learning_rate,
        max_depth=cfg.max_depth,
        subsample=cfg.subsample,
        colsample_bytree=cfg.colsample_bytree,
        min_child_samples=cfg.min_child_samples,
        random_state=cfg.random_state,
        n_jobs=-1,
    )
    model.fit(X, y)
    return model


def predict_returns(
    model: LGBMRegressor,
    df: pd.DataFrame,
    feature_cols: Sequence[str],
    pred_col: str = "pred_next_ret",
) -> pd.DataFrame:
    """Generate next-period return predictions and attach to dataframe."""

    out = df.copy()
    out[pred_col] = model.predict(out[feature_cols])
    return out


def prediction_to_signal(
    df: pd.DataFrame,
    pred_col: str = "pred_next_ret",
    signal_col: str = "signal_lgb",
    long_threshold: float = 0.0,
    short_threshold: float | None = None,
) -> pd.DataFrame:
    """Convert predicted returns to a {-1,0,1} trading signal."""

    out = df.copy()
    preds = out[pred_col].astype(float)

    if short_threshold is None:
        short_threshold = -abs(long_threshold)

    signal = pd.Series(0.0, index=out.index, name=signal_col)
    signal[preds > long_threshold] = 1.0
    signal[preds < short_threshold] = -1.0
    out[signal_col] = signal
    return out


def train_test_split_time(
    df: pd.DataFrame, train_frac: float = 0.7
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Time-ordered split (no shuffling)."""
    if not 0.0 < train_frac < 1.0:
        raise ValueError("train_frac must be in (0,1)")
    split = int(len(df) * train_frac)
    return df.iloc[:split], df.iloc[split:]
