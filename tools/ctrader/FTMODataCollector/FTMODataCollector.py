"""Read-only FTMO/cTrader market-data collector.

This file is intended to be pasted into a Python cBot named
``FTMODataCollector``.  It never submits, modifies, or closes orders.
"""

import clr

clr.AddReference("cAlgo.API")

from cAlgo.API import *  # noqa: F403
from robot_wrapper import *  # noqa: F403
from System.IO import File


class FTMODataCollector:
    BAR_HEADER = "timestamp_utc,open,high,low,close,tick_volume\n"
    QUOTE_HEADER = "timestamp_utc,symbol,bid,ask,spread\n"

    def on_start(self):
        self.symbol_names = [
            value.strip().upper()
            for value in str(api.SymbolsCsv).split(",")
            if value.strip()
        ]
        if not self.symbol_names:
            raise ValueError("Symbols must contain at least one symbol name.")

        self.symbols = []
        self.started_utc = api.TimeInUtc
        self.stop_at_utc = None
        if int(api.StopAfterMinutes) > 0:
            self.stop_at_utc = self.started_utc.AddMinutes(int(api.StopAfterMinutes))

        File.WriteAllText("quotes_live.csv", self.QUOTE_HEADER)
        metadata_items = []

        for symbol_name in self.symbol_names:
            symbol = api.Symbols.GetSymbol(symbol_name)
            if symbol is None:
                raise ValueError(f"Symbol '{symbol_name}' is not available on this account.")

            self.symbols.append(symbol)
            metadata_items.append(self._symbol_metadata_json(symbol))
            self._export_m1_bars(symbol)

        metadata_json = ("{\n"
            f'  "captured_at_utc": "{self._iso(api.TimeInUtc)}",\n'
            f'  "account_asset": "{self._escape(str(api.Account.Asset.Name))}",\n'
            f'  "account_is_live": {str(bool(api.Account.IsLive)).lower()},\n'
            f'  "history_days_requested": {int(api.HistoryDays)},\n'
            '  "symbols": [\n    '
            + ",\n    ".join(metadata_items)
            + "\n  ]\n}\n"
        )
        File.WriteAllText("symbol_metadata.json", metadata_json)

        sample_seconds = max(1, int(api.QuoteSampleSeconds))
        api.Timer.Start(sample_seconds)
        self._sample_quotes()
        print(
            f"FTMODataCollector ready: symbols={','.join(self.symbol_names)} "
            f"history_days={int(api.HistoryDays)} quote_sample_seconds={sample_seconds}"
        )

    def on_timer(self):
        self._sample_quotes()
        if self.stop_at_utc is not None and api.TimeInUtc >= self.stop_at_utc:
            print("Configured collection duration completed; stopping collector.")
            api.Stop()

    def on_stop(self):
        print("FTMODataCollector stopped. No trading operations were performed.")

    def _export_m1_bars(self, symbol):
        bars = api.MarketData.GetBars(TimeFrame.Minute, symbol.Name)  # noqa: F405
        cutoff = api.TimeInUtc.AddDays(-max(1, int(api.HistoryDays)))
        batches = 0

        while bars.Count > 0 and bars.OpenTimes[0] > cutoff:
            if batches >= max(1, int(api.MaxHistoryBatches)):
                print(
                    f"WARNING {symbol.Name}: reached Max History Batches before cutoff; "
                    f"earliest={self._iso(bars.OpenTimes[0])} cutoff={self._iso(cutoff)}"
                )
                break
            loaded = int(bars.LoadMoreHistory())
            batches += 1
            if loaded <= 0:
                break

        rows = [self.BAR_HEADER]
        written = 0
        for index in range(int(bars.Count)):
            timestamp = bars.OpenTimes[index]
            if timestamp < cutoff:
                continue
            rows.append(
                f"{self._iso(timestamp)},"
                f"{float(bars.OpenPrices[index]):.10g},"
                f"{float(bars.HighPrices[index]):.10g},"
                f"{float(bars.LowPrices[index]):.10g},"
                f"{float(bars.ClosePrices[index]):.10g},"
                f"{float(bars.TickVolumes[index]):.10g}\n"
            )
            written += 1

        filename = f"{symbol.Name.lower()}_m1.csv"
        File.WriteAllText(filename, "".join(rows))
        earliest = self._iso(bars.OpenTimes[0]) if bars.Count else "n/a"
        latest = self._iso(bars.OpenTimes[bars.Count - 1]) if bars.Count else "n/a"
        print(
            f"Exported {filename}: rows={written} loaded_batches={batches} "
            f"available_range={earliest}..{latest}"
        )

    def _sample_quotes(self):
        timestamp = self._iso(api.TimeInUtc)
        rows = []
        for symbol in self.symbols:
            bid = float(symbol.Bid)
            ask = float(symbol.Ask)
            rows.append(
                f"{timestamp},{symbol.Name},{bid:.10g},{ask:.10g},{(ask - bid):.10g}\n"
            )
        if rows:
            File.AppendAllText("quotes_live.csv", "".join(rows))

    def _symbol_metadata_json(self, symbol):
        sessions = [self._escape(str(session)) for session in symbol.MarketHours.Sessions]
        sessions_json = ", ".join(f'"{value}"' for value in sessions)
        return (
            "{\n"
            f'      "name": "{self._escape(symbol.Name)}",\n'
            f'      "base_asset": "{self._escape(str(symbol.BaseAsset.Name))}",\n'
            f'      "quote_asset": "{self._escape(str(symbol.QuoteAsset.Name))}",\n'
            f'      "digits": {int(symbol.Digits)},\n'
            f'      "pip_size": {float(symbol.PipSize):.12g},\n'
            f'      "tick_size": {float(symbol.TickSize):.12g},\n'
            f'      "lot_size": {int(symbol.LotSize)},\n'
            f'      "volume_units_min": {float(symbol.VolumeInUnitsMin):.12g},\n'
            f'      "volume_units_max": {float(symbol.VolumeInUnitsMax):.12g},\n'
            f'      "volume_units_step": {float(symbol.VolumeInUnitsStep):.12g},\n'
            f'      "commission": {float(symbol.Commission):.12g},\n'
            f'      "commission_type": "{self._escape(str(symbol.CommissionType))}",\n'
            f'      "min_commission": {float(symbol.MinCommission):.12g},\n'
            f'      "swap_long": {float(symbol.SwapLong):.12g},\n'
            f'      "swap_short": {float(symbol.SwapShort):.12g},\n'
            f'      "swap_calculation_type": "{self._escape(str(symbol.SwapCalculationType))}",\n'
            f'      "swap_3day_rollover": "{self._escape(str(symbol.Swap3DaysRollover))}",\n'
            f'      "market_open_at_capture": {str(bool(symbol.MarketHours.IsOpened())).lower()},\n'
            f'      "market_sessions": [{sessions_json}],\n'
            f'      "bid_at_capture": {float(symbol.Bid):.12g},\n'
            f'      "ask_at_capture": {float(symbol.Ask):.12g}\n'
            "    }"
        )

    @staticmethod
    def _iso(value):
        return str(value.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ"))

    @staticmethod
    def _escape(value):
        return value.replace("\\", "\\\\").replace('"', '\\"')

