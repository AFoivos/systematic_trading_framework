from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

BASIS_POINTS_PER_UNIT = 10_000.0


class QuoteContractError(ValueError):
    """Raised when bid/ask data violates the canonical quote-unit contract."""


class SpreadSemantics(str, Enum):
    """Classification of an existing column named ``spread_bps``."""

    CANONICAL_BPS = "CANONICAL_BPS"
    LEGACY_FRACTION = "LEGACY_FRACTION"
    INCONSISTENT = "INCONSISTENT"
    INSUFFICIENT_COLUMNS = "INSUFFICIENT_COLUMNS"


@dataclass(frozen=True)
class QuoteColumnNames:
    """Column mapping for one synchronous bid/ask observation."""

    bid: str = "bid"
    ask: str = "ask"
    mid: str = "mid"
    spread_absolute: str = "spread_absolute"
    spread_fraction: str = "spread_fraction"
    spread_bps: str = "spread_bps"


CANONICAL_QUOTE_UNITS: dict[str, str] = {
    "bid": "price",
    "ask": "price",
    "mid": "price",
    "spread_absolute": "price",
    "spread_fraction": "fraction",
    "spread_bps": "basis_points",
}


def _numeric_series(
    value: pd.Series | np.ndarray | list[float], *, name: str
) -> pd.Series:
    series = value if isinstance(value, pd.Series) else pd.Series(value)
    numeric = pd.to_numeric(series, errors="coerce").astype(float)
    if numeric.isna().any() or not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise QuoteContractError(f"{name} must contain only finite numeric values.")
    return numeric


def compute_quote_metrics(
    bid: pd.Series | np.ndarray | list[float],
    ask: pd.Series | np.ndarray | list[float],
    *,
    mid: pd.Series | np.ndarray | list[float] | None = None,
    require_midpoint: bool = True,
    require_geometry: bool = True,
    rtol: float = 1e-10,
    atol: float = 1e-12,
) -> pd.DataFrame:
    """Compute the only canonical spread representations used by research data.

    ``spread_absolute = ask - bid``
    ``spread_fraction = spread_absolute / mid``
    ``spread_bps = 10_000 * spread_fraction``

    When ``mid`` is supplied it is required to equal the arithmetic midpoint by
    default. Diagnostic migrations may set ``require_geometry=False`` to expose
    crossed quotes in a quality report, but such output is not research eligible.
    """

    bid_series = _numeric_series(bid, name="bid")
    ask_series = _numeric_series(ask, name="ask")
    if not bid_series.index.equals(ask_series.index):
        raise QuoteContractError("bid and ask indices must be identical.")

    arithmetic_mid = (bid_series + ask_series) / 2.0
    if mid is None:
        mid_series = arithmetic_mid
    else:
        mid_series = _numeric_series(mid, name="mid")
        if not bid_series.index.equals(mid_series.index):
            raise QuoteContractError("bid, ask, and mid indices must be identical.")
        if require_midpoint and not np.allclose(
            mid_series.to_numpy(dtype=float),
            arithmetic_mid.to_numpy(dtype=float),
            rtol=rtol,
            atol=atol,
            equal_nan=False,
        ):
            raise QuoteContractError(
                "mid must equal (bid + ask) / 2 under the canonical contract."
            )

    spread_absolute = ask_series - bid_series
    if require_geometry:
        if (
            (bid_series <= 0.0).any()
            or (ask_series <= 0.0).any()
            or (mid_series <= 0.0).any()
        ):
            raise QuoteContractError("bid, ask, and mid must be strictly positive.")
        if (spread_absolute < 0.0).any():
            raise QuoteContractError("Canonical quote geometry requires bid <= ask.")
        if ((mid_series < bid_series) | (mid_series > ask_series)).any():
            raise QuoteContractError(
                "Canonical quote geometry requires bid <= mid <= ask."
            )

    denominator = mid_series.where(mid_series != 0.0)
    spread_fraction = spread_absolute / denominator
    spread_bps = spread_fraction * BASIS_POINTS_PER_UNIT
    return pd.DataFrame(
        {
            "mid": mid_series.astype(float),
            "spread_absolute": spread_absolute.astype(float),
            "spread_fraction": spread_fraction.astype(float),
            "spread_bps": spread_bps.astype(float),
        },
        index=bid_series.index,
    )


def classify_spread_bps_semantics(
    frame: pd.DataFrame,
    *,
    columns: QuoteColumnNames = QuoteColumnNames(),
    rtol: float = 1e-8,
    atol: float = 1e-12,
) -> SpreadSemantics:
    """Classify whether an existing ``spread_bps`` stores bps or a legacy fraction."""

    required = {columns.bid, columns.ask, columns.mid, columns.spread_bps}
    if not required.issubset(frame.columns):
        return SpreadSemantics.INSUFFICIENT_COLUMNS
    try:
        metrics = compute_quote_metrics(
            frame[columns.bid],
            frame[columns.ask],
            mid=frame[columns.mid],
            require_midpoint=False,
            require_geometry=False,
        )
        observed = _numeric_series(frame[columns.spread_bps], name=columns.spread_bps)
    except QuoteContractError:
        return SpreadSemantics.INCONSISTENT

    values = observed.to_numpy(dtype=float)
    if np.allclose(
        values,
        metrics["spread_bps"].to_numpy(dtype=float),
        rtol=rtol,
        atol=atol,
        equal_nan=False,
    ):
        return SpreadSemantics.CANONICAL_BPS
    if np.allclose(
        values,
        metrics["spread_fraction"].to_numpy(dtype=float),
        rtol=rtol,
        atol=atol,
        equal_nan=False,
    ):
        return SpreadSemantics.LEGACY_FRACTION
    return SpreadSemantics.INCONSISTENT


def validate_canonical_quote_columns(
    frame: pd.DataFrame,
    *,
    columns: QuoteColumnNames = QuoteColumnNames(),
    rtol: float = 1e-8,
    atol: float = 1e-12,
) -> None:
    """Fail loudly unless all canonical quote columns and formulas agree."""

    required = {
        columns.bid,
        columns.ask,
        columns.mid,
        columns.spread_absolute,
        columns.spread_fraction,
        columns.spread_bps,
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise QuoteContractError(f"Missing canonical quote columns: {missing}.")

    metrics = compute_quote_metrics(
        frame[columns.bid],
        frame[columns.ask],
        mid=frame[columns.mid],
        require_midpoint=True,
        require_geometry=True,
        rtol=rtol,
        atol=atol,
    )
    expected_by_column = {
        columns.mid: metrics["mid"],
        columns.spread_absolute: metrics["spread_absolute"],
        columns.spread_fraction: metrics["spread_fraction"],
        columns.spread_bps: metrics["spread_bps"],
    }
    for name, expected in expected_by_column.items():
        observed = _numeric_series(frame[name], name=name)
        if not np.allclose(
            observed.to_numpy(dtype=float),
            expected.to_numpy(dtype=float),
            rtol=rtol,
            atol=atol,
            equal_nan=False,
        ):
            raise QuoteContractError(
                f"{name} does not satisfy the canonical quote formula."
            )


def add_canonical_quote_columns(
    frame: pd.DataFrame,
    *,
    columns: QuoteColumnNames = QuoteColumnNames(),
    overwrite: bool = False,
    require_geometry: bool = True,
) -> pd.DataFrame:
    """Return a copy with explicit canonical quote columns.

    Existing conflicting columns are never reinterpreted silently. A migration
    must preserve the legacy value under an explicit legacy name and pass
    ``overwrite=True`` deliberately.
    """

    missing = [name for name in (columns.bid, columns.ask) if name not in frame.columns]
    if missing:
        raise QuoteContractError(f"Missing bid/ask source columns: {missing}.")
    mid = frame[columns.mid] if columns.mid in frame.columns else None
    metrics = compute_quote_metrics(
        frame[columns.bid],
        frame[columns.ask],
        mid=mid,
        require_midpoint=True,
        require_geometry=require_geometry,
    )
    out = frame.copy()
    assignments = {
        columns.mid: metrics["mid"],
        columns.spread_absolute: metrics["spread_absolute"],
        columns.spread_fraction: metrics["spread_fraction"],
        columns.spread_bps: metrics["spread_bps"],
    }
    for name, values in assignments.items():
        if name in out.columns and not overwrite:
            observed = pd.to_numeric(out[name], errors="coerce").astype(float)
            if observed.isna().any() or not np.allclose(
                observed.to_numpy(dtype=float),
                values.to_numpy(dtype=float),
                rtol=1e-8,
                atol=1e-12,
                equal_nan=False,
            ):
                raise QuoteContractError(
                    f"Refusing to overwrite conflicting column '{name}'. "
                    "Use an explicit migration that preserves the legacy value."
                )
        out[name] = values.astype(float)
    return out


def quote_contract_schema() -> dict[str, Any]:
    """Return the machine-readable canonical quote-unit schema."""

    return {
        "schema_version": 1,
        "formulas": {
            "mid": "(bid + ask) / 2",
            "spread_absolute": "ask - bid",
            "spread_fraction": "spread_absolute / mid",
            "spread_bps": "10000 * spread_fraction",
        },
        "units": dict(CANONICAL_QUOTE_UNITS),
        "geometry": ["bid <= mid <= ask", "spread_absolute >= 0"],
    }


__all__ = [
    "BASIS_POINTS_PER_UNIT",
    "CANONICAL_QUOTE_UNITS",
    "QuoteColumnNames",
    "QuoteContractError",
    "SpreadSemantics",
    "add_canonical_quote_columns",
    "classify_spread_bps_semantics",
    "compute_quote_metrics",
    "quote_contract_schema",
    "validate_canonical_quote_columns",
]
