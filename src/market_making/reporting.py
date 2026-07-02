from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


def write_market_making_markdown_report(
    run_dir: str | Path,
    diagnostics: Mapping[str, Any],
    *,
    output_path: str | Path | None = None,
) -> Path:
    """Write a human-readable market-making diagnostics report."""
    run_path = Path(run_dir)
    out = Path(output_path) if output_path is not None else run_path / "diagnostics" / "report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    run = diagnostics.get("run", {})
    gaps = diagnostics.get("gaps", {})
    warnings = diagnostics.get("warnings", [])
    quote = diagnostics.get("quote", {})
    fill = diagnostics.get("fill", {})
    markout = diagnostics.get("markout", {})
    inventory = diagnostics.get("inventory", {})
    market_quality = diagnostics.get("market_quality", {})
    risk = diagnostics.get("risk", {})

    enough_fills = not gaps.get("fill_count_too_low_for_edge_evaluation", True)
    lines = [
        "# Market Making Run Diagnostics",
        "",
        "## Executive Summary",
        f"- Total PnL: {_fmt(run.get('total_pnl'))}",
        f"- Fills: {_fmt(run.get('number_of_fills'))}",
        f"- Quotes: {_fmt(run.get('number_of_quotes'))}",
        f"- Fill ratio: {_fmt(run.get('fill_ratio'))}",
        f"- Fills per quote attempt: {_fmt(run.get('fills_per_quote_attempt'))}",
        f"- Fills per placed quote: {_fmt(run.get('fills_per_placed_quote'))}",
        f"- Fills per order: {_fmt(run.get('fills_per_order'))}",
        f"- Fills per input event: {_fmt(run.get('fills_per_input_event'))}",
        f"- Max drawdown: {_fmt(run.get('max_drawdown'))}",
        f"- Fill sample sufficient for edge evaluation: {'yes' if enough_fills else 'no'}",
        f"- Markout available: {'yes' if not gaps.get('markout_missing') else 'no'}",
        f"- Quote-event logging available: {'yes' if not gaps.get('quote_events_missing') else 'no'}",
        f"- Lineage available: {'yes' if not gaps.get('lineage_missing') else 'no'}",
        f"- PnL attribution approximate: {'yes' if gaps.get('pnl_attribution_approximate') else 'no'}",
        f"- Adverse-selection filter active: {'yes' if run.get('adverse_selection_filter_active') else 'no'}",
        f"- Operational stability clean: {'yes' if not run.get('kill_switch_events') and not run.get('runtime_errors') else 'no'}",
        "",
        "## Run Funnel",
        f"- Input events: {_fmt(run.get('input_events'))}",
        f"- Quoted events: {_fmt(run.get('quoted_events'))}",
        f"- Skipped events: {_fmt(run.get('skipped_events'))}",
        f"- Fills: {_fmt(run.get('number_of_fills'))}",
        "",
        "## PnL and Drawdown",
        f"- Net PnL: {_fmt(diagnostics.get('pnl', {}).get('net_pnl'))}",
        f"- Fees: {_fmt(run.get('fees'))}",
        f"- Fee drag ratio: {_fmt(run.get('fee_drag_ratio'))}",
        "",
        "## Quote Behavior",
        f"- Quote count: {_fmt(quote.get('quote_count'))}",
        f"- Placed quote rate: {_fmt(quote.get('placed_quote_rate'))}",
        f"- Avg quoted spread bps: {_fmt(quote.get('avg_quoted_spread_bps'))}",
        f"- Quote at top-of-book count: {_fmt(quote.get('quote_at_top_of_book_count'))}",
        "",
        "## Fill Behavior",
        f"- Buy fills: {_fmt(fill.get('buy_fill_count'))}",
        f"- Sell fills: {_fmt(fill.get('sell_fill_count'))}",
        f"- Total fill notional: {_fmt(fill.get('total_fill_notional'))}",
        f"- Filled quote count: {_fmt(fill.get('filled_quote_count'))}",
        f"- Filled quote rate: {_fmt(fill.get('filled_quote_rate'))}",
        "",
        "## Markout / Adverse Selection",
        f"- Markout unavailable: {bool(markout.get('markout_unavailable', gaps.get('markout_missing')))}",
        f"- H1 adverse selection rate: {_fmt(markout.get('adverse_selection_rate_h1'))}",
        "",
        "## Inventory Risk",
        f"- Avg abs inventory: {_fmt(inventory.get('avg_abs_inventory'))}",
        f"- Max abs inventory: {_fmt(inventory.get('max_abs_inventory'))}",
        f"- Inventory limit utilization: {_fmt(inventory.get('inventory_limit_utilization'))}",
        "",
        "## Market Quality",
        f"- Order book events: {_fmt(market_quality.get('event_count'))}",
        f"- Crossed books: {_fmt(market_quality.get('crossed_book_count'))}",
        f"- Missing top-of-book rows: {_fmt(market_quality.get('missing_top_of_book_count'))}",
        f"- Avg spread bps: {_fmt(market_quality.get('avg_spread_bps'))}",
        "",
        "## Risk Gates",
        f"- Risk rejects: {_fmt(risk.get('risk_reject_count'))}",
        f"- Kill switches: {_fmt(risk.get('risk_kill_switch_count'))}",
        f"- Reasons: {risk.get('risk_reason_counts', {})}",
        "",
        "## Diagnostics Gaps",
    ]
    lines.extend([f"- {key}: {value}" for key, value in gaps.items()])
    lines.extend(
        [
            "",
            "## Interpretation",
            _interpretation(diagnostics),
            "",
            "## Recommended Next Actions",
            _recommendations(diagnostics),
            "",
        ]
    )
    if warnings:
        lines.extend(["## Warnings", *[f"- {warning}" for warning in warnings], ""])
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _interpretation(diagnostics: Mapping[str, Any]) -> str:
    gaps = diagnostics.get("gaps", {})
    if gaps.get("fill_count_too_low_for_edge_evaluation"):
        return "The run does not have enough fills for robust edge evaluation. Treat PnL and markout as exploratory."
    if gaps.get("markout_missing"):
        return "Fill edge cannot be separated from adverse selection because markout data is unavailable."
    return "The run has enough basic artifacts to evaluate quote behavior, fills, markout, inventory, and PnL."


def _recommendations(diagnostics: Mapping[str, Any]) -> str:
    gaps = diagnostics.get("gaps", {})
    recs: list[str] = []
    if gaps.get("quote_events_missing"):
        recs.append("Enable quote_events.csv logging for risk and quote rejection attribution.")
    if gaps.get("lineage_missing"):
        recs.append("Add/verify quote_event_id and parent_quote_event_id lineage so fill-to-quote attribution is not approximate.")
    if gaps.get("markout_missing"):
        recs.append("Provide orderbook_events.csv to compute markout and adverse-selection diagnostics.")
    if gaps.get("fill_count_too_low_for_edge_evaluation"):
        recs.append("Collect more fills before evaluating market-making edge; fewer than 30 fills is too sparse.")
    run = diagnostics.get("run", {})
    risk = diagnostics.get("risk", {})
    if run.get("adverse_selection_filter_active") and not risk.get("quote_reason_counts"):
        recs.append("Adverse-selection filter is active but produced no visible rejection counts; verify thresholds and quote event wiring.")
    if (run.get("number_of_quotes") or 0) > 1000 and (run.get("number_of_fills") or 0) <= 1:
        recs.append("High quote count with near-zero fills: review quote placement mode, spread, tick size, replay fill model, queue position, and latency assumptions.")
    if gaps.get("missing_queue_position_model"):
        recs.append("Add queue-position modeling before treating paper fills as venue-realistic.")
    if gaps.get("missing_partial_fill_model"):
        recs.append("Add partial-fill simulation for better fill-rate realism.")
    if gaps.get("missing_latency_model"):
        recs.append("Add latency-aware replay before demo/live order placement.")
    return "\n".join(f"- {rec}" for rec in recs) if recs else "- Continue with parameter sweeps and out-of-sample replay."


__all__ = ["write_market_making_markdown_report"]
