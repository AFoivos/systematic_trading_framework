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
      const isLong = trade.side !== "short";
      markers.push({
        time: asTime(trade.entry_time),
        position: isLong ? "belowBar" : "aboveBar",
        color: isLong ? "#0f9f6e" : "#d14f3f",
        shape: isLong ? "arrowUp" : "arrowDown",
        text: isLong ? "Entry L" : "Entry S"
      });
    }
    if (trade.exit_time) {
      markers.push({
        time: asTime(trade.exit_time),
        position: "aboveBar",
        color: "#6b7280",
        shape: "circle",
        text: trade.return === null ? "Exit" : `Exit ${(trade.return * 100).toFixed(2)}%`
      });
    }
    return markers;
  });
}
