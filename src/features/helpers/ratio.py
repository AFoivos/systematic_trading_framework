from __future__ import annotations

import numpy as np
import pandas as pd

from .common import output_column, resolve_configured_column


def compute_ratio(
    numerator: pd.Series,
    denominator: pd.Series,
    *,
    eps: float = 1e-8,
    subtract: float = 0.0,
    denominator_offset: float = 0.0,
) -> pd.Series:
    """
    Compute the ``ratio`` feature helper value.
    
    This feature helper uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        transforms:
          ratio:
            params:
              eps: 1e-08
              subtract: 0.0
              denominator_offset: 0.0
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    eps:
        Configuration parameter accepted by this feature helper. Default: ``1e-08``.
    subtract:
        Configuration parameter accepted by this feature helper. Default: ``0.0``.
    denominator_offset:
        Constant added to the denominator before division.
    """
    if not isinstance(numerator, pd.Series):
        raise TypeError("numerator must be a pandas Series.")
    if not isinstance(denominator, pd.Series):
        raise TypeError("denominator must be a pandas Series.")
    denom = denominator.astype(float) + float(denominator_offset)
    out = numerator.astype(float) / denom.where(denom.abs() > float(eps), np.nan) - float(subtract)
    out.name = numerator.name
    return out.astype("float32")


def add_ratio_transform(
    df: pd.DataFrame,
    *,
    numerator_col: str | None = None,
    numerator_selector: dict[str, object] | None = None,
    denominator_col: str | None = None,
    denominator_selector: dict[str, object] | None = None,
    output_col: str | None = None,
    eps: float = 1e-8,
    subtract: float = 0.0,
    denominator_offset: float = 0.0,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``ratio`` feature helper transformation.
    
    This feature helper uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        transforms:
          ratio:
            params:
              numerator_col: null
              numerator_selector: null
              denominator_col: null
              denominator_selector: null
              output_col: null
              eps: 1e-08
              subtract: 0.0
              denominator_offset: 0.0
              inplace: false
          outputs:
            - configured by output_col
    
    Required input columns
    ----------------------
    numerator_col:
        Input dataframe column configured by ``numerator_col``. Default: ``null``.
    denominator_col:
        Input dataframe column configured by ``denominator_col``. Default: ``null``.
    
    Parameters
    ----------
    numerator_col:
        Input dataframe column configured by ``numerator_col``. Default: ``null``.
    numerator_selector:
        Column selector used when the matching explicit column is not provided. Default: ``null``.
    denominator_col:
        Input dataframe column configured by ``denominator_col``. Default: ``null``.
    denominator_selector:
        Column selector used when the matching explicit column is not provided. Default: ``null``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
    eps:
        Configuration parameter accepted by this feature helper. Default: ``1e-08``.
    subtract:
        Configuration parameter accepted by this feature helper. Default: ``0.0``.
    denominator_offset:
        Constant added to the denominator before division.
    inplace:
        Boolean switch controlling optional feature helper behavior. Default: ``false``.
    """
    out = df if inplace else df.copy()
    cfg = {
        "numerator_col": numerator_col,
        "numerator_selector": numerator_selector,
        "denominator_col": denominator_col,
        "denominator_selector": denominator_selector,
    }
    numerator = resolve_configured_column(
        out,
        cfg,
        col_key="numerator_col",
        selector_key="numerator_selector",
        field_prefix="ratio",
    )
    denominator = resolve_configured_column(
        out,
        cfg,
        col_key="denominator_col",
        selector_key="denominator_selector",
        field_prefix="ratio",
    )
    col = output_column(output_col, default=f"{numerator}_over_{denominator}")
    out[col] = compute_ratio(
        out[numerator],
        out[denominator],
        eps=float(eps),
        subtract=float(subtract),
        denominator_offset=float(denominator_offset),
    )
    return out


__all__ = ["add_ratio_transform", "compute_ratio"]
