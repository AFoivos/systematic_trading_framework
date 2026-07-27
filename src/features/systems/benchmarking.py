from __future__ import annotations

from collections.abc import Sequence
from numbers import Integral, Real

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.feature_selection import mutual_info_classif
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

from src.features.garman_klass_volatility import add_garman_klass_volatility
from src.features.parkinson_volatility import add_parkinson_volatility
from src.features.technical.adx import compute_adx
from src.features.technical.atr import compute_atr
from src.features.technical.macd import compute_macd
from src.features.technical.ppo import compute_ppo
from src.features.technical.roc import compute_roc
from src.features.technical.rsi import compute_rsi
from src.features.technical.stochastic import compute_stoch_d, compute_stoch_k
from src.features.yang_zhang_volatility import add_yang_zhang_volatility

from .common import prepare_market_data


TRADITIONAL_BENCHMARK_COLUMNS = (
    "benchmark_plus_di_14",
    "benchmark_minus_di_14",
    "benchmark_adx_14",
    "benchmark_signed_adx_14",
    "benchmark_ema_slope_20",
    "benchmark_macd_12_26",
    "benchmark_macd_hist_12_26_9",
    "benchmark_ppo_12_26",
    "benchmark_ppo_hist_12_26_9",
    "benchmark_atr_14",
    "benchmark_return_std_20",
    "benchmark_parkinson_vol_20",
    "benchmark_garman_klass_vol_20",
    "benchmark_yang_zhang_vol_20",
    "benchmark_roc_14",
    "benchmark_rsi_14",
    "benchmark_stochastic_k_14",
    "benchmark_stochastic_d_14_3",
)


def add_traditional_indicator_benchmarks(
    df: pd.DataFrame,
    *,
    window: int = 14,
    volatility_window: int = 20,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Add causal traditional indicators for neutral research comparisons.

    The function does not claim superiority and does not remove existing
    indicator implementations. All calculations use midpoint OHLC through the
    current closed bar.
    """
    if isinstance(window, bool) or not isinstance(window, Integral) or window <= 1:
        raise ValueError("window must be an integer > 1.")
    if (
        isinstance(volatility_window, bool)
        or not isinstance(volatility_window, Integral)
        or volatility_window <= 1
    ):
        raise ValueError("volatility_window must be an integer > 1.")
    market = prepare_market_data(df)
    out = df if inplace else df.copy()
    close = market.close.astype(float)
    high = market.high.astype(float)
    low = market.low.astype(float)

    adx = compute_adx(high, low, close, window=int(window))
    plus_di = adx[f"plus_di_{window}"]
    minus_di = adx[f"minus_di_{window}"]
    adx_value = adx[f"adx_{window}"]
    out[f"benchmark_plus_di_{window}"] = plus_di
    out[f"benchmark_minus_di_{window}"] = minus_di
    out[f"benchmark_adx_{window}"] = adx_value
    out[f"benchmark_signed_adx_{window}"] = np.sign(plus_di - minus_di) * adx_value

    ema = close.ewm(span=20, adjust=False).mean()
    out["benchmark_ema_slope_20"] = np.log(ema).diff()
    macd = compute_macd(close, fast=12, slow=26, signal=9)
    out["benchmark_macd_12_26"] = macd["macd_12_26"]
    out["benchmark_macd_hist_12_26_9"] = macd["macd_hist_12_26_9"]
    ppo = compute_ppo(close, fast=12, slow=26, signal=9)
    out["benchmark_ppo_12_26"] = ppo["ppo_12_26"]
    out["benchmark_ppo_hist_12_26_9"] = ppo["ppo_hist_12_26_9"]

    out[f"benchmark_atr_{window}"] = compute_atr(
        high,
        low,
        close,
        window=int(window),
        method="wilder",
    )
    returns = np.log(close / close.shift(1))
    out[f"benchmark_return_std_{volatility_window}"] = returns.rolling(
        int(volatility_window),
        min_periods=int(volatility_window),
    ).std(ddof=0)

    midpoint = market.as_frame().rename(
        columns={
            "mid_open": "open",
            "mid_high": "high",
            "mid_low": "low",
            "mid_close": "close",
        }
    )
    out[f"benchmark_parkinson_vol_{volatility_window}"] = add_parkinson_volatility(
        midpoint,
        window=int(volatility_window),
        output_col="__benchmark__",
    )["__benchmark__"]
    out[f"benchmark_garman_klass_vol_{volatility_window}"] = add_garman_klass_volatility(
        midpoint,
        window=int(volatility_window),
        output_col="__benchmark__",
    )["__benchmark__"]
    out[f"benchmark_yang_zhang_vol_{volatility_window}"] = add_yang_zhang_volatility(
        midpoint,
        window=int(volatility_window),
        output_col="__benchmark__",
    )["__benchmark__"]

    out[f"benchmark_roc_{window}"] = compute_roc(close, window=int(window))
    out[f"benchmark_rsi_{window}"] = compute_rsi(
        close,
        window=int(window),
        method="wilder",
    )
    stochastic_k = compute_stoch_k(close, high, low, window=int(window))
    out[f"benchmark_stochastic_k_{window}"] = stochastic_k
    out[f"benchmark_stochastic_d_{window}_3"] = compute_stoch_d(
        stochastic_k,
        smooth=3,
    )
    return out


def evaluate_feature_benchmarks(
    frame: pd.DataFrame,
    *,
    feature_cols: Sequence[str],
    target: pd.Series,
    forward_returns: pd.Series | None = None,
    costs: float | pd.Series | None = None,
    n_splits: int = 5,
    min_train_size: int | None = None,
    selective_quantile: float = 0.80,
    random_state: int = 0,
) -> pd.DataFrame:
    """
    Evaluate univariate features with expanding walk-forward splits.

    Scaling, logistic fitting, and selective-quantile thresholds use training
    rows only. Reported predictions are exclusively out of sample. Costs are
    accepted only as an externally supplied scalar or aligned Series.
    """
    if not feature_cols:
        raise ValueError("feature_cols must not be empty.")
    missing = [column for column in feature_cols if column not in frame.columns]
    if missing:
        raise KeyError(f"Missing benchmark feature columns: {missing}.")
    if isinstance(n_splits, bool) or not isinstance(n_splits, Integral) or n_splits < 2:
        raise ValueError("n_splits must be an integer >= 2.")
    if not 0.5 < float(selective_quantile) < 1.0:
        raise ValueError("selective_quantile must be in (0.5, 1).")

    aligned_target = pd.to_numeric(target.reindex(frame.index), errors="coerce").astype(float)
    observed_labels = set(aligned_target.dropna().unique())
    if not observed_labels.issubset({0.0, 1.0}):
        raise ValueError("target must contain binary values 0/1 or NaN.")
    aligned_returns = (
        pd.to_numeric(forward_returns.reindex(frame.index), errors="coerce").astype(float)
        if forward_returns is not None
        else None
    )
    aligned_costs = _resolve_costs(costs, index=frame.index)
    splits = _expanding_splits(
        len(frame),
        n_splits=int(n_splits),
        min_train_size=min_train_size,
    )

    rows: list[dict[str, float | int | str]] = []
    for feature in feature_cols:
        values = pd.to_numeric(frame[feature], errors="coerce").astype(float)
        fold_ic: list[float] = []
        fold_mi: list[float] = []
        probabilities: list[pd.Series] = []
        labels: list[pd.Series] = []
        positions: list[pd.Series] = []
        returns: list[pd.Series] = []
        turnover_costs: list[pd.Series] = []
        selective_correct = 0
        selective_count = 0
        completed_folds = 0

        for train_positions, test_positions in splits:
            train_index = frame.index[train_positions]
            test_index = frame.index[test_positions]
            train = pd.DataFrame(
                {"feature": values.loc[train_index], "target": aligned_target.loc[train_index]}
            ).replace([np.inf, -np.inf], np.nan).dropna()
            test = pd.DataFrame(
                {"feature": values.loc[test_index], "target": aligned_target.loc[test_index]}
            ).replace([np.inf, -np.inf], np.nan).dropna()
            if len(train) < 10 or len(test) < 2 or train["target"].nunique() < 2:
                continue
            mean = float(train["feature"].mean())
            std = float(train["feature"].std(ddof=0))
            if not np.isfinite(std) or std <= 0.0:
                continue
            model = LogisticRegression(random_state=random_state, solver="lbfgs")
            model.fit(
                ((train[["feature"]] - mean) / std).to_numpy(dtype=float),
                train["target"].to_numpy(dtype=int),
            )
            probability = pd.Series(
                model.predict_proba(
                    ((test[["feature"]] - mean) / std).to_numpy(dtype=float)
                )[:, 1],
                index=test.index,
                dtype="float64",
            )
            probability = probability.clip(lower=1e-12, upper=1.0 - 1e-12)
            position = pd.Series(
                np.where(probability >= 0.5, 1.0, -1.0),
                index=test.index,
                dtype="float64",
            )
            probabilities.append(probability)
            labels.append(test["target"])
            positions.append(position)
            turnover_costs.append(aligned_costs.loc[test.index])
            if aligned_returns is not None:
                returns.append(aligned_returns.loc[test.index])

            ic_reference = (
                aligned_returns.loc[test.index]
                if aligned_returns is not None
                else test["target"]
            )
            valid_ic = test["feature"].notna() & ic_reference.notna()
            if int(valid_ic.sum()) >= 3:
                correlation = spearmanr(
                    test.loc[valid_ic, "feature"],
                    ic_reference.loc[valid_ic],
                ).statistic
                if np.isfinite(correlation):
                    fold_ic.append(float(correlation))
            if test["target"].nunique() >= 2 and test["feature"].nunique() >= 2:
                fold_mi.append(
                    float(
                        mutual_info_classif(
                            test[["feature"]].to_numpy(dtype=float),
                            test["target"].to_numpy(dtype=int),
                            random_state=random_state,
                        )[0]
                    )
                )

            upper = float(train["feature"].quantile(selective_quantile))
            lower = float(train["feature"].quantile(1.0 - selective_quantile))
            high = test["feature"] >= upper
            low = test["feature"] <= lower
            selective_correct += int(test.loc[high, "target"].eq(1.0).sum())
            selective_correct += int(test.loc[low, "target"].eq(0.0).sum())
            selective_count += int(high.sum() + low.sum())
            completed_folds += 1

        row: dict[str, float | int | str] = {
            "feature": feature,
            "walk_forward_folds": completed_folds,
            "spearman_ic_mean": _safe_mean(fold_ic),
            "spearman_ic_std": _safe_std(fold_ic),
            "mutual_information_mean": _safe_mean(fold_mi),
            "log_loss": np.nan,
            "brier_score": np.nan,
            "auc": np.nan,
            "selective_precision": (
                selective_correct / selective_count if selective_count else np.nan
            ),
            "selective_observations": selective_count,
            "turnover": np.nan,
            "net_expectancy": np.nan,
        }
        if probabilities:
            probability = pd.concat(probabilities).sort_index()
            label = pd.concat(labels).sort_index().reindex(probability.index)
            row["log_loss"] = float(log_loss(label, probability, labels=[0, 1]))
            row["brier_score"] = float(brier_score_loss(label, probability))
            if label.nunique() >= 2:
                row["auc"] = float(roc_auc_score(label, probability))
            position = pd.concat(positions).sort_index()
            turnover = position.diff().abs().fillna(position.abs()) / 2.0
            row["turnover"] = float(turnover.mean())
            if aligned_returns is not None:
                oos_returns = pd.concat(returns).sort_index().reindex(position.index)
                oos_costs = pd.concat(turnover_costs).sort_index().reindex(position.index)
                valid_expectancy = oos_returns.notna() & oos_costs.notna()
                if bool(valid_expectancy.any()):
                    net = (
                        position.loc[valid_expectancy] * oos_returns.loc[valid_expectancy]
                        - turnover.loc[valid_expectancy] * oos_costs.loc[valid_expectancy]
                    )
                    row["net_expectancy"] = float(net.mean())
        rows.append(row)

    return pd.DataFrame(rows).set_index("feature", drop=False)


def compare_quant_systems_to_traditional(
    df: pd.DataFrame,
    *,
    new_feature_cols: Sequence[str],
    target: pd.Series,
    forward_returns: pd.Series | None = None,
    costs: float | pd.Series | None = None,
    n_splits: int = 5,
    min_train_size: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return a feature frame and neutral OOS comparison table."""
    benchmark_frame = add_traditional_indicator_benchmarks(df)
    feature_columns = list(new_feature_cols) + [
        column for column in TRADITIONAL_BENCHMARK_COLUMNS if column in benchmark_frame.columns
    ]
    metrics = evaluate_feature_benchmarks(
        benchmark_frame,
        feature_cols=feature_columns,
        target=target,
        forward_returns=forward_returns,
        costs=costs,
        n_splits=n_splits,
        min_train_size=min_train_size,
    )
    return benchmark_frame, metrics


def _expanding_splits(
    row_count: int,
    *,
    n_splits: int,
    min_train_size: int | None,
) -> list[tuple[np.ndarray, np.ndarray]]:
    resolved_min_train = (
        int(min_train_size)
        if min_train_size is not None
        else max(30, row_count // (n_splits + 1))
    )
    if resolved_min_train <= 0 or resolved_min_train >= row_count:
        raise ValueError("min_train_size must be positive and smaller than row count.")
    remaining = row_count - resolved_min_train
    test_size = remaining // n_splits
    if test_size < 2:
        raise ValueError("Insufficient rows for the requested walk-forward splits.")
    splits: list[tuple[np.ndarray, np.ndarray]] = []
    for split in range(n_splits):
        train_end = resolved_min_train + split * test_size
        test_end = row_count if split == n_splits - 1 else train_end + test_size
        splits.append(
            (
                np.arange(0, train_end, dtype=int),
                np.arange(train_end, test_end, dtype=int),
            )
        )
    return splits


def _resolve_costs(
    costs: float | pd.Series | None,
    *,
    index: pd.Index,
) -> pd.Series:
    if costs is None:
        return pd.Series(0.0, index=index, dtype="float64")
    if isinstance(costs, Real) and not isinstance(costs, bool):
        value = float(costs)
        if not np.isfinite(value) or value < 0.0:
            raise ValueError("costs must be finite and >= 0.")
        return pd.Series(value, index=index, dtype="float64")
    if not isinstance(costs, pd.Series):
        raise TypeError("costs must be a non-negative scalar, pandas Series, or None.")
    resolved = pd.to_numeric(costs.reindex(index), errors="coerce").astype(float)
    if bool((resolved.dropna() < 0.0).any()):
        raise ValueError("costs Series must be >= 0 where finite.")
    return resolved


def _safe_mean(values: list[float]) -> float:
    return float(np.mean(values)) if values else float("nan")


def _safe_std(values: list[float]) -> float:
    return float(np.std(values, ddof=0)) if values else float("nan")


__all__ = [
    "TRADITIONAL_BENCHMARK_COLUMNS",
    "add_traditional_indicator_benchmarks",
    "compare_quant_systems_to_traditional",
    "evaluate_feature_benchmarks",
]
