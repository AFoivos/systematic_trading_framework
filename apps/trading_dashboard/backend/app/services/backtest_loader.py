from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from app.services.experiment_loader import ExperimentLoader
from app.services.schema_mapper import DataSchemaError, coerce_timestamps, to_iso_z


class BacktestLoader:
    def __init__(self, experiments: ExperimentLoader | None = None) -> None:
        self.experiments = experiments or ExperimentLoader()

    def load_trades(self, run_id: str) -> list[dict[str, Any]]:
        run_dir = self.experiments.resolve_run_dir(run_id)
        path = self._find_trades_path(run_dir)
        if path is None:
            return []
        frame = pd.read_csv(path)
        if frame.empty:
            return []
        return [self._normalize_trade(row) for _, row in frame.iterrows()]

    def load_equity(self, run_id: str) -> list[dict[str, Any]]:
        run_dir = self.experiments.resolve_run_dir(run_id)
        path = run_dir / "equity_curve.csv"
        if not path.exists():
            return []
        frame = pd.read_csv(path)
        if frame.empty:
            return []
        time_col = next((column for column in frame.columns if str(column).lower() in {"timestamp", "datetime", "date", "time"}), frame.columns[0])
        value_cols = [column for column in frame.columns if column != time_col]
        if not value_cols:
            raise DataSchemaError(f"Equity file has no value column: {path}")
        times = coerce_timestamps(frame[time_col])
        values = pd.to_numeric(frame[value_cols[0]], errors="coerce")
        return [
            {"time": to_iso_z(time), "value": None if pd.isna(value) else float(value)}
            for time, value in zip(times, values, strict=False)
        ]

    def _find_trades_path(self, run_dir: Path) -> Path | None:
        for path in (
            run_dir / "report_assets" / "trades.csv",
            run_dir / "trades.csv",
            run_dir / "report_assets" / "trade_events.csv",
        ):
            if path.exists():
                return path
        return None

    def _normalize_trade(self, row: pd.Series) -> dict[str, Any]:
        entry_time = row.get("entry_timestamp", row.get("entry_time", row.get("timestamp")))
        exit_time = row.get("exit_timestamp", row.get("exit_time"))
        side = str(row.get("side", "long")).lower()
        return {
            "entry_time": self._format_optional_time(entry_time),
            "exit_time": self._format_optional_time(exit_time),
            "side": side,
            "entry_price": self._float_or_none(row.get("entry_price", row.get("price"))),
            "exit_price": self._float_or_none(row.get("exit_price")),
            "pnl": self._float_or_none(row.get("pnl", row.get("net_return", row.get("gross_return")))),
            "return": self._float_or_none(row.get("return", row.get("net_return", row.get("gross_return")))),
            "size": self._float_or_none(row.get("size", row.get("position_size", row.get("position_after")))),
        }

    @staticmethod
    def _format_optional_time(value: Any) -> str | None:
        if value is None or pd.isna(value):
            return None
        return to_iso_z(coerce_timestamps(pd.Series([value]))[0])

    @staticmethod
    def _float_or_none(value: Any) -> float | None:
        if value is None or pd.isna(value):
            return None
        return float(value)

