from __future__ import annotations

import pandas as pd
import pytest

from src.features.opening_range_breakout import add_opening_range_breakout_features


LONDON_SESSION = [
    {
        "name": "london",
        "timezone": "Europe/London",
        "session_open_time": "08:00",
        "opening_range_bars": 2,
        "trade_until_time": "12:00",
    }
]

NY_CASH_SESSION = [
    {
        "name": "new_york_cash",
        "timezone": "America/New_York",
        "session_open_time": "09:30",
        "opening_range_bars": 2,
        "trade_until_time": "12:00",
    }
]


def _frame(times: list[str], *, breakout: str = "up") -> pd.DataFrame:
    idx = pd.DatetimeIndex(pd.to_datetime(times, utc=True))
    close = pd.Series(100.0, index=idx)
    high = pd.Series(100.5, index=idx)
    low = pd.Series(99.5, index=idx)
    open_ = pd.Series(100.0, index=idx)

    if len(idx) >= 3:
        high.iloc[1] = 101.0
        low.iloc[1] = 99.0
        close.iloc[1] = 100.0
        open_.iloc[1] = 100.0
    if len(idx) >= 4:
        if breakout == "up":
            close.iloc[3] = 102.0
            high.iloc[3] = 102.2
            low.iloc[3] = 101.8
            open_.iloc[3] = 101.9
        elif breakout == "down":
            close.iloc[3] = 98.0
            high.iloc[3] = 98.2
            low.iloc[3] = 97.8
            open_.iloc[3] = 98.1
        elif breakout == "none":
            close.iloc[3] = 101.5
            high.iloc[3] = 101.7
            low.iloc[3] = 101.1
            open_.iloc[3] = 101.4
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": 100.0,
            "atr_24": 2.0,
            "vol_rolling_24": 0.01,
        },
        index=idx,
    )


def _apply_london(df: pd.DataFrame, **params) -> pd.DataFrame:
    defaults = {
        "min_range_atr": 0.1,
        "max_range_atr": 5.0,
        "breakout_buffer_atr": 0.0,
        "post_breakout_active_bars": 2,
    }
    defaults.update(params)
    return add_opening_range_breakout_features(
        df,
        sessions=LONDON_SESSION,
        enabled_sessions=["london"],
        asset="GER40",
        **defaults,
    )


def test_orb_london_session_uses_europe_london_local_time_and_dst() -> None:
    summer = _frame(
        [
            "2024-06-03 06:30:00",
            "2024-06-03 07:00:00",
            "2024-06-03 07:30:00",
            "2024-06-03 08:00:00",
            "2024-06-03 08:30:00",
        ]
    )
    winter = _frame(
        [
            "2024-01-03 07:30:00",
            "2024-01-03 08:00:00",
            "2024-01-03 08:30:00",
            "2024-01-03 09:00:00",
            "2024-01-03 09:30:00",
        ]
    )

    summer_out = _apply_london(summer)
    winter_out = _apply_london(winter)

    assert summer_out.loc[pd.Timestamp("2024-06-03 08:00:00", tz="UTC"), "orb_candidate"] == pytest.approx(1.0)
    assert winter_out.loc[pd.Timestamp("2024-01-03 09:00:00", tz="UTC"), "orb_candidate"] == pytest.approx(1.0)


def test_orb_new_york_cash_uses_america_new_york_local_time() -> None:
    df = _frame(
        [
            "2024-06-03 13:00:00",
            "2024-06-03 13:30:00",
            "2024-06-03 14:00:00",
            "2024-06-03 14:30:00",
            "2024-06-03 15:00:00",
        ]
    )

    out = add_opening_range_breakout_features(
        df,
        sessions=NY_CASH_SESSION,
        enabled_sessions=["new_york_cash"],
        asset="US100",
        min_range_atr=0.1,
        max_range_atr=5.0,
        breakout_buffer_atr=0.0,
        post_breakout_active_bars=2,
    )

    assert out.loc[pd.Timestamp("2024-06-03 14:30:00", tz="UTC"), "orb_candidate"] == pytest.approx(1.0)
    assert out.loc[pd.Timestamp("2024-06-03 14:30:00", tz="UTC"), "orb_session_name"] == "new_york_cash"


def test_orb_range_is_unknown_until_opening_range_completes() -> None:
    df = _frame(
        [
            "2024-06-03 06:30:00",
            "2024-06-03 07:00:00",
            "2024-06-03 07:30:00",
            "2024-06-03 08:00:00",
        ]
    )

    out = _apply_london(df)

    assert pd.isna(out.loc[pd.Timestamp("2024-06-03 07:00:00", tz="UTC"), "orb_range_high"])
    assert out.loc[pd.Timestamp("2024-06-03 07:30:00", tz="UTC"), "orb_candidate"] == pytest.approx(0.0)
    assert out.loc[pd.Timestamp("2024-06-03 08:00:00", tz="UTC"), "orb_range_high"] == pytest.approx(101.0)
    assert out.loc[pd.Timestamp("2024-06-03 08:00:00", tz="UTC"), "orb_range_low"] == pytest.approx(99.0)


def test_orb_upside_and_downside_candidates_set_side() -> None:
    times = [
        "2024-06-03 06:30:00",
        "2024-06-03 07:00:00",
        "2024-06-03 07:30:00",
        "2024-06-03 08:00:00",
    ]

    up = _apply_london(_frame(times, breakout="up"))
    down = _apply_london(_frame(times, breakout="down"))

    assert up.loc[pd.Timestamp("2024-06-03 08:00:00", tz="UTC"), "orb_side"] == pytest.approx(1.0)
    assert down.loc[pd.Timestamp("2024-06-03 08:00:00", tz="UTC"), "orb_side"] == pytest.approx(-1.0)


def test_orb_range_filters_and_breakout_buffer_gate_candidates() -> None:
    times = [
        "2024-06-03 06:30:00",
        "2024-06-03 07:00:00",
        "2024-06-03 07:30:00",
        "2024-06-03 08:00:00",
    ]
    df = _frame(times, breakout="up")

    min_filtered = _apply_london(df, min_range_atr=2.0)
    max_filtered = _apply_london(df, max_range_atr=0.5)
    buffered = _apply_london(_frame(times, breakout="none"), breakout_buffer_atr=0.5)

    assert min_filtered["orb_candidate"].sum() == pytest.approx(0.0)
    assert max_filtered["orb_candidate"].sum() == pytest.approx(0.0)
    assert buffered["orb_candidate"].sum() == pytest.approx(0.0)


def test_orb_candidate_expires_after_post_breakout_active_bars() -> None:
    df = _frame(
        [
            "2024-06-03 06:30:00",
            "2024-06-03 07:00:00",
            "2024-06-03 07:30:00",
            "2024-06-03 08:00:00",
            "2024-06-03 08:30:00",
            "2024-06-03 09:00:00",
        ]
    )

    out = _apply_london(df, post_breakout_active_bars=2)

    assert out.loc[pd.Timestamp("2024-06-03 08:00:00", tz="UTC"), "orb_candidate"] == pytest.approx(1.0)
    assert out.loc[pd.Timestamp("2024-06-03 08:30:00", tz="UTC"), "orb_candidate"] == pytest.approx(1.0)
    assert out.loc[pd.Timestamp("2024-06-03 09:00:00", tz="UTC"), "orb_candidate"] == pytest.approx(0.0)
    assert out.loc[pd.Timestamp("2024-06-03 08:30:00", tz="UTC"), "bars_since_orb_breakout"] == pytest.approx(1.0)


def test_orb_max_breakouts_per_session_uses_only_first_breakout() -> None:
    df = _frame(
        [
            "2024-06-03 06:30:00",
            "2024-06-03 07:00:00",
            "2024-06-03 07:30:00",
            "2024-06-03 08:00:00",
            "2024-06-03 08:30:00",
            "2024-06-03 09:00:00",
        ]
    )
    df.loc[pd.Timestamp("2024-06-03 09:00:00", tz="UTC"), "close"] = 98.0
    df.loc[pd.Timestamp("2024-06-03 09:00:00", tz="UTC"), "low"] = 97.8

    out = _apply_london(df, post_breakout_active_bars=1, max_breakouts_per_session=1)

    assert out["orb_candidate"].sum() == pytest.approx(1.0)
    assert out.loc[pd.Timestamp("2024-06-03 09:00:00", tz="UTC"), "orb_side"] == pytest.approx(0.0)


def test_orb_failed_breakout_recent_is_point_in_time() -> None:
    df = _frame(
        [
            "2024-06-03 06:30:00",
            "2024-06-03 07:00:00",
            "2024-06-03 07:30:00",
            "2024-06-03 08:00:00",
            "2024-06-03 08:30:00",
        ]
    )
    df.loc[pd.Timestamp("2024-06-03 08:30:00", tz="UTC"), "close"] = 100.0
    df.loc[pd.Timestamp("2024-06-03 08:30:00", tz="UTC"), "high"] = 100.2
    df.loc[pd.Timestamp("2024-06-03 08:30:00", tz="UTC"), "low"] = 99.8

    out = _apply_london(df, post_breakout_active_bars=2)

    assert out.loc[pd.Timestamp("2024-06-03 08:00:00", tz="UTC"), "orb_failed_breakout_recent"] == pytest.approx(0.0)
    assert out.loc[pd.Timestamp("2024-06-03 08:30:00", tz="UTC"), "orb_failed_breakout_recent"] == pytest.approx(1.0)


def test_orb_asset_specific_session_mapping_supports_initial_universe() -> None:
    london = _frame(
        [
            "2024-06-03 06:30:00",
            "2024-06-03 07:00:00",
            "2024-06-03 07:30:00",
            "2024-06-03 08:00:00",
        ]
    )
    ny = _frame(
        [
            "2024-06-03 13:00:00",
            "2024-06-03 13:30:00",
            "2024-06-03 14:00:00",
            "2024-06-03 14:30:00",
        ]
    )
    frames = []
    for asset, base in {
        "XAUUSD": london,
        "GER40": london,
        "US100": ny,
        "US30": ny,
        "SPX500": ny,
    }.items():
        frames.append(base.assign(timestamp=base.index, asset=asset).reset_index(drop=True))
    long = pd.concat(frames, ignore_index=True)

    out = add_opening_range_breakout_features(long, min_range_atr=0.1, max_range_atr=5.0, breakout_buffer_atr=0.0)

    by_asset = out.loc[out["orb_candidate"] == 1.0].groupby("asset")["orb_session_name"].first().to_dict()
    assert by_asset["XAUUSD"] == "london"
    assert by_asset["GER40"] == "london"
    assert by_asset["US100"] == "new_york_cash"
    assert by_asset["US30"] == "new_york_cash"
    assert by_asset["SPX500"] == "new_york_cash"
