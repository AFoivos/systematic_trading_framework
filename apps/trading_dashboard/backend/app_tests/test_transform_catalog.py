from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.transforms import TransformSeriesRequest, TransformStepConfig
from app.services import transform_catalog


def _ohlcv_frame(periods: int = 80) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=periods, freq="h", tz="UTC")
    close = pd.Series([100.0 + idx * 0.2 for idx in range(periods)], index=index)
    return pd.DataFrame(
        {
            "open": close.shift(1).fillna(close.iloc[0] - 0.1),
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": [1000.0] * periods,
        },
        index=index,
    )


def _install_fake_loader(monkeypatch, frame: pd.DataFrame) -> None:
    class FakeLoader:
        def load_frame(self, **_: object):
            return frame, SimpleNamespace(id="in-memory", assets=["XAUUSD"])

    monkeypatch.setattr(transform_catalog, "DataLoader", lambda: FakeLoader())


def test_builder_catalog_exposes_registered_feature_signal_and_target_defaults() -> None:
    feature_by_name = {builder.name: builder for builder in transform_catalog.feature_builders()}
    signal_by_name = {builder.name: builder for builder in transform_catalog.signal_builders()}
    target_by_name = {builder.name: builder for builder in transform_catalog.target_builders()}

    assert "rsi" in feature_by_name
    assert "vwap" in feature_by_name
    assert "ema_rms_ppo_vwap" in signal_by_name
    assert "vwap_rms_ema_cross_long" in signal_by_name
    assert "trend_state" in signal_by_name
    assert "forward_return" in target_by_name

    rsi_params = {param.name: param for param in feature_by_name["rsi"].parameters}
    assert rsi_params["windows"].kind == "list"
    assert rsi_params["windows"].default_value == [14]

    atr_params = {param.name: param for param in feature_by_name["atr"].parameters}
    assert atr_params["windows"].kind == "list"

    trend_state_params = {param.name: param for param in signal_by_name["trend_state"].parameters}
    assert trend_state_params["state_col"].required is False
    assert trend_state_params["state_col"].default_value == "close_trend_state_sma_20_50"

    forward_return_params = {param.name: param for param in target_by_name["forward_return"].parameters}
    assert forward_return_params["horizon"].default_value == 1


def test_transform_series_runs_existing_builders_without_writing_artifacts(monkeypatch) -> None:
    index = pd.date_range("2024-01-01", periods=8, freq="h", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": [100, 101, 102, 103, 104, 105, 106, 107],
            "high": [101, 102, 103, 104, 105, 106, 107, 108],
            "low": [99, 100, 101, 102, 103, 104, 105, 106],
            "close": [100, 101, 102, 103, 104, 105, 106, 107],
            "volume": [1000] * 8,
        },
        index=index,
    )

    class FakeLoader:
        def load_frame(self, **_: object):
            return frame, SimpleNamespace(id="in-memory")

    monkeypatch.setattr(transform_catalog, "DataLoader", lambda: FakeLoader())

    response = transform_catalog.run_transform_series(
        TransformSeriesRequest(
            asset="XAUUSD",
            limit=5,
            features=[
                TransformStepConfig(step="returns", params={"log": False}, enabled=True),
            ],
            targets=[
                TransformStepConfig(step="forward_return", params={"price_col": "close", "horizon": 2}, enabled=True),
            ],
        )
    )

    series_ids = {series.series_id for series in response.series}
    assert {"close_ret", "target_fwd_2", "label"}.issubset(series_ids)
    assert response.metadata["dataset_id"] == "in-memory"
    assert response.metadata["rows_loaded"] == 8
    assert response.metadata["rows_returned"] == 5


def test_transform_series_materializes_missing_target_returns_from_ohlcv(monkeypatch) -> None:
    _install_fake_loader(monkeypatch, _ohlcv_frame())

    response = transform_catalog.run_transform_series(
        TransformSeriesRequest(
            asset="XAUUSD",
            targets=[
                TransformStepConfig(
                    step="forward_return",
                    params={
                        "returns_col": "close_logret",
                        "returns_type": "log",
                        "horizon": 2,
                    },
                ),
            ],
        )
    )

    assert {series.series_id for series in response.series} == {"target_fwd_2", "label"}
    assert response.steps[0].metadata["materialized_prerequisites"] == ["close_logret"]


def test_transform_series_materializes_tsfresh_transform_source_from_ohlcv(monkeypatch) -> None:
    _install_fake_loader(monkeypatch, _ohlcv_frame())

    response = transform_catalog.run_transform_series(
        TransformSeriesRequest(
            asset="XAUUSD",
            features=[
                TransformStepConfig(
                    step="feature_transforms",
                    params={
                        "transforms": [
                            {
                                "source_col": "close_logret",
                                "kind": "tsfresh_rolling",
                                "window": 4,
                                "calculators": ["mean", "length"],
                            }
                        ]
                    },
                ),
            ],
        )
    )

    assert {series.series_id for series in response.series} == {
        "close_logret__mean",
        "close_logret__length",
    }
    assert response.steps[0].metadata["materialized_prerequisites"] == ["close_logret"]


def test_transform_series_materializes_default_rsi_signal_dependencies_from_ohlcv(monkeypatch) -> None:
    _install_fake_loader(monkeypatch, _ohlcv_frame())

    response = transform_catalog.run_transform_series(
        TransformSeriesRequest(
            asset="XAUUSD",
            signals=[TransformStepConfig(step="rsi")],
        )
    )

    assert {series.series_id for series in response.series} == {"signal_rsi"}
    assert response.steps[0].metadata["materialized_prerequisites"] == ["close_rsi_14"]


def test_transform_series_materializes_recursive_trend_state_dependencies_from_ohlcv(monkeypatch) -> None:
    _install_fake_loader(monkeypatch, _ohlcv_frame())

    response = transform_catalog.run_transform_series(
        TransformSeriesRequest(
            asset="XAUUSD",
            signals=[TransformStepConfig(step="trend_state")],
        )
    )

    assert {series.series_id for series in response.series} == {"signal_trend_state"}
    prerequisites = set(response.steps[0].metadata["materialized_prerequisites"])
    assert {"close_sma_20", "close_sma_50", "close_trend_state_sma_20_50"}.issubset(prerequisites)


def test_transform_series_materializes_ema_rms_ppo_vwap_signal_dependencies_from_ohlcv(monkeypatch) -> None:
    _install_fake_loader(monkeypatch, _ohlcv_frame(periods=120))

    response = transform_catalog.run_transform_series(
        TransformSeriesRequest(
            asset="XAUUSD",
            signals=[TransformStepConfig(step="ema_rms_ppo_vwap")],
        )
    )

    assert {"signal_side", "signal_candidate", "ema_rms_fast_slope"}.issubset(
        {series.series_id for series in response.series}
    )
    prerequisites = set(response.steps[0].metadata["materialized_prerequisites"])
    assert {
        "atr_14",
        "ema_20__root_mean_square",
        "ema_50__root_mean_square",
        "ema_100__root_mean_square",
        "vwap_20",
        "vwap_20__root_mean_square",
        "ppo",
        "ppo_signal",
    }.issubset(prerequisites)


def test_transform_series_materializes_vwap_rms_ema_cross_long_dependencies_from_ohlcv(monkeypatch) -> None:
    _install_fake_loader(monkeypatch, _ohlcv_frame(periods=120))

    response = transform_catalog.run_transform_series(
        TransformSeriesRequest(
            asset="XAUUSD",
            signals=[TransformStepConfig(step="vwap_rms_ema_cross_long")],
        )
    )

    assert {"signal_side", "signal_candidate", "vwap_rms_ema_cross_long_setup"}.issubset(
        {series.series_id for series in response.series}
    )
    prerequisites = set(response.steps[0].metadata["materialized_prerequisites"])
    assert {
        "ema_50",
        "ema_100",
        "ema_50__root_mean_square",
        "vwap_20",
        "vwap_20__root_mean_square",
        "ppo",
        "ppo_signal",
    }.issubset(prerequisites)


def test_transform_series_rejects_non_derivable_prediction_dependency(monkeypatch) -> None:
    _install_fake_loader(monkeypatch, _ohlcv_frame())

    with pytest.raises(KeyError, match="cannot derive prerequisite column 'pred_ret'"):
        transform_catalog.run_transform_series(
            TransformSeriesRequest(
                asset="XAUUSD",
                signals=[TransformStepConfig(step="forecast_threshold")],
            )
        )
