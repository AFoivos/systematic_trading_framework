from __future__ import annotations

import pandas as pd

from src.signals._common import resolve_signal_output_name
from src.signals.forecast_signal import _resolve_activation_filter_mask


_ALLOWED_MODES = {"long_only", "short_only", "long_short"}


def forecast_threshold_mtf_momentum_gate_signal(
    df: pd.DataFrame,
    forecast_col: str = "pred_ret",
    signal_col: str | None = None,
    upper: float = 0.7,
    lower: float = -0.85,
    mode: str = "long_short",
    momentum_1h_col: str = "ret_2",
    momentum_4h_col: str = "ret_8",
    momentum_6h_col: str = "ret_12",
    momentum_12h_col: str = "ret_24",
    require_1h_agreement: bool = True,
    veto_all_higher_timeframes_opposite: bool = True,
    activation_filters: list[dict[str, object]] | None = None,
    inclusive: bool = False,
) -> pd.Series:
    """Gate a forecast-threshold signal with causal 1h/4h/6h/12h momentum.

    Long entries require positive 1h momentum when ``require_1h_agreement`` is true.
    They are rejected when 4h, 6h and 12h momentum are all negative and the higher-
    timeframe veto is enabled. Short entries use the symmetric rules.

    The momentum columns are trailing returns generated from the 30-minute base frame:
    2, 8, 12 and 24 bars respectively. Missing inputs fail closed.

    YAML declaration::

        signals:
          kind: forecast_threshold_mtf_momentum_gate
          params:
            forecast_col: pred_ret
            upper: 0.7
            lower: -0.85
            mode: long_short
            momentum_1h_col: ret_2
            momentum_4h_col: ret_8
            momentum_6h_col: ret_12
            momentum_12h_col: ret_24

    Required input columns
    ----------------------
    forecast_col:
        Causal forecast or OOS prediction consumed by the threshold rule.
    momentum_1h_col, momentum_4h_col, momentum_6h_col, momentum_12h_col:
        Trailing base-frame return columns used by the causal agreement/veto
        gates. Columns referenced by activation filters are also required.

    Parameters
    ----------
    upper, lower:
        Long and short forecast thresholds.
    mode:
        One of ``long_only``, ``short_only`` or ``long_short``.
    require_1h_agreement, veto_all_higher_timeframes_opposite:
        Enable the short-horizon agreement and symmetric higher-timeframe veto.
    activation_filters:
        Optional causal column filters applied before signal activation.
    inclusive:
        Use inclusive threshold comparisons when true.
    signal_col:
        Optional output-column name.
    """
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of {_ALLOWED_MODES}")
    if not isinstance(inclusive, bool):
        raise TypeError("inclusive must be boolean.")

    required = [
        forecast_col,
        momentum_1h_col,
        momentum_4h_col,
        momentum_6h_col,
        momentum_12h_col,
    ]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for MTF momentum gate: {missing}")

    output_col = resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_forecast_mtf_momentum",
    )
    forecast = pd.to_numeric(df[forecast_col], errors="coerce")
    mom_1h = pd.to_numeric(df[momentum_1h_col], errors="coerce")
    mom_4h = pd.to_numeric(df[momentum_4h_col], errors="coerce")
    mom_6h = pd.to_numeric(df[momentum_6h_col], errors="coerce")
    mom_12h = pd.to_numeric(df[momentum_12h_col], errors="coerce")

    valid = forecast.notna() & mom_1h.notna() & mom_4h.notna() & mom_6h.notna() & mom_12h.notna()
    valid &= _resolve_activation_filter_mask(
        df,
        index=df.index,
        activation_filters=activation_filters,
    )

    long_threshold = forecast.ge(float(upper)) if inclusive else forecast.gt(float(upper))
    short_threshold = forecast.le(float(lower)) if inclusive else forecast.lt(float(lower))

    long_allowed = pd.Series(True, index=df.index, dtype=bool)
    short_allowed = pd.Series(True, index=df.index, dtype=bool)
    if require_1h_agreement:
        long_allowed &= mom_1h > 0.0
        short_allowed &= mom_1h < 0.0
    if veto_all_higher_timeframes_opposite:
        long_allowed &= ~((mom_4h < 0.0) & (mom_6h < 0.0) & (mom_12h < 0.0))
        short_allowed &= ~((mom_4h > 0.0) & (mom_6h > 0.0) & (mom_12h > 0.0))

    signal = pd.Series(0.0, index=df.index, name=output_col, dtype=float)
    if mode in {"long_only", "long_short"}:
        signal.loc[valid & long_threshold & long_allowed] = 1.0
    if mode in {"short_only", "long_short"}:
        signal.loc[valid & short_threshold & short_allowed] = -1.0
    return signal


__all__ = ["forecast_threshold_mtf_momentum_gate_signal"]
