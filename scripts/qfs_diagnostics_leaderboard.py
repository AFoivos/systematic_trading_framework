#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover - optional dependency guard for CLI use.
    yaml = None  # type: ignore[assignment]


METRIC_COLUMNS = [
    "run_dir",
    "run_name",
    "config_file",
    "cumulative_return",
    "net_pnl",
    "gross_pnl",
    "total_cost",
    "cost_to_gross_pnl",
    "profit_factor",
    "sharpe",
    "sortino",
    "max_drawdown",
    "hit_rate",
    "total_turnover",
    "executed_trade_count",
    "trade_rate",
    "roc_auc",
    "accuracy",
    "positive_rate",
    "target_candidate_rows",
    "target_positive_rate",
    "target_avg_hit_step",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a leaderboard for QFS diagnostic experiment runs.")
    parser.add_argument("--root", default="logs/experiments", help="Experiment logs root.")
    parser.add_argument("--top", type=int, default=30, help="Rows to print to stdout.")
    parser.add_argument("--csv", default="", help="Optional CSV output path.")
    args = parser.parse_args()

    rows = collect_rows(Path(args.root))
    rows.sort(
        key=lambda row: (
            _sort_number(row.get("net_pnl")),
            _sort_number(row.get("profit_factor")),
            _sort_number(row.get("sharpe")),
        ),
        reverse=True,
    )

    if args.csv:
        write_csv(Path(args.csv), rows)
    print_table(rows[: max(int(args.top), 0)])


def collect_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not root.exists():
        return rows
    for summary_path in sorted(root.glob("*/summary.json")):
        run_dir = summary_path.parent
        run_name = run_dir.name
        if "qfs" not in run_name and "quote_flow_proxy_scalp_meta" not in run_name:
            continue
        try:
            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows.append(build_row(run_dir, summary_payload))
    return rows


def build_row(run_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    primary = dict(_get(payload, "evaluation.primary_summary") or payload.get("summary") or {})
    model_meta = dict(payload.get("model_meta") or {})
    classification = dict(model_meta.get("oos_classification_summary") or {})
    target = dict(model_meta.get("target") or {})
    trade_diag = dict(_get(payload, "evaluation.trade_diagnostics") or {})

    row: dict[str, Any] = {column: None for column in METRIC_COLUMNS}
    row["run_dir"] = str(run_dir)
    row["run_name"] = run_dir.name
    row["config_file"] = resolve_config_file(run_dir)
    for metric in (
        "cumulative_return",
        "net_pnl",
        "gross_pnl",
        "total_cost",
        "cost_to_gross_pnl",
        "profit_factor",
        "sharpe",
        "sortino",
        "max_drawdown",
        "hit_rate",
        "total_turnover",
    ):
        row[metric] = primary.get(metric)
    row["executed_trade_count"] = (
        primary.get("executed_trade_count")
        or trade_diag.get("executed_trade_count")
        or trade_diag.get("trade_count")
    )
    row["trade_rate"] = primary.get("trade_rate") or trade_diag.get("trade_rate")
    row["roc_auc"] = classification.get("roc_auc")
    row["accuracy"] = classification.get("accuracy")
    row["positive_rate"] = classification.get("positive_rate")
    row["target_candidate_rows"] = target.get("candidate_rows")
    row["target_positive_rate"] = target.get("positive_rate")
    row["target_avg_hit_step"] = target.get("avg_hit_step")
    return row


def resolve_config_file(run_dir: Path) -> str | None:
    config_used = run_dir / "config_used.yaml"
    if not config_used.exists() or yaml is None:
        return config_used.name if config_used.exists() else None
    try:
        cfg = yaml.safe_load(config_used.read_text(encoding="utf-8")) or {}
    except Exception:
        return config_used.name
    run_name = str(_get(cfg, "logging.run_name") or _get(cfg, "strategy.name") or "")
    return f"{run_name}.yaml" if run_name else config_used.name


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=METRIC_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def print_table(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("No QFS diagnostic runs found.")
        return
    widths = {
        column: max(len(column), *(len(_format(row.get(column))) for row in rows))
        for column in METRIC_COLUMNS
    }
    print(" | ".join(column.ljust(widths[column]) for column in METRIC_COLUMNS))
    print("-+-".join("-" * widths[column] for column in METRIC_COLUMNS))
    for row in rows:
        print(" | ".join(_format(row.get(column)).ljust(widths[column]) for column in METRIC_COLUMNS))


def _get(payload: dict[str, Any], dotted_path: str) -> Any:
    current: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _sort_number(value: Any) -> float:
    try:
        if value is None:
            return float("-inf")
        return float(value)
    except (TypeError, ValueError):
        return float("-inf")


def _format(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


if __name__ == "__main__":
    main()
