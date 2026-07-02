from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class MomentQuoteFilterConfig:
    maker_fee_bps: float = 0.0
    expected_spread_capture_bps: float = 0.0
    safety_buffer_bps: float = 0.0
    max_uncertainty: float = 1.0
    min_expected_edge_bps: float = 0.0


@dataclass(frozen=True)
class MomentQuoteFilterDecision:
    allow_buy: bool
    allow_sell: bool
    moment_buy_score: float | None
    moment_sell_score: float | None
    moment_buy_expected_edge_bps: float | None
    moment_sell_expected_edge_bps: float | None
    moment_uncertainty: float | None
    moment_decision: str
    moment_reason: str

    def to_dict(self) -> dict[str, float | str | bool | None]:
        return {
            "allow_buy": self.allow_buy,
            "allow_sell": self.allow_sell,
            "moment_buy_score": self.moment_buy_score,
            "moment_sell_score": self.moment_sell_score,
            "moment_buy_expected_edge_bps": self.moment_buy_expected_edge_bps,
            "moment_sell_expected_edge_bps": self.moment_sell_expected_edge_bps,
            "moment_uncertainty": self.moment_uncertainty,
            "moment_decision": self.moment_decision,
            "moment_reason": self.moment_reason,
        }


class MomentQuoteFilter:
    """Fee-aware quote-side filter for MOMENT predicted markout or good-fill probability."""

    def __init__(self, config: MomentQuoteFilterConfig) -> None:
        self.config = config

    def decide(self, prediction: Mapping[str, object], *, candidate_side: str = "both") -> MomentQuoteFilterDecision:
        buy_score = _optional_float(prediction.get("moment_buy_score", prediction.get("predicted_buy_markout_bps")))
        sell_score = _optional_float(prediction.get("moment_sell_score", prediction.get("predicted_sell_markout_bps")))
        uncertainty = _optional_float(prediction.get("moment_uncertainty", prediction.get("uncertainty")))
        buy_edge = self._expected_edge(buy_score)
        sell_edge = self._expected_edge(sell_score)
        uncertainty_ok = uncertainty is None or uncertainty <= self.config.max_uncertainty
        buy_candidate = candidate_side in {"buy", "both"}
        sell_candidate = candidate_side in {"sell", "both"}
        allow_buy = bool(buy_candidate and uncertainty_ok and buy_edge is not None and buy_edge > self.config.min_expected_edge_bps)
        allow_sell = bool(sell_candidate and uncertainty_ok and sell_edge is not None and sell_edge > self.config.min_expected_edge_bps)
        if not uncertainty_ok:
            decision = "block"
            reason = "uncertainty_above_threshold"
        elif allow_buy and allow_sell:
            decision = "allow_both"
            reason = "positive_fee_adjusted_edge"
        elif allow_buy:
            decision = "allow_buy"
            reason = "positive_buy_edge"
        elif allow_sell:
            decision = "allow_sell"
            reason = "positive_sell_edge"
        else:
            decision = "block"
            reason = "non_positive_fee_adjusted_edge"
        return MomentQuoteFilterDecision(
            allow_buy=allow_buy,
            allow_sell=allow_sell,
            moment_buy_score=buy_score,
            moment_sell_score=sell_score,
            moment_buy_expected_edge_bps=buy_edge,
            moment_sell_expected_edge_bps=sell_edge,
            moment_uncertainty=uncertainty,
            moment_decision=decision,
            moment_reason=reason,
        )

    def _expected_edge(self, predicted_markout_bps: float | None) -> float | None:
        if predicted_markout_bps is None:
            return None
        return (
            predicted_markout_bps
            + self.config.expected_spread_capture_bps
            - self.config.maker_fee_bps
            - self.config.safety_buffer_bps
        )


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["MomentQuoteFilter", "MomentQuoteFilterConfig", "MomentQuoteFilterDecision"]
