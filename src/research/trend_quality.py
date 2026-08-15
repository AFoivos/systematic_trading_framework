"""Deterministic AR-0003 multi-asset trend-quality research primitives.

The functions in this module operate only on an already validated, STF-owned
long-form panel.  They do not load data, fit a model, create portfolio weights,
or promote research evidence.  Cross-sectional transformations use only rows
observed at the same timestamp.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

import numpy as np
import pandas as pd

from src.research.multi_asset import compute_cross_sectional_diagnostics


class TrendQualityResearchError(ValueError):
    """Raised when the AR-0003 score contract cannot be evaluated safely."""


@dataclass(frozen=True)
class TrendQualityScorePolicy:
    """Frozen, causal policy for the deterministic AR-0003 primary score."""

    momentum_columns: tuple[str, str, str] = (
        "log_return_16",
        "log_return_32",
        "log_return_64",
    )
    path_efficiency_columns: tuple[str, str, str] = (
        "path_efficiency_16",
        "path_efficiency_32",
        "path_efficiency_48",
    )
    volatility_fast_column: str = "realized_volatility_32"
    volatility_slow_column: str = "realized_volatility_192"
    minimum_assets_per_timestamp: int = 5
    minimum_same_direction_horizons: int = 2
    path_efficiency_min_percentile: float = 0.70
    volatility_min_percentile: float = 0.20
    volatility_max_percentile: float = 0.80

    def __post_init__(self) -> None:
        if len(set(self.momentum_columns)) != 3:
            raise TrendQualityResearchError(
                "momentum_columns must contain three unique columns."
            )
        if len(set(self.path_efficiency_columns)) != 3:
            raise TrendQualityResearchError(
                "path_efficiency_columns must contain three unique columns."
            )
        if (
            isinstance(self.minimum_assets_per_timestamp, bool)
            or not isinstance(self.minimum_assets_per_timestamp, int)
            or self.minimum_assets_per_timestamp < 3
        ):
            raise TrendQualityResearchError(
                "minimum_assets_per_timestamp must be an integer >= 3."
            )
        if self.minimum_same_direction_horizons not in {2, 3}:
            raise TrendQualityResearchError(
                "minimum_same_direction_horizons must be 2 or 3."
            )
        percentiles = (
            self.path_efficiency_min_percentile,
            self.volatility_min_percentile,
            self.volatility_max_percentile,
        )
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(float(value))
            or not 0.0 <= float(value) <= 1.0
            for value in percentiles
        ):
            raise TrendQualityResearchError(
                "Regime percentiles must be finite values in [0, 1]."
            )
        if self.volatility_min_percentile >= self.volatility_max_percentile:
            raise TrendQualityResearchError(
                "volatility_min_percentile must be below volatility_max_percentile."
            )


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    values = pd.to_numeric(frame[column], errors="coerce").astype(float)
    return values.replace([np.inf, -np.inf], np.nan)


def _same_timestamp_zscore(
    values: pd.Series,
    timestamps: pd.Series,
    *,
    minimum_assets: int,
) -> pd.Series:
    """Population z-score within each observed timestamp, with no fill."""

    def transform(group: pd.Series) -> pd.Series:
        finite = group.dropna()
        if len(finite) < minimum_assets:
            return pd.Series(np.nan, index=group.index, dtype=float)
        scale = float(finite.std(ddof=0))
        if not isfinite(scale) or scale <= 0.0:
            return pd.Series(np.nan, index=group.index, dtype=float)
        result = pd.Series(np.nan, index=group.index, dtype=float)
        result.loc[finite.index] = (finite - float(finite.mean())) / scale
        return result

    return values.groupby(timestamps, sort=False, group_keys=False).apply(transform)


def _same_timestamp_percentile_rank(
    values: pd.Series,
    timestamps: pd.Series,
    *,
    minimum_assets: int,
) -> pd.Series:
    """Average-tie percentile rank within one contemporaneous cross-section."""

    def transform(group: pd.Series) -> pd.Series:
        finite = group.dropna()
        if len(finite) < minimum_assets:
            return pd.Series(np.nan, index=group.index, dtype=float)
        result = pd.Series(np.nan, index=group.index, dtype=float)
        result.loc[finite.index] = finite.rank(method="average", pct=True)
        return result

    return values.groupby(timestamps, sort=False, group_keys=False).apply(transform)


def build_multi_horizon_trend_quality_score(
    frame: pd.DataFrame,
    *,
    policy: TrendQualityScorePolicy | None = None,
    timestamp_column: str = "timestamp",
    asset_column: str = "asset_id",
    base_eligibility_column: str = "prediction_eligible",
) -> pd.DataFrame:
    """Build the frozen AR-0003 score over an STF-owned long-form panel.

    Inputs must already be causal feature outputs.  The function preserves
    missing values, never densifies the panel, and never reads a later
    timestamp to transform an earlier row.
    """

    resolved = policy or TrendQualityScorePolicy()
    required = {
        timestamp_column,
        asset_column,
        *resolved.momentum_columns,
        *resolved.path_efficiency_columns,
        resolved.volatility_fast_column,
        resolved.volatility_slow_column,
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise TrendQualityResearchError(
            f"AR-0003 panel is missing required columns: {missing}."
        )
    timestamps = pd.to_datetime(frame[timestamp_column], errors="raise")
    if timestamps.dt.tz is None:
        raise TrendQualityResearchError("AR-0003 timestamps must be timezone-aware.")
    identities = pd.DataFrame(
        {timestamp_column: timestamps, asset_column: frame[asset_column]}
    )
    if identities.duplicated([timestamp_column, asset_column]).any():
        raise TrendQualityResearchError(
            "AR-0003 requires unique (timestamp, asset_id) rows."
        )
    expected_order = identities.sort_values(
        [timestamp_column, asset_column], kind="mergesort"
    ).index
    if not expected_order.equals(frame.index):
        raise TrendQualityResearchError(
            "AR-0003 panel must be canonically sorted by timestamp then asset_id."
        )

    out = frame.copy()
    out[timestamp_column] = timestamps
    momentum = [_numeric(out, column) for column in resolved.momentum_columns]
    path_efficiency = [
        _numeric(out, column) for column in resolved.path_efficiency_columns
    ]
    for column, values in zip(resolved.momentum_columns, momentum):
        suffix = column.removeprefix("log_return_")
        out[f"cross_sectional_zscore_log_return_{suffix}"] = (
            _same_timestamp_zscore(
                values,
                timestamps,
                minimum_assets=resolved.minimum_assets_per_timestamp,
            )
        )

    zscore_columns = [
        f"cross_sectional_zscore_log_return_{column.removeprefix('log_return_')}"
        for column in resolved.momentum_columns
    ]
    out["trend_score"] = out[zscore_columns].median(axis=1, skipna=False)
    out["quality_score"] = pd.concat(path_efficiency, axis=1).median(
        axis=1, skipna=False
    )
    out["alpha_score"] = out["trend_score"] * out["quality_score"]

    positive_count = sum(values.gt(0.0).astype("int8") for values in momentum)
    negative_count = sum(values.lt(0.0).astype("int8") for values in momentum)
    agreement_count = pd.concat([positive_count, negative_count], axis=1).max(axis=1)
    out["trend_agreement_count"] = agreement_count.astype("int8")
    out["trend_direction"] = np.select(
        [positive_count.ge(resolved.minimum_same_direction_horizons),
         negative_count.ge(resolved.minimum_same_direction_horizons)],
        [1, -1],
        default=0,
    ).astype("int8")

    fast_volatility = _numeric(out, resolved.volatility_fast_column)
    slow_volatility = _numeric(out, resolved.volatility_slow_column)
    out["volatility_ratio_32_192"] = fast_volatility / slow_volatility.where(
        slow_volatility > 0.0
    )
    out["quality_cross_sectional_percentile"] = _same_timestamp_percentile_rank(
        out["quality_score"],
        timestamps,
        minimum_assets=resolved.minimum_assets_per_timestamp,
    )
    out["volatility_ratio_cross_sectional_percentile"] = (
        _same_timestamp_percentile_rank(
            out["volatility_ratio_32_192"],
            timestamps,
            minimum_assets=resolved.minimum_assets_per_timestamp,
        )
    )
    out["trend_agreement_eligible"] = agreement_count.ge(
        resolved.minimum_same_direction_horizons
    )
    out["path_efficiency_regime_eligible"] = out[
        "quality_cross_sectional_percentile"
    ].ge(resolved.path_efficiency_min_percentile)
    out["volatility_regime_eligible"] = out[
        "volatility_ratio_cross_sectional_percentile"
    ].between(
        resolved.volatility_min_percentile,
        resolved.volatility_max_percentile,
        inclusive="both",
    )

    complete = out[
        [
            "trend_score",
            "quality_score",
            "alpha_score",
            "volatility_ratio_32_192",
            "quality_cross_sectional_percentile",
            "volatility_ratio_cross_sectional_percentile",
        ]
    ].notna().all(axis=1)
    if base_eligibility_column in out.columns:
        base_eligible = out[base_eligibility_column]
        if not pd.api.types.is_bool_dtype(base_eligible.dtype):
            raise TrendQualityResearchError(
                f"{base_eligibility_column} must be boolean when supplied."
            )
    else:
        base_eligible = pd.Series(True, index=out.index, dtype=bool)
    out["ar0003_score_eligible"] = (
        base_eligible
        & complete
        & out["trend_agreement_eligible"]
        & out["path_efficiency_regime_eligible"]
        & out["volatility_regime_eligible"]
    )
    out["ar0003_score_direction"] = np.sign(out["alpha_score"]).fillna(0).astype(
        "int8"
    )
    return out


def evaluate_multi_horizon_trend_quality_score(
    scored_frame: pd.DataFrame,
    *,
    executable_target_column: str,
    minimum_assets_per_timestamp: int = 5,
    quantile_fraction: float = 0.20,
    include_prediction_records: bool = True,
) -> dict[str, Any]:
    """Return prediction diagnostics without portfolio or validation semantics."""

    required = {
        "timestamp",
        "asset_id",
        "alpha_score",
        "ar0003_score_eligible",
        executable_target_column,
    }
    missing = sorted(required.difference(scored_frame.columns))
    if missing:
        raise TrendQualityResearchError(
            f"AR-0003 diagnostics are missing required columns: {missing}."
        )
    eligible = scored_frame.loc[
        scored_frame["ar0003_score_eligible"].astype(bool),
        ["timestamp", "asset_id", "alpha_score", executable_target_column],
    ].copy()
    eligible = eligible.rename(
        columns={"alpha_score": "prediction", executable_target_column: "target"}
    )
    eligible["prediction"] = pd.to_numeric(
        eligible["prediction"], errors="coerce"
    )
    eligible["target"] = pd.to_numeric(eligible["target"], errors="coerce")
    eligible = eligible.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["prediction", "target"]
    )
    diagnostics = compute_cross_sectional_diagnostics(
        eligible,
        minimum_assets_per_timestamp=minimum_assets_per_timestamp,
        quantile_fraction=quantile_fraction,
    )
    prediction_records = (
        [
            {
                "timestamp": pd.Timestamp(row.timestamp).isoformat(),
                "asset_id": str(row.asset_id),
                "prediction": float(row.prediction),
                "target": float(row.target),
                "screening_eligible": True,
                "model_fit_required": False,
                "screening_stage": "DISCOVERY",
            }
            for row in eligible.itertuples(index=False)
        ]
        if include_prediction_records
        else []
    )
    diagnostics.update(
        {
            "eligible_prediction_rows": int(len(eligible)),
            "prediction_records": prediction_records,
            "screening_stage": "DISCOVERY",
            "canonical_validation_required": True,
            "portfolio_interpretation": False,
            "top_bottom_interpretation": (
                "prediction_target_diagnostic_only_not_portfolio_return"
            ),
        }
    )
    return diagnostics


__all__ = [
    "TrendQualityResearchError",
    "TrendQualityScorePolicy",
    "build_multi_horizon_trend_quality_score",
    "evaluate_multi_horizon_trend_quality_score",
]
