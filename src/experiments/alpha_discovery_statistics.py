from __future__ import annotations

"""Dependence-aware inference for preregistered conditional state effects."""

from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any, Sequence

import numpy as np


class AlphaDiscoveryStatisticsError(ValueError):
    """Raised when statistical inputs violate the frozen inference contract."""


@dataclass(frozen=True)
class BootstrapSummary:
    n: int
    mean: float
    median: float
    standard_error: float
    hit_rate: float
    effect_size: float
    confidence_lower: float
    confidence_upper: float
    p_value: float
    block_length: int
    resamples: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def stable_hypothesis_seed(base_seed: int, identity: str) -> int:
    if isinstance(base_seed, bool) or not isinstance(base_seed, int):
        raise AlphaDiscoveryStatisticsError("base_seed must be an integer.")
    if not isinstance(identity, str) or not identity:
        raise AlphaDiscoveryStatisticsError("identity must be a non-empty string.")
    digest = sha256(f"{base_seed}:{identity}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _circular_block_sums(values: np.ndarray, block_length: int) -> np.ndarray:
    if block_length <= 0 or block_length > len(values):
        raise AlphaDiscoveryStatisticsError("Invalid circular block length.")
    extended = np.concatenate([values, values[: block_length - 1]])
    cumulative = np.concatenate([[0.0], np.cumsum(extended, dtype=float)])
    starts = np.arange(len(values), dtype=int)
    return cumulative[starts + block_length] - cumulative[starts]


def moving_block_bootstrap_summary(
    values: Sequence[float] | np.ndarray,
    *,
    block_length: int,
    resamples: int,
    confidence_level: float,
    seed: int,
) -> BootstrapSummary:
    """Estimate mean uncertainty with a deterministic circular moving-block bootstrap.

    The percentile interval resamples the observed series.  The two-sided
    p-value uses the corresponding centered bootstrap distribution under a
    zero-mean null, with a plus-one finite-resample correction.
    """

    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    n = int(len(array))
    if n < 2:
        raise AlphaDiscoveryStatisticsError(
            "Moving-block inference requires at least two finite observations."
        )
    if isinstance(block_length, bool) or int(block_length) != block_length:
        raise AlphaDiscoveryStatisticsError("block_length must be an integer.")
    if isinstance(resamples, bool) or int(resamples) != resamples or resamples < 1:
        raise AlphaDiscoveryStatisticsError("resamples must be a positive integer.")
    if not 0.0 < float(confidence_level) < 1.0:
        raise AlphaDiscoveryStatisticsError("confidence_level must lie in (0, 1).")
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)):
        raise AlphaDiscoveryStatisticsError("seed must be an integer.")

    requested_block = int(block_length)
    if requested_block <= 0:
        raise AlphaDiscoveryStatisticsError("block_length must be positive.")
    resolved_block = min(requested_block, max(1, n // 2))
    full_blocks, remainder = divmod(n, resolved_block)
    draws_per_resample = full_blocks + int(remainder > 0)
    rng = np.random.default_rng(int(seed))
    starts = rng.integers(
        0,
        n,
        size=(int(resamples), draws_per_resample),
        endpoint=False,
    )
    block_sums = _circular_block_sums(array, resolved_block)
    total = block_sums[starts[:, :full_blocks]].sum(axis=1)
    if remainder:
        remainder_sums = _circular_block_sums(array, remainder)
        total = total + remainder_sums[starts[:, -1]]
    bootstrap_means = total / float(n)

    observed_mean = float(np.mean(array))
    observed_std = float(np.std(array, ddof=1))
    alpha = 1.0 - float(confidence_level)
    confidence_lower, confidence_upper = np.quantile(
        bootstrap_means, [alpha / 2.0, 1.0 - alpha / 2.0]
    )
    centered_bootstrap = bootstrap_means - observed_mean
    exceedances = int(
        np.count_nonzero(np.abs(centered_bootstrap) >= abs(observed_mean))
    )
    p_value = (exceedances + 1.0) / (int(resamples) + 1.0)
    return BootstrapSummary(
        n=n,
        mean=observed_mean,
        median=float(np.median(array)),
        standard_error=float(np.std(bootstrap_means, ddof=1)),
        hit_rate=float(np.mean(array > 0.0)),
        effect_size=(
            observed_mean / observed_std if observed_std > 0.0 else float("nan")
        ),
        confidence_lower=float(confidence_lower),
        confidence_upper=float(confidence_upper),
        p_value=float(min(max(p_value, 0.0), 1.0)),
        block_length=resolved_block,
        resamples=int(resamples),
    )


def adjust_pvalues(
    p_values: Sequence[float] | np.ndarray,
    *,
    method: str,
) -> np.ndarray:
    """Apply Benjamini-Hochberg or Benjamini-Yekutieli with NaN preservation."""

    values = np.asarray(p_values, dtype=float)
    output = np.full(values.shape, np.nan, dtype=float)
    finite_mask = np.isfinite(values)
    finite = values[finite_mask]
    if ((finite < 0.0) | (finite > 1.0)).any():
        raise AlphaDiscoveryStatisticsError("p-values must lie in [0, 1].")
    count = len(finite)
    if count == 0:
        return output
    normalized_method = str(method).strip().upper()
    if normalized_method not in {"BH", "BY"}:
        raise AlphaDiscoveryStatisticsError("method must be BH or BY.")
    order = np.argsort(finite, kind="mergesort")
    ranked = finite[order]
    ranks = np.arange(1, count + 1, dtype=float)
    dependence_factor = 1.0 if normalized_method == "BH" else float(np.sum(1.0 / ranks))
    scaled = ranked * count * dependence_factor / ranks
    adjusted_ranked = np.minimum.accumulate(scaled[::-1])[::-1]
    adjusted_ranked = np.clip(adjusted_ranked, 0.0, 1.0)
    adjusted = np.empty(count, dtype=float)
    adjusted[order] = adjusted_ranked
    output[finite_mask] = adjusted
    return output


def chronological_block_ids(length: int, *, block_count: int) -> np.ndarray:
    if isinstance(length, bool) or not isinstance(length, int) or length <= 0:
        raise AlphaDiscoveryStatisticsError("length must be a positive integer.")
    if (
        isinstance(block_count, bool)
        or not isinstance(block_count, int)
        or block_count <= 1
        or block_count > length
    ):
        raise AlphaDiscoveryStatisticsError(
            "block_count must be an integer in [2, length]."
        )
    return np.minimum(
        np.floor(np.arange(length, dtype=float) * block_count / length).astype(int),
        block_count - 1,
    )


def harmonic_number(length: int) -> float:
    if isinstance(length, bool) or not isinstance(length, int) or length <= 0:
        raise AlphaDiscoveryStatisticsError("length must be a positive integer.")
    return float(sum(1.0 / index for index in range(1, length + 1)))


__all__ = [
    "AlphaDiscoveryStatisticsError",
    "BootstrapSummary",
    "adjust_pvalues",
    "chronological_block_ids",
    "harmonic_number",
    "moving_block_bootstrap_summary",
    "stable_hypothesis_seed",
]
