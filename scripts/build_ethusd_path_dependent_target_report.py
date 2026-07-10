from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backtesting.manual_barrier import run_manual_barrier_backtest
from src.signals.forecast_signal import compute_forecast_threshold_candidates
from src.targets.path_dependent_r import build_path_dependent_r_target


DEFAULT_CONFIG = (
    ROOT
    / "config"
    / "experiments"
    / "foundation_alpha"
    / "BEST"
    / "ethusd"
    / "BEST_ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_trial_0054_manual_barrier.yaml"
)
DEFAULT_PROCESSED_DATASET = (
    ROOT
    / "data"
    / "processed"
    / "processed"
    / "ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_179ecc87_trial_0054"
    / "dataset.csv"
)
DEFAULT_REPORT = ROOT / "reports" / "ethusd_path_dependent_target_report.md"
DEFAULT_DATASET_OUT = ROOT / "reports" / "ethusd_path_dependent_target_dataset.csv"


def _latest_prediction_csv() -> Path:
    candidates = sorted(
        (ROOT / "logs" / "experiments").rglob("prediction_distribution.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("No prediction_distribution.csv artifact found under logs/experiments.")
    return candidates[0]


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Expected YAML mapping at {path}.")
    return payload


def _require_columns(df: pd.DataFrame, cols: list[str], *, label: str) -> None:
    missing = [col for col in cols if col not in df.columns]
    if missing:
        raise KeyError(f"{label} is missing required columns: {missing}")


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return str(int(value))
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if math.isnan(number):
            return ""
        if math.isinf(number):
            return str(number)
        if number == 0.0:
            return "0.0"
        if abs(number) >= 1000 or abs(number) < 1e-4:
            return f"{number:.6e}"
        return f"{number:.6f}"
    return str(value)


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "_None_\n"
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_fmt(value) for value in row) + " |")
    return "\n".join(lines) + "\n"


def _numeric_summary(series: pd.Series) -> list[Any]:
    values = pd.to_numeric(series, errors="coerce").dropna().astype(float)
    if values.empty:
        return [0, None, None, None, None, None, None, None]
    return [
        int(len(values)),
        float(values.mean()),
        float(values.median()),
        float(values.quantile(0.05)),
        float(values.quantile(0.25)),
        float(values.quantile(0.75)),
        float(values.quantile(0.95)),
        float((values > 0.0).mean()),
    ]


def _label_rows(frame: pd.DataFrame, label_cols: list[str]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for col in label_cols:
        values = pd.to_numeric(frame[col], errors="coerce").dropna()
        counts = values.astype(int).value_counts().sort_index()
        rows.append(
            [
                col,
                int(len(values)),
                int(counts.get(0, 0)),
                int(counts.get(1, 0)),
                float(values.mean()) if len(values) else None,
            ]
        )
    return rows


def _group_rows(frame: pd.DataFrame, by: str) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for key, group in frame.groupby(by, dropna=False):
        candidates = group.loc[group["meta_candidate"].fillna(0.0).astype(float) > 0.0]
        valid = candidates.loc[pd.to_numeric(candidates["meta_net_r"], errors="coerce").notna()]
        rows.append(
            [
                key,
                int(len(group)),
                int(len(candidates)),
                int(len(valid)),
                float(valid["meta_net_r"].mean()) if len(valid) else None,
                float(valid["meta_net_r"].median()) if len(valid) else None,
                float((valid["meta_net_r"] > 0.0).mean()) if len(valid) else None,
                int((valid["meta_exit_reason"] == "take_profit").sum()),
                int(valid["meta_exit_reason"].astype(str).str.contains("stop", regex=False).sum()),
                int((valid["meta_exit_reason"] == "max_holding_close").sum()),
            ]
        )
    return rows


def _agreement_check(
    frame: pd.DataFrame,
    *,
    signal_col: str,
    backtest_cfg: dict[str, Any],
    risk_cfg: dict[str, Any],
) -> dict[str, Any]:
    check_frame = frame.copy()
    check_frame[signal_col] = np.where(
        pd.to_numeric(check_frame["meta_net_r"], errors="coerce").notna(),
        pd.to_numeric(check_frame["primary_candidate_side"], errors="coerce").fillna(0.0),
        0.0,
    )
    result = run_manual_barrier_backtest(
        check_frame,
        signal_col=signal_col,
        open_col=str(backtest_cfg.get("open_col", "open")),
        high_col=str(backtest_cfg.get("high_col", "high")),
        low_col=str(backtest_cfg.get("low_col", "low")),
        close_col=str(backtest_cfg.get("close_col", "close")),
        take_profit_r=float(backtest_cfg.get("take_profit_r", 5.0)),
        stop_loss_r=float(backtest_cfg.get("stop_loss_r", 2.0)),
        risk_per_trade=float(backtest_cfg.get("risk_per_trade", 0.006)),
        max_holding_bars=backtest_cfg.get("max_holding_bars", 24),
        cost_per_unit_turnover=float(risk_cfg.get("cost_per_turnover", 0.0)),
        slippage_per_unit_turnover=float(risk_cfg.get("slippage_per_turnover", 0.0)),
        max_leverage=float(risk_cfg.get("max_leverage", 1.0)),
        periods_per_year=int(backtest_cfg.get("periods_per_year", 17520)),
        allow_short=bool(backtest_cfg.get("allow_short", False)),
        stop_mode=str(backtest_cfg.get("stop_mode", "volatility_stop")),
        vol_col=str(backtest_cfg.get("vol_col", "atr_over_price_48")),
    )
    trades = result.trades.copy() if result.trades is not None else pd.DataFrame()
    if trades.empty:
        return {
            "executed_trades": 0,
            "matched_target_rows": 0,
            "missing_target_rows": 0,
            "max_abs_trade_r_diff": None,
            "max_abs_entry_price_diff": None,
            "max_abs_exit_price_diff": None,
            "max_abs_bars_held_diff": None,
            "exit_reason_mismatches": 0,
        }

    lookup_cols = [
        "meta_net_r",
        "meta_entry_price",
        "meta_exit_price",
        "meta_holding_bars",
        "meta_exit_reason",
    ]
    target_lookup = frame.loc[:, lookup_cols].copy()
    joined = trades.merge(
        target_lookup,
        left_on="signal_timestamp",
        right_index=True,
        how="left",
    )
    matched = joined.loc[pd.to_numeric(joined["meta_net_r"], errors="coerce").notna()].copy()
    if matched.empty:
        return {
            "executed_trades": int(len(trades)),
            "matched_target_rows": 0,
            "missing_target_rows": int(len(trades)),
            "max_abs_trade_r_diff": None,
            "max_abs_entry_price_diff": None,
            "max_abs_exit_price_diff": None,
            "max_abs_bars_held_diff": None,
            "exit_reason_mismatches": int(len(trades)),
        }

    return {
        "executed_trades": int(len(trades)),
        "matched_target_rows": int(len(matched)),
        "missing_target_rows": int(len(trades) - len(matched)),
        "max_abs_trade_r_diff": float((matched["trade_r"] - matched["meta_net_r"]).abs().max()),
        "max_abs_entry_price_diff": float((matched["entry_price"] - matched["meta_entry_price"]).abs().max()),
        "max_abs_exit_price_diff": float((matched["exit_price"] - matched["meta_exit_price"]).abs().max()),
        "max_abs_bars_held_diff": float((matched["bars_held"] - matched["meta_holding_bars"]).abs().max()),
        "exit_reason_mismatches": int((matched["exit_reason"].astype(str) != matched["meta_exit_reason"].astype(str)).sum()),
    }


def _load_analysis_frame(
    *,
    processed_dataset: Path,
    prediction_csv: Path,
    cfg: dict[str, Any],
) -> pd.DataFrame:
    signal_params = dict(dict(cfg.get("signals", {}) or {}).get("params", {}) or {})
    backtest_cfg = dict(cfg.get("backtest", {}) or {})
    activation_filters = list(signal_params.get("activation_filters", []) or [])
    filter_cols = [str(item["col"]) for item in activation_filters if isinstance(item, dict) and item.get("col")]
    required_processed = [
        "timestamp",
        "asset",
        str(backtest_cfg.get("open_col", "open")),
        str(backtest_cfg.get("high_col", "high")),
        str(backtest_cfg.get("low_col", "low")),
        str(backtest_cfg.get("close_col", "close")),
        str(backtest_cfg.get("vol_col", "atr_over_price_48")),
        *filter_cols,
    ]
    required_processed = list(dict.fromkeys(required_processed))
    processed = pd.read_csv(processed_dataset, usecols=lambda col: col in set(required_processed))
    _require_columns(processed, required_processed, label="processed dataset")
    processed["timestamp"] = pd.to_datetime(processed["timestamp"])
    processed = processed.sort_values(["asset", "timestamp"]).reset_index(drop=True)

    prediction = pd.read_csv(prediction_csv, usecols=["timestamp", "asset", "prediction", "realized", "residual"])
    _require_columns(prediction, ["timestamp", "asset", "prediction"], label="prediction artifact")
    prediction["timestamp"] = pd.to_datetime(prediction["timestamp"])
    prediction = prediction.rename(columns={"prediction": "pred_ret"})
    prediction = prediction.sort_values(["asset", "timestamp"]).reset_index(drop=True)
    split_cfg = dict(dict(cfg.get("model", {}) or {}).get("split", {}) or {})
    test_size = int(split_cfg.get("test_size") or 0)
    if test_size > 0:
        prediction["walk_forward_fold"] = (np.arange(len(prediction)) // test_size) + 1
    else:
        prediction["walk_forward_fold"] = np.nan
    prediction["pred_is_oos"] = True

    merged = processed.merge(
        prediction[["timestamp", "asset", "pred_ret", "pred_is_oos", "walk_forward_fold"]],
        on=["timestamp", "asset"],
        how="left",
        validate="one_to_one",
    )
    merged["pred_is_oos"] = merged["pred_is_oos"].where(merged["pred_is_oos"].notna(), False).astype(bool)
    return merged.sort_values(["asset", "timestamp"]).set_index("timestamp", drop=False)


def build_report(
    *,
    config_path: Path,
    processed_dataset: Path,
    prediction_csv: Path,
    report_path: Path,
    dataset_out: Path,
) -> dict[str, Any]:
    cfg = _load_yaml(config_path)
    signal_params = dict(dict(cfg.get("signals", {}) or {}).get("params", {}) or {})
    backtest_cfg = dict(cfg.get("backtest", {}) or {})
    risk_cfg = dict(cfg.get("risk", {}) or {})

    frame = _load_analysis_frame(
        processed_dataset=processed_dataset,
        prediction_csv=prediction_csv,
        cfg=cfg,
    )
    candidate_frame = compute_forecast_threshold_candidates(
        frame,
        forecast_col=str(signal_params.get("forecast_col", "pred_ret")),
        pred_is_oos_col=str(dict(cfg.get("model", {}) or {}).get("pred_is_oos_col", "pred_is_oos")),
        upper=float(signal_params.get("upper", 0.7)),
        lower=float(signal_params.get("lower", -0.85)),
        mode=str(signal_params.get("mode", "long_short")),
        activation_filters=list(signal_params.get("activation_filters", []) or []),
    )
    target_cfg = {
        "kind": "path_dependent_r",
        "candidate_col": "primary_candidate",
        "side_col": "primary_candidate_side",
        "pred_is_oos_col": str(dict(cfg.get("model", {}) or {}).get("pred_is_oos_col", "pred_is_oos")),
        "require_oos": True,
        "open_col": str(backtest_cfg.get("open_col", "open")),
        "high_col": str(backtest_cfg.get("high_col", "high")),
        "low_col": str(backtest_cfg.get("low_col", "low")),
        "close_col": str(backtest_cfg.get("close_col", "close")),
        "volatility_col": str(backtest_cfg.get("vol_col", "atr_over_price_48")),
        "stop_mode": str(backtest_cfg.get("stop_mode", "volatility_stop")),
        "take_profit_r": float(backtest_cfg.get("take_profit_r", 5.0)),
        "stop_loss_r": float(backtest_cfg.get("stop_loss_r", 2.0)),
        "max_holding_bars": backtest_cfg.get("max_holding_bars", 24),
        "risk_per_trade": float(backtest_cfg.get("risk_per_trade", 0.006)),
        "cost_per_unit_turnover": float(risk_cfg.get("cost_per_turnover", 0.0)),
        "slippage_per_unit_turnover": float(risk_cfg.get("slippage_per_turnover", 0.0)),
        "max_leverage": float(risk_cfg.get("max_leverage", 1.0)),
        "entry_price_mode": "next_open",
        "tie_break": "conservative",
        "allow_partial_horizon": False,
        "legacy_same_bar_stop_reason": True,
    }
    target_frame, _, _, target_meta = build_path_dependent_r_target(candidate_frame, target_cfg)
    oos_frame = target_frame.loc[target_frame["pred_is_oos"].astype(bool)].copy()
    oos_frame["year"] = pd.to_datetime(oos_frame["timestamp"]).dt.year
    oos_frame["side_name"] = np.select(
        [
            pd.to_numeric(oos_frame["meta_side"], errors="coerce") > 0.0,
            pd.to_numeric(oos_frame["meta_side"], errors="coerce") < 0.0,
        ],
        ["long", "short"],
        default="none",
    )
    candidate_rows = oos_frame.loc[pd.to_numeric(oos_frame["meta_candidate"], errors="coerce").fillna(0.0) > 0.0]
    valid_rows = candidate_rows.loc[pd.to_numeric(candidate_rows["meta_net_r"], errors="coerce").notna()]
    invalid_rows = candidate_rows.loc[pd.to_numeric(candidate_rows["meta_net_r"], errors="coerce").isna()]
    agreement = _agreement_check(
        target_frame,
        signal_col=str(backtest_cfg.get("signal_col", "signal_structured_tail")),
        backtest_cfg=backtest_cfg,
        risk_cfg=risk_cfg,
    )

    dataset_out.parent.mkdir(parents=True, exist_ok=True)
    output_cols = [
        "timestamp",
        "asset",
        "walk_forward_fold",
        "pred_ret",
        "pred_is_oos",
        "open",
        "high",
        "low",
        "close",
        str(backtest_cfg.get("vol_col", "atr_over_price_48")),
        "atr_pct_rank_192",
        "range_to_atr",
        "bollinger_bandwidth_rank_192",
        "primary_candidate",
        "primary_candidate_side",
        "primary_candidate_strength",
        "primary_candidate_threshold_distance",
        *target_meta["output_cols"],
    ]
    output_cols = [col for col in dict.fromkeys(output_cols) if col in oos_frame.columns]
    oos_frame.loc[:, output_cols].to_csv(dataset_out, index=False)

    summary_rows = [
        ["OOS prediction rows", int(len(oos_frame))],
        ["Candidate rows", int(len(candidate_rows))],
        ["Valid labeled candidates", int(len(valid_rows))],
        ["Invalid/unavailable candidates", int(len(invalid_rows))],
        ["Long candidates", int((candidate_rows["meta_side"].astype(float) > 0.0).sum())],
        ["Short candidates", int((candidate_rows["meta_side"].astype(float) < 0.0).sum())],
        ["Win rate, net R > 0", float((valid_rows["meta_net_r"] > 0.0).mean()) if len(valid_rows) else None],
        ["Mean net R", float(valid_rows["meta_net_r"].mean()) if len(valid_rows) else None],
        ["Median net R", float(valid_rows["meta_net_r"].median()) if len(valid_rows) else None],
    ]
    label_cols = [
        "meta_label_positive",
        "meta_label_min_0_25r",
        "meta_label_min_0_50r",
        "meta_label_min_1_00r",
    ]
    distribution_rows = [
        ["meta_net_r", *_numeric_summary(valid_rows["meta_net_r"])],
        ["meta_gross_r", *_numeric_summary(valid_rows["meta_gross_r"])],
        ["meta_mfe_r", *_numeric_summary(valid_rows["meta_mfe_r"])],
        ["meta_mae_r", *_numeric_summary(valid_rows["meta_mae_r"])],
    ]
    exit_rows = [
        [reason, int(count)]
        for reason, count in valid_rows["meta_exit_reason"].value_counts(dropna=True).sort_index().items()
    ]
    invalid_reason_rows = [
        [reason, int(count)]
        for reason, count in invalid_rows["meta_exit_reason"].value_counts(dropna=True).sort_index().items()
    ]
    agreement_rows = [[key, value] for key, value in agreement.items()]

    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# ETHUSD Path-Dependent Candidate Target Report",
        "",
        "This report evaluates an OOS-only candidate target layer for the existing ETHUSD 30m LightGBM strategy.",
        "The primary model target, features, thresholds, activation filters, and manual-barrier trade management are read from the locked baseline YAML and are not modified by this report.",
        "",
        "## Inputs",
        _table(
            ["Artifact", "Path"],
            [
                ["Locked baseline config", str(config_path)],
                ["Processed OHLC/features", str(processed_dataset)],
                ["OOS prediction artifact", str(prediction_csv)],
                ["Candidate/outcome CSV", str(dataset_out)],
            ],
        ),
        "## Strategy Contract",
        _table(
            ["Parameter", "Value"],
            [
                ["signal.kind", dict(cfg.get("signals", {}) or {}).get("kind")],
                ["forecast_col", signal_params.get("forecast_col", "pred_ret")],
                ["upper", signal_params.get("upper")],
                ["lower", signal_params.get("lower")],
                ["mode", signal_params.get("mode")],
                ["activation_filters", signal_params.get("activation_filters")],
                ["backtest.engine", backtest_cfg.get("engine")],
                ["stop_mode", backtest_cfg.get("stop_mode")],
                ["vol_col", backtest_cfg.get("vol_col")],
                ["take_profit_r", backtest_cfg.get("take_profit_r")],
                ["stop_loss_r", backtest_cfg.get("stop_loss_r")],
                ["max_holding_bars", backtest_cfg.get("max_holding_bars")],
                ["risk_per_trade", backtest_cfg.get("risk_per_trade")],
                ["allow_short", backtest_cfg.get("allow_short")],
                ["cost_per_turnover", risk_cfg.get("cost_per_turnover")],
                ["slippage_per_turnover", risk_cfg.get("slippage_per_turnover")],
            ],
        ),
        "Causal convention: signal at close t, entry at open t+1, then future high/low/close path is evaluated up to the configured max holding. Same-bar TP/SL ties use the conservative manual-barrier convention.",
        "",
        "## Overall Summary",
        _table(["Metric", "Value"], summary_rows),
        "## Net R and Path Distribution",
        _table(["Metric", "Rows", "Mean", "Median", "Q05", "Q25", "Q75", "Q95", "Positive rate"], distribution_rows),
        "## Label Balance",
        _table(["Label", "Rows", "Class 0", "Class 1", "Positive rate"], _label_rows(oos_frame, label_cols)),
        "## Exit Reasons",
        _table(["Exit reason", "Count"], exit_rows),
        "## Invalid or Tail Candidates",
        _table(["Reason", "Count"], invalid_reason_rows),
        "## Long/Short Breakdown",
        _table(
            [
                "Side",
                "OOS rows",
                "Candidates",
                "Valid labels",
                "Mean net R",
                "Median net R",
                "Win rate",
                "TP",
                "Stop",
                "Time exit",
            ],
            _group_rows(oos_frame, "side_name"),
        ),
        "## By Year",
        _table(
            [
                "Year",
                "OOS rows",
                "Candidates",
                "Valid labels",
                "Mean net R",
                "Median net R",
                "Win rate",
                "TP",
                "Stop",
                "Time exit",
            ],
            _group_rows(oos_frame, "year"),
        ),
        "## By Walk-Forward Fold",
        _table(
            [
                "Fold",
                "OOS rows",
                "Candidates",
                "Valid labels",
                "Mean net R",
                "Median net R",
                "Win rate",
                "TP",
                "Stop",
                "Time exit",
            ],
            _group_rows(oos_frame, "walk_forward_fold"),
        ),
        "## Manual-Barrier Agreement Check",
        "The check reruns `run_manual_barrier_backtest` on valid candidate rows only and compares executed, non-overlapping trades with their target rows.",
        _table(["Check", "Value"], agreement_rows),
        "## Notes",
        "- Labels are populated only on OOS rows that become primary candidates and have a complete future path.",
        "- Non-candidate rows keep NaN `meta_*` outcomes and NaN labels in the target output.",
        "- The compact CSV includes all OOS prediction rows, candidate metadata, path outcomes, and label columns.",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "report_path": str(report_path),
        "dataset_path": str(dataset_out),
        "candidate_rows": int(len(candidate_rows)),
        "valid_rows": int(len(valid_rows)),
        "agreement": agreement,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--processed-dataset", type=Path, default=DEFAULT_PROCESSED_DATASET)
    parser.add_argument("--prediction-csv", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--dataset-out", type=Path, default=DEFAULT_DATASET_OUT)
    args = parser.parse_args()

    prediction_csv = args.prediction_csv or _latest_prediction_csv()
    result = build_report(
        config_path=args.config,
        processed_dataset=args.processed_dataset,
        prediction_csv=prediction_csv,
        report_path=args.report,
        dataset_out=args.dataset_out,
    )
    print(yaml.safe_dump(result, sort_keys=False).rstrip())


if __name__ == "__main__":
    main()
