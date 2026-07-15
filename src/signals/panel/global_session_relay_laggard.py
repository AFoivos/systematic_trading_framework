from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from src.features.panel.global_session_relay import DEFAULT_CLUSTERS

GLOBAL_SESSION_RELAY_ENABLED_MODULES = frozenset(
    {
        "intra_asia",
        "intra_europe",
        "intra_usa",
        "intra_energy",
        "intra_metals",
        "asia_to_europe_relay",
        "europe_to_usa_relay",
    }
)


def _enabled(enabled_modules: Mapping[str, object], name: str) -> bool:
    return bool(enabled_modules.get(name, False))


def _finite(value: object) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def _valid_next_open(frame: pd.DataFrame, position: int) -> bool:
    if position >= len(frame) - 1 or "open" not in frame.columns:
        return False
    return _finite(frame["open"].iloc[position + 1])


def _cluster_candidate(
    row: pd.Series,
    *,
    asset: str,
    cluster: str,
    two_member_cluster: bool,
) -> tuple[float, str | None]:
    prefix = f"{cluster}_cluster"
    required = {
        "eligible": f"{prefix}_eligible",
        "median": f"{prefix}_impulse_median",
        "breadth": f"{prefix}_breadth_signed",
        "leader": f"{prefix}_leader_impulse",
        "laggard": f"{prefix}_laggard_asset",
        "laggard_impulse": f"{prefix}_laggard_impulse",
        "member_count": f"{prefix}_member_count",
        "positive_count": f"{prefix}_positive_count",
        "negative_count": f"{prefix}_negative_count",
    }
    if any(column not in row.index for column in required.values()):
        return 0.0, "cluster_ineligible"
    if not bool(row[required["eligible"]]):
        return 0.0, "cluster_ineligible"
    median = row[required["median"]]
    breadth = row[required["breadth"]]
    leader = row[required["leader"]]
    laggard = row[required["laggard"]]
    laggard_impulse = row[required["laggard_impulse"]]
    member_count = row[required["member_count"]]
    if not all(_finite(value) for value in (median, breadth, leader, laggard_impulse, member_count)):
        return 0.0, "insufficient_members"
    if str(laggard) != asset:
        return 0.0, "target_not_laggard"
    if float(median) > 0.0:
        if float(median) < 0.80:
            return 0.0, "cluster_threshold"
        if float(breadth) < 0.75:
            return 0.0, "breadth_threshold"
        if float(leader) < 1.25:
            return 0.0, "leader_threshold"
        if not 0.0 <= float(laggard_impulse) <= 0.45:
            return 0.0, "laggard_threshold"
        if two_member_cluster and int(row[required["positive_count"]]) != int(member_count):
            return 0.0, "no_same_side_laggard"
        return 1.0, None
    if float(median) < 0.0:
        if float(median) > -0.80:
            return 0.0, "cluster_threshold"
        if float(breadth) > -0.75:
            return 0.0, "breadth_threshold"
        if float(leader) > -1.25:
            return 0.0, "leader_threshold"
        if not -0.45 <= float(laggard_impulse) <= 0.0:
            return 0.0, "laggard_threshold"
        if two_member_cluster and int(row[required["negative_count"]]) != int(member_count):
            return 0.0, "no_same_side_laggard"
        return -1.0, None
    return 0.0, "cluster_threshold"


def _relay_candidate(
    row: pd.Series,
    *,
    asset: str,
    cluster: str,
    prefix: str,
) -> tuple[float, str | None]:
    relay_eligible = f"{prefix}_eligible"
    relay_score = f"{prefix}_relay_score"
    if relay_eligible not in row.index or not bool(row[relay_eligible]):
        return 0.0, "relay_ineligible"
    if not _finite(row.get(relay_score)):
        return 0.0, "stale_context"
    if "is_primary_session_open_window" not in row.index or not bool(row["is_primary_session_open_window"]):
        return 0.0, "outside_entry_window"
    base = f"{cluster}_cluster"
    for column in (f"{base}_eligible", f"{base}_breadth_signed", f"{base}_laggard_asset", f"{base}_laggard_impulse"):
        if column not in row.index:
            return 0.0, "cluster_ineligible"
    if not bool(row[f"{base}_eligible"]):
        return 0.0, "cluster_ineligible"
    score = float(row[relay_score])
    breadth = row[f"{base}_breadth_signed"]
    laggard = row[f"{base}_laggard_asset"]
    laggard_impulse = row[f"{base}_laggard_impulse"]
    if not _finite(breadth) or not _finite(laggard_impulse):
        return 0.0, "insufficient_members"
    if str(laggard) != asset:
        return 0.0, "target_not_laggard"
    required_breadth = 0.50 if cluster == "europe" else 0.333333
    if score >= 0.80:
        if float(breadth) < required_breadth:
            return 0.0, "breadth_threshold"
        if not 0.0 <= float(laggard_impulse) <= 0.50:
            return 0.0, "laggard_threshold"
        return 1.0, None
    if score <= -0.80:
        if float(breadth) > -required_breadth:
            return 0.0, "breadth_threshold"
        if not -0.50 <= float(laggard_impulse) <= 0.0:
            return 0.0, "laggard_threshold"
        return -1.0, None
    return 0.0, "relay_ineligible"


def global_session_relay_laggard_signal(
    asset_frames: dict[str, pd.DataFrame],
    *,
    clusters: Mapping[str, Mapping[str, object]] | None = None,
    enabled_modules: Mapping[str, object] | None = None,
    context_only_assets: tuple[str, ...] | list[str] = ("ETHUSD", "EURUSD"),
    impulse_col: str = "impulse_12_96",
    atr_col: str = "atr_20",
    volatility_col: str = "vol_rolling_96",
    macro_veto: Mapping[str, object] | None = None,
    signal_col: str = "signal_global_session_relay",
) -> dict[str, pd.DataFrame]:
    """Emit one deterministic laggard/relay signal per native asset bar.

    The function is intentionally panel-wide because leader and laggard identity can only be
    determined after all native frames have supplied causal, fresh context.
    """
    resolved_clusters = {name: dict(spec) for name, spec in (clusters or DEFAULT_CLUSTERS).items()}
    asset_cluster = {
        str(asset): str(cluster)
        for cluster, spec in resolved_clusters.items()
        for asset in list(spec.get("assets", []) or [])
    }
    modules = (
        {name: True for name in GLOBAL_SESSION_RELAY_ENABLED_MODULES}
        if enabled_modules is None
        else dict(enabled_modules)
    )
    veto = dict(macro_veto or {})
    veto_enabled = bool(veto.get("enabled", False))
    context_only = {str(asset) for asset in context_only_assets}
    out: dict[str, pd.DataFrame] = {}
    for asset, source in sorted(asset_frames.items()):
        frame = source.copy()
        signal = pd.Series(0.0, index=frame.index, dtype=float)
        signal_module = pd.Series("none", index=frame.index, dtype="object")
        strength = pd.Series(0.0, index=frame.index, dtype=float)
        eligible = pd.Series(False, index=frame.index, dtype=bool)
        evaluated = pd.Series(False, index=frame.index, dtype=bool)
        candidate = pd.Series(False, index=frame.index, dtype=bool)
        rejection = pd.Series(pd.NA, index=frame.index, dtype="object")
        entry_cluster = pd.Series(asset_cluster.get(asset, "macro"), index=frame.index, dtype="object")
        direction = pd.Series("neutral", index=frame.index, dtype="object")
        cluster_impulse = pd.to_numeric(frame[impulse_col], errors="coerce") if impulse_col in frame else pd.Series(np.nan, index=frame.index)
        gap = pd.Series(np.nan, index=frame.index, dtype=float)
        relay_score = pd.Series(np.nan, index=frame.index, dtype=float)
        entry_context_age = pd.Series(np.nan, index=frame.index, dtype=float)
        entry_macro_context_age = pd.to_numeric(frame.get("macro_context_age_bars"), errors="coerce")
        macro_score = pd.to_numeric(frame.get("macro_score"), errors="coerce")
        if asset in context_only:
            rejection[:] = "context_only_asset"
        elif asset not in asset_cluster:
            rejection[:] = "cluster_ineligible"
        else:
            cluster = asset_cluster[asset]
            base = f"{cluster}_cluster"
            if f"{base}_impulse_median" in frame:
                median = pd.to_numeric(frame[f"{base}_impulse_median"], errors="coerce")
                direction.loc[median > 0.0] = "positive"
                direction.loc[median < 0.0] = "negative"
                gap = (median - cluster_impulse).abs()
            for pos, (timestamp, row) in enumerate(frame.iterrows()):
                base_reason: str | None = None
                candidates: list[tuple[str, float, float | None]] = []
                if cluster == "usa" and _enabled(modules, "europe_to_usa_relay"):
                    evaluated.at[timestamp] = True
                    side, reason = _relay_candidate(row, asset=asset, cluster=cluster, prefix="europe_to_usa")
                    if side:
                        candidates.append(("europe_to_usa_relay", side, float(row["europe_to_usa_relay_score"])))
                    else:
                        base_reason = reason
                if cluster == "europe" and _enabled(modules, "asia_to_europe_relay"):
                    evaluated.at[timestamp] = True
                    side, reason = _relay_candidate(row, asset=asset, cluster=cluster, prefix="asia_to_europe")
                    if side:
                        candidates.append(("asia_to_europe_relay", side, float(row["asia_to_europe_relay_score"])))
                    elif base_reason is None:
                        base_reason = reason
                intra_name = f"intra_{cluster}"
                if _enabled(modules, intra_name):
                    evaluated.at[timestamp] = True
                    side, reason = _cluster_candidate(
                        row, asset=asset, cluster=cluster, two_member_cluster=cluster in {"energy", "metals"}
                    )
                    if side:
                        candidates.append(("intra_cluster", side, None))
                    elif base_reason is None:
                        base_reason = reason
                if candidates:
                    candidate.at[timestamp] = True
                chosen = next(
                    (candidate for priority in ("europe_to_usa_relay", "asia_to_europe_relay", "intra_cluster")
                     for candidate in candidates if candidate[0] == priority),
                    None,
                )
                if chosen is None:
                    rejection.at[timestamp] = base_reason or "module_disabled"
                    continue
                module, side, score = chosen
                if impulse_col not in row.index or not _finite(row.get(impulse_col)):
                    rejection.at[timestamp] = "missing_impulse"
                    continue
                if atr_col not in row.index or not _finite(row.get(atr_col)) or float(row[atr_col]) <= 0.0:
                    rejection.at[timestamp] = "missing_atr"
                    continue
                if volatility_col not in row.index or not _finite(row.get(volatility_col)) or float(row[volatility_col]) <= 0.0:
                    rejection.at[timestamp] = "missing_volatility"
                    continue
                if not _valid_next_open(frame, pos):
                    rejection.at[timestamp] = "missing_next_open"
                    continue
                equity_index = cluster in {"asia", "europe", "usa"}
                if veto_enabled and equity_index:
                    if not bool(row.get("macro_context_eligible", False)) or not _finite(row.get("macro_score")):
                        rejection.at[timestamp] = "macro_veto"
                        continue
                    if (side > 0.0 and float(row["macro_score"]) < 0.0) or (side < 0.0 and float(row["macro_score"]) > 0.0):
                        rejection.at[timestamp] = "macro_veto"
                        continue
                signal.at[timestamp] = float(side)
                signal_module.at[timestamp] = module
                strength.at[timestamp] = abs(float(score)) if score is not None else abs(float(row[f"{base}_impulse_median"]))
                relay_score.at[timestamp] = float(score) if score is not None else np.nan
                eligible.at[timestamp] = True
                if module == "intra_cluster":
                    context_col = f"{cluster}_cluster_context_age_bars"
                elif module == "asia_to_europe_relay":
                    context_col = "asia_to_europe_context_age_bars"
                else:
                    context_col = "europe_to_usa_context_age_bars"
                entry_context_age.at[timestamp] = pd.to_numeric(row.get(context_col), errors="coerce")
                rejection.at[timestamp] = pd.NA
        frame[signal_col] = signal
        frame["signal_module"] = signal_module
        frame["signal_strength"] = strength
        frame["entry_eligible"] = eligible
        frame["entry_evaluated"] = evaluated
        frame["entry_rejection_reason"] = rejection
        frame["entry_cluster"] = entry_cluster
        frame["entry_cluster_direction"] = direction
        frame["entry_cluster_impulse"] = cluster_impulse.astype(float)
        frame["entry_laggard_gap"] = gap
        frame["entry_relay_score"] = relay_score
        frame["entry_macro_score"] = macro_score.astype(float)
        frame["entry_candidate"] = candidate
        frame["entry_context_age_bars"] = entry_context_age
        frame["entry_macro_context_age_bars"] = entry_macro_context_age
        out[asset] = frame
    return out


__all__ = ["GLOBAL_SESSION_RELAY_ENABLED_MODULES", "global_session_relay_laggard_signal"]
