from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd

from .common import compute_gap_diagnostics, prepare_market_data, validate_bar_minutes
from .config import KDSConfig, LMDSConfig, RLVSConfig
from .kds import add_kds_features
from .lmds import add_lmds_features
from .rlvs import add_rlvs_features


QMS_OUTPUT_COLUMNS = (
    "qms_trend",
    "qms_trend_confidence",
    "qms_volatility",
    "qms_volatility_shock",
    "qms_momentum",
    "qms_momentum_quality",
    "qms_trend_momentum_alignment",
    "qms_state_uncertainty",
    "qms_gap_flag",
    "qms_gap_minutes",
    "qms_weekend_gap",
    "qms_unexpected_data_gap",
    "qms_post_gap_age",
    "qms_contiguous_bars",
    "qms_state_reinitialized",
    "qms_opening_gap_return",
)


def add_quant_market_state_features(
    df: pd.DataFrame,
    *,
    preset: str = "balanced",
    kds_config: KDSConfig | Mapping[str, object] | None = None,
    rlvs_config: RLVSConfig | Mapping[str, object] | None = None,
    lmds_config: LMDSConfig | Mapping[str, object] | None = None,
    bar_minutes: float = 1.0,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``quant_market_state`` feature transformation.

    The orchestrator validates market data and computes KDS, RLVS, then LMDS in
    dependency order. Its eight compact outputs are explicit aliases or simple
    composites; the underlying system columns remain available for audit.

    YAML declaration::

        features:
          - step: quant_market_state
            params:
              preset: balanced
              kds_config: null
              rlvs_config: null
              lmds_config: null
              bar_minutes: 1.0
              inplace: false

    Required input columns
    ----------------------
    Preferred:
        Full bid/ask OHLC columns.
    Fallback:
        ``open``, ``high``, ``low``, ``close``.
    Optional:
        ``spread_bps`` and ``tick_volume``.

    Parameters
    ----------
    preset:
        Shared system preset: ``conservative``, ``balanced``, or ``responsive``.
    kds_config:
        Optional transparent KDS overrides.
    rlvs_config:
        Optional transparent RLVS overrides.
    lmds_config:
        Optional transparent LMDS overrides.
    bar_minutes:
        Explicit duration of one input bar in minutes. Defaults to ``1.0`` to
        preserve the historical M1 contract.
    inplace:
        If true, append outputs to the supplied dataframe. Default: ``false``.
    """
    out = df if inplace else df.copy()
    resolved_bar_minutes = validate_bar_minutes(bar_minutes)
    market = prepare_market_data(out)
    gaps = compute_gap_diagnostics(
        out.index,
        expected_bar_minutes=resolved_bar_minutes,
    )
    out = add_kds_features(
        out,
        preset=preset,
        config=kds_config,
        bar_minutes=resolved_bar_minutes,
        inplace=True,
    )
    out = add_rlvs_features(
        out,
        preset=preset,
        config=rlvs_config,
        bar_minutes=resolved_bar_minutes,
        inplace=True,
    )
    out = add_lmds_features(
        out,
        preset=preset,
        config=lmds_config,
        bar_minutes=resolved_bar_minutes,
        inplace=True,
    )

    momentum_quality = np.sqrt(
        (
            out["lmom_efficiency"]
            * ((1.0 + out["lmom_persistence"].abs()) / 2.0)
        ).clip(lower=0.0)
    )
    state_uncertainty = (
        out["ktrend_uncertainty"] + out["rlv_state_uncertainty"]
    ) / 2.0
    values = {
        "qms_trend": out["ktrend_score"],
        "qms_trend_confidence": out["ktrend_confidence"],
        "qms_volatility": out["rlv_sigma"],
        "qms_volatility_shock": out["rlv_shock_z"],
        "qms_momentum": out["lmom_score"],
        "qms_momentum_quality": momentum_quality.clip(lower=0.0, upper=1.0),
        "qms_trend_momentum_alignment": out["lmom_alignment"],
        "qms_state_uncertainty": state_uncertainty.clip(lower=0.0, upper=1.0),
        "qms_gap_flag": gaps.is_gap.astype("float64"),
        "qms_gap_minutes": gaps.missing_minutes,
        "qms_weekend_gap": gaps.is_weekend_gap.astype("float64"),
        "qms_unexpected_data_gap": gaps.unexpected_data_gap.astype("float64"),
        "qms_post_gap_age": gaps.post_gap_age.astype("float64"),
        "qms_contiguous_bars": gaps.contiguous_bars.astype("float64"),
        "qms_state_reinitialized": gaps.is_hard_gap.astype("float64"),
        "qms_opening_gap_return": np.log(market.close / market.close.shift(1)).where(gaps.is_gap),
    }
    for column in QMS_OUTPUT_COLUMNS:
        out[column] = values[column]
    return out


__all__ = ["QMS_OUTPUT_COLUMNS", "add_quant_market_state_features"]
