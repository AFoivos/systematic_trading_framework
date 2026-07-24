import type { UTCTimestamp } from "lightweight-charts";

export interface MarketBar {
  time: UTCTimestamp;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  volatility: number;
  zscore: number;
  slope: number;
}

function seededNoise(index: number): number {
  const value = Math.sin(index * 12.9898) * 43758.5453;
  return (value - Math.floor(value)) - 0.5;
}

export function createMarketBars(count = 420): MarketBar[] {
  const start = Date.UTC(2025, 0, 6, 8, 0) / 1000;
  const bars: MarketBar[] = [];
  let close = 5_920;

  for (let index = 0; index < count; index += 1) {
    const trend = Math.sin(index / 37) * 1.9 + Math.sin(index / 11) * 0.7;
    const change = trend + seededNoise(index) * 13;
    const open = close;
    close = Math.max(4_800, open + change);
    const spread = 4 + Math.abs(seededNoise(index + 500)) * 13;
    const volatility = 8 + Math.abs(Math.sin(index / 18)) * 16 + Math.abs(seededNoise(index + 900)) * 8;
    const zscore = Math.max(-3, Math.min(3, Math.sin(index / 16) * 1.6 + seededNoise(index + 200) * 0.8));
    const slope = Math.sin(index / 22) * 0.7 + seededNoise(index + 400) * 0.25;
    bars.push({
      time: (start + index * 30 * 60) as UTCTimestamp,
      open,
      high: Math.max(open, close) + spread,
      low: Math.min(open, close) - spread,
      close,
      volume: Math.round(8_000 + Math.abs(seededNoise(index + 100)) * 20_000),
      volatility,
      zscore,
      slope
    });
  }

  return bars;
}
