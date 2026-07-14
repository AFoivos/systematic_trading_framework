from __future__ import annotations

from collections.abc import Mapping, Sequence
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .context import align_latest_context


DEFAULT_CLUSTERS: dict[str, dict[str, object]] = {
    "asia": {"assets": ["NIKKEI225", "AUS200"], "minimum_active_assets": 2, "require_all_assets": True},
    "europe": {
        "assets": ["EU50", "GER40", "FRA40", "UK100"],
        "minimum_active_assets": 3,
        "require_all_assets": False,
    },
    "usa": {"assets": ["SPX500", "US30", "US100"], "minimum_active_assets": 3, "require_all_assets": True},
    "energy": {"assets": ["BRENT", "USOIL"], "minimum_active_assets": 2, "require_all_assets": True},
    "metals": {"assets": ["XAUUSD", "XAGUSD"], "minimum_active_assets": 2, "require_all_assets": True},
}

DEFAULT_SESSIONS: dict[str, dict[str, str]] = {
    "NIKKEI225": {"timezone": "Asia/Tokyo", "open": "09:00", "close": "15:00"},
    "AUS200": {"timezone": "Australia/Sydney", "open": "10:00", "close": "16:00"},
    "EU50": {"timezone": "Europe/Berlin", "open": "09:00", "close": "17:30"},
    "GER40": {"timezone": "Europe/Berlin", "open": "09:00", "close": "17:30"},
    "FRA40": {"timezone": "Europe/Paris", "open": "09:00", "close": "17:30"},
    "UK100": {"timezone": "Europe/London", "open": "08:00", "close": "16:30"},
    "SPX500": {"timezone": "America/New_York", "open": "09:30", "close": "16:00"},
    "US30": {"timezone": "America/New_York", "open": "09:30", "close": "16:00"},
    "US100": {"timezone": "America/New_York", "open": "09:30", "close": "16:00"},
    "BRENT": {"timezone": "Europe/London", "open": "08:00", "close": "18:00"},
    "USOIL": {"timezone": "America/New_York", "open": "09:00", "close": "14:30"},
    "XAUUSD": {"timezone": "America/New_York", "open": "08:20", "close": "13:30"},
    "XAGUSD": {"timezone": "America/New_York", "open": "08:25", "close": "13:25"},
    "ETHUSD": {"timezone": "UTC", "open": "00:00", "close": "24:00"},
    "EURUSD": {"timezone": "UTC", "open": "00:00", "close": "24:00"},
}


def _time_minutes(value: str, *, allow_24: bool = False) -> int:
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        raise ValueError("Session times must be HH:MM strings.")
    try:
        hour, minute = (int(part) for part in value.split(":"))
    except ValueError as exc:
        raise ValueError("Session times must be HH:MM strings.") from exc
    if value == "24:00" and allow_24:
        return 24 * 60
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Session times must be valid HH:MM values.")
    return hour * 60 + minute


def _copy_frames(asset_frames: Mapping[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for asset, frame in sorted(asset_frames.items()):
        if not isinstance(frame, pd.DataFrame) or not isinstance(frame.index, pd.DatetimeIndex):
            raise TypeError("Panel features require DataFrames with DatetimeIndex values.")
        if frame.index.has_duplicates:
            raise ValueError(f"Asset '{asset}' has duplicate timestamps.")
        out[str(asset)] = frame.sort_index().copy()
    return out


def _session_state(
    frame: pd.DataFrame,
    *,
    asset: str,
    session: Mapping[str, object],
    entry_window_bars: int,
    volatility_col: str,
) -> pd.DataFrame:
    """Emit local-time, DST-aware state based solely on actual bars in a frame."""
    if "open" not in frame.columns or "close" not in frame.columns:
        raise KeyError(f"Session state for '{asset}' requires open and close columns.")
    timezone = str(session.get("timezone", "UTC"))
    ZoneInfo(timezone)  # fail with a useful ZoneInfo error before doing any work
    open_minutes = _time_minutes(str(session.get("open", "00:00")))
    close_minutes = _time_minutes(str(session.get("close", "24:00")), allow_24=True)
    if open_minutes == close_minutes:
        raise ValueError(f"Session for '{asset}' has equal open and close times.")
    raw_idx = pd.DatetimeIndex(frame.index)
    utc_idx = raw_idx.tz_localize("UTC") if raw_idx.tz is None else raw_idx.tz_convert("UTC")
    local_idx = utc_idx.tz_convert(timezone)
    minute = local_idx.hour * 60 + local_idx.minute
    if open_minutes < close_minutes:
        in_session = (minute >= open_minutes) & (minute < close_minutes)
        session_date = pd.Series(local_idx.date, index=frame.index)
    else:
        in_session = (minute >= open_minutes) | (minute < close_minutes)
        session_date = pd.Series(local_idx.date, index=frame.index)
        session_date.loc[minute < close_minutes] = (local_idx[minute < close_minutes] - pd.Timedelta(days=1)).date

    out = frame.copy()
    inside = pd.Series(in_session, index=frame.index, dtype=bool)
    session_id = pd.Series(pd.NA, index=frame.index, dtype="object")
    session_id.loc[inside] = [f"{asset}:{value.isoformat()}" for value in session_date.loc[inside]]
    valid_open = pd.to_numeric(out["open"], errors="coerce").where(inside)
    valid_close = pd.to_numeric(out["close"], errors="coerce").where(inside)
    first_open = valid_open.groupby(session_id, dropna=True).transform("first")
    bars_since = valid_open.groupby(session_id, dropna=True).cumcount().astype(float)
    session_return = valid_close / first_open - 1.0
    out["is_in_primary_session"] = inside.astype(bool)
    out["session_id"] = session_id
    out["session_open_price"] = first_open.astype(float)
    out["session_return"] = session_return.replace([np.inf, -np.inf], np.nan).astype(float)
    out["bars_since_session_open"] = bars_since.where(inside).astype(float)
    out["is_primary_session_open_window"] = (
        inside & bars_since.notna() & (bars_since < float(entry_window_bars))
    ).astype(bool)
    vol = pd.to_numeric(out[volatility_col], errors="coerce") if volatility_col in out.columns else pd.Series(np.nan, index=out.index)
    denominator = vol * np.sqrt(bars_since.clip(lower=1.0))
    out["normalized_session_return"] = (
        out["session_return"] / denominator.where(denominator > 0.0)
    ).replace([np.inf, -np.inf], np.nan)
    return out


def _cluster_columns(prefix: str) -> list[str]:
    return [
        f"{prefix}_cluster_impulse_median",
        f"{prefix}_cluster_impulse_mean",
        f"{prefix}_cluster_breadth_signed",
        f"{prefix}_cluster_member_count",
        f"{prefix}_cluster_positive_count",
        f"{prefix}_cluster_negative_count",
        f"{prefix}_cluster_leader_asset",
        f"{prefix}_cluster_leader_impulse",
        f"{prefix}_cluster_laggard_asset",
        f"{prefix}_cluster_laggard_impulse",
        f"{prefix}_cluster_dispersion",
        f"{prefix}_cluster_eligible",
        f"{prefix}_cluster_context_age_bars",
        f"{prefix}_cluster_direction",
    ]


def _choose_cluster_members(values: dict[str, float], *, eligible: bool) -> dict[str, object]:
    valid = [(asset, value) for asset, value in sorted(values.items()) if np.isfinite(value)]
    if not valid:
        return {
            "median": np.nan, "mean": np.nan, "breadth": np.nan, "positive": 0, "negative": 0,
            "leader_asset": pd.NA, "leader_impulse": np.nan, "laggard_asset": pd.NA,
            "laggard_impulse": np.nan, "dispersion": np.nan, "direction": "neutral",
        }
    vector = np.array([value for _, value in valid], dtype=float)
    median = float(np.median(vector))
    direction = "positive" if median > 0.0 else "negative" if median < 0.0 else "neutral"
    result: dict[str, object] = {
        "median": median,
        "mean": float(np.mean(vector)),
        "breadth": float(np.mean(np.sign(vector))),
        "positive": int(np.sum(vector > 0.0)),
        "negative": int(np.sum(vector < 0.0)),
        "leader_asset": pd.NA,
        "leader_impulse": np.nan,
        "laggard_asset": pd.NA,
        "laggard_impulse": np.nan,
        "dispersion": float(np.median(np.abs(vector - median))),
        "direction": direction,
    }
    if not eligible or direction == "neutral":
        return result
    if direction == "positive":
        leader = sorted(valid, key=lambda item: (-item[1], item[0]))[0]
        same_side = [(asset, value) for asset, value in valid if value >= 0.0]
        laggard = sorted(same_side, key=lambda item: (item[1], item[0]))[0] if same_side else None
    else:
        leader = sorted(valid, key=lambda item: (item[1], item[0]))[0]
        same_side = [(asset, value) for asset, value in valid if value <= 0.0]
        laggard = sorted(same_side, key=lambda item: (-item[1], item[0]))[0] if same_side else None
    result["leader_asset"], result["leader_impulse"] = leader
    if laggard is not None:
        result["laggard_asset"], result["laggard_impulse"] = laggard
    return result


def _add_cluster_features(
    frames: dict[str, pd.DataFrame],
    *,
    cluster: str,
    spec: Mapping[str, object],
    impulse_col: str,
    max_age_bars: float,
    interval_minutes: int,
    universe_mode: str,
) -> None:
    members = [str(asset) for asset in list(spec.get("assets", []) or [])]
    if any(asset not in frames for asset in members):
        missing = [asset for asset in members if asset not in frames]
        raise KeyError(f"Cluster '{cluster}' refers to unavailable assets: {missing}")
    minimum = int(spec.get("minimum_active_assets", len(members)))
    require_all = bool(spec.get("require_all_assets", False))
    prefix = str(cluster)
    for target_asset in members:
        target = frames[target_asset]
        contexts: dict[str, pd.DataFrame] = {}
        for member in members:
            if impulse_col not in frames[member].columns:
                raise KeyError(f"Cluster '{cluster}' requires '{impulse_col}' on '{member}'.")
            contexts[member] = align_latest_context(
                frames[member][[impulse_col]], target.index,
                value_columns=[impulse_col], max_age_bars=max_age_bars, interval_minutes=interval_minutes,
            )
        values = pd.DataFrame({asset: ctx[impulse_col] for asset, ctx in contexts.items()}, index=target.index)
        ages = pd.DataFrame({asset: ctx["context_age_bars"] for asset, ctx in contexts.items()}, index=target.index)
        counts = values.notna().sum(axis=1)
        eligible = counts >= minimum
        if require_all:
            eligible &= counts == len(members)
        # Fixed mode deliberately uses only this module's own eligibility period.  It never
        # reaches into optional macro assets or another cluster's history.
        if universe_mode == "fixed" and bool(eligible.any()):
            first, last = eligible[eligible].index[[0, -1]]
            eligible &= (eligible.index >= first) & (eligible.index <= last)
        rows: list[dict[str, object]] = []
        for timestamp in target.index:
            row_values = {asset: float(values.at[timestamp, asset]) for asset in members if pd.notna(values.at[timestamp, asset])}
            row = _choose_cluster_members(row_values, eligible=bool(eligible.at[timestamp]))
            row["member_count"] = int(counts.at[timestamp])
            row["eligible"] = bool(eligible.at[timestamp])
            valid_ages = ages.loc[timestamp, values.loc[timestamp].notna()]
            row["context_age"] = float(valid_ages.max()) if not valid_ages.empty else np.nan
            rows.append(row)
        metrics = pd.DataFrame(rows, index=target.index)
        target[f"{prefix}_cluster_impulse_median"] = metrics["median"].astype(float)
        target[f"{prefix}_cluster_impulse_mean"] = metrics["mean"].astype(float)
        target[f"{prefix}_cluster_breadth_signed"] = metrics["breadth"].astype(float)
        target[f"{prefix}_cluster_member_count"] = metrics["member_count"].astype(float)
        target[f"{prefix}_cluster_positive_count"] = metrics["positive"].astype(float)
        target[f"{prefix}_cluster_negative_count"] = metrics["negative"].astype(float)
        target[f"{prefix}_cluster_leader_asset"] = metrics["leader_asset"].astype("object")
        target[f"{prefix}_cluster_leader_impulse"] = metrics["leader_impulse"].astype(float)
        target[f"{prefix}_cluster_laggard_asset"] = metrics["laggard_asset"].astype("object")
        target[f"{prefix}_cluster_laggard_impulse"] = metrics["laggard_impulse"].astype(float)
        target[f"{prefix}_cluster_dispersion"] = metrics["dispersion"].astype(float)
        target[f"{prefix}_cluster_eligible"] = metrics["eligible"].astype(bool)
        target[f"{prefix}_cluster_context_age_bars"] = metrics["context_age"].astype(float)
        target[f"{prefix}_cluster_direction"] = metrics["direction"].astype("object")


def _add_relay(
    frames: dict[str, pd.DataFrame],
    *,
    source_assets: Sequence[str],
    target_assets: Sequence[str],
    prefix: str,
    minimum_sources: int,
    max_age_bars: float,
    interval_minutes: int,
    universe_mode: str,
) -> None:
    sources = [asset for asset in source_assets if asset in frames]
    for target_asset in target_assets:
        if target_asset not in frames:
            continue
        target = frames[target_asset]
        contexts: dict[str, pd.DataFrame] = {}
        for source_asset in sources:
            source = frames[source_asset]
            source_values = source.loc[source["normalized_session_return"].notna(), ["normalized_session_return"]]
            contexts[source_asset] = align_latest_context(
                source_values, target.index, value_columns=["normalized_session_return"],
                max_age_bars=max_age_bars, interval_minutes=interval_minutes,
            )
        values = pd.DataFrame(
            {asset: context["normalized_session_return"] for asset, context in contexts.items()}, index=target.index
        )
        ages = pd.DataFrame({asset: context["context_age_bars"] for asset, context in contexts.items()}, index=target.index)
        counts = values.notna().sum(axis=1)
        eligible = counts >= int(minimum_sources)
        if universe_mode == "fixed" and bool(eligible.any()):
            first, last = eligible[eligible].index[[0, -1]]
            eligible &= (eligible.index >= first) & (eligible.index <= last)
        target[f"{prefix}_relay_score"] = values.median(axis=1, skipna=True).where(eligible).astype(float)
        target[f"{prefix}_source_count"] = counts.astype(float)
        target[f"{prefix}_context_age_bars"] = ages.max(axis=1, skipna=True).where(counts > 0).astype(float)
        target[f"{prefix}_eligible"] = eligible.astype(bool)


def _add_macro_context(
    frames: dict[str, pd.DataFrame],
    *,
    impulse_col: str,
    max_age_bars: float,
    interval_minutes: int,
) -> None:
    macro_assets = {"eth": "ETHUSD", "gold": "XAUUSD", "brent": "BRENT", "eurusd": "EURUSD"}
    available = {name: asset for name, asset in macro_assets.items() if asset in frames and impulse_col in frames[asset]}
    for target_asset, target in frames.items():
        contexts: dict[str, pd.DataFrame] = {}
        for name, source_asset in available.items():
            contexts[name] = align_latest_context(
                frames[source_asset][[impulse_col]], target.index, value_columns=[impulse_col],
                max_age_bars=max_age_bars, interval_minutes=interval_minutes,
            )
        def value(name: str) -> pd.Series:
            return contexts[name][impulse_col] if name in contexts else pd.Series(np.nan, index=target.index)
        def age(name: str) -> pd.Series:
            return contexts[name]["context_age_bars"] if name in contexts else pd.Series(np.nan, index=target.index)
        eth, gold, brent = value("eth"), value("gold"), value("brent")
        eligible = eth.notna() & gold.notna() & brent.notna()
        score = (np.sign(eth) - np.sign(gold) + np.sign(brent)) / 3.0
        target["macro_score"] = score.where(eligible).astype(float)
        target["macro_context_eligible"] = eligible.astype(bool)
        target["macro_context_age_bars"] = pd.concat([age("eth"), age("gold"), age("brent")], axis=1).max(axis=1).where(eligible)
        target["eurusd_context_impulse"] = value("eurusd").astype(float)


def _add_dynamic_exit_columns(
    frames: dict[str, pd.DataFrame],
    *,
    clusters: Mapping[str, Mapping[str, object]],
    impulse_col: str,
) -> None:
    asset_cluster = {
        asset: cluster
        for cluster, spec in clusters.items()
        for asset in list(spec.get("assets", []) or [])
    }
    for asset, frame in frames.items():
        cluster = asset_cluster.get(asset)
        if cluster is None:
            for column in (
                "relay_convergence_exit", "relay_cluster_failure_exit", "relay_stale_context_exit",
                "relay_dynamic_exit", "relay_dynamic_exit_reason",
            ):
                frame[column] = False if column != "relay_dynamic_exit_reason" else pd.NA
            for suffix in ("long", "short"):
                for base in ("relay_convergence_exit", "relay_cluster_failure_exit", "relay_stale_context_exit", "relay_dynamic_exit"):
                    frame[f"{base}_{suffix}"] = False
            continue
        median = pd.to_numeric(frame[f"{cluster}_cluster_impulse_median"], errors="coerce")
        impulse = pd.to_numeric(frame[impulse_col], errors="coerce")
        convergence = (impulse.sub(median).abs() <= 0.20) & impulse.notna() & median.notna()
        failure_long = (median <= 0.0) | (median.abs() < 0.30)
        failure_short = (median >= 0.0) | (median.abs() < 0.30)
        cluster_stale = ~frame[f"{cluster}_cluster_eligible"].fillna(False).astype(bool)
        relay_prefix = "asia_to_europe" if cluster == "europe" else "europe_to_usa" if cluster == "usa" else None
        relay_stale = (
            ~frame[f"{relay_prefix}_eligible"].fillna(False).astype(bool)
            if relay_prefix and f"{relay_prefix}_eligible" in frame else cluster_stale
        )
        frame["relay_convergence_exit"] = convergence.astype(bool)
        frame["relay_cluster_failure_exit"] = (failure_long | failure_short).astype(bool)
        frame["relay_stale_context_exit"] = relay_stale.astype(bool)
        frame["relay_convergence_exit_long"] = convergence.astype(bool)
        frame["relay_convergence_exit_short"] = convergence.astype(bool)
        frame["relay_cluster_failure_exit_long"] = failure_long.astype(bool)
        frame["relay_cluster_failure_exit_short"] = failure_short.astype(bool)
        frame["relay_stale_context_exit_long"] = relay_stale.astype(bool)
        frame["relay_stale_context_exit_short"] = relay_stale.astype(bool)
        frame["relay_dynamic_exit_long"] = (convergence | failure_long | relay_stale).astype(bool)
        frame["relay_dynamic_exit_short"] = (convergence | failure_short | relay_stale).astype(bool)
        frame["relay_dynamic_exit"] = (frame["relay_dynamic_exit_long"] | frame["relay_dynamic_exit_short"]).astype(bool)
        reason = pd.Series(pd.NA, index=frame.index, dtype="object")
        reason.loc[relay_stale] = "stale_context"
        reason.loc[failure_long | failure_short] = "cluster_failure"
        reason.loc[convergence] = "convergence"
        frame["relay_dynamic_exit_reason"] = reason
        # Module-aware columns stop a stale relay feed from closing an intra-cluster trade.
        for module, stale in (
            ("intra_cluster", cluster_stale),
            ("asia_to_europe", relay_stale if cluster == "europe" else pd.Series(False, index=frame.index)),
            ("europe_to_usa", relay_stale if cluster == "usa" else pd.Series(False, index=frame.index)),
        ):
            for side, failure in (("long", failure_long), ("short", failure_short)):
                frame[f"relay_dynamic_exit_{module}_{side}"] = (convergence | failure | stale).astype(bool)
            module_reason = pd.Series(pd.NA, index=frame.index, dtype="object")
            module_reason.loc[stale] = "stale_context"
            module_reason.loc[failure_long | failure_short] = "cluster_failure"
            module_reason.loc[convergence] = "convergence"
            frame[f"relay_dynamic_exit_reason_{module}"] = module_reason


def global_session_relay_features(
    asset_frames: Mapping[str, pd.DataFrame],
    *,
    clusters: Mapping[str, Mapping[str, object]] | None = None,
    sessions: Mapping[str, Mapping[str, object]] | None = None,
    impulse_col: str = "impulse_12_96",
    volatility_col: str = "vol_rolling_96",
    interval_minutes: int = 30,
    entry_window_bars: int = 4,
    cluster_context_max_age_bars: float = 8.0,
    relay_context_max_age_bars: float = 8.0,
    macro_context_max_age_bars: float = 4.0,
    universe_mode: str = "fixed",
) -> dict[str, pd.DataFrame]:
    """Build causal cross-session cluster, relay, macro, and exit features.

    Every asset keeps its original index.  Cross-asset values are aligned only as temporary
    as-of context and are disabled whenever their elapsed timestamp age exceeds the configured
    limit.
    """
    if universe_mode not in {"fixed", "dynamic"}:
        raise ValueError("universe_mode must be 'fixed' or 'dynamic'.")
    if isinstance(entry_window_bars, bool) or int(entry_window_bars) <= 0:
        raise ValueError("entry_window_bars must be a positive integer.")
    frames = _copy_frames(asset_frames)
    resolved_clusters = {name: dict(spec) for name, spec in (clusters or DEFAULT_CLUSTERS).items()}
    resolved_sessions = {name: dict(spec) for name, spec in DEFAULT_SESSIONS.items()}
    resolved_sessions.update({str(name): dict(spec) for name, spec in dict(sessions or {}).items()})
    for asset, frame in list(frames.items()):
        if asset not in resolved_sessions:
            raise KeyError(f"No research session metadata configured for asset '{asset}'.")
        frames[asset] = _session_state(
            frame, asset=asset, session=resolved_sessions[asset], entry_window_bars=int(entry_window_bars),
            volatility_col=volatility_col,
        )
    for cluster, spec in sorted(resolved_clusters.items()):
        _add_cluster_features(
            frames, cluster=str(cluster), spec=spec, impulse_col=impulse_col,
            max_age_bars=float(cluster_context_max_age_bars), interval_minutes=int(interval_minutes),
            universe_mode=universe_mode,
        )
    _add_relay(
        frames, source_assets=["NIKKEI225", "AUS200"],
        target_assets=list(resolved_clusters.get("europe", {}).get("assets", [])),
        prefix="asia_to_europe", minimum_sources=2, max_age_bars=float(relay_context_max_age_bars),
        interval_minutes=int(interval_minutes), universe_mode=universe_mode,
    )
    _add_relay(
        frames, source_assets=["EU50", "GER40", "FRA40", "UK100"],
        target_assets=list(resolved_clusters.get("usa", {}).get("assets", [])),
        prefix="europe_to_usa", minimum_sources=3, max_age_bars=float(relay_context_max_age_bars),
        interval_minutes=int(interval_minutes), universe_mode=universe_mode,
    )
    _add_macro_context(
        frames, impulse_col=impulse_col, max_age_bars=float(macro_context_max_age_bars),
        interval_minutes=int(interval_minutes),
    )
    _add_dynamic_exit_columns(frames, clusters=resolved_clusters, impulse_col=impulse_col)
    return frames


__all__ = ["DEFAULT_CLUSTERS", "DEFAULT_SESSIONS", "global_session_relay_features"]
