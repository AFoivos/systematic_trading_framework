from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.experiments.orchestration.feature_stage import apply_signal_step
from src.signals.quote_flow_scalp_router_signal import (
    build_quote_flow_scalp_router_signal,
    quote_flow_scalp_router_signal,
)
from src.utils.config import load_experiment_config


DIAGNOSTIC_CONFIG_DIR = Path("config/experiments/scalp/diagnostics")


def _base_row() -> dict[str, float]:
    return {
        "close": 100.0,
        "high": 101.0,
        "low": 99.0,
        "atr_14": 1.0,
        "close_minus_vwap_20_atr": 0.0,
        "vpin_proxy_50_rank_252": 0.50,
        "ofi_proxy_5_norm": 0.0,
        "ofi_proxy_15_norm": 0.0,
        "spread_bps_rank_252": 0.30,
        "spread_bps_z_252": 0.0,
        "volume_relative_48": 1.0,
        "close_pos_in_bar": 0.50,
        "bar_range_atr": 0.50,
        "bar_body_atr": 0.0,
        "upper_wick_atr": 0.10,
        "lower_wick_atr": 0.10,
        "close_minus_support_atr": 1.0,
        "resistance_minus_close_atr": 1.0,
        "session_london_ny_liquid": 1.0,
    }


def _frame(rows: list[dict[str, float]]) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(rows), freq="5min", tz="UTC")
    return pd.DataFrame(rows, index=idx)


def _with(**updates: float) -> dict[str, float]:
    row = _base_row()
    row.update(updates)
    return row


def test_quote_flow_scalp_router_flat_when_spread_too_high() -> None:
    out, meta = build_quote_flow_scalp_router_signal(
        _frame(
            [
                _with(
                    spread_bps_rank_252=0.95,
                    vpin_proxy_50_rank_252=0.8,
                    ofi_proxy_5_norm=0.3,
                    ofi_proxy_15_norm=0.1,
                    volume_relative_48=1.2,
                    close_pos_in_bar=0.8,
                    bar_body_atr=0.2,
                )
            ]
        )
    )

    assert meta["kind"] == "quote_flow_scalp_router"
    assert out["signal_candidate"].tolist() == [0]
    assert out["signal_side"].tolist() == [0]
    assert out["qfs_cond_spread_ok"].tolist() == [0]


def test_quote_flow_scalp_router_toxic_flow_long_and_short_trigger() -> None:
    out, _ = build_quote_flow_scalp_router_signal(
        _frame(
            [
                _with(
                    vpin_proxy_50_rank_252=0.8,
                    ofi_proxy_5_norm=0.3,
                    ofi_proxy_15_norm=0.1,
                    volume_relative_48=1.2,
                    close_pos_in_bar=0.8,
                    bar_body_atr=0.2,
                ),
                _with(
                    vpin_proxy_50_rank_252=0.8,
                    ofi_proxy_5_norm=-0.3,
                    ofi_proxy_15_norm=-0.1,
                    volume_relative_48=1.2,
                    close_pos_in_bar=0.2,
                    bar_body_atr=-0.2,
                ),
            ]
        )
    )

    assert out["signal_side"].tolist() == [1, -1]
    assert out["signal_mode"].tolist() == [1, 1]
    assert out["qfs_cond_toxic_flow_long"].tolist() == [1, 0]
    assert out["qfs_cond_toxic_flow_short"].tolist() == [0, 1]


def test_quote_flow_scalp_router_sweep_fade_long_and_short_trigger() -> None:
    out, _ = build_quote_flow_scalp_router_signal(
        _frame(
            [
                _with(
                    lower_wick_atr=0.5,
                    close_pos_in_bar=0.7,
                    bar_range_atr=0.8,
                    close_minus_support_atr=0.2,
                    ofi_proxy_5_norm=-0.1,
                ),
                _with(
                    upper_wick_atr=0.5,
                    close_pos_in_bar=0.3,
                    bar_range_atr=0.8,
                    resistance_minus_close_atr=0.2,
                    ofi_proxy_5_norm=0.1,
                ),
            ]
        )
    )

    assert out["signal_side"].tolist() == [1, -1]
    assert out["signal_mode"].tolist() == [2, 2]
    assert out["qfs_cond_sweep_fade_long"].tolist() == [1, 0]
    assert out["qfs_cond_sweep_fade_short"].tolist() == [0, 1]


def test_quote_flow_scalp_router_vwap_snapback_long_and_short_trigger() -> None:
    out, _ = build_quote_flow_scalp_router_signal(
        _frame(
            [
                _with(
                    close_minus_vwap_20_atr=-1.2,
                    vpin_proxy_50_rank_252=0.6,
                    lower_wick_atr=0.4,
                    close_pos_in_bar=0.6,
                ),
                _with(
                    close_minus_vwap_20_atr=1.2,
                    vpin_proxy_50_rank_252=0.6,
                    upper_wick_atr=0.4,
                    close_pos_in_bar=0.4,
                ),
            ]
        )
    )

    assert out["signal_side"].tolist() == [1, -1]
    assert out["signal_mode"].tolist() == [3, 3]
    assert out["qfs_cond_vwap_snapback_long"].tolist() == [1, 0]
    assert out["qfs_cond_vwap_snapback_short"].tolist() == [0, 1]


def test_quote_flow_scalp_router_priority_prefers_sweep_fade() -> None:
    out, _ = build_quote_flow_scalp_router_signal(
        _frame(
            [
                _with(
                    close_minus_vwap_20_atr=-1.2,
                    vpin_proxy_50_rank_252=0.8,
                    ofi_proxy_5_norm=-0.1,
                    lower_wick_atr=0.5,
                    close_pos_in_bar=0.75,
                    bar_range_atr=0.8,
                    close_minus_support_atr=0.2,
                )
            ]
        )
    )

    assert out["qfs_cond_sweep_fade_long"].tolist() == [1]
    assert out["qfs_cond_vwap_snapback_long"].tolist() == [1]
    assert out["signal_side"].tolist() == [1]
    assert out["signal_mode"].tolist() == [2]


def test_quote_flow_scalp_router_enabled_modes_default_keeps_all_modes() -> None:
    frame = _frame(
        [
            _with(
                vpin_proxy_50_rank_252=0.8,
                ofi_proxy_5_norm=0.3,
                ofi_proxy_15_norm=0.1,
                volume_relative_48=1.2,
                close_pos_in_bar=0.8,
                bar_body_atr=0.2,
            ),
            _with(
                lower_wick_atr=0.5,
                close_pos_in_bar=0.7,
                bar_range_atr=0.8,
                close_minus_support_atr=0.2,
                ofi_proxy_5_norm=-0.1,
            ),
            _with(
                close_minus_vwap_20_atr=-1.2,
                vpin_proxy_50_rank_252=0.6,
                lower_wick_atr=0.4,
                close_pos_in_bar=0.6,
            ),
        ]
    )

    out, meta = build_quote_flow_scalp_router_signal(frame)

    assert meta["enabled_modes"] is None
    assert out["signal_mode"].tolist() == [1, 2, 3]
    assert out["signal_candidate"].tolist() == [1, 1, 1]


def test_quote_flow_scalp_router_enabled_modes_only_mode_1() -> None:
    out, meta = build_quote_flow_scalp_router_signal(
        _frame(
            [
                _with(
                    vpin_proxy_50_rank_252=0.8,
                    ofi_proxy_5_norm=0.3,
                    ofi_proxy_15_norm=0.1,
                    volume_relative_48=1.2,
                    close_pos_in_bar=0.8,
                    bar_body_atr=0.2,
                ),
                _with(
                    lower_wick_atr=0.5,
                    close_pos_in_bar=0.7,
                    bar_range_atr=0.8,
                    close_minus_support_atr=0.2,
                    ofi_proxy_5_norm=-0.1,
                ),
                _with(
                    close_minus_vwap_20_atr=-1.2,
                    vpin_proxy_50_rank_252=0.6,
                    lower_wick_atr=0.4,
                    close_pos_in_bar=0.6,
                ),
            ]
        ),
        enabled_modes=[1],
    )

    assert meta["enabled_modes"] == [1]
    assert out["signal_mode"].tolist() == [1, 0, 0]
    assert out["signal_candidate"].tolist() == [1, 0, 0]


def test_quote_flow_scalp_router_enabled_modes_only_mode_2() -> None:
    out, _ = build_quote_flow_scalp_router_signal(
        _frame(
            [
                _with(
                    vpin_proxy_50_rank_252=0.8,
                    ofi_proxy_5_norm=0.3,
                    ofi_proxy_15_norm=0.1,
                    volume_relative_48=1.2,
                    close_pos_in_bar=0.8,
                    bar_body_atr=0.2,
                ),
                _with(
                    lower_wick_atr=0.5,
                    close_pos_in_bar=0.7,
                    bar_range_atr=0.8,
                    close_minus_support_atr=0.2,
                    ofi_proxy_5_norm=-0.1,
                ),
                _with(
                    close_minus_vwap_20_atr=-1.2,
                    vpin_proxy_50_rank_252=0.6,
                    lower_wick_atr=0.4,
                    close_pos_in_bar=0.6,
                ),
            ]
        ),
        enabled_modes=[2],
    )

    assert out["signal_mode"].tolist() == [0, 2, 0]
    assert out["signal_candidate"].tolist() == [0, 1, 0]


def test_quote_flow_scalp_router_enabled_modes_only_mode_3() -> None:
    out, _ = build_quote_flow_scalp_router_signal(
        _frame(
            [
                _with(
                    vpin_proxy_50_rank_252=0.8,
                    ofi_proxy_5_norm=0.3,
                    ofi_proxy_15_norm=0.1,
                    volume_relative_48=1.2,
                    close_pos_in_bar=0.8,
                    bar_body_atr=0.2,
                ),
                _with(
                    lower_wick_atr=0.5,
                    close_pos_in_bar=0.7,
                    bar_range_atr=0.8,
                    close_minus_support_atr=0.2,
                    ofi_proxy_5_norm=-0.1,
                ),
                _with(
                    close_minus_vwap_20_atr=-1.2,
                    vpin_proxy_50_rank_252=0.6,
                    lower_wick_atr=0.4,
                    close_pos_in_bar=0.6,
                ),
            ]
        ),
        enabled_modes=[3],
    )

    assert out["signal_mode"].tolist() == [0, 0, 3]
    assert out["signal_candidate"].tolist() == [0, 0, 1]


def test_quote_flow_scalp_router_enabled_modes_combined_modes() -> None:
    out, _ = build_quote_flow_scalp_router_signal(
        _frame(
            [
                _with(
                    vpin_proxy_50_rank_252=0.8,
                    ofi_proxy_5_norm=0.3,
                    ofi_proxy_15_norm=0.1,
                    volume_relative_48=1.2,
                    close_pos_in_bar=0.8,
                    bar_body_atr=0.2,
                ),
                _with(
                    lower_wick_atr=0.5,
                    close_pos_in_bar=0.7,
                    bar_range_atr=0.8,
                    close_minus_support_atr=0.2,
                    ofi_proxy_5_norm=-0.1,
                ),
                _with(
                    close_minus_vwap_20_atr=-1.2,
                    vpin_proxy_50_rank_252=0.6,
                    lower_wick_atr=0.4,
                    close_pos_in_bar=0.6,
                ),
            ]
        ),
        enabled_modes=[1, 2],
    )

    assert out["signal_mode"].tolist() == [1, 2, 0]
    assert out["signal_candidate"].tolist() == [1, 1, 0]


def test_quote_flow_scalp_router_enabled_modes_validation() -> None:
    with pytest.raises(ValueError, match="enabled_modes"):
        build_quote_flow_scalp_router_signal(_frame([_base_row()]), enabled_modes=[4])


def test_quote_flow_scalp_router_missing_columns_raise_clear_error() -> None:
    with pytest.raises(KeyError, match="quote_flow_scalp_router"):
        build_quote_flow_scalp_router_signal(_frame([_base_row()]).drop(columns=["ofi_proxy_5_norm"]))


def test_quote_flow_scalp_router_does_not_modify_unrelated_columns_or_input() -> None:
    frame = _frame([_base_row(), _base_row()])
    frame["unrelated"] = [7.0, 8.0]
    before = frame.copy(deep=True)

    out = quote_flow_scalp_router_signal(frame)

    pd.testing.assert_frame_equal(frame, before)
    assert out["unrelated"].tolist() == [7.0, 8.0]
    assert "signal_side" in out.columns


def test_quote_flow_scalp_router_current_bar_logic_is_causal_and_feature_compatible() -> None:
    frame = _frame(
        [
            _with(),
            _with(close_minus_vwap_20_atr=-1.2, vpin_proxy_50_rank_252=0.6, lower_wick_atr=0.4, close_pos_in_bar=0.6),
            _with(),
        ]
    )
    baseline, _ = build_quote_flow_scalp_router_signal(frame)
    changed = frame.copy(deep=True)
    changed.iloc[-1] = _with(
        vpin_proxy_50_rank_252=0.9,
        ofi_proxy_5_norm=0.4,
        ofi_proxy_15_norm=0.2,
        volume_relative_48=1.3,
        close_pos_in_bar=0.9,
        bar_body_atr=0.3,
    )
    changed_out, _ = build_quote_flow_scalp_router_signal(changed)

    compare_cols = ["signal_candidate", "signal_side", "signal_mode", "quote_flow_score"]
    pd.testing.assert_frame_equal(baseline.iloc[:-1][compare_cols], changed_out.iloc[:-1][compare_cols])

    stepped = apply_signal_step(frame, {"kind": "quote_flow_scalp_router"})
    assert "signal_side" in stepped.columns


@pytest.mark.parametrize(
    ("path", "timeframe", "load_path"),
    [
        (
            "config/experiments/scalp/us100_5m_quote_flow_proxy_scalp_meta_v1.yaml",
            "5m",
            "data/raw/dukascopy_5m_clean/us100_5m.csv",
        ),
        (
            "config/experiments/scalp/us100_30m_quote_flow_proxy_scalp_meta_v1.yaml",
            "30m",
            "data/raw/dukascopy_30m_clean/us100_30m.csv",
        ),
    ],
)
def test_us100_quote_flow_scalp_meta_configs_are_asset_specific_and_not_threshold_dead(
    path: str,
    timeframe: str,
    load_path: str,
) -> None:
    cfg = load_experiment_config(path)
    params = cfg["signals"]["params"]
    ev_probability_floor = (
        float(params["stop_barrier_r"]) + float(params["min_expected_value_r"])
    ) / (float(params["profit_barrier_r"]) + float(params["stop_barrier_r"]))

    assert cfg["strategy"]["name"] == f"us100_{timeframe}_quote_flow_proxy_scalp_meta_v1"
    assert cfg["strategy"]["assets"] == ["US100"]
    assert cfg["data"]["symbol"] == "US100"
    assert cfg["data"]["interval"] == timeframe
    assert cfg["data"]["storage"]["dataset_id"] == f"us100_{timeframe}_quote_flow_proxy_scalp_meta_v1"
    assert str(cfg["data"]["storage"]["load_path"]).endswith(load_path)
    assert cfg["signals"]["kind"] == "meta_probability_side"
    assert float(params["threshold"]) <= ev_probability_floor


def test_qfs_diagnostic_yaml_suite_loads_and_preserves_contract() -> None:
    paths = sorted(DIAGNOSTIC_CONFIG_DIR.glob("*.yaml"))
    assert len(paths) == 18

    for path in paths:
        cfg = load_experiment_config(path)
        router_params = next(
            step["params"]
            for step in cfg["features"]
            if step.get("step") == "quote_flow_scalp_router"
        )
        target = cfg["model"]["target"]
        signal_params = cfg["signals"]["params"]

        assert cfg["data"]["symbol"] == "US100"
        assert cfg["data"]["interval"] == "30m"
        assert str(cfg["data"]["storage"]["load_path"]).endswith(
            "data/raw/dukascopy_30m_clean/us100_30m.csv"
        )
        assert cfg["backtest"]["periods_per_year"] == 12096
        assert target["kind"] == "directional_triple_barrier"
        assert target["entry_price_mode"] == "next_open"
        assert target["profit_barrier_r"] == pytest.approx(0.70)
        assert target["stop_barrier_r"] == pytest.approx(0.50)
        assert signal_params["profit_barrier_r"] == pytest.approx(0.70)
        assert signal_params["stop_barrier_r"] == pytest.approx(0.50)
        assert cfg["execution"]["enabled"] is False
        assert cfg["runtime"]["seed"] == 7
        assert cfg["runtime"]["deterministic"] is True
        assert router_params.get("enabled_modes") in (None, [1], [2], [3], [1, 2], [2, 3])
