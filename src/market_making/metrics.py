from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaperRunSummary:
    """Summary metrics emitted at the end of a paper market-making run."""

    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    fees: float
    number_of_fills: int
    number_of_quotes: int
    number_of_cancels: int
    fill_ratio: float
    average_spread_quoted: float
    average_inventory: float
    max_inventory: float
    max_drawdown: float
    kill_switch_events: list[str]
    fills_per_quote_attempt: float | None = None
    fills_per_placed_quote: float | None = None
    fills_per_order: float | None = None
    fills_per_input_event: float | None = None
    runtime_errors: int = 0
    reconnects: int = 0
    input_events: int = 0
    quoted_events: int = 0
    skipped_events: int = 0
    reconstructed_book_events: int = 0
    fill_model: str = "trade_through"
    data_source: str = "synthetic"
    adverse_selection_filter_active: bool = False

    def to_dict(self) -> dict[str, float | int | list[str] | str]:
        """Return JSON-friendly summary values."""
        return {
            "total_pnl": self.total_pnl,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "fees": self.fees,
            "number_of_fills": self.number_of_fills,
            "number_of_quotes": self.number_of_quotes,
            "number_of_cancels": self.number_of_cancels,
            "fill_ratio": self.fill_ratio,
            "fills_per_quote_attempt": self.fills_per_quote_attempt,
            "fills_per_placed_quote": self.fills_per_placed_quote,
            "fills_per_order": self.fills_per_order,
            "fills_per_input_event": self.fills_per_input_event,
            "average_spread_quoted": self.average_spread_quoted,
            "average_inventory": self.average_inventory,
            "max_inventory": self.max_inventory,
            "max_drawdown": self.max_drawdown,
            "kill_switch_events": self.kill_switch_events,
            "runtime_errors": self.runtime_errors,
            "reconnects": self.reconnects,
            "input_events": self.input_events,
            "quoted_events": self.quoted_events,
            "skipped_events": self.skipped_events,
            "reconstructed_book_events": self.reconstructed_book_events,
            "fill_model": self.fill_model,
            "data_source": self.data_source,
            "adverse_selection_filter_active": self.adverse_selection_filter_active,
        }


def max_drawdown(values: list[float]) -> float:
    """Compute absolute max drawdown over an equity curve."""
    peak: float | None = None
    worst = 0.0
    for value in values:
        peak = value if peak is None else max(peak, value)
        worst = min(worst, value - peak)
    return abs(worst)


__all__ = ["PaperRunSummary", "max_drawdown"]
