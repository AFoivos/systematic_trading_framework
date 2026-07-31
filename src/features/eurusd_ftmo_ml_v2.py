from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.features.helpers.registry import NORMALIZATION_HELPERS, TRANSFORM_HELPERS
from src.meta.completed_trade_history import add_completed_trade_history_features

from src.utils.eurusd_ftmo_ml_v2_contract import (
    DIRECTION_INTERACTION_COLUMNS,
    FEATURE_COLUMNS,
    PULLBACK_COMPONENTS,
)

from .eurusd_ftmo_ml_v2_contract import validate_model_matrix


MOMENTUM_HORIZONS = (1, 2, 4, 8, 16, 24, 48, 96, 192)
EMA_SPANS = (8, 16, 32, 48, 96, 192, 384, 768)
RSI_WINDOWS = (7, 14, 28, 56)
VOL_WINDOWS = (8, 16, 48, 96, 192, 384)
RANGE_WINDOWS = (24, 48, 96, 192, 384)


def add_candidate_indicators(market: pd.DataFrame) -> pd.DataFrame:
    """Compose exact candidate indicators from registered feature builders."""
    from src.features.registry import get_feature_fn

    out = market.copy()
    if "atr48" not in out.columns:
        out = get_feature_fn("atr")(
            out,
            high_col="mid_high",
            low_col="mid_low",
            close_col="mid_close",
            window=48,
            method="wilder_ewm",
            atr_col="atr48",
        )
    spans = sorted({192, *(component.ema_span for component in PULLBACK_COMPONENTS)})
    missing_spans = [span for span in spans if f"ema_{span}" not in out.columns]
    if missing_spans:
        out = get_feature_fn("trend")(
            out,
            price_col="mid_close",
            sma_windows=(),
            ema_spans=missing_spans,
            ema_col_template="ema_{span}",
        )
    out["slow_direction"] = np.sign(out["mid_close"] - out["ema_192"]).astype(np.int8)
    for component in PULLBACK_COMPONENTS:
        out[f"z_{component.component_id}"] = (
            (out["mid_close"] - out[f"ema_{component.ema_span}"]) / out["atr48"]
        )
    return out


def _transform(frame: pd.DataFrame, name: str, **params: object) -> pd.DataFrame:
    return TRANSFORM_HELPERS[name](frame, **params)


def _normalize(frame: pd.DataFrame, name: str, **params: object) -> pd.DataFrame:
    return NORMALIZATION_HELPERS[name](frame, **params)


def build_bar_feature_frame(market: pd.DataFrame) -> pd.DataFrame:
    """Build the causal bar-level part of the fixed feature contract.

    YAML declaration::

        features:
          - step: eurusd_ftmo_ml_v2
            params: {}

    Required input columns
    ----------------------
    mid_open, mid_high, mid_low, mid_close, volume, spread_close:
        Validated canonical EURUSD M30 market columns available at each bar.

    Parameters
    ----------
    market:
        Chronologically sorted, UTC-naive market frame. The transformation
        preserves its index and uses only information available at or before t.
    """
    from src.features.registry import get_feature_fn

    out = add_candidate_indicators(market)
    out = _normalize(
        out,
        "returns",
        close_col="mid_close",
        windows=MOMENTUM_HORIZONS,
        log_returns=True,
    )
    out["logret1"] = out["log_return_1"]
    out = get_feature_fn("volatility")(
        out,
        returns_col="logret1",
        rolling_windows=VOL_WINDOWS,
        ewma_spans=(),
        annualization_factor=None,
    )
    for window in VOL_WINDOWS:
        out[f"vol_{window}"] = out[f"vol_rolling_{window}"]

    for horizon in MOMENTUM_HORIZONS:
        out = _transform(
            out,
            "ratio",
            numerator_col=f"log_return_{horizon}",
            denominator_col="vol_48",
            output_col=f"__mom_{horizon}_vol_unscaled",
        )
        out = _transform(
            out,
            "affine",
            source_col=f"__mom_{horizon}_vol_unscaled",
            output_col=f"mom_{horizon}_vol",
            scale=1.0 / math.sqrt(horizon),
        )
        out = _transform(
            out,
            "lag",
            source_col="mid_close",
            output_col=f"__mid_close_lag_{horizon}",
            lag=horizon,
        )
        out = _normalize(
            out,
            "atr_scaled_distance",
            base_col="mid_close",
            ref_col=f"__mid_close_lag_{horizon}",
            atr_col="atr48",
            output_col=f"mom_{horizon}_atr",
        )

    missing_ema = [span for span in EMA_SPANS if f"ema_{span}" not in out.columns]
    if missing_ema:
        out = get_feature_fn("trend")(
            out,
            price_col="mid_close",
            sma_windows=(),
            ema_spans=missing_ema,
            ema_col_template="ema_{span}",
        )
    for span in EMA_SPANS:
        out = _normalize(
            out,
            "atr_scaled_distance",
            base_col="mid_close",
            ref_col=f"ema_{span}",
            atr_col="atr48",
            output_col=f"ema_dist_{span}",
        )
        out = _transform(
            out,
            "difference",
            source_col=f"ema_{span}",
            periods=8,
            output_col=f"__ema_slope_{span}_raw",
        )
        out = _transform(
            out,
            "ratio",
            numerator_col=f"__ema_slope_{span}_raw",
            denominator_col="atr48",
            output_col=f"__ema_slope_{span}_atr",
        )
        out = _transform(
            out,
            "affine",
            source_col=f"__ema_slope_{span}_atr",
            output_col=f"ema_slope_{span}",
            scale=1.0 / math.sqrt(8.0),
        )

    out = get_feature_fn("rsi")(out, price_col="mid_close", windows=RSI_WINDOWS, method="wilder")
    for window in RSI_WINDOWS:
        out = _transform(
            out,
            "affine",
            source_col=f"mid_close_rsi_{window}",
            output_col=f"rsi_{window}",
            scale=1.0 / 25.0,
            offset=-2.0,
        )
    out = _transform(
        out,
        "difference",
        source_col="rsi_7",
        reference_col="rsi_28",
        output_col="rsi_ratio_7_28",
    )

    out = get_feature_fn("adx")(
        out,
        high_col="mid_high",
        low_col="mid_low",
        close_col="mid_close",
        window=14,
    )
    out = _transform(out, "affine", source_col="adx_14", output_col="adx14", scale=1.0 / 50.0)
    out = _transform(
        out,
        "difference",
        source_col="plus_di_14",
        reference_col="minus_di_14",
        output_col="__di_diff_raw",
    )
    out = _transform(out, "affine", source_col="__di_diff_raw", output_col="di_diff", scale=1.0 / 50.0)
    out = _transform(out, "affine", source_col="plus_di_14", output_col="__plus_di_offset", offset=1.0)
    out = _transform(
        out,
        "ratio",
        numerator_col="__plus_di_offset",
        denominator_col="minus_di_14",
        denominator_offset=1.0,
        output_col="__di_ratio",
    )
    out = _transform(out, "log", source_col="__di_ratio", output_col="di_logratio")

    for numerator_window, denominator_window, output in (
        (8, 48, "vol_ratio_8_48"),
        (16, 48, "vol_ratio_16_48"),
        (48, 192, "vol_ratio_48_192"),
        (96, 384, "vol_ratio_96_384"),
    ):
        out = _transform(
            out,
            "ratio",
            numerator_col=f"vol_{numerator_window}",
            denominator_col=f"vol_{denominator_window}",
            output_col=f"__{output}_ratio",
        )
        out = _transform(out, "log", source_col=f"__{output}_ratio", output_col=output)
    out = _transform(
        out,
        "ratio",
        numerator_col="atr48",
        denominator_col="mid_close",
        output_col="__atr_relative",
    )
    out = _transform(
        out,
        "rolling_zscore",
        source_col="__atr_relative",
        output_col="atr_rel_z",
        window=192,
        shift=0,
        ddof=1,
    )

    out["__bar_range"] = out["mid_high"] - out["mid_low"]
    out["__body"] = out["mid_close"] - out["mid_open"]
    out["__close_from_low"] = out["mid_close"] - out["mid_low"]
    out["__upper_wick"] = out["mid_high"] - out[["mid_open", "mid_close"]].max(axis=1)
    out["__lower_wick"] = out[["mid_open", "mid_close"]].min(axis=1) - out["mid_low"]
    for numerator, output in (
        ("__body", "body_range"),
        ("__upper_wick", "upper_wick"),
        ("__lower_wick", "lower_wick"),
    ):
        out = _transform(
            out,
            "ratio",
            numerator_col=numerator,
            denominator_col="__bar_range",
            output_col=output,
            eps=0.0,
        )
    out = _transform(
        out,
        "ratio",
        numerator_col="__close_from_low",
        denominator_col="__bar_range",
        output_col="__close_location_unit",
        eps=0.0,
    )
    out = _transform(
        out,
        "affine",
        source_col="__close_location_unit",
        output_col="close_loc",
        scale=2.0,
        offset=-1.0,
    )
    out = _transform(
        out,
        "ratio",
        numerator_col="__bar_range",
        denominator_col="atr48",
        output_col="range_atr",
        eps=0.0,
    )

    for window in RANGE_WINDOWS:
        unit_col = f"__range_pos_{window}_unit"
        out = _normalize(
            out,
            "range_position",
            value_col="mid_close",
            high_col="mid_high",
            low_col="mid_low",
            window=window,
            output_col=unit_col,
            clip=False,
        )
        out = _transform(
            out,
            "affine",
            source_col=unit_col,
            output_col=f"range_pos_{window}",
            scale=2.0,
            offset=-1.0,
        )
        out[f"__rolling_high_{window}"] = out["mid_high"].rolling(window, min_periods=window).max()
        out[f"__rolling_low_{window}"] = out["mid_low"].rolling(window, min_periods=window).min()
        out = _transform(
            out,
            "lag",
            source_col=f"__rolling_high_{window}",
            output_col=f"__previous_high_{window}",
            lag=1,
        )
        out = _transform(
            out,
            "lag",
            source_col=f"__rolling_low_{window}",
            output_col=f"__previous_low_{window}",
            lag=1,
        )
        out = _normalize(
            out,
            "atr_scaled_distance",
            base_col="mid_close",
            ref_col=f"__previous_high_{window}",
            atr_col="atr48",
            output_col=f"break_hi_{window}",
        )
        out = _normalize(
            out,
            "atr_scaled_distance",
            base_col="mid_close",
            ref_col=f"__previous_low_{window}",
            atr_col="atr48",
            output_col=f"break_lo_{window}",
        )

    for window in (48, 192, 960):
        out = _transform(
            out,
            "rolling_zscore",
            source_col="volume",
            output_col=f"volume_z_{window}",
            window=window,
            shift=0,
            ddof=1,
        )
    out = _transform(
        out,
        "ratio",
        numerator_col="spread_close",
        denominator_col="atr48",
        output_col="spread_atr",
        eps=0.0,
    )
    out = _transform(out, "log", source_col="spread_close", output_col="__log_spread", eps=0.0)
    out = _transform(
        out,
        "rolling_zscore",
        source_col="__log_spread",
        output_col="spread_z",
        window=192,
        shift=0,
        ddof=1,
    )
    out = get_feature_fn("path_efficiency")(
        out,
        price_col="mid_close",
        windows=(24, 48, 96, 192),
        use_log_prices=True,
        output_template="eff_{window}",
        clip=True,
    )
    out = get_feature_fn("rolling_autocorrelation")(
        out,
        source_col="logret1",
        windows=(48, 192),
        lag=1,
        output_template="ac_{window}",
    )

    hour_fraction = out.index.hour + out.index.minute / 60.0
    weekday = out.index.weekday
    out["hour_sin"] = np.sin(2.0 * np.pi * hour_fraction / 24.0)
    out["hour_cos"] = np.cos(2.0 * np.pi * hour_fraction / 24.0)
    out["dow_sin"] = np.sin(2.0 * np.pi * weekday / 5.0)
    out["dow_cos"] = np.cos(2.0 * np.pi * weekday / 5.0)
    out["liquid_london_ny"] = ((hour_fraction >= 6.0) & (hour_fraction <= 18.0)).astype(np.int8)
    return out.replace([np.inf, -np.inf], np.nan)


def build_candidate_feature_frame(
    market: pd.DataFrame,
    candidates: pd.DataFrame,
) -> pd.DataFrame:
    """Sample features at signal close and add strictly completed-trade state."""
    required_candidates = {
        "candidate_id", "signal_timestamp", "exit_timestamp", "direction", "is_session",
        "amplitude", "bars_planned", "net_return",
    }
    missing = sorted(required_candidates.difference(candidates.columns))
    if missing:
        raise KeyError(f"Missing candidate feature columns: {missing}")
    bars = build_bar_feature_frame(market)
    context_columns = {"direction", "is_session", "amplitude", "bars_planned"}
    history_columns = {"past_win20", "past_mean20", "past_mean_all", "past_win_all"}
    interaction_columns = set(DIRECTION_INTERACTION_COLUMNS)
    bar_columns = [
        column for column in FEATURE_COLUMNS
        if column not in context_columns | history_columns | interaction_columns
    ]
    missing_bar = [column for column in bar_columns if column not in bars.columns]
    if missing_bar:
        raise AssertionError(f"Bar feature pipeline did not emit: {missing_bar}")

    signal_times = pd.DatetimeIndex(pd.to_datetime(candidates["signal_timestamp"]))
    absent = signal_times.difference(bars.index)
    if len(absent):
        raise ValueError(f"Candidate signal timestamps are absent from market data: {list(absent[:5])}")
    sampled = bars.loc[list(signal_times), bar_columns].reset_index(drop=True)
    enriched = candidates.reset_index(drop=True).copy()
    for column in bar_columns:
        enriched[column] = sampled[column].to_numpy()
    enriched = add_completed_trade_history_features(
        enriched,
        candidate_time_col="signal_timestamp",
        completion_time_col="exit_timestamp",
        outcome_col="net_return",
        rolling_window=20,
        win_threshold=0.0,
        allow_same_timestamp=False,
    )
    for output_column in DIRECTION_INTERACTION_COLUMNS:
        source_column = output_column.removeprefix("dir_")
        if source_column not in enriched.columns:
            raise AssertionError(f"Direction interaction source is missing: {source_column}")
        enriched = _transform(
            enriched,
            "product",
            left_col="direction",
            right_col=source_column,
            output_col=output_column,
        )
    enriched = enriched.replace([np.inf, -np.inf], np.nan)
    validate_model_matrix(enriched.loc[:, list(FEATURE_COLUMNS)])
    return enriched


def model_matrix(candidate_features: pd.DataFrame) -> pd.DataFrame:
    matrix = candidate_features.loc[:, list(FEATURE_COLUMNS)].copy()
    matrix = matrix.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    return validate_model_matrix(matrix)


__all__ = [
    "add_candidate_indicators",
    "build_bar_feature_frame",
    "build_candidate_feature_frame",
    "model_matrix",
]
