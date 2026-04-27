from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


_INTERNAL_TS_COL = "__orb_timestamp_utc"

DEFAULT_SESSIONS: tuple[dict[str, object], ...] = (
    {
        "name": "london",
        "timezone": "Europe/London",
        "session_open_time": "08:00",
        "opening_range_bars": 2,
        "trade_until_time": "12:00",
    },
    {
        "name": "new_york_xau",
        "timezone": "America/New_York",
        "session_open_time": "08:00",
        "opening_range_bars": 2,
        "trade_until_time": "12:00",
    },
    {
        "name": "new_york_cash",
        "timezone": "America/New_York",
        "session_open_time": "09:30",
        "opening_range_bars": 2,
        "trade_until_time": "12:00",
        "extended_trade_until_time": "15:30",
    },
)

DEFAULT_ASSET_SESSION_MAP: dict[str, list[str]] = {
    "XAUUSD": ["london", "new_york_xau"],
    "US100": ["new_york_cash"],
    "NAS100": ["new_york_cash"],
    "US30": ["new_york_cash"],
    "SPX500": ["new_york_cash"],
    "GER40": ["london"],
    "DAX": ["london"],
}

DEFAULT_ASSET_ALIAS_MAP: dict[str, str] = {
    "NAS100": "US100",
    "DAX": "GER40",
}

ORB_OUTPUT_COLUMNS: tuple[str, ...] = (
    "orb_session_name",
    "orb_range_high",
    "orb_range_low",
    "orb_range_mid",
    "orb_range_width",
    "orb_range_width_atr",
    "orb_breakout_up",
    "orb_breakout_down",
    "orb_candidate",
    "orb_side",
    "orb_breakout_price",
    "bars_since_orb_breakout",
    "orb_close_position_in_range",
    "orb_breakout_strength_atr",
    "orb_breakout_strength_range",
    "orb_pre_breakout_volatility",
    "orb_failed_breakout_recent",
    "orb_active_window",
)


def _parse_clock(value: str, *, field: str) -> time:
    parts = str(value).strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"{field} must use HH:MM format.")
    hour = int(parts[0])
    minute = int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"{field} must use a valid HH:MM clock time.")
    return time(hour=hour, minute=minute)


def _coerce_utc_index(values: pd.Index | pd.Series, *, timezone: str) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(pd.to_datetime(values, errors="raise"))
    if idx.tz is None:
        idx = idx.tz_localize(str(timezone))
    else:
        idx = idx.tz_convert(str(timezone))
    return idx.tz_convert("UTC")


def _input_was_tz_naive(values: pd.Index | pd.Series) -> bool:
    return pd.DatetimeIndex(pd.to_datetime(values, errors="raise")).tz is None


def _restore_timestamp_convention(index: pd.DatetimeIndex, *, tz_naive: bool) -> pd.DatetimeIndex:
    utc_index = index.tz_convert("UTC")
    if tz_naive:
        return utc_index.tz_localize(None)
    return utc_index


def _require_columns(df: pd.DataFrame, columns: Sequence[str]) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for opening_range_breakout features: {missing}")


def _prepare_single_asset_frame(
    df: pd.DataFrame,
    *,
    timestamp_col: str,
    timezone_input: str,
) -> tuple[pd.DataFrame, bool, bool]:
    has_timestamp_col = timestamp_col in df.columns
    time_values: pd.Index | pd.Series = df[timestamp_col] if has_timestamp_col else df.index
    tz_naive = _input_was_tz_naive(time_values)
    utc_index = _coerce_utc_index(time_values, timezone=timezone_input)

    out = df.copy()
    out[_INTERNAL_TS_COL] = utc_index
    out = out.sort_values(_INTERNAL_TS_COL, kind="mergesort")
    out = out.drop_duplicates(subset=[_INTERNAL_TS_COL], keep="last")
    out = out.set_index(_INTERNAL_TS_COL, drop=False)
    out.index.name = _INTERNAL_TS_COL
    return out, has_timestamp_col, tz_naive


def _normalize_sessions(sessions: Sequence[Mapping[str, object]] | None) -> dict[str, dict[str, object]]:
    raw_sessions = list(sessions or DEFAULT_SESSIONS)
    out: dict[str, dict[str, object]] = {}
    for raw in raw_sessions:
        session = dict(raw)
        name = str(session.get("name", "")).strip()
        if not name:
            raise ValueError("Each ORB session must define a non-empty name.")
        if name in out:
            raise ValueError(f"Duplicate ORB session name: {name}")
        for key in ("timezone", "session_open_time", "trade_until_time"):
            if not isinstance(session.get(key), str) or not str(session[key]).strip():
                raise ValueError(f"ORB session '{name}' must define {key}.")
        session["session_open_time"] = _parse_clock(str(session["session_open_time"]), field=f"sessions.{name}.session_open_time")
        session["trade_until_time"] = _parse_clock(str(session["trade_until_time"]), field=f"sessions.{name}.trade_until_time")
        if session.get("extended_trade_until_time") is not None:
            session["extended_trade_until_time"] = _parse_clock(
                str(session["extended_trade_until_time"]),
                field=f"sessions.{name}.extended_trade_until_time",
            )
        bars = int(session.get("opening_range_bars", 2))
        if bars <= 0:
            raise ValueError(f"ORB session '{name}' opening_range_bars must be positive.")
        session["opening_range_bars"] = bars
        out[name] = session
    return out


def _session_end_time(session: Mapping[str, object], *, use_extended_trade_until: bool) -> time:
    if use_extended_trade_until and session.get("extended_trade_until_time") is not None:
        return session["extended_trade_until_time"]  # type: ignore[return-value]
    return session["trade_until_time"]  # type: ignore[return-value]


def _local_boundary(day: date, clock: time, tz_name: str) -> pd.Timestamp:
    return pd.Timestamp(datetime.combine(day, clock), tz=ZoneInfo(tz_name))


def _session_bounds_for_day(
    day: date,
    *,
    open_time: time,
    end_time: time,
    tz_name: str,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    open_dt = _local_boundary(day, open_time, tz_name)
    end_dt = _local_boundary(day, end_time, tz_name)
    if end_dt <= open_dt:
        end_dt = end_dt + pd.Timedelta(days=1)
    return open_dt, end_dt


def _init_orb_columns(index: pd.Index) -> dict[str, pd.Series]:
    return {
        "orb_session_name": pd.Series(pd.NA, index=index, dtype="object"),
        "orb_range_high": pd.Series(np.nan, index=index, dtype=float),
        "orb_range_low": pd.Series(np.nan, index=index, dtype=float),
        "orb_range_mid": pd.Series(np.nan, index=index, dtype=float),
        "orb_range_width": pd.Series(np.nan, index=index, dtype=float),
        "orb_range_width_atr": pd.Series(np.nan, index=index, dtype=float),
        "orb_breakout_up": pd.Series(0.0, index=index, dtype=float),
        "orb_breakout_down": pd.Series(0.0, index=index, dtype=float),
        "orb_candidate": pd.Series(0.0, index=index, dtype=float),
        "orb_side": pd.Series(0.0, index=index, dtype=float),
        "orb_breakout_price": pd.Series(np.nan, index=index, dtype=float),
        "bars_since_orb_breakout": pd.Series(np.nan, index=index, dtype=float),
        "orb_close_position_in_range": pd.Series(np.nan, index=index, dtype=float),
        "orb_breakout_strength_atr": pd.Series(np.nan, index=index, dtype=float),
        "orb_breakout_strength_range": pd.Series(np.nan, index=index, dtype=float),
        "orb_pre_breakout_volatility": pd.Series(np.nan, index=index, dtype=float),
        "orb_failed_breakout_recent": pd.Series(0.0, index=index, dtype=float),
        "orb_active_window": pd.Series(0.0, index=index, dtype=float),
    }


def _finite_positive(value: float) -> bool:
    return bool(np.isfinite(value) and value > 0.0)


def _resolve_asset_sessions(
    *,
    asset: str | None,
    enabled_sessions: Sequence[str],
    asset_session_map: Mapping[str, Sequence[str]] | None,
    asset_alias_map: Mapping[str, str] | None,
) -> list[str]:
    enabled = [str(name) for name in enabled_sessions]
    if not asset:
        return enabled

    raw_map = {
        str(k): [str(item) for item in list(v)]
        for k, v in dict(asset_session_map or DEFAULT_ASSET_SESSION_MAP).items()
    }
    aliases = {str(k): str(v) for k, v in dict(DEFAULT_ASSET_ALIAS_MAP | dict(asset_alias_map or {})).items()}
    asset_key = str(asset)
    canonical_key = aliases.get(asset_key, asset_key)

    configured = raw_map.get(asset_key, raw_map.get(canonical_key))
    if configured is None:
        return enabled
    return [name for name in configured if name in set(enabled)]


def _current_breakout_flags(
    row: pd.Series,
    *,
    range_high: float,
    range_low: float,
    atr_value: float,
    breakout_buffer_atr: float,
    use_close_breakout: bool,
    high_col: str,
    low_col: str,
    close_col: str,
) -> tuple[bool, bool, float, float]:
    buffer_value = float(breakout_buffer_atr) * atr_value if _finite_positive(atr_value) else 0.0
    close_price = float(row[close_col])
    up_probe = close_price if use_close_breakout else float(row[high_col])
    down_probe = close_price if use_close_breakout else float(row[low_col])
    up_distance = up_probe - (range_high + buffer_value)
    down_distance = (range_low - buffer_value) - down_probe
    return up_distance > 0.0, down_distance > 0.0, float(up_distance), float(down_distance)


def _range_filter_passes(
    *,
    range_width_atr: float,
    min_range_atr: float | None,
    max_range_atr: float | None,
) -> bool:
    if not np.isfinite(range_width_atr):
        return False
    if min_range_atr is not None and range_width_atr < float(min_range_atr):
        return False
    if max_range_atr is not None and range_width_atr > float(max_range_atr):
        return False
    return True


def _fill_range_context(
    columns: dict[str, pd.Series],
    *,
    row_index: pd.Index,
    session_name: str,
    range_high: float,
    range_low: float,
    range_width_atr: float,
) -> None:
    range_width = range_high - range_low
    range_mid = (range_high + range_low) / 2.0
    columns["orb_session_name"].loc[row_index] = session_name
    columns["orb_range_high"].loc[row_index] = float(range_high)
    columns["orb_range_low"].loc[row_index] = float(range_low)
    columns["orb_range_mid"].loc[row_index] = float(range_mid)
    columns["orb_range_width"].loc[row_index] = float(range_width)
    columns["orb_range_width_atr"].loc[row_index] = float(range_width_atr)


def _fill_event_window(
    columns: dict[str, pd.Series],
    session_rows: pd.DataFrame,
    *,
    start_pos: int,
    session_name: str,
    side: float,
    range_high: float,
    range_low: float,
    pre_breakout_vol: float,
    post_breakout_active_bars: int,
    high_col: str,
    low_col: str,
    close_col: str,
    atr_col: str,
    breakout_buffer_atr: float,
    use_close_breakout: bool,
) -> None:
    range_width = float(range_high - range_low)
    if not _finite_positive(range_width):
        return

    failed_seen = False
    end_pos = min(len(session_rows), start_pos + int(post_breakout_active_bars))
    for pos in range(start_pos, end_pos):
        idx = session_rows.index[pos]
        row = session_rows.iloc[pos]
        close_price = float(row[close_col])
        atr_value = float(row[atr_col])
        up_now, down_now, _, _ = _current_breakout_flags(
            row,
            range_high=range_high,
            range_low=range_low,
            atr_value=atr_value,
            breakout_buffer_atr=breakout_buffer_atr,
            use_close_breakout=use_close_breakout,
            high_col=high_col,
            low_col=low_col,
            close_col=close_col,
        )
        inside_range = range_low <= close_price <= range_high
        if pos > start_pos and inside_range:
            failed_seen = True

        if side > 0.0:
            boundary_distance = close_price - range_high
            breakout_flag_up = up_now
            breakout_flag_down = False
        else:
            boundary_distance = range_low - close_price
            breakout_flag_up = False
            breakout_flag_down = down_now

        columns["orb_session_name"].loc[idx] = session_name
        columns["orb_breakout_up"].loc[idx] = float(breakout_flag_up)
        columns["orb_breakout_down"].loc[idx] = float(breakout_flag_down)
        columns["orb_candidate"].loc[idx] = 1.0
        columns["orb_side"].loc[idx] = float(side)
        columns["orb_breakout_price"].loc[idx] = close_price
        columns["bars_since_orb_breakout"].loc[idx] = float(pos - start_pos)
        columns["orb_close_position_in_range"].loc[idx] = float((close_price - range_low) / range_width)
        columns["orb_breakout_strength_atr"].loc[idx] = (
            float(boundary_distance / atr_value) if _finite_positive(atr_value) else np.nan
        )
        columns["orb_breakout_strength_range"].loc[idx] = float(boundary_distance / range_width)
        columns["orb_pre_breakout_volatility"].loc[idx] = pre_breakout_vol
        columns["orb_failed_breakout_recent"].loc[idx] = float(failed_seen)
        columns["orb_active_window"].loc[idx] = 1.0


def _apply_session_to_asset(
    frame: pd.DataFrame,
    columns: dict[str, pd.Series],
    *,
    session: Mapping[str, object],
    opening_range_bars_override: int | None,
    min_range_atr: float | None,
    max_range_atr: float | None,
    breakout_buffer_atr: float,
    post_breakout_active_bars: int,
    max_breakouts_per_session: int,
    use_close_breakout: bool,
    allow_reversal_same_session: bool,
    use_extended_trade_until: bool,
    high_col: str,
    low_col: str,
    close_col: str,
    atr_col: str,
    volatility_col: str,
) -> None:
    session_name = str(session["name"])
    tz_name = str(session["timezone"])
    open_time = session["session_open_time"]  # type: ignore[assignment]
    end_time = _session_end_time(session, use_extended_trade_until=use_extended_trade_until)
    range_bars = int(opening_range_bars_override or session.get("opening_range_bars", 2))

    local_index = pd.DatetimeIndex(frame.index).tz_convert(tz_name)
    local_dates = pd.Index(local_index.date).unique()
    local_ts = pd.Series(local_index, index=frame.index)

    for local_day in sorted(local_dates):
        open_dt, end_dt = _session_bounds_for_day(
            local_day,
            open_time=open_time,
            end_time=end_time,
            tz_name=tz_name,
        )
        in_window = (local_ts >= open_dt) & (local_ts <= end_dt)
        window = frame.loc[in_window.to_numpy()]
        if len(window) <= range_bars:
            continue

        opening = window.iloc[:range_bars]
        range_high = float(opening[high_col].max())
        range_low = float(opening[low_col].min())
        range_width = range_high - range_low
        if not _finite_positive(range_width):
            continue

        completion_idx = opening.index[-1]
        completion_atr = float(frame.loc[completion_idx, atr_col])
        range_width_atr = range_width / completion_atr if _finite_positive(completion_atr) else np.nan

        # The opening range is only assigned after the last range bar has closed. Rows inside
        # `opening` intentionally keep NaN/zero ORB outputs so a model cannot see the final
        # range while it is still being formed.
        trade_rows = window.loc[window.index > completion_idx]
        if trade_rows.empty:
            continue
        _fill_range_context(
            columns,
            row_index=trade_rows.index,
            session_name=session_name,
            range_high=range_high,
            range_low=range_low,
            range_width_atr=range_width_atr,
        )

        if not _range_filter_passes(
            range_width_atr=range_width_atr,
            min_range_atr=min_range_atr,
            max_range_atr=max_range_atr,
        ):
            continue

        breakouts_used = 0
        blocked_side = 0.0
        next_detection_pos = 0
        for pos, (_, row) in enumerate(trade_rows.iterrows()):
            if breakouts_used >= int(max_breakouts_per_session):
                break
            if pos < next_detection_pos:
                continue

            atr_value = float(row[atr_col])
            up_breakout, down_breakout, up_distance, down_distance = _current_breakout_flags(
                row,
                range_high=range_high,
                range_low=range_low,
                atr_value=atr_value,
                breakout_buffer_atr=breakout_buffer_atr,
                use_close_breakout=use_close_breakout,
                high_col=high_col,
                low_col=low_col,
                close_col=close_col,
            )
            if allow_reversal_same_session is False and blocked_side != 0.0:
                if (blocked_side > 0.0 and down_breakout) or (blocked_side < 0.0 and up_breakout):
                    continue

            side = 0.0
            if up_breakout and down_breakout:
                side = 1.0 if up_distance >= down_distance else -1.0
            elif up_breakout:
                side = 1.0
            elif down_breakout:
                side = -1.0
            if side == 0.0:
                continue

            pre_vol = (
                float(frame.loc[completion_idx, volatility_col])
                if pos == 0
                else float(trade_rows.iloc[pos - 1][volatility_col])
            )
            _fill_event_window(
                columns,
                trade_rows,
                start_pos=pos,
                session_name=session_name,
                side=side,
                range_high=range_high,
                range_low=range_low,
                pre_breakout_vol=pre_vol,
                post_breakout_active_bars=post_breakout_active_bars,
                high_col=high_col,
                low_col=low_col,
                close_col=close_col,
                atr_col=atr_col,
                breakout_buffer_atr=breakout_buffer_atr,
                use_close_breakout=use_close_breakout,
            )
            breakouts_used += 1
            blocked_side = side
            next_detection_pos = pos + int(post_breakout_active_bars)


def _add_orb_single_asset(
    df: pd.DataFrame,
    *,
    asset: str | None,
    sessions: Sequence[Mapping[str, object]] | None,
    enabled_sessions: Sequence[str] | None,
    asset_session_map: Mapping[str, Sequence[str]] | None,
    asset_alias_map: Mapping[str, str] | None,
    timestamp_col: str,
    timezone_input: str,
    high_col: str,
    low_col: str,
    close_col: str,
    atr_col: str,
    volatility_col: str,
    min_range_atr: float | None,
    max_range_atr: float | None,
    breakout_buffer_atr: float,
    post_breakout_active_bars: int,
    max_breakouts_per_session: int,
    use_close_breakout: bool,
    allow_reversal_same_session: bool,
    opening_range_bars: int | None,
    use_extended_trade_until: bool,
) -> pd.DataFrame:
    _require_columns(df, [high_col, low_col, close_col, atr_col, volatility_col])
    prepared, has_timestamp_col, tz_naive = _prepare_single_asset_frame(
        df,
        timestamp_col=timestamp_col,
        timezone_input=timezone_input,
    )
    for col in (high_col, low_col, close_col, atr_col, volatility_col):
        prepared[col] = pd.to_numeric(prepared[col], errors="coerce")

    session_by_name = _normalize_sessions(sessions)
    active_names = _resolve_asset_sessions(
        asset=asset,
        enabled_sessions=list(enabled_sessions or session_by_name),
        asset_session_map=asset_session_map,
        asset_alias_map=asset_alias_map,
    )
    unknown_sessions = [name for name in active_names if name not in session_by_name]
    if unknown_sessions:
        raise ValueError(f"enabled_sessions refers to unknown ORB sessions: {unknown_sessions}")

    orb_columns = _init_orb_columns(prepared.index)
    for session_name in active_names:
        _apply_session_to_asset(
            prepared,
            orb_columns,
            session=session_by_name[session_name],
            opening_range_bars_override=opening_range_bars,
            min_range_atr=min_range_atr,
            max_range_atr=max_range_atr,
            breakout_buffer_atr=float(breakout_buffer_atr),
            post_breakout_active_bars=int(post_breakout_active_bars),
            max_breakouts_per_session=int(max_breakouts_per_session),
            use_close_breakout=bool(use_close_breakout),
            allow_reversal_same_session=bool(allow_reversal_same_session),
            use_extended_trade_until=bool(use_extended_trade_until),
            high_col=high_col,
            low_col=low_col,
            close_col=close_col,
            atr_col=atr_col,
            volatility_col=volatility_col,
        )

    out = prepared.copy()
    for col in ORB_OUTPUT_COLUMNS:
        out[col] = orb_columns[col].reindex(out.index)

    restored_index = _restore_timestamp_convention(
        pd.DatetimeIndex(out[_INTERNAL_TS_COL]),
        tz_naive=tz_naive,
    )
    out = out.drop(columns=[_INTERNAL_TS_COL])
    if has_timestamp_col:
        out[timestamp_col] = restored_index
        return out.reset_index(drop=True)
    out.index = restored_index
    out.index.name = df.index.name
    return out


def add_opening_range_breakout_features(
    df: pd.DataFrame,
    *,
    sessions: Sequence[Mapping[str, object]] | None = None,
    enabled_sessions: Sequence[str] | None = None,
    asset_session_map: Mapping[str, Sequence[str]] | None = None,
    asset_alias_map: Mapping[str, str] | None = None,
    timestamp_col: str = "timestamp",
    timezone_input: str = "UTC",
    price_col: str = "close",
    open_col: str = "open",
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    atr_col: str = "atr_24",
    volatility_col: str = "vol_rolling_24",
    min_range_atr: float | None = 0.4,
    max_range_atr: float | None = 2.5,
    breakout_buffer_atr: float = 0.10,
    post_breakout_active_bars: int = 3,
    max_breakouts_per_session: int = 1,
    use_close_breakout: bool = True,
    allow_reversal_same_session: bool = False,
    opening_range_bars: int | None = None,
    use_extended_trade_until: bool = False,
    asset_col: str = "asset",
    asset: str | None = None,
) -> pd.DataFrame:
    """
    Add London/New York opening-range breakout candidate features.

    The function converts UTC timestamps to each session's local timezone before comparing
    session times, so DST transitions are handled by the IANA timezone database rather than by
    fixed UTC-hour assumptions.
    """
    _ = price_col, open_col  # Kept for config symmetry with other OHLCV feature steps.
    if int(post_breakout_active_bars) <= 0:
        raise ValueError("post_breakout_active_bars must be positive.")
    if int(max_breakouts_per_session) <= 0:
        raise ValueError("max_breakouts_per_session must be positive.")
    if opening_range_bars is not None and int(opening_range_bars) <= 0:
        raise ValueError("opening_range_bars must be positive when provided.")
    if min_range_atr is not None and float(min_range_atr) < 0.0:
        raise ValueError("min_range_atr must be >= 0 when provided.")
    if max_range_atr is not None and float(max_range_atr) <= 0.0:
        raise ValueError("max_range_atr must be > 0 when provided.")
    if min_range_atr is not None and max_range_atr is not None and float(min_range_atr) > float(max_range_atr):
        raise ValueError("min_range_atr must be <= max_range_atr.")
    if float(breakout_buffer_atr) < 0.0:
        raise ValueError("breakout_buffer_atr must be >= 0.")

    if timestamp_col in df.columns and asset_col in df.columns:
        frames: list[pd.DataFrame] = []
        for asset_name, group in df.groupby(asset_col, sort=True, dropna=False):
            frames.append(
                _add_orb_single_asset(
                    group,
                    asset=str(asset_name),
                    sessions=sessions,
                    enabled_sessions=enabled_sessions,
                    asset_session_map=asset_session_map,
                    asset_alias_map=asset_alias_map,
                    timestamp_col=timestamp_col,
                    timezone_input=timezone_input,
                    high_col=high_col,
                    low_col=low_col,
                    close_col=close_col,
                    atr_col=atr_col,
                    volatility_col=volatility_col,
                    min_range_atr=min_range_atr,
                    max_range_atr=max_range_atr,
                    breakout_buffer_atr=float(breakout_buffer_atr),
                    post_breakout_active_bars=int(post_breakout_active_bars),
                    max_breakouts_per_session=int(max_breakouts_per_session),
                    use_close_breakout=bool(use_close_breakout),
                    allow_reversal_same_session=bool(allow_reversal_same_session),
                    opening_range_bars=int(opening_range_bars) if opening_range_bars is not None else None,
                    use_extended_trade_until=bool(use_extended_trade_until),
                )
            )
        if not frames:
            return df.copy()
        return pd.concat(frames, axis=0, ignore_index=True, sort=False).sort_values(
            [timestamp_col, asset_col],
            kind="mergesort",
        ).reset_index(drop=True)

    return _add_orb_single_asset(
        df,
        asset=asset,
        sessions=sessions,
        enabled_sessions=enabled_sessions,
        asset_session_map=asset_session_map,
        asset_alias_map=asset_alias_map,
        timestamp_col=timestamp_col,
        timezone_input=timezone_input,
        high_col=high_col,
        low_col=low_col,
        close_col=close_col,
        atr_col=atr_col,
        volatility_col=volatility_col,
        min_range_atr=min_range_atr,
        max_range_atr=max_range_atr,
        breakout_buffer_atr=float(breakout_buffer_atr),
        post_breakout_active_bars=int(post_breakout_active_bars),
        max_breakouts_per_session=int(max_breakouts_per_session),
        use_close_breakout=bool(use_close_breakout),
        allow_reversal_same_session=bool(allow_reversal_same_session),
        opening_range_bars=int(opening_range_bars) if opening_range_bars is not None else None,
        use_extended_trade_until=bool(use_extended_trade_until),
    )


__all__ = [
    "DEFAULT_ASSET_SESSION_MAP",
    "DEFAULT_SESSIONS",
    "ORB_OUTPUT_COLUMNS",
    "add_opening_range_breakout_features",
]
