from __future__ import annotations

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from src.experiments.orchestration.feature_stage import apply_feature_steps
from src.features.helpers import (
    add_affine_transform, add_log_transform, add_product_transform,
    compute_affine, compute_log, compute_product,
)
from src.features.path_efficiency import add_path_efficiency
from src.features.rolling_autocorrelation import compute_rolling_autocorrelation
from src.meta.completed_trade_history import CompletedTradeHistoryState, add_completed_trade_history_features


def test_scalar_transforms_are_float32_safe_and_non_mutating() -> None:
    frame = pd.DataFrame({"x": [1.0, 0.0, -1.0, np.nan, np.inf], "side": [-1, 0, 1, 1, 1]})
    logged = add_log_transform(frame, source_col="x", offset=1.0, eps=1.0, output_col="log_x")
    affine = add_affine_transform(frame, source_col="x", scale=-2.0, offset=1.0)
    product = add_product_transform(frame, left_col="side", right_col="x")
    assert "log_x" not in frame
    assert logged["log_x"].dtype == np.dtype("float32")
    assert np.isnan(logged.loc[1, "log_x"])  # shifted value equals eps boundary only when eps=1
    assert np.isnan(logged.loc[2, "log_x"])
    assert affine["x_affine"].iloc[0] == pytest.approx(-1.0)
    assert product["side_times_x"].tolist()[:3] == [-1.0, 0.0, -1.0]
    with pytest.raises(ValueError):
        compute_log(frame["x"], eps=np.inf)
    with pytest.raises(ValueError):
        compute_affine(frame["x"], scale=np.nan)
    with pytest.raises(ValueError):
        compute_product(frame["x"], frame["side"], scale=np.inf)


def test_nested_transform_pipeline_produces_affine_log_and_product() -> None:
    frame = pd.DataFrame({"close": [1.0, 2.0, 4.0], "direction": [-1, 0, 1]})
    out = apply_feature_steps(frame, [{
        "step": "returns", "params": {"log": False, "col_name": "ret"},
        "transforms": {
            "affine": {"items": [{"source_col": "close", "output_col": "scaled", "scale": .5}]},
            "log": {"items": [{"source_col": "close", "output_col": "logged"}]},
            "product": {"items": [{"left_col": "direction", "right_col": "scaled", "output_col": "directed"}]},
        },
    }])
    assert {"scaled", "logged", "directed"}.issubset(out)


def test_path_efficiency_exact_flat_and_no_lookahead() -> None:
    frame = pd.DataFrame({"close": [1.0, 2.0, 3.0, 2.0, 3.0, 4.0]})
    out = add_path_efficiency(frame, windows=[2], use_log_prices=False)
    assert out["eff_2"].iloc[2] == pytest.approx(1.0)
    assert out["eff_2"].iloc[3] == pytest.approx(0.0)
    flat = add_path_efficiency(pd.DataFrame({"close": [2.0] * 5}), windows=[2])
    assert flat["eff_2"].isna().all()
    changed = frame.copy(); changed.loc[4:, "close"] = 100.0
    pdt.assert_series_equal(out["eff_2"].iloc[:4], add_path_efficiency(changed, windows=[2], use_log_prices=False)["eff_2"].iloc[:4])


def test_autocorrelation_matches_pandas_and_is_causal() -> None:
    series = pd.Series([1., -1., 1., -1., 1., -1., 1.])
    actual = compute_rolling_autocorrelation(series, window=4, lag=1)
    expected = series.rolling(4, min_periods=4).corr(series.shift(1)).astype("float32")
    pdt.assert_series_equal(actual, expected)
    changed = series.copy(); changed.iloc[6] = 999
    pdt.assert_series_equal(actual.iloc[:6], compute_rolling_autocorrelation(changed, window=4).iloc[:6])


def test_completed_trade_history_boundaries_groups_order_and_parity() -> None:
    trades = pd.DataFrame({"done": [2, 4, 4, 8], "outcome": [1., -1., 3., 99.], "asset": ["A", "A", "A", "A"]})
    candidates = pd.DataFrame({"at": [1, 4, 5, 9], "asset": ["A"] * 4}, index=[9, 3, 8, 1])
    batch = add_completed_trade_history_features(candidates, trades, candidate_time_col="at",
        completion_time_col="done", outcome_col="outcome", group_cols=["asset"], rolling_window=2)
    assert batch.index.tolist() == candidates.index.tolist()
    assert np.isnan(batch.iloc[0]["past_mean_all"])
    assert batch.iloc[1]["past_mean_all"] == pytest.approx(1.0)
    assert batch.iloc[2]["past_mean20"] == pytest.approx(1.0)  # stable last two: -1, 3
    state = CompletedTradeHistoryState(rolling_window=2)
    for row in trades.itertuples(index=False):
        state.update_completed_trade(row.done, row.outcome, group=(row.asset,))
    for pos, row in enumerate(candidates.itertuples(index=False)):
        got = state.features_at(row.at, group=(row.asset,))
        assert got["past_mean_all"] == pytest.approx(batch.iloc[pos]["past_mean_all"], nan_ok=True)
