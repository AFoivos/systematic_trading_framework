from __future__ import annotations

"""Frozen dependence-aware inference for AR-0001 conditional effects."""

from dataclasses import asdict, dataclass
from hashlib import sha256
from math import ceil, erfc, sqrt
from typing import Any, Sequence

import numpy as np


class AlphaDiscoveryStatisticsError(ValueError):
    """Raised when statistical inputs violate the frozen inference contract."""


@dataclass(frozen=True)
class HACSummary:
    timeline_n: int
    condition_n: int
    mean: float
    standard_error: float
    statistic: float
    p_value: float
    estimator: str
    kernel: str
    lag_bars: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SegmentedBootstrapSummary:
    timeline_n: int
    condition_n: int
    mean: float
    standard_error: float
    confidence_lower: float
    confidence_upper: float
    block_length_bars: int
    resamples_requested: int
    resamples_valid: int
    valid_resample_fraction: float
    method: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def stable_hypothesis_seed(base_seed: int, identity: str) -> int:
    if isinstance(base_seed, bool) or not isinstance(base_seed, int):
        raise AlphaDiscoveryStatisticsError("base_seed must be an integer.")
    if not isinstance(identity, str) or not identity:
        raise AlphaDiscoveryStatisticsError("identity must be a non-empty string.")
    digest = sha256(f"{base_seed}:{identity}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _positive_integer(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise AlphaDiscoveryStatisticsError(f"{field} must be a positive integer.")
    resolved = int(value)
    if resolved <= 0:
        raise AlphaDiscoveryStatisticsError(f"{field} must be a positive integer.")
    return resolved


def _full_timeline_inputs(
    values: Sequence[float] | np.ndarray,
    *,
    condition: Sequence[bool] | np.ndarray,
    eligible: Sequence[bool] | np.ndarray,
    continuity_segment_ids: Sequence[int] | np.ndarray,
    stratum_ids: Sequence[int] | np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    array = np.asarray(values, dtype=float)
    condition_array = np.asarray(condition)
    eligible_array = np.asarray(eligible)
    continuity = np.asarray(continuity_segment_ids)
    strata = np.asarray(stratum_ids)
    if array.ndim != 1:
        raise AlphaDiscoveryStatisticsError("values must be one-dimensional.")
    if any(
        candidate.ndim != 1 or len(candidate) != len(array)
        for candidate in (condition_array, eligible_array, continuity, strata)
    ):
        raise AlphaDiscoveryStatisticsError(
            "Full-timeline values, masks, segment IDs, and strata must have equal length."
        )
    if len(array) < 2:
        raise AlphaDiscoveryStatisticsError(
            "Dependence-aware inference requires at least two timeline rows."
        )
    if condition_array.dtype != np.bool_ or eligible_array.dtype != np.bool_:
        raise AlphaDiscoveryStatisticsError(
            "condition and eligible must be explicit boolean arrays."
        )
    if any(np.asarray(ids, dtype=object).tolist().count(None) for ids in (continuity, strata)):
        raise AlphaDiscoveryStatisticsError("Segment and stratum IDs cannot be missing.")
    return array, condition_array, eligible_array, continuity, strata


def newey_west_conditional_mean_summary(
    values: Sequence[float] | np.ndarray,
    *,
    condition: Sequence[bool] | np.ndarray,
    eligible: Sequence[bool] | np.ndarray,
    continuity_segment_ids: Sequence[int] | np.ndarray,
    stratum_ids: Sequence[int] | np.ndarray,
    lag_bars: int,
    estimator: str = "CONDITIONAL_MEAN_RATIO",
    kernel: str = "BARTLETT",
) -> HACSummary:
    """Newey-West inference for a conditional mean on the original row timeline.

    The ratio estimator is ``sum(I*E*R) / sum(I*E)``.  Its influence series is
    zero outside the frozen state/eligibility mask, so intermittent state hits
    retain their actual temporal spacing.  Autocovariance pairs are admitted
    only when both rows belong to the same gap-free segment and frozen calendar
    stratum.
    """

    if estimator != "CONDITIONAL_MEAN_RATIO":
        raise AlphaDiscoveryStatisticsError(
            "HAC estimator must be CONDITIONAL_MEAN_RATIO."
        )
    if kernel != "BARTLETT":
        raise AlphaDiscoveryStatisticsError("HAC kernel must be BARTLETT.")
    lag = _positive_integer(lag_bars, field="lag_bars")
    array, condition_array, eligible_array, continuity, strata = _full_timeline_inputs(
        values,
        condition=condition,
        eligible=eligible,
        continuity_segment_ids=continuity_segment_ids,
        stratum_ids=stratum_ids,
    )
    finite = np.isfinite(array)
    effective = condition_array & eligible_array & finite
    condition_n = int(effective.sum())
    if condition_n < 2:
        raise AlphaDiscoveryStatisticsError(
            "HAC conditional-mean inference requires at least two eligible observations."
        )

    timeline_n = int(len(array))
    mean = float(np.mean(array[effective]))
    probability = condition_n / float(timeline_n)
    influence = np.zeros(timeline_n, dtype=float)
    influence[effective] = (array[effective] - mean) / probability
    long_run_variance = float(np.dot(influence, influence) / timeline_n)
    maximum_lag = min(lag, timeline_n - 1)
    for offset in range(1, maximum_lag + 1):
        same_segment = continuity[offset:] == continuity[:-offset]
        same_stratum = strata[offset:] == strata[:-offset]
        admitted = same_segment & same_stratum
        if not admitted.any():
            continue
        covariance = float(
            np.dot(influence[offset:][admitted], influence[:-offset][admitted])
            / timeline_n
        )
        weight = 1.0 - offset / float(lag + 1)
        long_run_variance += 2.0 * weight * covariance
    # Finite-sample covariance estimates can be slightly negative.  A materially
    # negative estimate is not silently repaired because it invalidates the SE.
    tolerance = np.finfo(float).eps * max(1.0, float(np.var(influence))) * 100.0
    if long_run_variance < -tolerance:
        raise AlphaDiscoveryStatisticsError(
            "HAC long-run variance is materially negative under the frozen contract."
        )
    standard_error = sqrt(max(0.0, long_run_variance) / timeline_n)
    if standard_error == 0.0:
        statistic = 0.0 if mean == 0.0 else float(np.sign(mean) * np.inf)
        p_value = 1.0 if mean == 0.0 else 0.0
    else:
        statistic = mean / standard_error
        p_value = erfc(abs(statistic) / sqrt(2.0))
    return HACSummary(
        timeline_n=timeline_n,
        condition_n=condition_n,
        mean=mean,
        standard_error=float(standard_error),
        statistic=float(statistic),
        p_value=float(min(max(p_value, 0.0), 1.0)),
        estimator=estimator,
        kernel=kernel,
        lag_bars=lag,
    )


def _valid_block_starts(
    *,
    continuity: np.ndarray,
    strata: np.ndarray,
    stratum: object,
    block_length: int,
) -> np.ndarray:
    positions = np.flatnonzero(strata == stratum)
    if len(positions) < block_length:
        return np.asarray([], dtype=int)
    candidate = positions[: len(positions) - block_length + 1]
    end = candidate + block_length - 1
    same_stratum = strata[candidate] == strata[end]
    same_segment = continuity[candidate] == continuity[end]
    consecutive_rows = end < len(strata)
    return candidate[same_stratum & same_segment & consecutive_rows]


def _prefix_sum(values: np.ndarray) -> np.ndarray:
    return np.concatenate([np.asarray([0.0]), np.cumsum(values, dtype=float)])


def segmented_moving_block_bootstrap_summary(
    values: Sequence[float] | np.ndarray,
    *,
    condition: Sequence[bool] | np.ndarray,
    eligible: Sequence[bool] | np.ndarray,
    continuity_segment_ids: Sequence[int] | np.ndarray,
    stratum_ids: Sequence[int] | np.ndarray,
    block_length_bars: int,
    resamples: int,
    confidence_level: float,
    minimum_valid_resample_fraction: float,
    seed: int,
) -> SegmentedBootstrapSummary:
    """Non-circular moving-block bootstrap on the unsqueezed row timeline.

    Blocks have exactly the requested length, are sampled within each frozen
    calendar stratum, and can never cross a timestamp gap.  State membership,
    target eligibility, and returns are resampled jointly.  No condition-hit
    array is compressed before resampling.
    """

    block_length = _positive_integer(block_length_bars, field="block_length_bars")
    sample_count = _positive_integer(resamples, field="resamples")
    if not 0.0 < float(confidence_level) < 1.0:
        raise AlphaDiscoveryStatisticsError("confidence_level must lie in (0, 1).")
    if not 0.0 < float(minimum_valid_resample_fraction) <= 1.0:
        raise AlphaDiscoveryStatisticsError(
            "minimum_valid_resample_fraction must lie in (0, 1]."
        )
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)):
        raise AlphaDiscoveryStatisticsError("seed must be an integer.")
    array, condition_array, eligible_array, continuity, strata = _full_timeline_inputs(
        values,
        condition=condition,
        eligible=eligible,
        continuity_segment_ids=continuity_segment_ids,
        stratum_ids=stratum_ids,
    )
    finite = np.isfinite(array)
    effective = condition_array & eligible_array & finite
    condition_n = int(effective.sum())
    if condition_n < 2:
        raise AlphaDiscoveryStatisticsError(
            "Segmented bootstrap requires at least two eligible condition observations."
        )

    weighted_values = np.where(effective, array, 0.0)
    weights = effective.astype(float)
    value_prefix = _prefix_sum(weighted_values)
    weight_prefix = _prefix_sum(weights)
    bootstrap_numerator = np.zeros(sample_count, dtype=float)
    bootstrap_denominator = np.zeros(sample_count, dtype=float)
    rng = np.random.default_rng(int(seed))

    ordered_strata = list(dict.fromkeys(strata.tolist()))
    for stratum in ordered_strata:
        stratum_size = int(np.count_nonzero(strata == stratum))
        starts = _valid_block_starts(
            continuity=continuity,
            strata=strata,
            stratum=stratum,
            block_length=block_length,
        )
        if not len(starts):
            raise AlphaDiscoveryStatisticsError(
                "A frozen calendar stratum has no exact-length, gap-free bootstrap block: "
                f"stratum={stratum!r}, block_length={block_length}."
            )
        draws = int(ceil(stratum_size / block_length))
        chosen = starts[
            rng.integers(0, len(starts), size=(sample_count, draws), endpoint=False)
        ]
        full_draws, remainder = divmod(stratum_size, block_length)
        if full_draws:
            selected = chosen[:, :full_draws]
            bootstrap_numerator += (
                value_prefix[selected + block_length] - value_prefix[selected]
            ).sum(axis=1)
            bootstrap_denominator += (
                weight_prefix[selected + block_length] - weight_prefix[selected]
            ).sum(axis=1)
        if remainder:
            final_start = chosen[:, -1]
            bootstrap_numerator += (
                value_prefix[final_start + remainder] - value_prefix[final_start]
            )
            bootstrap_denominator += (
                weight_prefix[final_start + remainder] - weight_prefix[final_start]
            )

    valid_resample = bootstrap_denominator > 0.0
    valid_count = int(valid_resample.sum())
    valid_fraction = valid_count / float(sample_count)
    if valid_fraction < float(minimum_valid_resample_fraction):
        raise AlphaDiscoveryStatisticsError(
            "Segmented bootstrap valid-resample fraction is below the frozen minimum: "
            f"observed={valid_fraction:.6f}, required={minimum_valid_resample_fraction:.6f}."
        )
    bootstrap_means = (
        bootstrap_numerator[valid_resample] / bootstrap_denominator[valid_resample]
    )
    alpha = 1.0 - float(confidence_level)
    lower, upper = np.quantile(
        bootstrap_means,
        [alpha / 2.0, 1.0 - alpha / 2.0],
    )
    return SegmentedBootstrapSummary(
        timeline_n=int(len(array)),
        condition_n=condition_n,
        mean=float(np.mean(array[effective])),
        standard_error=float(np.std(bootstrap_means, ddof=1)),
        confidence_lower=float(lower),
        confidence_upper=float(upper),
        block_length_bars=block_length,
        resamples_requested=sample_count,
        resamples_valid=valid_count,
        valid_resample_fraction=float(valid_fraction),
        method="STRATIFIED_SEGMENTED_MOVING_BLOCK",
    )


def adjust_pvalues(
    p_values: Sequence[float] | np.ndarray,
    *,
    method: str,
    total_hypotheses: int | None = None,
    missing_hypothesis_p_value: float = 1.0,
) -> np.ndarray:
    """Apply BH/BY while optionally retaining a larger preregistered universe.

    ``total_hypotheses`` freezes the correction denominator.  Unobserved members
    of that universe are appended at ``missing_hypothesis_p_value`` (AR-0001
    requires 1.0), so filtering failed hypotheses can never make FDR correction
    less stringent.
    """

    values = np.asarray(p_values, dtype=float)
    if values.ndim != 1:
        raise AlphaDiscoveryStatisticsError("p-values must be one-dimensional.")
    output = np.full(values.shape, np.nan, dtype=float)
    finite_mask = np.isfinite(values)
    finite = values[finite_mask]
    if ((finite < 0.0) | (finite > 1.0)).any():
        raise AlphaDiscoveryStatisticsError("p-values must lie in [0, 1].")
    observed_count = len(finite)
    family_count = observed_count
    if total_hypotheses is not None:
        family_count = _positive_integer(
            total_hypotheses,
            field="total_hypotheses",
        )
        if family_count < observed_count:
            raise AlphaDiscoveryStatisticsError(
                "total_hypotheses cannot be smaller than finite observed p-values."
            )
        if not 0.0 <= float(missing_hypothesis_p_value) <= 1.0:
            raise AlphaDiscoveryStatisticsError(
                "missing_hypothesis_p_value must lie in [0, 1]."
            )
    if observed_count == 0:
        return output
    padded = np.concatenate(
        [
            finite,
            np.full(
                family_count - observed_count,
                float(missing_hypothesis_p_value),
                dtype=float,
            ),
        ]
    )
    normalized_method = str(method).strip().upper()
    if normalized_method not in {"BH", "BY"}:
        raise AlphaDiscoveryStatisticsError("method must be BH or BY.")
    order = np.argsort(padded, kind="mergesort")
    ranked = padded[order]
    ranks = np.arange(1, family_count + 1, dtype=float)
    dependence_factor = 1.0 if normalized_method == "BH" else harmonic_number(family_count)
    scaled = ranked * family_count * dependence_factor / ranks
    adjusted_ranked = np.minimum.accumulate(scaled[::-1])[::-1]
    adjusted_ranked = np.clip(adjusted_ranked, 0.0, 1.0)
    adjusted_padded = np.empty(family_count, dtype=float)
    adjusted_padded[order] = adjusted_ranked
    output[finite_mask] = adjusted_padded[:observed_count]
    return output


def chronological_block_ids(length: int, *, block_count: int) -> np.ndarray:
    """Legacy helper retained for callers outside the frozen AR-0001 scanner."""

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
    "HACSummary",
    "SegmentedBootstrapSummary",
    "adjust_pvalues",
    "chronological_block_ids",
    "harmonic_number",
    "newey_west_conditional_mean_summary",
    "segmented_moving_block_bootstrap_summary",
    "stable_hypothesis_seed",
]
