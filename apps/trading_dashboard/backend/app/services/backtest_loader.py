from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from app.services.experiment_loader import ExperimentLoader
from app.services.schema_mapper import DataSchemaError, coerce_timestamps, to_iso_z


class BacktestLoader:
    def __init__(self, experiments: ExperimentLoader | None = None) -> None:
        self.experiments = experiments or ExperimentLoader()

    def load_trades(self, run_id: str, asset: str | None = None) -> list[dict[str, Any]]:
        run_dir = self.experiments.resolve_run_dir(run_id)
        path = self._find_trades_path(run_dir)
        if path is None:
            return []
        frame = pd.read_csv(path)
        if frame.empty:
            return []
        if asset and "asset" in frame.columns:
            frame = frame.loc[frame["asset"].astype(str).str.upper() == asset.upper()]
            if frame.empty:
                return []
        if path.name == "trade_events.csv":
            return self._normalize_trade_events(frame)
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

    def _normalize_trade_events(self, frame: pd.DataFrame) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        open_trades: dict[tuple[str, str], list[pd.Series]] = {}
        ordered = frame.copy()
        time_col = self._time_column(ordered)
        if time_col is not None:
            ordered["_dashboard_event_time"] = coerce_timestamps(ordered[time_col])
            ordered = ordered.sort_values("_dashboard_event_time", kind="stable")

        for _, row in ordered.iterrows():
            event_type = str(row.get("event_type", row.get("event", ""))).lower().strip()
            side = str(row.get("side", "long")).lower().strip() or "long"
            asset = str(row.get("asset", "")).upper().strip()
            key = (asset, side)
            if event_type == "entry":
                open_trades.setdefault(key, []).append(row)
                continue
            if event_type == "exit":
                pending = open_trades.get(key, [])
                entry = pending.pop(0) if pending else None
                if not pending and key in open_trades:
                    del open_trades[key]
                records.append(self._trade_from_events(entry, row))

        records.extend(self._trade_from_events(entry, None) for pending in open_trades.values() for entry in pending)
        return records

    def _trade_from_events(self, entry: pd.Series | None, exit_row: pd.Series | None) -> dict[str, Any]:
        source = entry if entry is not None else exit_row
        side = str(source.get("side", "long")).lower() if source is not None else "long"
        return {
            "entry_time": self._event_time(entry) if entry is not None else None,
            "exit_time": self._event_time(exit_row) if exit_row is not None else None,
            "side": side,
            "entry_price": self._float_or_none(entry.get("price")) if entry is not None else None,
            "exit_price": self._float_or_none(exit_row.get("price")) if exit_row is not None else None,
            "pnl": self._float_or_none(exit_row.get("pnl")) if exit_row is not None else None,
            "return": self._float_or_none(exit_row.get("return")) if exit_row is not None else None,
            "size": self._event_size(entry if entry is not None else exit_row),
        }

    def _event_time(self, row: pd.Series | None) -> str | None:
        if row is None:
            return None
        time_col = self._time_column(row)
        return self._format_optional_time(row.get(time_col)) if time_col is not None else None

    @staticmethod
    def _time_column(row_or_frame: pd.Series | pd.DataFrame) -> str | None:
        columns = row_or_frame.index if isinstance(row_or_frame, pd.Series) else row_or_frame.columns
        return next((column for column in columns if str(column).lower() in {"timestamp", "datetime", "date", "time"}), None)

    def _event_size(self, row: pd.Series | None) -> float | None:
        if row is None:
            return None
        before = self._float_or_none(row.get("position_before"))
        after = self._float_or_none(row.get("position_after"))
        if before is not None and after is not None:
            return abs(after - before)
        return self._float_or_none(row.get("size", row.get("position_size")))

    @staticmethod
    def _format_optional_time(value: Any) -> str | None:
        if value is None or pd.isna(value):
            return None
        return to_iso_z(coerce_timestamps(pd.Series([value]))[0])

    @staticmethod
    def _float_or_none(value: Any) -> float | None:
        if value is None or pd.isna(value) or str(value).strip() == "":
            return None
        return float(value)
