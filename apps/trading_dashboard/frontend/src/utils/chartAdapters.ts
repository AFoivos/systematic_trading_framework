import type { HistogramData, LineData, SeriesMarker, Time, UTCTimestamp, WhitespaceData } from "lightweight-charts";
import type { OHLCVCandle, TimeValuePoint, TradeRecord } from "../types/market";

function asTime(value: string): UTCTimestamp {
  return Math.floor(Date.parse(value) / 1000) as UTCTimestamp;
}

function numericValue(value: TimeValuePoint["value"]): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "boolean") {
    return value ? 1 : 0;
  }
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

const exitReasonLabels: Record<string, string> = {
  take_profit: "TP",
  stop_loss: "SL",
  stop_and_target_same_bar_stop_first: "SL*",
  max_holding_close: "TIME",
  end_of_data_close: "EOD",
  signal_off_exit: "SIG",
  no_progress_exit: "NP",
  breakeven_stop: "BE",
  profit_lock_stop: "PL",
  atr_trailing_stop: "ATR"
};

function isShortSide(side: TradeRecord["side"]): boolean {
  const normalized = String(side ?? "").trim().toLowerCase();
  return normalized === "short" || normalized === "sell";
}

function signedPercentLabel(value: number | null): string | null {
  if (value === null) {
    return null;
  }
  const percent = value * 100;
  const sign = percent > 0 ? "+" : "";
  return `${sign}${percent.toFixed(2)}%`;
}

function inferredExitLabel(value: number | null): string | null {
  if (value === null) {
    return null;
  }
  if (value > 0) {
    return "TP";
  }
  if (value < 0) {
    return "SL";
  }
  return "BE";
}

function exitMarkerText(trade: TradeRecord): string {
  const returnLabel = signedPercentLabel(trade.return);
  const normalizedReason = trade.exit_reason?.trim().toLowerCase();
  const reasonLabel = normalizedReason
    ? (exitReasonLabels[normalizedReason] ?? normalizedReason.toUpperCase())
    : inferredExitLabel(trade.return);
  const label = [reasonLabel, returnLabel].filter(Boolean).join(" ");
  return label || "Exit";
}

export function toCandles(candles: OHLCVCandle[]) {
  return candles.map((candle) => ({
    time: asTime(candle.time),
    open: candle.open,
    high: candle.high,
    low: candle.low,
    close: candle.close
  }));
}

export function toLineData(points: TimeValuePoint[]): LineData[] {
  return points.flatMap((point) => {
    const value = numericValue(point.value);
    return value === null ? [] : [{ time: asTime(point.time), value }];
  });
}

export function toHistogramData(points: TimeValuePoint[], color: string): HistogramData[] {
  return points.flatMap((point) => {
    const value = numericValue(point.value);
    return value === null ? [] : [{ time: asTime(point.time), value, color }];
  });
}

export function toWhitespaceData(candles: OHLCVCandle[]): WhitespaceData[] {
  return candles.map((candle) => ({ time: asTime(candle.time) }));
}

export function toTradeMarkers(trades: TradeRecord[]): SeriesMarker<Time>[] {
  return trades.flatMap((trade) => {
    const markers: SeriesMarker<Time>[] = [];
    if (trade.entry_time) {
      const isLong = !isShortSide(trade.side);
      const entryText =
        trade.exit_time === null && (trade.side === "long" || trade.side === "short")
          ? isLong
            ? "Buy fill"
            : "Sell fill"
          : isLong
            ? "Entry L"
            : "Entry S";
      markers.push({
        time: asTime(trade.entry_time),
        position: isLong ? "belowBar" : "aboveBar",
        color: isLong ? "#0f9f6e" : "#d14f3f",
        shape: isLong ? "arrowUp" : "arrowDown",
        text: entryText
      });
    }
    if (trade.exit_time) {
      markers.push({
        time: asTime(trade.exit_time),
        position: "aboveBar",
        color: "#6b7280",
        shape: "circle",
        text: exitMarkerText(trade)
      });
    }
    return markers;
  });
}
