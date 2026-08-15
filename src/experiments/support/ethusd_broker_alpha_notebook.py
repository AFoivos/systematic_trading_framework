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


def build_ethusd_broker_alpha_notebook(
    run_dir: str | Path,
    *,
    execute: bool = True,
) -> Path:
    """Build and optionally execute the frozen-artifact analysis notebook."""

    directory = Path(run_dir)
    if not directory.is_absolute():
        directory = PROJECT_ROOT / directory
    directory = enforce_safe_absolute_path(directory.resolve())
    if not (directory / "summary.json").is_file():
        raise FileNotFoundError(f"Suite summary not found in {directory}")
    destination = directory / "ethusd_broker_alpha_report.ipynb"

    notebook = nbformat.v4.new_notebook()
    notebook["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3"},
    }
    notebook["cells"] = [
        _markdown(
            """
# ETHUSD cTrader broker-data alpha validation

## TL;DR

This notebook is a runnable companion to the frozen Model-07 cTrader-transfer suite. It does not tune a model, threshold, gate, or stress scenario. It reloads the immutable v3 outputs and verifies the decision from three separate evidence layers: cross-feed transfer, approximate OOT bars, and exact bid/ask ticks.
"""
        ),
        _markdown(
            """
## Context & methods

- Signal contract: unchanged Model-07 feature list, LightGBM artifact, activation filters, thresholds, and 24-bar minimum holding period.
- Causality: a feature at M30 bar-open timestamp `t` uses that completed bar and becomes executable at `t+30m`.
- Exact fills: long ask→bid and short bid→ask, first quote at/after decision plus delay, rejected when quote wait exceeds 120 seconds.
- Robustness grid: 0/60/120/300-second delays × 1x/2x observed spread × 0/1 bp per-side slippage; 0.5 bp commission per side.
- Decision metrics: `conventional_sharpe`, cumulative return, drawdown, trade count, full-grid stress survival, and sample-readiness gates.
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

cwd = Path.cwd().resolve()
PROJECT_ROOT = next(path for path in [cwd, *cwd.parents] if (path / "src").is_dir())
RUN_DIR = PROJECT_ROOT / "logs/experiments/ethusd_broker_alpha_suite_20260811_full_v3"

summary = json.loads((RUN_DIR / "summary.json").read_text(encoding="utf-8"))
inventory = pd.read_csv(RUN_DIR / "data_inventory.csv")
feature_transfer = pd.read_csv(RUN_DIR / "feature_transfer.csv")
stress = pd.read_csv(RUN_DIR / "tick_stress_metrics.csv")
ledger = pd.read_csv(RUN_DIR / "tick_trade_ledger_base.csv", parse_dates=["entry_timestamp", "exit_timestamp"])
meta_samples = pd.read_csv(RUN_DIR / "meta_label_samples.csv")

display(Markdown(f"**Verdict:** {summary['research_verdict']}"))
"""
        ),
        _markdown(
            """
## Data

Every cTrader source file is hashed in `provenance.json`. Bar timestamps are explicitly assumed to be UTC bar-open times for this run, the final exported bar is excluded, and missing minutes are never filled. The exporter timezone still requires confirmation from the cTrader terminal settings.
"""
        ),
        _code(
            """
display(inventory)
quality = summary["data_quality"]
consistency = pd.DataFrame(quality["timeframe_consistency"]).T.reset_index(names="timeframe")
display(consistency[["timeframe", "common_rows", "ohlc_match_rate", "ohlc_mismatch_count", "tick_volume_match_rate"]])
"""
        ),
        _markdown(
            """
## Results — evidence hierarchy

Cross-feed agreement tests whether the feature/model contract transfers mechanically. It is not a return test. The approximate OOT layer covers all cTrader M30 bars after the frozen training cutoff. The exact layer is authoritative for execution but is limited to trades whose entry and exit both lie inside the cTrader tick export.
"""
        ),
        _code(
            """
transfer = summary["prediction_transfer"]
approximate = summary["approximate_oot"]
exact = summary["exact_tick_base"]
overview = pd.DataFrame([
    {
        "layer": "cross-feed transfer",
        "coverage": transfer["common_timestamps"],
        "cumulative_return": np.nan,
        "conventional_sharpe": np.nan,
        "max_drawdown": np.nan,
        "note": f"prediction corr={transfer['prediction_pearson_correlation']:.3f}",
    },
    {
        "layer": "approximate OOT bars",
        "coverage": approximate["bars"],
        "cumulative_return": approximate["cumulative_return"],
        "conventional_sharpe": approximate["conventional_sharpe"],
        "max_drawdown": approximate["max_drawdown"],
        "note": "close-to-close + observed median spread assumption",
    },
    {
        "layer": "exact side-aware ticks",
        "coverage": exact["trade_count"],
        "cumulative_return": exact["cumulative_return"],
        "conventional_sharpe": exact["conventional_sharpe"],
        "max_drawdown": exact["max_drawdown"],
        "note": "closed trades inside tick coverage",
    },
])
display(overview)
"""
        ),
        _markdown("## Results — feature transfer drift"),
        _code(
            """
top_drift = feature_transfer.sort_values("psi", ascending=False).head(15).sort_values("psi")
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
axes[0].barh(top_drift["feature"], top_drift["psi"], color="#355C7D")
axes[0].set_title("Largest cross-feed PSI values")
axes[0].set_xlabel("PSI")
axes[1].hist(feature_transfer["pearson_correlation"].dropna(), bins=18, color="#6C5B7B", edgecolor="white")
axes[1].set_title("Feature-level cross-feed correlations")
axes[1].set_xlabel("Pearson correlation")
axes[1].set_ylabel("Feature count")
plt.tight_layout()
plt.show()
display(feature_transfer.sort_values("psi", ascending=False).head(15))
"""
        ),
        _markdown("## Results — exact trade path and stress grid"),
        _code(
            """
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
if not ledger.empty:
    equity = (1.0 + ledger.sort_values("exit_timestamp")["net_return"]).cumprod()
    axes[0].plot(ledger.sort_values("exit_timestamp")["exit_timestamp"], equity, marker="o", color="#C06C84")
    axes[0].axhline(1.0, color="black", linewidth=0.8)
axes[0].set_title("Base exact-tick trade equity")
axes[0].set_ylabel("Equity from 1.0")

pivot = stress.pivot_table(
    index=["delay_seconds", "spread_multiplier"],
    columns="slippage_bps_per_side",
    values="cumulative_return",
).sort_index()
pivot.plot(kind="bar", ax=axes[1], color=["#355C7D", "#F67280"])
axes[1].axhline(0.0, color="black", linewidth=0.8)
axes[1].set_title("Cumulative return across all 16 stresses")
axes[1].set_ylabel("Net cumulative return")
axes[1].legend(title="slippage bp/side")
plt.tight_layout()
plt.show()
display(stress[["scenario_id", "trade_count", "cumulative_return", "conventional_sharpe", "max_drawdown"]].sort_values("cumulative_return"))
"""
        ),
        _markdown(
            """
## Model/validation details

The M1 gate and meta-label branches are intentionally sample-gated. A failed readiness gate is a valid result, not a reason to lower requirements. Barrier outcomes use the side-specific executable quote over a fixed 12-hour, 1-ATR first-passage window; timeouts remain unlabeled.
"""
        ),
        _code(
            """
meta_status = json.loads((RUN_DIR / "meta_label_status.json").read_text(encoding="utf-8"))
gate_status = json.loads((RUN_DIR / "m1_gate_status.json").read_text(encoding="utf-8"))
barrier_counts = meta_samples["barrier_1atr_outcome_12h"].value_counts(dropna=False) if not meta_samples.empty else pd.Series(dtype=int)
display(pd.DataFrame([
    {"branch": "M1 chronological gates", "status": gate_status["status"], "reason": gate_status.get("reason", "")},
    {"branch": "logistic meta-label", "status": meta_status["status"], "reason": meta_status["reason"]},
]))
display(barrier_counts.rename("trades").to_frame())
"""
        ),
        _markdown(
            """
## Limitations & robustness

- Only nine exact closed trades are available. No inference about persistence is justified.
- The exact base result is negative, and all 16 predeclared stress scenarios are negative.
- The tick history appears capped at 2,000,000 rows; M1 also appears capped. This creates coverage selection risk.
- cTrader `tick_volume` is only a mechanical substitute for the Model-07 VWAP feature and is not cross-provider economic volume.
- Swap, rejected fills, market impact, account-level FTMO loss controls, and prospective live behavior are not in this ledger.
"""
        ),
        _markdown(
            """
## Takeaways

1. The new data materially improves falsification power, not the strategy's measured alpha: the frozen signal is negative in both approximate OOT bars and exact ticks.
2. Feature/prediction transfer is reasonably high, so the failure cannot be dismissed as a completely broken feed mapping; active-signal Jaccard remains only moderate.
3. M1 timing and meta-labeling are now implemented but correctly remain inactive because nine trades do not satisfy the predeclared readiness gates.
4. The next valid experiment is prospective append-only data collection with the model/config hashes frozen. Threshold search on these nine trades would manufacture alpha.

### Exact rerun command

```bash
docker compose run --rm app python -m src.experiments.support.ethusd_broker_alpha --output-dir logs/experiments/<new-run-id>
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
    parser = argparse.ArgumentParser(description="Build the executed ETHUSD broker alpha notebook.")
    parser.add_argument("run_dir")
    parser.add_argument("--no-execute", action="store_true")
    args = parser.parse_args()
    destination = build_ethusd_broker_alpha_notebook(args.run_dir, execute=not args.no_execute)
    print(destination)


if __name__ == "__main__":
    main()


__all__ = ["build_ethusd_broker_alpha_notebook"]
