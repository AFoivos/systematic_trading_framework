import { useCallback, useEffect, useMemo, useRef, type RefObject } from "react";
import {
  ColorType,
  CrosshairMode,
  LineStyle,
  createChart,
  type ChartOptions,
  type DeepPartial,
  type IChartApi,
  type UTCTimestamp
} from "lightweight-charts";
import { createMarketBars } from "./marketData";
import type { ChartPlacement } from "./runStore";

interface TradingChartProps {
  routes: Record<string, ChartPlacement>;
}

const chartTheme: DeepPartial<ChartOptions> = {
  layout: {
    background: { type: ColorType.Solid, color: "#ffffff" },
    textColor: "#5f6b7a",
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
    fontSize: 11
  },
  grid: {
    vertLines: { color: "#edf0f3", style: LineStyle.Solid },
    horzLines: { color: "#edf0f3", style: LineStyle.Solid }
  },
  crosshair: { mode: CrosshairMode.Normal },
  rightPriceScale: { borderColor: "#d8dde4", scaleMargins: { top: 0.08, bottom: 0.18 } },
  timeScale: { borderColor: "#d8dde4", timeVisible: true, secondsVisible: false, rightOffset: 8, barSpacing: 7 },
  handleScroll: true,
  handleScale: true
};

function useResponsiveChart(containerRef: RefObject<HTMLDivElement>, create: (element: HTMLDivElement) => IChartApi) {
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const chart = create(container);
    const observer = new ResizeObserver(([entry]) => {
      chart.applyOptions({
        width: Math.floor(entry.contentRect.width),
        height: Math.floor(entry.contentRect.height)
      });
    });
    observer.observe(container);
    return () => {
      observer.disconnect();
      chart.remove();
    };
  }, [containerRef, create]);
}

export function TradingChart({ routes }: TradingChartProps) {
  const bars = useMemo(() => createMarketBars(), []);
  const mainRef = useRef<HTMLDivElement | null>(null);
  const lowerRef = useRef<HTMLDivElement | null>(null);
  const mainChartRef = useRef<IChartApi | null>(null);
  const lowerChartRef = useRef<IChartApi | null>(null);
  const normalizedRoutes = useMemo(() => Object.entries(routes).map(([name, placement]) => ({
    name,
    placement,
    series: name.includes("zscore") || name.includes("__z") ? "zscore" : name.includes("slope") ? "slope" : "volatility"
  })), [routes]);
  const lowerSeries = normalizedRoutes.filter(({ placement }) => placement === "lower");
  const mainSeries = normalizedRoutes.filter(({ placement }) => placement === "main");

  const createMainChart = useCallback((element: HTMLDivElement) => {
    const chart = createChart(element, chartTheme);
    mainChartRef.current = chart;
    const candles = chart.addCandlestickSeries({
      upColor: "#159b62",
      downColor: "#df4b53",
      wickUpColor: "#159b62",
      wickDownColor: "#df4b53",
      borderVisible: false
    });
    candles.setData(bars.map(({ time, open, high, low, close }) => ({ time, open, high, low, close })));

    if (mainSeries.some(({ series }) => series === "volatility")) {
      const volatility = chart.addLineSeries({ color: "#2f7cf6", lineWidth: 2, priceScaleId: "volatility" });
      volatility.priceScale().applyOptions({ scaleMargins: { top: 0.78, bottom: 0.02 } });
      volatility.setData(bars.map((bar) => ({ time: bar.time, value: bar.volatility })));
    }
    if (mainSeries.some(({ series }) => series === "slope")) {
      const slope = chart.addLineSeries({ color: "#8a5cf6", lineWidth: 2 });
      slope.setData(bars.map((bar) => ({ time: bar.time, value: bar.close + bar.slope * 35 })));
    }
    chart.timeScale().fitContent();
    return chart;
  }, [bars, mainSeries]);

  const createLowerChart = useCallback((element: HTMLDivElement) => {
    const chart = createChart(element, {
      ...chartTheme,
      rightPriceScale: { borderColor: "#d8dde4", scaleMargins: { top: 0.15, bottom: 0.15 } }
    });
    lowerChartRef.current = chart;
    const palette = { volatility: "#2f7cf6", zscore: "#8a5cf6", slope: "#df8a22" };
    for (const { name: feature, series: seriesKind } of lowerSeries) {
      const series = chart.addLineSeries({
        color: palette[seriesKind as keyof typeof palette] ?? "#2f7cf6",
        lineWidth: 2,
        title: feature
      });
      series.setData(bars.map((bar) => ({
        time: bar.time,
        value: seriesKind === "volatility" ? bar.volatility : seriesKind === "zscore" ? bar.zscore : bar.slope
      })));
    }
    chart.timeScale().fitContent();
    return chart;
  }, [bars, lowerSeries]);

  useResponsiveChart(mainRef, createMainChart);
  useResponsiveChart(lowerRef, createLowerChart);

  useEffect(() => {
    const main = mainChartRef.current;
    const lower = lowerChartRef.current;
    if (!main || !lower) return;
    let syncing = false;
    const syncToLower = (range: { from: number; to: number } | null) => {
      if (!range || syncing) return;
      syncing = true;
      lower.timeScale().setVisibleLogicalRange(range);
      syncing = false;
    };
    const syncToMain = (range: { from: number; to: number } | null) => {
      if (!range || syncing) return;
      syncing = true;
      main.timeScale().setVisibleLogicalRange(range);
      syncing = false;
    };
    main.timeScale().subscribeVisibleLogicalRangeChange(syncToLower);
    lower.timeScale().subscribeVisibleLogicalRangeChange(syncToMain);
    return () => {
      main.timeScale().unsubscribeVisibleLogicalRangeChange(syncToLower);
      lower.timeScale().unsubscribeVisibleLogicalRangeChange(syncToMain);
    };
  }, [lowerSeries.length]);

  return (
    <div className="trading-chart-stack">
      <section className="chart-panel main-chart-panel">
        <header>
          <div><strong>SPX500</strong><span>30m · Candles</span></div>
          <div className="chart-legend"><span className="legend-candles">Price</span>{mainSeries.map(({ name }) => <span key={name}>{name}</span>)}</div>
        </header>
        <div className="chart-host" ref={mainRef} />
      </section>
      {lowerSeries.length ? (
        <section className="chart-panel lower-chart-panel">
          <header><strong>Lower panel</strong><div className="chart-legend">{lowerSeries.map(({ name }) => <span key={name}>{name}</span>)}</div></header>
          <div className="chart-host" ref={lowerRef} />
        </section>
      ) : null}
    </div>
  );
}
