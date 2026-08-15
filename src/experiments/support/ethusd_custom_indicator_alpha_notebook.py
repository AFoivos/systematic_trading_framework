from __future__ import annotations

import argparse
from pathlib import Path

import nbformat
from nbclient import NotebookClient

from src.utils.paths import PROJECT_ROOT, enforce_safe_absolute_path


def _markdown(text: str) -> nbformat.NotebookNode:
    return nbformat.v4.new_markdown_cell(text.strip())


def _code(text: str) -> nbformat.NotebookNode:
    return nbformat.v4.new_code_cell(text.strip())


def build_ethusd_custom_indicator_alpha_notebook(
    run_dir: str | Path,
    *,
    execute: bool = True,
) -> Path:
    """Build a reproducible notebook from a frozen custom-indicator run."""

    directory = Path(run_dir)
    if not directory.is_absolute():
        directory = PROJECT_ROOT / directory
    directory = enforce_safe_absolute_path(directory.resolve())
    if not (directory / "summary.json").is_file():
        raise FileNotFoundError(f"Suite summary not found in {directory}")
    destination = directory / "ethusd_custom_indicator_alpha_report.ipynb"

    notebook = nbformat.v4.new_notebook()
    notebook["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3"},
    }
    notebook["cells"] = [
        _markdown(
            """
# ETHUSD custom-indicator alpha search

## TL;DR

This notebook audits a predeclared 96-candidate search built from four original, causal OHLCV indicator families. The canonical v2 workflow is fail-closed: if no candidate is positive in both development and validation, locked bars and exact cTrader ticks remain unread for strategy evaluation. The requested 70% win rate is a gate, not an optimization target or a promised outcome.
"""
        ),
        _markdown(
            """
## Context & methods

- Provider: cTrader CSV exports under `data/ETHUSD`.
- Signal timing: indicators use completed M30 bars; an entry is allowed only at the next M30 open.
- Same-bar ambiguity: when both stop and target lie inside one OHLC bar, the stop is assumed first.
- Selection: development through 2023-12-31 and validation from 2024-01-01 through 2025-06-30.
- Locked gate: begins 2025-07-01 and is accessed only after a candidate passes selection.
- Costs: observed median cTrader tick spread plus 0.5 bp commission per side.
- Acceptance: at least 70% wins must coexist with positive net return, profit factor, conventional Sharpe, sufficient trades, both sides, and exact execution robustness.
"""
        ),
        _code(
            """
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import Markdown, display

RUN_DIR = Path.cwd().resolve()
summary = json.loads((RUN_DIR / "summary.json").read_text(encoding="utf-8"))
candidates = pd.read_csv(RUN_DIR / "candidate_search_development_validation.csv")
selection = summary["candidate_search"]

assert summary["split_contract"]["selection_reads_locked_rows"] is False
if selection["eligible_candidate_count"] == 0:
    assert summary["locked_bar"]["status"] == "not_evaluated"
    assert summary["exact_tick_base"]["status"] == "not_evaluated"

display(Markdown(f"**Canonical verdict:** {summary['research_verdict']}"))
"""
        ),
        _markdown(
            """
## Data and reproducibility contract

The suite records hashes for the M30 and tick exports in `provenance.json`, the complete candidate grid, Git metadata, split boundaries, and the cost contract. Timestamps are assumed to be UTC bar-open labels; that assumption still needs confirmation from the cTrader exporter settings.
"""
        ),
        _code(
            """
provenance = json.loads((RUN_DIR / "provenance.json").read_text(encoding="utf-8"))
contract = pd.DataFrame([
    {"item": "provider", "value": summary["provider"]},
    {"item": "candidate count", "value": selection["candidate_count"]},
    {"item": "eligible candidates", "value": selection["eligible_candidate_count"]},
    {"item": "round-trip cost (bp)", "value": summary["cost_contract"]["bar_round_trip_cost_bps"]},
    {"item": "development end", "value": summary["split_contract"]["development_end"]},
    {"item": "validation end", "value": summary["split_contract"]["validation_end"]},
    {"item": "locked start", "value": summary["split_contract"]["locked_start"]},
    {"item": "locked evaluation authorized", "value": selection["locked_evaluation_authorized"]},
])
display(contract)
display(pd.DataFrame(provenance["data_files"]).T.reset_index(names="source"))
"""
        ),
        _markdown(
            """
## Results — the selection gate failed

`robust_win_rate` is the lower of development and validation win rate. It prevents a high rate in one split from hiding deterioration in the other. A high win rate alone is insufficient: asymmetric 0.6R targets can raise the hit rate while producing a deeply negative payoff distribution after costs.
"""
        ),
        _code(
            """
positive_both = (
    (candidates["development_cumulative_return"] > 0.0)
    & (candidates["validation_cumulative_return"] > 0.0)
)
selection_audit = pd.DataFrame([
    {"test": "predeclared candidates", "result": len(candidates)},
    {"test": "eligible candidates", "result": int(candidates["eligible"].sum())},
    {"test": "positive return in both selection splits", "result": int(positive_both.sum())},
    {"test": "maximum robust win rate", "result": float(candidates["robust_win_rate"].max())},
    {"test": "maximum validation win rate", "result": float(candidates["validation_win_rate"].max())},
    {"test": "70% robust win candidates", "result": int((candidates["robust_win_rate"] >= 0.70).sum())},
])
display(selection_audit)

top = candidates.nlargest(12, "robust_win_rate").sort_values("robust_win_rate")
fig, axes = plt.subplots(1, 2, figsize=(15, 5.5))
axes[0].barh(top["candidate_id"].str.replace("__", " | ", regex=False), top["robust_win_rate"], color="#355C7D")
axes[0].axvline(0.70, color="#C44E52", linestyle="--", label="70% gate")
axes[0].set_xlim(0.45, 0.72)
axes[0].set_xlabel("min(development, validation) win rate")
axes[0].set_title("Best robust hit rates still miss 70%")
axes[0].legend()

colors = np.where(positive_both, "#55A868", "#C44E52")
axes[1].scatter(
    candidates["development_cumulative_return"],
    candidates["validation_cumulative_return"],
    c=colors,
    alpha=0.75,
)
axes[1].axhline(0.0, color="black", linewidth=0.8)
axes[1].axvline(0.0, color="black", linewidth=0.8)
axes[1].set_xlabel("development cumulative return")
axes[1].set_ylabel("validation cumulative return")
axes[1].set_title("No candidate is profitable in both splits")
plt.tight_layout()
figure_path = RUN_DIR / "candidate_selection_diagnostics.png"
fig.savefig(figure_path, dpi=160, bbox_inches="tight")
plt.show()
"""
        ),
        _markdown("## Results — diagnostic leader, not a selected strategy"),
        _code(
            """
leader = candidates.loc[candidates["candidate_id"].eq(selection["diagnostic_leader_id"])].iloc[0]
leader_view = pd.DataFrame([
    {
        "split": "development",
        "trades": int(leader["development_trade_count"]),
        "win_rate": leader["development_win_rate"],
        "cumulative_return": leader["development_cumulative_return"],
        "profit_factor": leader["development_trade_profit_factor"],
        "conventional_sharpe": leader["development_conventional_sharpe"],
    },
    {
        "split": "validation",
        "trades": int(leader["validation_trade_count"]),
        "win_rate": leader["validation_win_rate"],
        "cumulative_return": leader["validation_cumulative_return"],
        "profit_factor": leader["validation_trade_profit_factor"],
        "conventional_sharpe": leader["validation_conventional_sharpe"],
    },
])
display(Markdown(f"Diagnostic leader only: `{selection['diagnostic_leader_id']}`"))
display(leader_view)
"""
        ),
        _markdown(
            """
## Limitations and evidence status

- The v2 run correctly withholds locked and exact-tick evaluation because selection failed.
- A superseded v1 diagnostic run opened those layers before fail-closed enforcement. That exposure burns the old locked period for this exact hypothesis family; its numbers are not canonical v2 evidence and must not be used for retuning.
- The 96-candidate grid still creates multiple-testing risk inside selection.
- M30 OHLC first passage is approximate; it cannot resolve an intrabar path except by the deliberately conservative stop-first rule.
- Swap, rejected orders, market impact, and account-level FTMO controls are outside the selection ledger.
- Real alpha requires a frozen rule and newly accumulated append-only prospective evidence.
"""
        ),
        _markdown(
            """
## Takeaways

1. Four original causal indicator families and a complete execution-aware selection harness were implemented successfully.
2. They did not produce a credible alpha candidate on these cTrader data: 0/96 rules were profitable in both development and validation.
3. The maximum robust win rate was about 58.18%, well below 70%; the high-hit-rate configurations were strongly negative after costs.
4. The correct decision is to reject this continuation family, not to tune until the requested percentage appears.
5. The next valid research step is a separately predeclared hypothesis and a new prospective cTrader confirmation period.

### Exact rerun command

```bash
docker compose run --rm app python -m src.experiments.support.ethusd_custom_indicator_alpha --output-dir logs/experiments/<new-run-id>
```
"""
        ),
    ]

    nbformat.write(notebook, destination)
    if execute:
        client = NotebookClient(
            notebook,
            timeout=600,
            kernel_name="python3",
            resources={"metadata": {"path": str(directory)}},
        )
        client.execute()
        nbformat.write(notebook, destination)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the executed ETHUSD custom-indicator alpha notebook."
    )
    parser.add_argument("run_dir")
    parser.add_argument("--no-execute", action="store_true")
    args = parser.parse_args()
    destination = build_ethusd_custom_indicator_alpha_notebook(
        args.run_dir,
        execute=not args.no_execute,
    )
    print(destination)


if __name__ == "__main__":
    main()


__all__ = ["build_ethusd_custom_indicator_alpha_notebook"]
