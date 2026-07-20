from __future__ import annotations

"""Supervised trade-evaluation targets backed by the shared barrier simulator."""

from typing import Any

import numpy as np
import pandas as pd

from src.targets.output_aliases import apply_target_output_aliases
from src.targets.path_dependent_r import build_path_dependent_r_target


TRADE_EVALUATION_TARGET_KINDS = frozenset(
    {
        "expected_realized_r",
        "target_before_stop_probability",
        "trade_mfe_mae_regression",
    }
)

TRADE_EVALUATION_REGRESSION_TARGET_KINDS = frozenset(
    {"expected_realized_r", "trade_mfe_mae_regression"}
)


_DEFAULT_OUTPUTS = {
    "meta_candidate_col": "target_trade_candidate",
    "meta_side_col": "target_trade_side",
    "entry_price_col": "target_entry_price",
    "exit_price_col": "target_exit_price",
    "exit_reason_col": "target_exit_reason",
    "hit_type_col": "target_hit_type",
    "hit_step_col": "target_hit_step",
    "holding_bars_col": "target_holding_bars",
    "gross_return_col": "target_gross_return",
    "net_return_col": "target_net_return",
    "gross_r_col": "target_gross_r",
    "net_r_col": "target_realized_r",
    "mfe_r_col": "target_mfe_r",
    "mae_r_col": "target_mae_r",
    "positive_label_col": "__target_trade_positive",
    "min_025_label_col": "__target_trade_min_0_25r",
    "min_050_label_col": "__target_trade_min_0_50r",
    "min_100_label_col": "__target_trade_min_1_00r",
}


def _flatten_cfg(target_cfg: dict[str, Any] | None) -> dict[str, Any]:
    cfg = dict(target_cfg or {})
    params = cfg.pop("params", None)
    if params is not None:
        if not isinstance(params, dict):
            raise ValueError("trade-evaluation target params must be a mapping when provided.")
        cfg.update(dict(params))
    return apply_target_output_aliases(cfg)


def _non_empty_col(value: Any, default: str, *, field: str) -> str:
    resolved = default if value is None else str(value)
    if not resolved.strip():
        raise ValueError(f"trade-evaluation target {field} must be a non-empty string.")
    return resolved.strip()


def _finite_positive(value: Any, *, field: str) -> float:
    resolved = float(value)
    if not np.isfinite(resolved) or resolved <= 0.0:
        raise ValueError(f"trade-evaluation target {field} must be finite and > 0.")
    return resolved


def _finite_non_negative(value: Any, *, field: str) -> float:
    resolved = float(value)
    if not np.isfinite(resolved) or resolved < 0.0:
        raise ValueError(f"trade-evaluation target {field} must be finite and >= 0.")
    return resolved


def _numeric_summary(series: pd.Series) -> dict[str, float | int | None]:
    values = pd.to_numeric(series, errors="coerce")
    values = values.loc[np.isfinite(values)].astype(float)
    if values.empty:
        return {
            "rows": 0,
            "mean": None,
            "median": None,
            "q05": None,
            "q25": None,
            "q75": None,
            "q95": None,
            "positive_rate": None,
        }
    return {
        "rows": int(len(values)),
        "mean": float(values.mean()),
        "median": float(values.median()),
        "q05": float(values.quantile(0.05)),
        "q25": float(values.quantile(0.25)),
        "q75": float(values.quantile(0.75)),
        "q95": float(values.quantile(0.95)),
        "positive_rate": float((values > 0.0).mean()),
    }


def _resolved_common_cfg(target_cfg: dict[str, Any] | None) -> dict[str, Any]:
    cfg = _flatten_cfg(target_cfg)
    cfg.setdefault("candidate_col", "signal_candidate")
    cfg.setdefault("side_col", "signal_side")
    cfg.setdefault("open_col", "open")
    cfg.setdefault("high_col", "high")
    cfg.setdefault("low_col", "low")
    cfg.setdefault("close_col", cfg.get("price_col", "close"))
    cfg.setdefault("volatility_col", "atr_over_price_14")
    cfg.setdefault("entry_price_mode", "next_open")
    cfg.setdefault("stop_mode", "volatility_stop")
    cfg.setdefault("tie_break", "conservative")
    cfg.setdefault("take_profit_r", 2.0)
    cfg.setdefault("stop_loss_r", 1.0)
    cfg.setdefault("risk_per_trade", 0.006)
    cfg.setdefault("max_leverage", 1.0)
    cfg.setdefault("max_holding_bars", cfg.get("max_holding", 24))
    cfg.setdefault("cost_per_unit_turnover", cfg.get("cost_per_turnover", 0.0))
    cfg.setdefault("slippage_per_unit_turnover", cfg.get("slippage_per_turnover", 0.0))
    cfg.setdefault("allow_partial_horizon", False)
    cfg.setdefault("require_oos", False)
    cfg.setdefault("apply_risk_sizing", False)
    cfg.setdefault("strict_path_validation", True)

    for field in (
        "candidate_col",
        "side_col",
        "open_col",
        "high_col",
        "low_col",
        "close_col",
        "volatility_col",
    ):
        cfg[field] = _non_empty_col(cfg.get(field), str(cfg[field]), field=field)

    if cfg["entry_price_mode"] not in {"next_open", "current_close"}:
        raise ValueError(
            "trade-evaluation target entry_price_mode must be one of: next_open, current_close."
        )
    if cfg["stop_mode"] not in {"volatility_stop", "fixed_return"}:
        raise ValueError(
            "trade-evaluation target stop_mode must be one of: volatility_stop, fixed_return."
        )
    if cfg["tie_break"] not in {"conservative", "take_profit", "stop_loss", "closest_to_open"}:
        raise ValueError(
            "trade-evaluation target tie_break must be one of: conservative, take_profit, "
            "stop_loss, closest_to_open."
        )

    for field in ("take_profit_r", "stop_loss_r", "risk_per_trade", "max_leverage"):
        cfg[field] = _finite_positive(cfg[field], field=field)
    for field in ("cost_per_unit_turnover", "slippage_per_unit_turnover"):
        cfg[field] = _finite_non_negative(cfg[field], field=field)

    max_holding = cfg.get("max_holding_bars")
    if isinstance(max_holding, bool) or not isinstance(max_holding, int) or max_holding <= 0:
        raise ValueError("trade-evaluation target max_holding_bars must be a positive integer.")
    for field in (
        "allow_partial_horizon",
        "require_oos",
        "apply_risk_sizing",
        "strict_path_validation",
    ):
        if not isinstance(cfg.get(field), bool):
            raise ValueError(f"trade-evaluation target {field} must be boolean.")
    return cfg


def _path_output_config(cfg: dict[str, Any]) -> dict[str, str]:
    outputs: dict[str, str] = {}
    for key, default in _DEFAULT_OUTPUTS.items():
        outputs[key] = _non_empty_col(cfg.get(key), default, field=key)
    return outputs


def _strict_path_invalid_positions(
    df: pd.DataFrame,
    out: pd.DataFrame,
    *,
    cfg: dict[str, Any],
    outputs: dict[str, str],
) -> list[int]:
    if not bool(cfg["strict_path_validation"]):
        return []

    ohlc = df[
        [str(cfg["open_col"]), str(cfg["high_col"]), str(cfg["low_col"]), str(cfg["close_col"])]
    ].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    candidates = out[outputs["meta_candidate_col"]].fillna(0.0).to_numpy(dtype=float) > 0.0
    hit_steps = pd.to_numeric(out[outputs["hit_step_col"]], errors="coerce").to_numpy(dtype=float)
    net_r = pd.to_numeric(out[outputs["net_r_col"]], errors="coerce").to_numpy(dtype=float)
    entry_offset = 1 if cfg["entry_price_mode"] == "next_open" else 0
    path_offset = 1
    invalid: list[int] = []

    for signal_idx in np.flatnonzero(candidates & np.isfinite(net_r)):
        hit_step = hit_steps[signal_idx]
        if not np.isfinite(hit_step):
            invalid.append(int(signal_idx))
            continue
        entry_idx = int(signal_idx) + entry_offset
        path_start_idx = int(signal_idx) + path_offset
        exit_idx = entry_idx + int(hit_step)
        if exit_idx < path_start_idx or exit_idx >= len(df):
            invalid.append(int(signal_idx))
            continue
        if not np.isfinite(ohlc[path_start_idx : exit_idx + 1]).all():
            invalid.append(int(signal_idx))
    return invalid


def _invalidate_paths(
    out: pd.DataFrame,
    *,
    invalid_positions: list[int],
    outputs: dict[str, str],
) -> None:
    if not invalid_positions:
        return
    numeric_keys = (
        "entry_price_col",
        "exit_price_col",
        "hit_step_col",
        "holding_bars_col",
        "gross_return_col",
        "net_return_col",
        "gross_r_col",
        "net_r_col",
        "mfe_r_col",
        "mae_r_col",
        "positive_label_col",
        "min_025_label_col",
        "min_050_label_col",
        "min_100_label_col",
    )
    for position in invalid_positions:
        row_label = out.index[position]
        for key in numeric_keys:
            out.at[row_label, outputs[key]] = np.nan
        out.at[row_label, outputs["exit_reason_col"]] = "invalid_future_path"
        out.at[row_label, outputs["hit_type_col"]] = "invalid_future_path"


def _add_risk_level_columns(
    df: pd.DataFrame,
    out: pd.DataFrame,
    *,
    cfg: dict[str, Any],
    outputs: dict[str, str],
) -> tuple[str, str, str]:
    risk_distance_col = _non_empty_col(
        cfg.get("risk_distance_col"), "target_stop_distance", field="risk_distance_col"
    )
    stop_price_col = _non_empty_col(
        cfg.get("stop_price_col"), "target_stop_price", field="stop_price_col"
    )
    take_profit_price_col = _non_empty_col(
        cfg.get("take_profit_price_col"),
        "target_take_profit_price",
        field="take_profit_price_col",
    )

    n = len(df)
    risk_distance = np.full(n, np.nan, dtype=float)
    stop_price = np.full(n, np.nan, dtype=float)
    take_profit_price = np.full(n, np.nan, dtype=float)
    candidates = out[outputs["meta_candidate_col"]].fillna(0.0).to_numpy(dtype=float) > 0.0
    valid = pd.to_numeric(out[outputs["net_r_col"]], errors="coerce").notna().to_numpy(dtype=bool)
    sides = pd.to_numeric(out[outputs["meta_side_col"]], errors="coerce").to_numpy(dtype=float)
    opens = pd.to_numeric(df[str(cfg["open_col"])], errors="coerce").to_numpy(dtype=float)
    closes = pd.to_numeric(df[str(cfg["close_col"])], errors="coerce").to_numpy(dtype=float)
    volatility = (
        pd.to_numeric(df[str(cfg["volatility_col"])], errors="coerce").to_numpy(dtype=float)
        if cfg["stop_mode"] == "volatility_stop"
        else None
    )

    for signal_idx in np.flatnonzero(candidates & valid):
        entry_idx = int(signal_idx) + (1 if cfg["entry_price_mode"] == "next_open" else 0)
        raw_entry = float(opens[entry_idx] if cfg["entry_price_mode"] == "next_open" else closes[signal_idx])
        if cfg["stop_mode"] == "volatility_stop":
            assert volatility is not None
            stop_distance_pct = float(volatility[signal_idx]) * float(cfg["stop_loss_r"])
            target_distance_pct = float(volatility[signal_idx]) * float(cfg["take_profit_r"])
        else:
            stop_distance_pct = float(cfg["risk_per_trade"]) * float(cfg["stop_loss_r"])
            target_distance_pct = float(cfg["risk_per_trade"]) * float(cfg["take_profit_r"])
        distance = raw_entry * stop_distance_pct
        risk_distance[signal_idx] = distance
        if sides[signal_idx] > 0.0:
            stop_price[signal_idx] = raw_entry - distance
            take_profit_price[signal_idx] = raw_entry * (1.0 + target_distance_pct)
        else:
            stop_price[signal_idx] = raw_entry + distance
            take_profit_price[signal_idx] = raw_entry * (1.0 - target_distance_pct)

    out[risk_distance_col] = risk_distance
    out[stop_price_col] = stop_price
    out[take_profit_price_col] = take_profit_price
    return risk_distance_col, stop_price_col, take_profit_price_col


def _build_trade_evaluation(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, dict[str, Any], dict[str, str], dict[str, Any]]:
    cfg = _resolved_common_cfg(target_cfg)
    outputs = _path_output_config(cfg)
    path_cfg = dict(cfg)
    path_cfg["kind"] = "path_dependent_r"
    path_cfg.update(outputs)

    out, _, _, path_meta = build_path_dependent_r_target(df, path_cfg)
    invalid_positions = _strict_path_invalid_positions(
        df,
        out,
        cfg=cfg,
        outputs=outputs,
    )
    _invalidate_paths(out, invalid_positions=invalid_positions, outputs=outputs)
    risk_distance_col, stop_price_col, take_profit_price_col = _add_risk_level_columns(
        df,
        out,
        cfg=cfg,
        outputs=outputs,
    )
    outputs.update(
        {
            "risk_distance_col": risk_distance_col,
            "stop_price_col": stop_price_col,
            "take_profit_price_col": take_profit_price_col,
        }
    )

    hidden_cols = [
        outputs["positive_label_col"],
        outputs["min_025_label_col"],
        outputs["min_050_label_col"],
        outputs["min_100_label_col"],
    ]
    out = out.drop(columns=hidden_cols)
    output_cols = sorted(
        {
            col
            for key, col in outputs.items()
            if key
            not in {
                "positive_label_col",
                "min_025_label_col",
                "min_050_label_col",
                "min_100_label_col",
            }
        }
    )
    meta = dict(path_meta)
    valid_outcomes = pd.to_numeric(out[outputs["net_r_col"]], errors="coerce").notna()
    exit_reason = out[outputs["exit_reason_col"]].astype("object")
    meta.pop("label_distribution", None)
    meta.update(
        {
            "horizon": int(cfg["max_holding_bars"]),
            "max_holding": int(cfg["max_holding_bars"]),
            "max_holding_bars": int(cfg["max_holding_bars"]),
            "unlimited_horizon": False,
            "strict_path_validation": bool(cfg["strict_path_validation"]),
            "invalid_future_path_count": int(len(invalid_positions)),
            "labeled_rows": int(valid_outcomes.sum()),
            "invalid_candidate_rows": int(
                out[outputs["meta_candidate_col"]].fillna(0.0).astype(bool).sum()
                - valid_outcomes.sum()
            ),
            "exit_reason_counts": {
                str(key): int(value)
                for key, value in exit_reason.loc[valid_outcomes].value_counts().items()
            },
            "take_profit_count": int((exit_reason.loc[valid_outcomes] == "take_profit").sum()),
            "stop_loss_count": int(
                exit_reason.loc[valid_outcomes].astype(str).str.contains("stop", regex=False).sum()
            ),
            "max_holding_close_count": int(
                (exit_reason.loc[valid_outcomes] == "max_holding_close").sum()
            ),
            "net_r_distribution": _numeric_summary(out[outputs["net_r_col"]]),
            "gross_r_distribution": _numeric_summary(out[outputs["gross_r_col"]]),
            "mfe_r_distribution": _numeric_summary(out[outputs["mfe_r_col"]]),
            "mae_r_distribution": _numeric_summary(out[outputs["mae_r_col"]]),
            "risk_distance_col": risk_distance_col,
            "stop_price_col": stop_price_col,
            "take_profit_price_col": take_profit_price_col,
            "output_cols": output_cols,
        }
    )
    return out, cfg, outputs, meta


def _copy_selected_target(
    out: pd.DataFrame,
    *,
    source_col: str,
    fwd_col: str,
    label_col: str,
) -> None:
    if fwd_col != source_col:
        out[fwd_col] = pd.to_numeric(out[source_col], errors="coerce").astype(float)
    if label_col != fwd_col:
        out[label_col] = pd.to_numeric(out[fwd_col], errors="coerce").astype(float)


def build_expected_realized_r_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Build net realized-R regression labels for causal candidate trades.

    YAML declaration::

        target:
          kind: expected_realized_r
          candidate_col: signal_candidate
          side_col: signal_side
          volatility_col: atr_over_price_14
          take_profit_r: 3.0
          stop_loss_r: 1.5
          max_holding_bars: 16

    Required input columns
    ----------------------
    candidate_col, side_col, open_col, high_col, low_col, close_col, volatility_col:
        Point-in-time candidate inputs and the subsequent OHLC trade path.

    Parameters
    ----------
    entry_price_mode, stop_mode, take_profit_r, stop_loss_r, max_holding_bars,
    cost_per_unit_turnover, slippage_per_unit_turnover, tie_break:
        Causal entry, barrier, timeout, friction, and same-bar collision semantics.
    """
    out, cfg, outputs, meta = _build_trade_evaluation(df, target_cfg)
    source_col = outputs["net_r_col"]
    fwd_col = _non_empty_col(cfg.get("fwd_col"), source_col, field="fwd_col")
    label_col = _non_empty_col(cfg.get("label_col"), fwd_col, field="label_col")
    _copy_selected_target(out, source_col=source_col, fwd_col=fwd_col, label_col=label_col)
    meta.update(
        {
            "kind": "expected_realized_r",
            "task_type": "regression",
            "fwd_col": fwd_col,
            "label_col": label_col,
            "realized_r_col": source_col,
            "threshold": 0.0,
            "output_cols": sorted(set(meta["output_cols"]) | {fwd_col, label_col}),
        }
    )
    return out, label_col, fwd_col, meta


def build_target_before_stop_probability_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Build binary labels for whether the profit target is reached before the stop.

    YAML declaration::

        target:
          kind: target_before_stop_probability
          candidate_col: signal_candidate
          side_col: signal_side
          volatility_col: atr_over_price_14
          take_profit_r: 3.0
          stop_loss_r: 1.5
          max_holding_bars: 16
          tie_break: conservative

    Required input columns
    ----------------------
    candidate_col, side_col, open_col, high_col, low_col, close_col, volatility_col:
        Point-in-time candidate inputs and the subsequent OHLC trade path.

    Parameters
    ----------
    entry_price_mode, stop_mode, take_profit_r, stop_loss_r, max_holding_bars, tie_break:
        Causal entry and path-dependent target/stop ordering. Timeouts are negative labels;
        incomplete or invalid paths remain unlabeled.
    """
    out, cfg, outputs, meta = _build_trade_evaluation(df, target_cfg)
    label_col = _non_empty_col(
        cfg.get("label_col"), "target_before_stop", field="label_col"
    )
    fwd_col = _non_empty_col(cfg.get("fwd_col"), label_col, field="fwd_col")
    valid = pd.to_numeric(out[outputs["net_r_col"]], errors="coerce").notna()
    exit_reason = out[outputs["exit_reason_col"]].astype("object")
    label = pd.Series(np.nan, index=out.index, dtype="float32")
    label.loc[valid] = (exit_reason.loc[valid] == "take_profit").astype("float32")
    out[label_col] = label
    if fwd_col != label_col:
        out[fwd_col] = label.astype("float32")

    labeled = label.dropna().astype(int)
    meta.update(
        {
            "kind": "target_before_stop_probability",
            "task_type": "binary_classification",
            "label_col": label_col,
            "fwd_col": fwd_col,
            "threshold": 0.5,
            "labeled_rows": int(len(labeled)),
            "positive_rate": float(labeled.mean()) if len(labeled) else None,
            "target_first_count": int((labeled == 1).sum()),
            "not_target_first_count": int((labeled == 0).sum()),
            "label_distribution": {
                "rows": int(len(labeled)),
                "class_counts": {
                    str(key): int(value)
                    for key, value in labeled.value_counts().sort_index().items()
                },
                "positive_rate": float(labeled.mean()) if len(labeled) else None,
            },
            "output_cols": sorted(set(meta["output_cols"]) | {label_col, fwd_col}),
        }
    )
    return out, label_col, fwd_col, meta


def build_trade_mfe_mae_regression_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Build path-dependent MFE and MAE in R units and select one regression output.

    YAML declaration::

        target:
          kind: trade_mfe_mae_regression
          target_col: mfe_r
          candidate_col: signal_candidate
          side_col: signal_side
          volatility_col: atr_over_price_14
          max_holding_bars: 16

    Required input columns
    ----------------------
    candidate_col, side_col, open_col, high_col, low_col, close_col, volatility_col:
        Point-in-time candidate inputs and the subsequent OHLC trade path.

    Parameters
    ----------
    target_col:
        ``mfe_r`` or ``mae_r``. Configure two model stages to predict both outputs safely.
    entry_price_mode, stop_mode, take_profit_r, stop_loss_r, max_holding_bars, tie_break:
        Causal entry and barrier-path semantics shared with manual-barrier backtests.
    """
    out, cfg, outputs, meta = _build_trade_evaluation(df, target_cfg)
    selection = str(cfg.get("target_col", "mfe_r")).strip()
    aliases = {
        "mfe": "mfe_r",
        "mfe_r": "mfe_r",
        outputs["mfe_r_col"]: "mfe_r",
        "mae": "mae_r",
        "mae_r": "mae_r",
        outputs["mae_r_col"]: "mae_r",
    }
    selected = aliases.get(selection)
    if selected is None:
        raise ValueError(
            "trade_mfe_mae_regression target_col must be one of: mfe_r, mae_r, "
            f"{outputs['mfe_r_col']}, {outputs['mae_r_col']}."
        )
    source_col = outputs["mfe_r_col"] if selected == "mfe_r" else outputs["mae_r_col"]
    fwd_col = _non_empty_col(cfg.get("fwd_col"), source_col, field="fwd_col")
    label_col = _non_empty_col(cfg.get("label_col"), fwd_col, field="label_col")
    _copy_selected_target(out, source_col=source_col, fwd_col=fwd_col, label_col=label_col)
    meta.update(
        {
            "kind": "trade_mfe_mae_regression",
            "task_type": "regression",
            "target_selection": selected,
            "target_col": source_col,
            "fwd_col": fwd_col,
            "label_col": label_col,
            "mfe_r_col": outputs["mfe_r_col"],
            "mae_r_col": outputs["mae_r_col"],
            "available_target_cols": [outputs["mfe_r_col"], outputs["mae_r_col"]],
            "threshold": 0.0,
            "output_cols": sorted(set(meta["output_cols"]) | {fwd_col, label_col}),
        }
    )
    return out, label_col, fwd_col, meta


__all__ = [
    "TRADE_EVALUATION_REGRESSION_TARGET_KINDS",
    "TRADE_EVALUATION_TARGET_KINDS",
    "build_expected_realized_r_target",
    "build_target_before_stop_probability_target",
    "build_trade_mfe_mae_regression_target",
]
