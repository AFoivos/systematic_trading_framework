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
