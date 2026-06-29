from __future__ import annotations

import numpy as np
import pandas as pd


def dense_return_forecast_signal(
    df: pd.DataFrame,
    *,
    forecast_col: str = "pred_ret",
    signal_col: str = "expected_net_return",
    expected_net_return_col: str = "expected_net_return",
    estimated_cost_col: str = "estimated_round_trip_cost",
    cost_per_turnover: float = 0.0,
    slippage_per_turnover: float = 0.0,
    cost_round_trip_mult: float = 2.0,
    forecast_is_vol_normalized: bool = False,
    volatility_col: str = "atr_14",
    price_col: str = "close",
    volatility_floor: float = 1e-12,
    signed_cost_adjustment: bool = True,
    clip: float | None = None,
) -> pd.DataFrame:
    """
    Apply the registered ``dense_return_forecast`` signal transformation.
    
    This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        signals:
          kind: dense_return_forecast
          params:
            forecast_col: pred_ret
            signal_col: expected_net_return
            expected_net_return_col: expected_net_return
            estimated_cost_col: estimated_round_trip_cost
            cost_per_turnover: 0.0
            slippage_per_turnover: 0.0
            cost_round_trip_mult: 2.0
            forecast_is_vol_normalized: false
            volatility_col: atr_14
            price_col: close
            volatility_floor: 1e-12
            signed_cost_adjustment: true
            clip: null
            output_cols:
              - expected_net_return
    
    Required input columns
    ----------------------
    forecast_col:
        Input dataframe column configured by ``forecast_col``. Default: ``pred_ret``.
    expected_net_return_col:
        Input dataframe column configured by ``expected_net_return_col``. Default: ``expected_net_return``.
    estimated_cost_col:
        Input dataframe column configured by ``estimated_cost_col``. Default: ``estimated_round_trip_cost``.
    volatility_col:
        Input dataframe column configured by ``volatility_col``. Default: ``atr_14``.
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    forecast_col:
        Input dataframe column configured by ``forecast_col``. Default: ``pred_ret``.
    signal_col:
        Output dataframe column configured by ``signal_col``. Default: ``expected_net_return``.
    expected_net_return_col:
        Input dataframe column configured by ``expected_net_return_col``. Default: ``expected_net_return``.
    estimated_cost_col:
        Input dataframe column configured by ``estimated_cost_col``. Default: ``estimated_round_trip_cost``.
    cost_per_turnover:
        Configuration parameter accepted by this signal. Default: ``0.0``.
    slippage_per_turnover:
        Configuration parameter accepted by this signal. Default: ``0.0``.
    cost_round_trip_mult:
        Configuration parameter accepted by this signal. Default: ``2.0``.
    forecast_is_vol_normalized:
        Configuration parameter accepted by this signal. Default: ``false``.
    volatility_col:
        Input dataframe column configured by ``volatility_col``. Default: ``atr_14``.
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    volatility_floor:
        Configuration parameter accepted by this signal. Default: ``1e-12``.
    signed_cost_adjustment:
        Configuration parameter accepted by this signal. Default: ``true``.
    clip:
        Configuration parameter accepted by this signal. Default: ``null``.
    """
    if forecast_col not in df.columns:
        raise KeyError(f"forecast_col '{forecast_col}' not found in DataFrame")
    if cost_round_trip_mult < 0.0:
        raise ValueError("cost_round_trip_mult must be >= 0.")
    if volatility_floor <= 0.0:
        raise ValueError("volatility_floor must be > 0.")

    out = df.copy()
    forecast = out[forecast_col].astype(float)
    raw_cost = float(cost_round_trip_mult) * (
        float(cost_per_turnover) + float(slippage_per_turnover)
    )
    cost = pd.Series(raw_cost, index=out.index, dtype=float)

    if forecast_is_vol_normalized:
        if volatility_col not in out.columns:
            raise KeyError(f"volatility_col '{volatility_col}' not found in DataFrame")
        if price_col not in out.columns:
            raise KeyError(f"price_col '{price_col}' not found in DataFrame")
        vol_unit = out[volatility_col].astype(float) / out[price_col].astype(float).abs()
        vol_unit = vol_unit.where(np.isfinite(vol_unit) & (vol_unit > volatility_floor))
        cost = cost / vol_unit

    out[estimated_cost_col] = cost.astype(float)
    if signed_cost_adjustment:
        magnitude = forecast.abs() - cost
        expected_net = np.sign(forecast) * magnitude
    else:
        expected_net = forecast - cost

    expected_net = pd.Series(expected_net, index=out.index, dtype=float)
    if clip is not None:
        clip_abs = float(clip)
        if clip_abs <= 0.0:
            raise ValueError("clip must be > 0 when provided.")
        expected_net = expected_net.clip(lower=-clip_abs, upper=clip_abs)

    out[expected_net_return_col] = expected_net.astype(float)
    out[signal_col] = expected_net.astype(float)
    return out


__all__ = ["dense_return_forecast_signal"]
