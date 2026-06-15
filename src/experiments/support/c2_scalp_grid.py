from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from src.backtesting.engine import BacktestResult
from src.backtesting.manual_barrier import run_manual_barrier_backtest
from src.evaluation.robustness import cost_multiplier_stress
from src.experiments.orchestration import apply_signal_step, apply_steps_to_assets
from src.experiments.runner import _load_asset_frames
from src.utils.config import load_experiment_config


@dataclass(frozen=True)
class C2ScalpVariant:
    """One diagnostic scalp parameterization for the C2 event signal."""

    name: str
    horizon_bars: int
    take_profit_atr: float
    stop_loss_atr: float
    side_mode: str


def default_c2_scalp_variants() -> list[C2ScalpVariant]:
    """
    Build a small diagnostic grid: three scalp horizons, two ATR barrier profiles, and
    long/short sides separated. The grid is intentionally narrow enough to inspect by hand.
    """
    variants: list[C2ScalpVariant] = []
    for horizon in (4, 6, 8):
        for take_profit_atr, stop_loss_atr in ((0.8, 0.6), (1.2, 0.8)):
            for side_mode in ("long_only", "short_only"):
                variants.append(
                    C2ScalpVariant(
                        name=(
                            f"h{horizon:02d}_tp{_slug_float(take_profit_atr)}_"
                            f"sl{_slug_float(stop_loss_atr)}_{side_mode}"
                        ),
                        horizon_bars=horizon,
                        take_profit_atr=take_profit_atr,
                        stop_loss_atr=stop_loss_atr,
                        side_mode=side_mode,
                    )
                )
    return variants


def build_c2_signaled_assets(config_path: str | Path) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """
    Load raw data once, apply configured C2 features and signal steps, and return signaled frames.
    This mirrors the experiment pipeline but stops before target construction or artifact writes.
    """
    cfg = load_experiment_config(config_path)
    asset_frames, _ = _load_asset_frames(dict(cfg.get("data", {}) or {}))
    featured = apply_steps_to_assets(asset_frames, feature_steps=list(cfg.get("features", []) or []))
    signals_cfg = dict(cfg.get("signals", {}) or {})
    signaled = {
        asset: apply_signal_step(frame, signals_cfg, asset=asset)
        for asset, frame in sorted(featured.items())
    }
    return signaled, cfg


def run_c2_scalp_grid(
    config_path: str | Path = "config/experiments/c2_30m_regime_aware_momentum_v1.yaml",
    *,
    variants: Iterable[C2ScalpVariant] | None = None,
    asset: str | None = None,
    output_dir: str | Path = "logs/diagnostics",
    run_name: str | None = None,
) -> dict[str, Any]:
    """
    Run the C2 scalp diagnostic grid and write CSV/JSON artifacts.

    The grid reuses the configured C2 signal and only mutates event-backtest parameters.
    It is diagnostic tooling, not a new production experiment contract.
    """
    signaled_assets, cfg = build_c2_signaled_assets(config_path)
    selected_asset = _resolve_asset(signaled_assets, asset)
    frame = signaled_assets[selected_asset]
    result = run_c2_scalp_grid_for_frame(
        frame,
        cfg,
        variants=variants,
        asset=selected_asset,
    )
    artifacts = write_c2_scalp_grid_artifacts(
        result,
        config_path=config_path,
        output_dir=output_dir,
        run_name=run_name,
    )
    return {**result, "artifacts": artifacts}


def run_c2_scalp_grid_for_frame(
    frame: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    variants: Iterable[C2ScalpVariant] | None = None,
    asset: str = "asset",
) -> dict[str, Any]:
    """Run scalp variants against an already signaled frame."""
    variant_list = list(variants) if variants is not None else default_c2_scalp_variants()
    if not variant_list:
        raise ValueError("At least one C2 scalp variant is required.")

    backtest_cfg = dict(cfg.get("backtest", {}) or {})
    risk_cfg = dict(cfg.get("risk", {}) or {})
    signal_params = dict(dict(cfg.get("signals", {}) or {}).get("params", {}) or {})
    base_signal_col = str(
        backtest_cfg.get("signal_col")
        or signal_params.get("signal_col")
        or "c2_signal"
    )
    if base_signal_col not in frame.columns:
        raise KeyError(f"C2 scalp grid signal column '{base_signal_col}' not found.")

    rows: list[dict[str, Any]] = []
    trade_rows: list[pd.DataFrame] = []
    for variant in variant_list:
        grid_frame = _frame_with_side_signal(
            frame,
            base_signal_col=base_signal_col,
            side_mode=variant.side_mode,
            output_col="_c2_scalp_grid_signal",
        )
        performance = _run_variant_backtest(
            grid_frame,
            backtest_cfg=backtest_cfg,
            risk_cfg=risk_cfg,
            signal_col="_c2_scalp_grid_signal",
            variant=variant,
        )
        rows.append(
            _summarize_variant(
                performance,
                variant=variant,
                frame=grid_frame,
                asset=asset,
                periods_per_year=int(backtest_cfg.get("periods_per_year", 252)),
            )
        )
        if performance.trades is not None and not performance.trades.empty:
            trades = performance.trades.copy()
            trades.insert(0, "variant", variant.name)
            trades.insert(1, "asset", asset)
            trade_rows.append(trades)

    results = pd.DataFrame(rows)
    results = _order_results_columns(results)
    trades = pd.concat(trade_rows, ignore_index=True) if trade_rows else pd.DataFrame()
    return {
        "asset": asset,
        "results": results,
        "trades": trades,
        "variant_count": int(len(variant_list)),
        "row_count": int(len(frame)),
    }


def write_c2_scalp_grid_artifacts(
    result: dict[str, Any],
    *,
    config_path: str | Path,
    output_dir: str | Path,
    run_name: str | None = None,
) -> dict[str, str]:
    """Persist grid outputs in a timestamped diagnostics directory."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_run_name = run_name or f"c2_scalp_grid_{timestamp}"
    run_dir = Path(output_dir) / safe_run_name
    run_dir.mkdir(parents=True, exist_ok=False)

    results = result["results"].copy()
    trades = result["trades"].copy()
    results_path = run_dir / "grid_results.csv"
    trades_path = run_dir / "grid_trades.csv"
    summary_path = run_dir / "grid_summary.json"

    results.to_csv(results_path, index=False)
    trades.to_csv(trades_path, index=False)

    summary = {
        "config_path": str(config_path),
        "asset": result.get("asset"),
        "row_count": int(result.get("row_count", 0)),
        "variant_count": int(result.get("variant_count", len(results))),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "best_by_net_pnl": _top_records(results, sort_col="net_pnl", n=5),
        "best_by_gross_pnl_per_trade": _top_records(results, sort_col="gross_pnl_per_trade", n=5),
        "positive_net_variants": int(
            pd.to_numeric(results.get("net_pnl"), errors="coerce")
            .fillna(0.0)
            .gt(0.0)
            .sum()
        ),
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "run_dir": str(run_dir),
        "results_csv": str(results_path),
        "trades_csv": str(trades_path),
        "summary_json": str(summary_path),
    }


def _run_variant_backtest(
    frame: pd.DataFrame,
    *,
    backtest_cfg: dict[str, Any],
    risk_cfg: dict[str, Any],
    signal_col: str,
    variant: C2ScalpVariant,
) -> BacktestResult:
    return run_manual_barrier_backtest(
        frame,
        signal_col=signal_col,
        open_col=str(backtest_cfg.get("open_col", "open")),
        high_col=str(backtest_cfg.get("high_col", "high")),
        low_col=str(backtest_cfg.get("low_col", "low")),
        close_col=str(backtest_cfg.get("close_col", "close")),
        take_profit_r=float(variant.take_profit_atr),
        stop_loss_r=float(variant.stop_loss_atr),
        risk_per_trade=float(backtest_cfg.get("risk_per_trade", 0.006)),
        max_holding_bars=int(variant.horizon_bars),
        cost_per_unit_turnover=float(risk_cfg.get("cost_per_turnover", 0.0)),
        slippage_per_unit_turnover=float(risk_cfg.get("slippage_per_turnover", 0.0)),
        max_leverage=float(risk_cfg.get("max_leverage", 1.0)),
        periods_per_year=int(backtest_cfg.get("periods_per_year", 252)),
        dynamic_exits=dict(backtest_cfg.get("dynamic_exits", {}) or {}),
        allow_short=True,
        stop_mode=str(backtest_cfg.get("stop_mode", "fixed_return")),
        vol_col=backtest_cfg.get("vol_col"),
    )


def _summarize_variant(
    performance: BacktestResult,
    *,
    variant: C2ScalpVariant,
    frame: pd.DataFrame,
    asset: str,
    periods_per_year: int,
) -> dict[str, Any]:
    summary = dict(performance.summary or {})
    trades = performance.trades.copy() if performance.trades is not None else pd.DataFrame()
    trade_count = int(len(trades))
    gross_pnl = _series_sum(performance.gross_returns)
    total_cost = _series_sum(performance.costs)
    net_pnl = _series_sum(performance.returns)
    signal_rows = int(pd.to_numeric(frame["_c2_scalp_grid_signal"], errors="coerce").fillna(0.0).ne(0.0).sum())
    stress = cost_multiplier_stress(
        gross_returns=performance.gross_returns,
        costs=performance.costs,
        periods_per_year=int(periods_per_year),
        multipliers=(0.0, 1.0, 2.0, 3.0),
    )
    row: dict[str, Any] = {
        "asset": asset,
        **asdict(variant),
        "signal_rows": signal_rows,
        "trade_count": trade_count,
        "gross_pnl": gross_pnl,
        "total_cost": total_cost,
        "net_pnl": net_pnl,
        "gross_pnl_per_trade": _per_trade(gross_pnl, trade_count),
        "cost_per_trade": _per_trade(total_cost, trade_count),
        "net_pnl_per_trade": _per_trade(net_pnl, trade_count),
        "gross_to_cost_ratio": _safe_ratio(gross_pnl, total_cost),
        "cost_to_gross_pnl": summary.get("cost_to_gross_pnl"),
        "cumulative_return": summary.get("cumulative_return"),
        "sharpe": summary.get("sharpe"),
        "max_drawdown": summary.get("max_drawdown"),
        "profit_factor": summary.get("profit_factor"),
        "hit_rate": summary.get("hit_rate"),
        "mean_bars_held": _trade_mean(trades, "bars_held"),
        "median_bars_held": _trade_median(trades, "bars_held"),
    }
    row.update(_side_metrics(trades))
    row.update(_exit_reason_counts(trades))
    for label, metrics in stress.items():
        prefix = label.replace(".", "p")
        row[f"{prefix}_cumulative_return"] = metrics.get("cumulative_return")
        row[f"{prefix}_profit_factor"] = metrics.get("profit_factor")
        row[f"{prefix}_hit_rate"] = metrics.get("hit_rate")
    row["passes_cost_diagnostic"] = bool(
        trade_count > 0
        and row["gross_pnl_per_trade"] is not None
        and row["cost_per_trade"] is not None
        and float(row["gross_pnl_per_trade"]) > 2.0 * float(row["cost_per_trade"])
        and float(net_pnl) > 0.0
    )
    return row


def _frame_with_side_signal(
    frame: pd.DataFrame,
    *,
    base_signal_col: str,
    side_mode: str,
    output_col: str,
) -> pd.DataFrame:
    if side_mode not in {"long_short", "long_only", "short_only"}:
        raise ValueError("side_mode must be one of: long_short, long_only, short_only.")
    signal = pd.to_numeric(frame[base_signal_col], errors="coerce").fillna(0.0).astype(float)
    if side_mode == "long_only":
        signal = signal.where(signal > 0.0, 0.0)
    elif side_mode == "short_only":
        signal = signal.where(signal < 0.0, 0.0)
    out = frame.copy()
    out[output_col] = signal
    return out


def _side_metrics(trades: pd.DataFrame) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for side in ("long", "short"):
        if trades.empty or "side" not in trades.columns:
            group = pd.DataFrame()
        else:
            group = trades.loc[trades["side"].astype(str).eq(side)]
        net = pd.to_numeric(group.get("net_return", pd.Series(dtype=float)), errors="coerce").dropna()
        gross = pd.to_numeric(group.get("gross_return", pd.Series(dtype=float)), errors="coerce").dropna()
        out[f"{side}_trade_count"] = int(len(group))
        out[f"{side}_net_pnl"] = float(net.sum()) if not net.empty else 0.0
        out[f"{side}_gross_pnl"] = float(gross.sum()) if not gross.empty else 0.0
        out[f"{side}_profit_factor"] = _profit_factor(net)
        out[f"{side}_hit_rate"] = float((net > 0.0).mean()) if not net.empty else None
    return out


def _exit_reason_counts(trades: pd.DataFrame) -> dict[str, int]:
    if trades.empty or "exit_reason" not in trades.columns:
        return {}
    counts = trades["exit_reason"].astype(str).value_counts(dropna=False).to_dict()
    return {f"exit_reason_{_slug_text(reason)}_count": int(count) for reason, count in counts.items()}


def _profit_factor(values: pd.Series) -> float | None:
    if values.empty:
        return None
    gains = float(values[values > 0.0].sum())
    losses = float(values[values < 0.0].sum())
    if losses == 0.0:
        return float("inf") if gains > 0.0 else None
    return float(gains / abs(losses))


def _per_trade(value: float, trade_count: int) -> float | None:
    if int(trade_count) <= 0:
        return None
    return float(value / int(trade_count))


def _series_sum(series: pd.Series | None) -> float:
    if series is None:
        return 0.0
    return float(pd.to_numeric(series, errors="coerce").fillna(0.0).sum())


def _trade_mean(trades: pd.DataFrame, column: str) -> float | None:
    if trades.empty or column not in trades.columns:
        return None
    values = pd.to_numeric(trades[column], errors="coerce").dropna()
    return float(values.mean()) if not values.empty else None


def _trade_median(trades: pd.DataFrame, column: str) -> float | None:
    if trades.empty or column not in trades.columns:
        return None
    values = pd.to_numeric(trades[column], errors="coerce").dropna()
    return float(values.median()) if not values.empty else None


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if abs(float(denominator)) <= 1e-12:
        return None
    return float(numerator / denominator)


def _resolve_asset(signaled_assets: dict[str, pd.DataFrame], requested: str | None) -> str:
    if requested is not None:
        if requested not in signaled_assets:
            raise KeyError(
                f"Requested asset '{requested}' not found. Available: {sorted(signaled_assets)}"
            )
        return requested
    if len(signaled_assets) != 1:
        raise ValueError(
            f"Multiple assets available; pass asset explicitly. Available: {sorted(signaled_assets)}"
        )
    return next(iter(signaled_assets))


def _order_results_columns(results: pd.DataFrame) -> pd.DataFrame:
    preferred = [
        "asset",
        "name",
        "horizon_bars",
        "take_profit_atr",
        "stop_loss_atr",
        "side_mode",
        "signal_rows",
        "trade_count",
        "gross_pnl",
        "total_cost",
        "net_pnl",
        "gross_pnl_per_trade",
        "cost_per_trade",
        "net_pnl_per_trade",
        "gross_to_cost_ratio",
        "cost_to_gross_pnl",
        "passes_cost_diagnostic",
        "cumulative_return",
        "sharpe",
        "max_drawdown",
        "profit_factor",
        "hit_rate",
        "long_trade_count",
        "short_trade_count",
        "long_profit_factor",
        "short_profit_factor",
        "long_hit_rate",
        "short_hit_rate",
        "mean_bars_held",
        "median_bars_held",
    ]
    ordered = [column for column in preferred if column in results.columns]
    ordered.extend(column for column in results.columns if column not in ordered)
    return results[ordered]


def _top_records(results: pd.DataFrame, *, sort_col: str, n: int) -> list[dict[str, Any]]:
    if results.empty or sort_col not in results.columns:
        return []
    top = results.sort_values(sort_col, ascending=False, na_position="last").head(int(n))
    return json.loads(top.to_json(orient="records"))


def _slug_float(value: float) -> str:
    return f"{float(value):g}".replace(".", "p").replace("-", "m")


def _slug_text(value: Any) -> str:
    text = str(value).strip().lower()
    out = "".join(ch if ch.isalnum() else "_" for ch in text)
    return "_".join(part for part in out.split("_") if part) or "missing"


__all__ = [
    "C2ScalpVariant",
    "build_c2_signaled_assets",
    "default_c2_scalp_variants",
    "run_c2_scalp_grid",
    "run_c2_scalp_grid_for_frame",
    "write_c2_scalp_grid_artifacts",
]
