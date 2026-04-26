from __future__ import annotations

import pandas as pd
import pytest

from src.models.runtime import infer_feature_columns, resolve_feature_selectors


def test_resolve_feature_selectors_supports_exact_include_exclude_and_strict_count() -> None:
    df = pd.DataFrame(
        {
            "open": [1.0],
            "close": [1.0],
            "shock_strength": [0.2],
            "close_rsi_2": [55.0],
            "close_rsi_14": [52.0],
            "bb_percent_b_24_2.0": [0.6],
            "target_forward_return": [0.01],
        }
    )

    feature_cols = resolve_feature_selectors(
        df,
        {
            "exact": ["shock_strength"],
            "include": [
                {"startswith": "close_rsi_"},
                {"regex": "^bb_percent_b_"},
            ],
            "exclude": [{"exact": "close_rsi_2"}],
            "strict": {"min_count": 3},
        },
    )

    assert feature_cols == ["shock_strength", "close_rsi_14", "bb_percent_b_24_2.0"]


def test_resolve_feature_selectors_fails_fast_when_include_matches_nothing() -> None:
    df = pd.DataFrame({"close": [1.0], "close_rsi_14": [52.0]})

    with pytest.raises(KeyError, match="matched no feature columns"):
        resolve_feature_selectors(df, {"include": [{"startswith": "missing_prefix_"}]})


def test_infer_feature_columns_combines_explicit_cols_and_feature_selectors_without_duplicates() -> None:
    df = pd.DataFrame(
        {
            "close": [1.0],
            "shock_strength": [0.2],
            "close_rsi_14": [52.0],
        }
    )

    feature_cols = infer_feature_columns(
        df,
        explicit_cols=["shock_strength"],
        feature_selectors={"include": [{"startswith": "close_rsi_"}, {"exact": "shock_strength"}]},
    )

    assert feature_cols == ["shock_strength", "close_rsi_14"]


def test_resolve_feature_selectors_supports_profiles_and_family_overrides() -> None:
    df = pd.DataFrame(
        {
            "hour_sin_24": [0.0],
            "session_liquid_fx": [1.0],
            "vol_rolling_24": [0.01],
            "close_over_ema_24": [1.02],
            "close_rsi_14": [55.0],
            "lag_close_logret_1": [0.001],
            "adx_24": [22.0],
            "cross_asset_usd_strength": [0.3],
        }
    )

    feature_cols = resolve_feature_selectors(
        df,
        {
            "profile": "ftmo_fx_intraday_balanced_v1",
            "families": {
                "momentum": False,
                "cross_asset": True,
            },
        },
    )

    assert "close_rsi_14" not in feature_cols
    assert "cross_asset_usd_strength" in feature_cols
    assert feature_cols == [
        "lag_close_logret_1",
        "vol_rolling_24",
        "close_over_ema_24",
        "hour_sin_24",
        "session_liquid_fx",
        "adx_24",
        "cross_asset_usd_strength",
    ]


def test_feature_selector_profile_excludes_target_prediction_and_signal_columns() -> None:
    df = pd.DataFrame(
        {
            "lag_close_logret_1": [0.001],
            "vol_rolling_24": [0.01],
            "target_fwd_24": [0.02],
            "label": [1.0],
            "pred_prob": [0.6],
            "signal_prob_vol_adj": [0.1],
            "tb_event_ret": [0.03],
        }
    )

    feature_cols = resolve_feature_selectors(
        df,
        {
            "profile": "ftmo_fx_intraday_balanced_v1",
        },
    )

    assert feature_cols == ["lag_close_logret_1", "vol_rolling_24"]
