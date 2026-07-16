from __future__ import annotations

import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.experiments.models import train_chronos_2_forecaster
from src.utils.config import load_experiment_config
from src.utils.config_validation import ConfigValidationError, validate_model_block


class FakeChronos2Pipeline:
    calls: list[dict[str, object]] = []
    point_steps = (0.01, 0.02)

    @classmethod
    def from_pretrained(cls, *args: object, **kwargs: object) -> "FakeChronos2Pipeline":
        return cls()

    def predict_df(
        self,
        df: pd.DataFrame,
        **kwargs: object,
    ) -> pd.DataFrame:
        type(self).calls.append({"context_df": df.copy(deep=True), "kwargs": dict(kwargs)})
        prediction_length = int(kwargs["prediction_length"])
        quantiles = [float(value) for value in list(kwargs["quantile_levels"])]
        rows: list[dict[str, object]] = []
        for item_id, item in df.groupby("item_id", sort=False):
            last_timestamp = pd.Timestamp(item["timestamp"].iloc[-1])
            for step in range(prediction_length):
                row: dict[str, object] = {
                    "item_id": item_id,
                    "timestamp": last_timestamp + pd.Timedelta(minutes=30 * (step + 1)),
                    "predictions": float(self.point_steps[step % len(self.point_steps)]),
                }
                for quantile in quantiles:
                    if quantile <= 0.1:
                        value = 0.005
                    elif quantile >= 0.9:
                        value = 0.03
                    else:
                        value = float(self.point_steps[step % len(self.point_steps)])
                    row[str(quantile)] = value
                rows.append(row)
        return pd.DataFrame(rows)


@pytest.fixture
def fake_chronos2(monkeypatch: pytest.MonkeyPatch) -> type[FakeChronos2Pipeline]:
    FakeChronos2Pipeline.calls = []
    FakeChronos2Pipeline.point_steps = (0.01, 0.02)
    monkeypatch.setitem(sys.modules, "chronos", types.SimpleNamespace(Chronos2Pipeline=FakeChronos2Pipeline))
    return FakeChronos2Pipeline


def _frame(n_rows: int = 16) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=n_rows, freq="30min")
    return pd.DataFrame(
        {
            "close": np.full(n_rows, 100.0),
            "close_ret": np.full(n_rows, 0.001),
            "atr_48": np.full(n_rows, 1.0),
            "feature_a": np.arange(n_rows, dtype=float),
            "feature_b": np.arange(n_rows, dtype=float) + 100.0,
        },
        index=index,
    )


def _model_cfg(
    *,
    use_features: bool = True,
    feature_cols: list[str] | None = None,
    test_size: int = 2,
    min_context: int = 4,
) -> dict[str, object]:
    return {
        "use_features": use_features,
        "feature_cols": feature_cols if feature_cols is not None else ["close_ret", "feature_a", "feature_b"],
        "target": {
            "kind": "future_return_regression",
            "price_col": "close",
            "returns_col": "close_ret",
            "returns_type": "simple",
            "horizon_bars": 2,
            "normalize_by_volatility": True,
            "volatility_col": "atr_48",
            "volatility_floor": 1.0e-12,
            "clip": [-4.0, 4.0],
            "fwd_col": "target_future_return_h2_atr",
            "label_col": "target_future_return_h2_atr",
        },
        "split": {
            "method": "walk_forward",
            "train_size": 8,
            "test_size": test_size,
            "step_size": test_size,
            "expanding": True,
            "max_folds": 1,
        },
        "params": {
            "model_id": "fake/chronos-2",
            "source_col": "close_ret",
            "source_kind": "returns",
            "source_returns_type": "simple",
            "lookback": 4,
            "min_context": min_context,
            "prediction_length": 2,
            "quantiles": [0.1, 0.5, 0.9],
            "batch_size": 16,
            "freq": "30min",
        },
    }


def test_chronos2_covariates_are_causal_independent_and_aligned(
    fake_chronos2: type[FakeChronos2Pipeline],
) -> None:
    df = _frame()
    sentinel = 9_999_999.0
    df.loc[df.index[9:], "feature_a"] = sentinel

    out, _, meta = train_chronos_2_forecaster(df, model_cfg=_model_cfg())

    assert len(fake_chronos2.calls) == 1
    call = fake_chronos2.calls[0]
    context_df = call["context_df"]
    assert isinstance(context_df, pd.DataFrame)
    assert list(context_df.columns) == ["item_id", "timestamp", "target", "feature_a", "feature_b"]
    assert call["kwargs"] == {
        "id_column": "item_id",
        "timestamp_column": "timestamp",
        "target": "target",
        "prediction_length": 2,
        "quantile_levels": [0.1, 0.5, 0.9],
        "batch_size": 16,
        "cross_learning": False,
        "validate_inputs": False,
        "freq": "30min",
    }

    first_origin = context_df.loc[context_df["item_id"] == "chronos2_origin_8"]
    second_origin = context_df.loc[context_df["item_id"] == "chronos2_origin_9"]
    assert first_origin["timestamp"].tolist() == df.index[5:9].tolist()
    assert second_origin["timestamp"].tolist() == df.index[6:10].tolist()
    assert sentinel not in first_origin["feature_a"].tolist()
    assert sentinel in second_origin["feature_a"].tolist()
    assert first_origin["target"].tolist() == df.loc[df.index[5:9], "close_ret"].tolist()

    predicted_rows = out.loc[out["pred_ret"].notna()]
    assert predicted_rows.index.tolist() == df.index[8:10].tolist()
    assert out.loc[df.index[8:10], "pred_is_oos"].all()
    assert not out.loc[df.index[:8], "pred_is_oos"].any()
    assert predicted_rows["pred_ret"].to_numpy() == pytest.approx([3.02, 3.02])
    assert not {"pred_q10", "pred_q50", "pred_q90", "pred_vol"}.intersection(out.columns)

    fold = meta["folds"][0]
    assert fold["covariate_cols"] == ["feature_a", "feature_b"]
    assert fold["excluded_duplicate_source_cols"] == ["close_ret"]
    assert fold["covariate_count"] == 2
    assert fold["minimum_context_rows"] == 4
    assert fold["maximum_context_rows"] == 4
    assert fold["test_rows_without_prediction"] == 0
    assert fold["quantile_return_columns_available"] is False
    assert fold["quantile_return_contract"] == "unavailable_without_joint_return_paths"
    assert meta["model_family"] == "chronos_2"
    assert meta["zero_shot"] is True
    assert meta["covariate_cols"] == ["feature_a", "feature_b"]
    assert meta["foundation_test_samples"] == 2
    assert meta["feature_pipeline"]["actual_model_feature_count"] == 2
    assert meta["feature_pipeline"]["final_feature_names"] == ["feature_a", "feature_b"]


def test_chronos2_univariate_mode_preserves_the_original_input_shape(
    fake_chronos2: type[FakeChronos2Pipeline],
) -> None:
    out, _, meta = train_chronos_2_forecaster(
        _frame(),
        model_cfg=_model_cfg(use_features=False, feature_cols=[]),
    )

    call = fake_chronos2.calls[0]
    context_df = call["context_df"]
    assert isinstance(context_df, pd.DataFrame)
    assert list(context_df.columns) == ["item_id", "timestamp", "target"]
    assert out.loc[out["pred_is_oos"], "pred_ret"].notna().all()
    fold = meta["folds"][0]
    assert fold["use_features"] is False
    assert fold["covariate_count"] == 0
    assert fold["covariate_cols"] == []


def test_chronos2_uses_a_contiguous_finite_suffix_and_reports_dropped_rows(
    fake_chronos2: type[FakeChronos2Pipeline],
) -> None:
    df = _frame()
    df.loc[df.index[7], "feature_a"] = np.nan

    out, _, meta = train_chronos_2_forecaster(
        df,
        model_cfg=_model_cfg(test_size=4, min_context=3),
    )

    call = fake_chronos2.calls[0]
    context_df = call["context_df"]
    assert isinstance(context_df, pd.DataFrame)
    assert context_df["item_id"].unique().tolist() == ["chronos2_origin_10", "chronos2_origin_11"]
    first_valid_context = context_df.loc[context_df["item_id"] == "chronos2_origin_10"]
    assert first_valid_context["timestamp"].tolist() == df.index[8:11].tolist()
    assert out.loc[df.index[8:12], "pred_is_oos"].all()
    assert out.loc[df.index[8:12], "pred_ret"].notna().tolist() == [False, False, True, True]
    fold = meta["folds"][0]
    assert fold["test_rows_without_prediction"] == 2
    assert fold["dropped_context_reasons"] == {"insufficient_contiguous_finite_context": 2}
    assert fold["minimum_context_rows"] == 3
    assert fold["maximum_context_rows"] == 4


def _validation_model() -> dict[str, object]:
    return {
        "kind": "chronos_2_forecaster",
        "use_features": True,
        "feature_cols": ["close_ret", "feature_a"],
        "target": {
            "kind": "future_return_regression",
            "price_col": "close",
            "returns_col": "close_ret",
            "horizon_bars": 24,
            "fwd_col": "target_future_return_h24_atr",
            "label_col": "target_future_return_h24_atr",
        },
        "split": {"method": "purged", "train_size": 100, "test_size": 20},
        "params": {
            "source_col": "close_ret",
            "source_kind": "returns",
            "source_returns_type": "simple",
            "lookback": 96,
            "min_context": 24,
            "prediction_length": 24,
            "batch_size": 8,
            "freq": "30min",
            "quantiles": [0.1, 0.5, 0.9],
        },
    }


def test_chronos2_covariate_config_validation_contract() -> None:
    valid = _validation_model()
    validate_model_block(valid)

    duplicate = _validation_model()
    duplicate["feature_cols"] = ["close_ret", "feature_a", "feature_a"]
    with pytest.raises(ConfigValidationError, match="must not contain duplicates"):
        validate_model_block(duplicate)

    invalid_source_kind = _validation_model()
    invalid_source_kind["params"] = {**dict(invalid_source_kind["params"]), "source_kind": "levels"}
    with pytest.raises(ConfigValidationError, match="source_kind"):
        validate_model_block(invalid_source_kind)

    invalid_context = _validation_model()
    invalid_context["params"] = {**dict(invalid_context["params"]), "min_context": 97}
    with pytest.raises(ConfigValidationError, match="min_context"):
        validate_model_block(invalid_context)

    target_feature = _validation_model()
    target_feature["feature_cols"] = ["close_ret", "target_future_return_h24_atr"]
    with pytest.raises(ConfigValidationError, match="target or label output"):
        validate_model_block(target_feature)

    no_usable_covariate = _validation_model()
    no_usable_covariate["feature_cols"] = ["close_ret"]
    with pytest.raises(ConfigValidationError, match="requires at least one usable covariate"):
        validate_model_block(no_usable_covariate)

    univariate = _validation_model()
    univariate["use_features"] = False
    univariate["feature_cols"] = []
    validate_model_block(univariate)


def test_chronos2_ethusd_experiment_config_loads_without_model_download() -> None:
    config_path = (
        Path("config/experiments/foundation_alpha/BEST/ethusd")
        / "ethusd_30m_chronos_2_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml"
    )
    cfg = load_experiment_config(config_path)

    assert cfg["model"]["kind"] == "chronos_2_forecaster"
    assert cfg["model"]["use_features"] is True
    assert cfg["model"]["params"]["source_col"] == "close_ret"
    assert cfg["model"]["params"]["prediction_length"] == 24
    assert cfg["signals"]["params"]["forecast_col"] == "pred_ret"
    assert cfg["logging"]["save_model"] is False
    assert cfg["logging"]["install_model"] is False
