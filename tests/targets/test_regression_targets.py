from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd
import pytest

from src.targets.registry import TARGET_REGISTRY, build_target
from src.utils.config_validation import ConfigValidationError, validate_model_block


REQUESTED_REGRESSION_TARGETS = {
    "volatility_normalized_future_return",
    "risk_adjusted_future_return",
    "r_multiple_regression",
    "mfe_regression",
    "mae_regression",
    "mfe_mae_ratio_regression",
    "downside_adjusted_future_return",
    "future_trend_slope",
    "future_path_efficiency",
    "excess_return_regression",
    "residual_return_regression",
    "future_range_regression",
    "future_realized_volatility",
    "future_drawdown_regression",
}

TWO_STEP_MINIMUM_TARGETS = {
    "risk_adjusted_future_return": 2,
    "future_trend_slope": 5,
    "future_path_efficiency": 2,
    "future_realized_volatility": 5,
}


def _base_frame() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=8, freq="30min")
    close = pd.Series([100.0, 102.0, 101.0, 105.0, 103.0, 106.0, 104.0, 108.0], index=idx)
    benchmark_close = pd.Series([100.0, 101.0, 102.0, 101.0, 103.0, 104.0, 103.0, 105.0], index=idx)
    return pd.DataFrame(
        {
            "open": close,
            "high": [101.0, 104.0, 103.0, 107.0, 106.0, 108.0, 106.0, 110.0],
            "low": [99.0, 100.0, 98.0, 102.0, 101.0, 103.0, 102.0, 105.0],
            "close": close,
            "atr_14": [2.0] * len(idx),
            "ret": close.pct_change().fillna(0.0),
            "log_ret": np.log(close / close.shift(1)).fillna(0.0),
            "benchmark_close": benchmark_close,
            "benchmark_ret": benchmark_close.pct_change().fillna(0.0),
            "benchmark_log_ret": np.log(benchmark_close / benchmark_close.shift(1)).fillna(0.0),
        },
        index=idx,
    )


def _residual_frame() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=8, freq="30min")
    benchmark_ret = pd.Series([0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07], index=idx)
    asset_ret = 2.0 * benchmark_ret
    benchmark_log_ret = np.log1p(benchmark_ret)
    return pd.DataFrame(
        {
            "close": 100.0 * (1.0 + asset_ret).cumprod(),
            "benchmark_close": 100.0 * (1.0 + benchmark_ret).cumprod(),
            "ret": asset_ret,
            "benchmark_ret": benchmark_ret,
            "log_ret": 2.0 * benchmark_log_ret,
            "benchmark_log_ret": benchmark_log_ret,
        },
        index=idx,
    )


def _realized_vol(df: pd.DataFrame, returns_col: str = "ret", *, start: int = 1, stop: int = 3) -> float:
    return float(pd.Series(df[returns_col].iloc[start:stop]).std(ddof=0))


def _cfg_for(kind: str) -> dict[str, Any]:
    cfg: dict[str, Any] = {"kind": kind, "horizon_bars": 2}
    if kind in {"volatility_normalized_future_return", "r_multiple_regression"}:
        cfg.update({"volatility_col": "atr_14"})
    if kind == "r_multiple_regression":
        cfg.update({"atr_multiple": 2.0})
    if kind in {
        "mfe_regression",
        "mae_regression",
        "mfe_mae_ratio_regression",
        "downside_adjusted_future_return",
        "future_drawdown_regression",
    }:
        cfg.update({"direction": "long"})
    if kind == "mfe_mae_ratio_regression":
        cfg.update({"mode": "ratio"})
    if kind in {"excess_return_regression", "residual_return_regression"}:
        cfg.update({"benchmark_price_col": "benchmark_close"})
    if kind == "residual_return_regression":
        cfg.update(
            {
                "returns_col": "ret",
                "benchmark_returns_col": "benchmark_ret",
                "beta_window": 2,
                "min_periods": 2,
                "horizon_bars": 1,
            }
        )
    if kind == "future_trend_slope":
        cfg.update({"horizon_bars": 3})
    if kind == "future_realized_volatility":
        cfg.update({"horizon_bars": 2})
    return cfg


def _frame_for(kind: str) -> pd.DataFrame:
    return _residual_frame() if kind == "residual_return_regression" else _base_frame()


BASIC_CASES: list[tuple[str, int, Callable[[pd.DataFrame], float]]] = [
    (
        "volatility_normalized_future_return",
        0,
        lambda df: (df["close"].iloc[2] / df["close"].iloc[0] - 1.0) / (df["atr_14"].iloc[0] / df["close"].iloc[0]),
    ),
    (
        "risk_adjusted_future_return",
        0,
        lambda df: (df["close"].iloc[2] / df["close"].iloc[0] - 1.0) / _realized_vol(df),
    ),
    (
        "r_multiple_regression",
        0,
        lambda df: (df["close"].iloc[2] / df["close"].iloc[0] - 1.0) / (2.0 * df["atr_14"].iloc[0] / df["close"].iloc[0]),
    ),
    ("mfe_regression", 0, lambda df: max(df["high"].iloc[1:3]) / df["close"].iloc[0] - 1.0),
    ("mae_regression", 0, lambda df: min(df["low"].iloc[1:3]) / df["close"].iloc[0] - 1.0),
    (
        "mfe_mae_ratio_regression",
        0,
        lambda df: (max(df["high"].iloc[1:3]) / df["close"].iloc[0] - 1.0)
        / abs(min(df["low"].iloc[1:3]) / df["close"].iloc[0] - 1.0),
    ),
    (
        "downside_adjusted_future_return",
        0,
        lambda df: (df["close"].iloc[2] / df["close"].iloc[0] - 1.0)
        - abs(min(df["low"].iloc[1:3]) / df["close"].iloc[0] - 1.0),
    ),
    ("future_trend_slope", 0, lambda df: 1.5 / df["close"].iloc[0]),
    (
        "future_path_efficiency",
        0,
        lambda df: (df["close"].iloc[2] - df["close"].iloc[0])
        / (abs(df["close"].iloc[1] - df["close"].iloc[0]) + abs(df["close"].iloc[2] - df["close"].iloc[1])),
    ),
    (
        "excess_return_regression",
        0,
        lambda df: (df["close"].iloc[2] / df["close"].iloc[0] - 1.0)
        - (df["benchmark_close"].iloc[2] / df["benchmark_close"].iloc[0] - 1.0),
    ),
    ("residual_return_regression", 2, lambda df: 0.0),
    (
        "future_range_regression",
        0,
        lambda df: (max(df["high"].iloc[1:3]) - min(df["low"].iloc[1:3])) / df["close"].iloc[0],
    ),
    ("future_realized_volatility", 0, lambda df: _realized_vol(df)),
    ("future_drawdown_regression", 0, lambda df: min(df["low"].iloc[1:3]) / df["close"].iloc[0] - 1.0),
]


def test_requested_regression_targets_are_registered() -> None:
    assert REQUESTED_REGRESSION_TARGETS.issubset(TARGET_REGISTRY)


@pytest.mark.parametrize("kind", sorted(REQUESTED_REGRESSION_TARGETS))
def test_regression_targets_are_validated_as_forecaster_targets(kind: str) -> None:
    target = _cfg_for(kind)
    validate_model_block(
        {
            "kind": "lightgbm_regressor",
            "feature_cols": ["feature_x"],
            "target": target,
        }
    )

    with pytest.raises(ConfigValidationError, match="regression forecasters"):
        validate_model_block(
            {
                "kind": "lightgbm_clf",
                "feature_cols": ["feature_x"],
                "target": target,
            }
        )


@pytest.mark.parametrize("kind,row,expected_fn", BASIC_CASES, ids=[case[0] for case in BASIC_CASES])
def test_regression_targets_basic_calculation_outputs_and_metadata(
    kind: str,
    row: int,
    expected_fn: Callable[[pd.DataFrame], float],
) -> None:
    df = _frame_for(kind)
    out, label_col, fwd_col, meta = build_target(df, _cfg_for(kind))

    assert label_col == fwd_col
    assert meta["kind"] == kind
    assert meta["horizon"] == meta["horizon_bars"]
    assert fwd_col in out.columns
    assert fwd_col in meta["output_cols"]
    assert "target_stats" in meta
    assert "q99" in meta["target_stats"]
    assert out[fwd_col].iloc[row] == pytest.approx(expected_fn(df))
    assert out[fwd_col].tail(int(meta["horizon"])).isna().all()
    assert 0.0 < meta["target_density"] <= 1.0


@pytest.mark.parametrize("kind", sorted(REQUESTED_REGRESSION_TARGETS))
def test_regression_targets_support_clipping_label_aliases_and_outputs(kind: str) -> None:
    cfg = _cfg_for(kind)
    cfg.update({"clip": [-0.01, 0.01], "fwd_col": "clipped_target", "label_col": "aliased_label"})

    out, label_col, fwd_col, meta = build_target(_frame_for(kind), cfg)

    assert label_col == "aliased_label"
    assert fwd_col == "clipped_target"
    assert {"clipped_target", "aliased_label"}.issubset(out.columns)
    assert {"clipped_target", "aliased_label"}.issubset(set(meta["output_cols"]))
    finite = out[fwd_col].dropna()
    assert not finite.empty
    assert float(finite.min()) >= -0.010000001
    assert float(finite.max()) <= 0.010000001
    pd.testing.assert_series_equal(out[fwd_col], out[label_col], check_names=False)


@pytest.mark.parametrize("kind", sorted(REQUESTED_REGRESSION_TARGETS))
def test_regression_targets_reject_invalid_horizon(kind: str) -> None:
    cfg = _cfg_for(kind)
    cfg["horizon_bars"] = 0

    with pytest.raises(ValueError, match="horizon_bars"):
        build_target(_frame_for(kind), cfg)


@pytest.mark.parametrize("kind", sorted(TWO_STEP_MINIMUM_TARGETS))
def test_two_step_targets_reject_horizon_one_during_validation_and_build(kind: str) -> None:
    cfg = _cfg_for(kind)
    cfg["horizon_bars"] = 1
    model = {
        "kind": "lightgbm_regressor",
        "feature_cols": ["feature_x"],
        "target": cfg,
    }

    with pytest.raises(ConfigValidationError, match="horizon_bars must be >= 2"):
        validate_model_block(model)
    with pytest.raises(ValueError, match="horizon_bars must be >= 2"):
        build_target(_frame_for(kind), cfg)


@pytest.mark.parametrize(
    ("kind", "expected_default"),
    sorted(TWO_STEP_MINIMUM_TARGETS.items()),
)
def test_two_step_target_defaults_match_validation_and_builder(
    kind: str,
    expected_default: int,
) -> None:
    cfg = _cfg_for(kind)
    cfg.pop("horizon_bars", None)

    validate_model_block(
        {
            "kind": "lightgbm_regressor",
            "feature_cols": ["feature_x"],
            "target": cfg,
        }
    )
    out, _, fwd_col, meta = build_target(_frame_for(kind), cfg)

    assert meta["horizon"] == expected_default
    assert out[fwd_col].notna().any()


@pytest.mark.parametrize(
    ("kind", "missing_col"),
    [
        ("volatility_normalized_future_return", "atr_14"),
        ("risk_adjusted_future_return", "close"),
        ("r_multiple_regression", "atr_14"),
        ("mfe_regression", "high"),
        ("mae_regression", "low"),
        ("mfe_mae_ratio_regression", "high"),
        ("downside_adjusted_future_return", "low"),
        ("future_trend_slope", "close"),
        ("future_path_efficiency", "close"),
        ("excess_return_regression", "benchmark_close"),
        ("residual_return_regression", "benchmark_ret"),
        ("future_range_regression", "high"),
        ("future_realized_volatility", "close"),
        ("future_drawdown_regression", "low"),
    ],
)
def test_regression_targets_raise_keyerror_for_missing_required_columns(kind: str, missing_col: str) -> None:
    df = _frame_for(kind).drop(columns=[missing_col])

    with pytest.raises(KeyError):
        build_target(df, _cfg_for(kind))


@pytest.mark.parametrize(
    ("kind", "overrides", "message"),
    [
        ("r_multiple_regression", {"atr_multiple": 0.0}, "atr_multiple"),
        ("volatility_normalized_future_return", {"volatility_floor": 0.0}, "volatility_floor"),
        ("mfe_mae_ratio_regression", {"mode": "bad"}, "mode"),
        ("mfe_mae_ratio_regression", {"denominator_floor": 0.0}, "denominator_floor"),
        ("downside_adjusted_future_return", {"penalty_lambda": -1.0}, "penalty_lambda"),
        ("future_path_efficiency", {"path_floor": 0.0}, "path_floor"),
        ("future_range_regression", {"normalize": "bad"}, "normalize"),
        ("residual_return_regression", {"beta_window": 2, "min_periods": 3}, "min_periods"),
    ],
)
def test_regression_targets_reject_invalid_params(kind: str, overrides: dict[str, Any], message: str) -> None:
    cfg = _cfg_for(kind)
    cfg.update(overrides)

    with pytest.raises(ValueError, match=message):
        build_target(_frame_for(kind), cfg)


@pytest.mark.parametrize(
    ("kind", "expected_fn"),
    [
        (
            "volatility_normalized_future_return",
            lambda df: np.log(df["close"].iloc[2] / df["close"].iloc[0]) / (df["atr_14"].iloc[0] / df["close"].iloc[0]),
        ),
        (
            "risk_adjusted_future_return",
            lambda df: np.log(df["close"].iloc[2] / df["close"].iloc[0]) / _realized_vol(df, "log_ret"),
        ),
        (
            "r_multiple_regression",
            lambda df: np.log(df["close"].iloc[2] / df["close"].iloc[0]) / (2.0 * df["atr_14"].iloc[0] / df["close"].iloc[0]),
        ),
        (
            "excess_return_regression",
            lambda df: np.log(df["close"].iloc[2] / df["close"].iloc[0])
            - np.log(df["benchmark_close"].iloc[2] / df["benchmark_close"].iloc[0]),
        ),
    ],
)
def test_regression_targets_support_returns_col_and_log_mode(
    kind: str,
    expected_fn: Callable[[pd.DataFrame], float],
) -> None:
    df = _base_frame()
    cfg = _cfg_for(kind)
    cfg.update({"returns_col": "log_ret", "returns_type": "log"})
    if kind == "excess_return_regression":
        cfg["benchmark_returns_col"] = "benchmark_log_ret"

    out, _, fwd_col, _ = build_target(df, cfg)

    assert out[fwd_col].iloc[0] == pytest.approx(expected_fn(df))


def test_residual_return_regression_supports_log_returns_col_mode_without_beta_leakage() -> None:
    df = _residual_frame()

    out, _, fwd_col, meta = build_target(
        df,
        {
            "kind": "residual_return_regression",
            "returns_col": "log_ret",
            "benchmark_returns_col": "benchmark_log_ret",
            "returns_type": "log",
            "beta_window": 2,
            "min_periods": 2,
            "horizon_bars": 1,
        },
    )

    assert out[meta["beta_col"]].iloc[2] == pytest.approx(2.0)
    assert out[fwd_col].iloc[2] == pytest.approx(0.0)
    assert "future benchmark return is used only to construct the residual target" in meta["leakage_note"]


@pytest.mark.parametrize("horizon", [2, 4])
def test_future_realized_volatility_supports_log_returns_from_price_and_annualization(
    horizon: int,
) -> None:
    df = _base_frame()

    out, _, fwd_col, meta = build_target(
        df,
        {
            "kind": "future_realized_volatility",
            "price_col": "close",
            "returns_type": "log",
            "horizon_bars": horizon,
            "annualize": True,
            "periods_per_year": 252,
        },
    )

    expected = float(df["log_ret"].iloc[1 : horizon + 1].std(ddof=0)) * np.sqrt(252)
    assert out[fwd_col].iloc[0] == pytest.approx(expected)
    assert meta["annualization_convention"] == "std(future one-step returns) * sqrt(periods_per_year)"
    assert meta["annualization_convention_version"] == 2


def test_short_regression_targets_use_canonical_unit_notional_pnl() -> None:
    idx = pd.date_range("2024-01-01", periods=3, freq="h")
    favorable = pd.DataFrame(
        {
            "open": [100.0, 50.0, 50.0],
            "high": [100.0, 100.0, 50.0],
            "low": [100.0, 50.0, 50.0],
            "close": [100.0, 50.0, 50.0],
            "atr_14": [1.0] * 3,
        },
        index=idx,
    )
    adverse = pd.DataFrame(
        {
            "open": [100.0, 200.0, 200.0],
            "high": [100.0, 200.0, 200.0],
            "low": [100.0, 100.0, 200.0],
            "close": [100.0, 200.0, 200.0],
            "atr_14": [1.0] * 3,
        },
        index=idx,
    )

    mfe_out, _, mfe_col, _ = build_target(
        favorable,
        {"kind": "mfe_regression", "direction": "short", "horizon_bars": 1},
    )
    return_out, _, return_col, _ = build_target(
        favorable,
        {
            "kind": "downside_adjusted_future_return",
            "direction": "short",
            "horizon_bars": 1,
            "penalty_lambda": 0.0,
        },
    )
    mae_out, _, mae_col, _ = build_target(
        adverse,
        {"kind": "mae_regression", "direction": "short", "horizon_bars": 1},
    )
    drawdown_out, _, drawdown_col, _ = build_target(
        adverse,
        {
            "kind": "future_drawdown_regression",
            "direction": "short",
            "horizon_bars": 1,
        },
    )

    assert mfe_out[mfe_col].iloc[0] == pytest.approx(0.5)
    assert return_out[return_col].iloc[0] == pytest.approx(0.5)
    assert mae_out[mae_col].iloc[0] == pytest.approx(-1.0)
    assert drawdown_out[drawdown_col].iloc[0] == pytest.approx(-1.0)


def test_regression_targets_handle_internal_nans_without_filling_future_windows() -> None:
    df = _base_frame()
    df.loc[df.index[1], "high"] = np.nan

    out, _, fwd_col, _ = build_target(df, _cfg_for("mfe_regression"))

    assert np.isnan(out[fwd_col].iloc[0])
    assert out[fwd_col].iloc[2:].notna().any()


def test_regression_targets_floor_protections_return_nan_instead_of_infinite_values() -> None:
    df = _base_frame()
    df["atr_14"] = 0.0
    out, _, fwd_col, _ = build_target(df, _cfg_for("volatility_normalized_future_return"))
    assert out[fwd_col].dropna().empty

    flat = _base_frame()
    flat["close"] = 100.0
    flat["high"] = 100.0
    flat["low"] = 100.0
    out, _, fwd_col, _ = build_target(flat, _cfg_for("mfe_mae_ratio_regression"))
    assert out[fwd_col].dropna().empty
