from __future__ import annotations

from numbers import Integral

import numpy as np
import pandas as pd


def add_order_flow_imbalance(
    df: pd.DataFrame,
    buy_volume_col: str | None = "buy_volume",
    sell_volume_col: str | None = "sell_volume",
    bid_price_col: str | None = None,
    ask_price_col: str | None = None,
    bid_size_col: str | None = None,
    ask_size_col: str | None = None,
    window: int = 1,
    normalize: bool = False,
    output_col: str | None = None,
) -> pd.DataFrame:
    """
    Apply the registered ``order_flow_imbalance`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: order_flow_imbalance
            params:
              buy_volume_col: buy_volume
              sell_volume_col: sell_volume
              bid_price_col: null
              ask_price_col: null
              bid_size_col: null
              ask_size_col: null
              window: 1
              normalize: false
              output_col: null
            output_cols:
              - configured by output_col
    
    Required input columns
    ----------------------
    buy_volume_col:
        Input dataframe column configured by ``buy_volume_col``. Default: ``buy_volume``.
    sell_volume_col:
        Input dataframe column configured by ``sell_volume_col``. Default: ``sell_volume``.
    bid_price_col:
        Input dataframe column configured by ``bid_price_col``. Default: ``null``.
    ask_price_col:
        Input dataframe column configured by ``ask_price_col``. Default: ``null``.
    bid_size_col:
        Input dataframe column configured by ``bid_size_col``. Default: ``null``.
    ask_size_col:
        Input dataframe column configured by ``ask_size_col``. Default: ``null``.
    
    Parameters
    ----------
    buy_volume_col:
        Input dataframe column configured by ``buy_volume_col``. Default: ``buy_volume``.
    sell_volume_col:
        Input dataframe column configured by ``sell_volume_col``. Default: ``sell_volume``.
    bid_price_col:
        Input dataframe column configured by ``bid_price_col``. Default: ``null``.
    ask_price_col:
        Input dataframe column configured by ``ask_price_col``. Default: ``null``.
    bid_size_col:
        Input dataframe column configured by ``bid_size_col``. Default: ``null``.
    ask_size_col:
        Input dataframe column configured by ``ask_size_col``. Default: ``null``.
    window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``1``.
    normalize:
        Configuration parameter accepted by this feature. Default: ``false``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
    """
    _validate_positive_int(window, name="window")
    col = _resolve_output_col(output_col, "order_flow_imbalance" if window == 1 else f"order_flow_imbalance_{window}")

    out = df.copy()
    raw, denominator = _resolve_ofi(
        out,
        buy_volume_col=buy_volume_col,
        sell_volume_col=sell_volume_col,
        bid_price_col=bid_price_col,
        ask_price_col=ask_price_col,
        bid_size_col=bid_size_col,
        ask_size_col=ask_size_col,
    )
    if window > 1:
        raw = raw.rolling(window=window, min_periods=window).sum()
        denominator = denominator.rolling(window=window, min_periods=window).sum()
    out[col] = raw / denominator.replace(0.0, np.nan) if normalize else raw
    return out


def _resolve_ofi(
    df: pd.DataFrame,
    *,
    buy_volume_col: str | None,
    sell_volume_col: str | None,
    bid_price_col: str | None,
    ask_price_col: str | None,
    bid_size_col: str | None,
    ask_size_col: str | None,
) -> tuple[pd.Series, pd.Series]:
    if buy_volume_col is not None and sell_volume_col is not None:
        _validate_columns(df, [buy_volume_col, sell_volume_col], feature="order flow imbalance")
        buy = df[buy_volume_col].astype(float)
        sell = df[sell_volume_col].astype(float)
        return buy - sell, buy + sell

    quote_cols = [bid_price_col, ask_price_col, bid_size_col, ask_size_col]
    if all(column is not None for column in quote_cols):
        columns = [str(column) for column in quote_cols]
        _validate_columns(df, columns, feature="order flow imbalance")
        bid_price = df[str(bid_price_col)].astype(float)
        ask_price = df[str(ask_price_col)].astype(float)
        bid_size = df[str(bid_size_col)].astype(float)
        ask_size = df[str(ask_size_col)].astype(float)

        bid_component = pd.Series(0.0, index=df.index, dtype="float64")
        ask_component = pd.Series(0.0, index=df.index, dtype="float64")
        bid_component.loc[bid_price >= bid_price.shift(1)] += bid_size.loc[bid_price >= bid_price.shift(1)]
        bid_component.loc[bid_price <= bid_price.shift(1)] -= bid_size.shift(1).loc[bid_price <= bid_price.shift(1)]
        ask_component.loc[ask_price <= ask_price.shift(1)] -= ask_size.loc[ask_price <= ask_price.shift(1)]
        ask_component.loc[ask_price >= ask_price.shift(1)] += ask_size.shift(1).loc[ask_price >= ask_price.shift(1)]
        raw = (bid_component + ask_component).replace([np.inf, -np.inf], np.nan)
        denominator = (bid_size + ask_size).replace([np.inf, -np.inf], np.nan)
        raw.iloc[0] = np.nan
        return raw, denominator

    raise KeyError(
        "Missing columns for order flow imbalance: provide buy_volume_col and sell_volume_col, "
        "or bid_price_col, ask_price_col, bid_size_col, and ask_size_col."
    )


def _validate_columns(df: pd.DataFrame, columns: list[str], *, feature: str) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for {feature}: {missing}")


def _validate_positive_int(value: int, *, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Integral) or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")


def _resolve_output_col(output_col: str | None, default: str) -> str:
    if output_col is None:
        return default
    if not isinstance(output_col, str) or not output_col.strip():
        raise ValueError("output_col must be a non-empty string.")
    return output_col


__all__ = [
    "add_order_flow_imbalance",
]
