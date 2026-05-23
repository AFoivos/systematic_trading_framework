from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.transforms import TransformSeriesRequest, TransformStepConfig
from app.services import transform_catalog


def test_builder_catalog_exposes_registered_feature_signal_and_target_defaults() -> None:
    feature_by_name = {builder.name: builder for builder in transform_catalog.feature_builders()}
    signal_by_name = {builder.name: builder for builder in transform_catalog.signal_builders()}
    target_by_name = {builder.name: builder for builder in transform_catalog.target_builders()}

    assert "rsi" in feature_by_name
    assert "vwap" in feature_by_name
    assert "trend_state" in signal_by_name
    assert "forward_return" in target_by_name

    rsi_params = {param.name: param for param in feature_by_name["rsi"].parameters}
    assert rsi_params["windows"].kind == "list"
    assert rsi_params["windows"].default_value == [14]

    atr_params = {param.name: param for param in feature_by_name["atr"].parameters}
    assert atr_params["windows"].kind == "list"

    trend_state_params = {param.name: param for param in signal_by_name["trend_state"].parameters}
    assert trend_state_params["state_col"].required is True

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
