from __future__ import annotations

from dataclasses import asdict, dataclass, field
from statistics import median
from typing import Any, Callable, Sequence

import numpy as np


@dataclass(frozen=True)
class SlidingWindowFold:
    fold: int
    train_start: int
    train_end: int
    validation_start: int
    validation_end: int
    test_start: int
    test_end: int

    @property
    def train_indices(self) -> np.ndarray:
        return np.arange(self.train_start, self.train_end, dtype=int)

    @property
    def validation_indices(self) -> np.ndarray:
        return np.arange(self.validation_start, self.validation_end, dtype=int)

    @property
    def test_indices(self) -> np.ndarray:
        return np.arange(self.test_start, self.test_end, dtype=int)

    def to_dict(self) -> dict[str, int]:
        return {key: int(value) for key, value in asdict(self).items()}


@dataclass(frozen=True)
class PolicyMetrics:
    cumulative_reward: float
    max_drawdown: float
    total_return: float
    final_equity: float
    trade_count: int
    evaluation_steps: int = 1

    def __post_init__(self) -> None:
        for field_name in ("cumulative_reward", "max_drawdown", "total_return", "final_equity"):
            value = float(getattr(self, field_name))
            if not np.isfinite(value):
                raise ValueError(f"{field_name} must be finite.")
        if self.max_drawdown < 0.0:
            raise ValueError("max_drawdown must be expressed as a non-negative fraction.")
        if self.trade_count < 0:
            raise ValueError("trade_count must be >= 0.")
        if (
            isinstance(self.evaluation_steps, bool)
            or not isinstance(self.evaluation_steps, (int, np.integer))
            or self.evaluation_steps <= 0
        ):
            raise ValueError("evaluation_steps must be a positive integer.")

    @property
    def mean_reward_per_step(self) -> float:
        """Reward normalized by evaluated transitions for comparable split scores."""
        return float(self.cumulative_reward / self.evaluation_steps)

    def to_dict(self) -> dict[str, float | int]:
        return {
            "cumulative_reward": float(self.cumulative_reward),
            "max_drawdown": float(self.max_drawdown),
            "total_return": float(self.total_return),
            "final_equity": float(self.final_equity),
            "trade_count": int(self.trade_count),
            "evaluation_steps": int(self.evaluation_steps),
            "mean_reward_per_step": self.mean_reward_per_step,
        }


@dataclass(frozen=True)
class PolicyEvaluation:
    metrics: PolicyMetrics
    trades: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    trace: tuple[dict[str, Any], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CheckpointEvaluation:
    checkpoint: str
    step: int
    train_tail: PolicyMetrics
    validation: PolicyMetrics


@dataclass(frozen=True)
class CheckpointSelection:
    checkpoint: str
    step: int
    train_tail_metrics: PolicyMetrics
    validation_metrics: PolicyMetrics
    train_tail_score: float
    validation_score: float
    checkpoint_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint": self.checkpoint,
            "step": int(self.step),
            "train_tail_metrics": self.train_tail_metrics.to_dict(),
            "validation_metrics": self.validation_metrics.to_dict(),
            "train_tail_score": float(self.train_tail_score),
            "validation_score": float(self.validation_score),
            "checkpoint_score": float(self.checkpoint_score),
        }


@dataclass(frozen=True)
class SelectedFoldEvaluation:
    selection: CheckpointSelection
    test: PolicyEvaluation


@dataclass(frozen=True)
class ConsistencyGateResult:
    passed: bool
    profitable_fold_ratio: float
    median_test_return: float
    minimum_profitable_fold_ratio: float
    minimum_median_test_return: float
    champion_checkpoint: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_sliding_window_folds(
    *,
    n_samples: int,
    train_size: int,
    validation_size: int,
    test_size: int,
    step_size: int | None = None,
    max_folds: int | None = None,
) -> list[SlidingWindowFold]:
    """Build fixed-size, strictly ordered rolling train/validation/test folds.

    Every interval is half-open. The training start advances by ``step_size``, so old
    observations leave the fixed-size training window. Validation and test follow training
    chronologically without overlap, and test windows are also required not to overlap.
    """
    for field_name, value in (
        ("n_samples", n_samples),
        ("train_size", train_size),
        ("validation_size", validation_size),
        ("test_size", test_size),
    ):
        if isinstance(value, bool) or int(value) <= 0:
            raise ValueError(f"{field_name} must be a positive integer.")
    resolved_step = int(test_size if step_size is None else step_size)
    if isinstance(step_size, bool) or resolved_step <= 0:
        raise ValueError("step_size must be a positive integer.")
    if resolved_step < int(test_size):
        raise ValueError("step_size must be >= test_size so held-out test windows do not overlap.")
    if max_folds is not None and (isinstance(max_folds, bool) or max_folds <= 0):
        raise ValueError("max_folds must be > 0 when provided.")

    required = int(train_size + validation_size + test_size)
    if n_samples < required:
        raise ValueError(
            "Not enough rows for one sliding-window fold: "
            f"n_samples={n_samples}, required={required}."
        )

    folds: list[SlidingWindowFold] = []
    train_start = 0
    while train_start + required <= n_samples:
        train_end = train_start + int(train_size)
        validation_end = train_end + int(validation_size)
        test_end = validation_end + int(test_size)
        folds.append(
            SlidingWindowFold(
                fold=len(folds),
                train_start=train_start,
                train_end=train_end,
                validation_start=train_end,
                validation_end=validation_end,
                test_start=validation_end,
                test_end=test_end,
            )
        )
        if max_folds is not None and len(folds) >= int(max_folds):
            break
        train_start += resolved_step
    return folds


def split_score(metrics: PolicyMetrics, *, drawdown_penalty: float) -> float:
    """Score a split in length-normalized reward units minus fractional drawdown.

    Raw cumulative reward grows with split length while max drawdown is a fraction. Dividing
    reward by evaluated transitions removes that mechanical length effect. The configured
    coefficient then has an explicit interpretation: mean reward-per-bar units charged for a
    full unit of drawdown. This preserves the requested reward/drawdown objective without
    using test returns or a data-dependent rescaling.
    """
    if not np.isfinite(drawdown_penalty) or drawdown_penalty < 0.0:
        raise ValueError("drawdown_penalty must be finite and >= 0.")
    return float(metrics.mean_reward_per_step - drawdown_penalty * metrics.max_drawdown)


def select_checkpoint_maximin(
    checkpoints: Sequence[CheckpointEvaluation],
    *,
    drawdown_penalty: float,
) -> CheckpointSelection:
    """Select by max(min(train-tail score, validation score)); test is not an input."""
    if not checkpoints:
        raise ValueError("At least one checkpoint evaluation is required.")
    scored: list[CheckpointSelection] = []
    for candidate in checkpoints:
        train_score = split_score(candidate.train_tail, drawdown_penalty=drawdown_penalty)
        validation_score = split_score(candidate.validation, drawdown_penalty=drawdown_penalty)
        scored.append(
            CheckpointSelection(
                checkpoint=str(candidate.checkpoint),
                step=int(candidate.step),
                train_tail_metrics=candidate.train_tail,
                validation_metrics=candidate.validation,
                train_tail_score=train_score,
                validation_score=validation_score,
                checkpoint_score=min(train_score, validation_score),
            )
        )
    # Prefer the later checkpoint only when maximin scores tie exactly.
    return max(scored, key=lambda item: (item.checkpoint_score, item.step))


def evaluate_checkpoints_then_test(
    *,
    checkpoints: Sequence[tuple[str, int]],
    evaluator: Callable[[str, str], PolicyEvaluation],
    drawdown_penalty: float,
) -> SelectedFoldEvaluation:
    """Evaluate train-tail/validation, select, then evaluate test exactly once.

    Test data is not passed to checkpoint scoring. Only the checkpoint selected by the
    maximin train-tail/validation rule is evaluated on the held-out test interval.
    """
    if not checkpoints:
        raise ValueError("At least one checkpoint is required.")
    candidates: list[CheckpointEvaluation] = []
    for checkpoint, step in checkpoints:
        train_tail = evaluator(str(checkpoint), "train_tail")
        validation = evaluator(str(checkpoint), "validation")
        candidates.append(
            CheckpointEvaluation(
                checkpoint=str(checkpoint),
                step=int(step),
                train_tail=train_tail.metrics,
                validation=validation.metrics,
            )
        )
    selected = select_checkpoint_maximin(candidates, drawdown_penalty=drawdown_penalty)
    test = evaluator(selected.checkpoint, "test")
    return SelectedFoldEvaluation(selection=selected, test=test)


def evaluate_consistency_gate(
    *,
    test_returns: Sequence[float],
    minimum_profitable_fold_ratio: float,
    minimum_median_test_return: float,
    last_fold_checkpoint: str,
) -> ConsistencyGateResult:
    """Promote the last-fold model only when aggregate held-out fold criteria pass."""
    returns = np.asarray(list(test_returns), dtype=float)
    if returns.ndim != 1 or returns.size == 0 or not bool(np.isfinite(returns).all()):
        raise ValueError("test_returns must be a non-empty finite one-dimensional sequence.")
    if not 0.0 <= minimum_profitable_fold_ratio <= 1.0:
        raise ValueError("minimum_profitable_fold_ratio must be in [0, 1].")
    if not np.isfinite(minimum_median_test_return):
        raise ValueError("minimum_median_test_return must be finite.")
    profitable_ratio = float(np.mean(returns > 0.0))
    median_return = float(median(float(value) for value in returns))
    passed = bool(
        profitable_ratio >= float(minimum_profitable_fold_ratio)
        and median_return >= float(minimum_median_test_return)
    )
    return ConsistencyGateResult(
        passed=passed,
        profitable_fold_ratio=profitable_ratio,
        median_test_return=median_return,
        minimum_profitable_fold_ratio=float(minimum_profitable_fold_ratio),
        minimum_median_test_return=float(minimum_median_test_return),
        champion_checkpoint=str(last_fold_checkpoint) if passed else None,
    )


__all__ = [
    "CheckpointEvaluation",
    "CheckpointSelection",
    "ConsistencyGateResult",
    "PolicyEvaluation",
    "PolicyMetrics",
    "SelectedFoldEvaluation",
    "SlidingWindowFold",
    "build_sliding_window_folds",
    "evaluate_checkpoints_then_test",
    "evaluate_consistency_gate",
    "select_checkpoint_maximin",
    "split_score",
]
