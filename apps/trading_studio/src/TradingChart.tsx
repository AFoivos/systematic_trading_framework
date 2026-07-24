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
import type { ChartPanelDefinition, ChartPlacement } from "./runStore";
import type { RuntimeCandle, RuntimeSeries } from "./runtime";

interface TradingChartProps {
  routes: Record<string, ChartPlacement>;
  panels?: ChartPanelDefinition[];
  candles?: RuntimeCandle[];
  runtimeSeries?: RuntimeSeries[];
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
  handleScroll: {
    mouseWheel: false,
    pressedMouseMove: true,
    horzTouchDrag: true,
    vertTouchDrag: false
  },
  handleScale: {
    axisPressedMouseMove: true,
    mouseWheel: false,
    pinch: true
  }
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

type RoutedSeries = { name: string; placement: ChartPlacement; series: "volatility" | "zscore" | "slope"; points?: RuntimeSeries["points"] };

function pointTime(time: string): UTCTimestamp {
  return Math.floor(new Date(time).getTime() / 1000) as UTCTimestamp;
}

function LowerPanelChart({ panel, seriesItems, bars }: { panel: ChartPanelDefinition; seriesItems: RoutedSeries[]; bars: ReturnType<typeof createMarketBars> }) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const createPanelChart = useCallback((element: HTMLDivElement) => {
    const chart = createChart(element, {
      ...chartTheme,
      rightPriceScale: { borderColor: "#d8dde4", scaleMargins: { top: 0.15, bottom: 0.15 } }
    });
    const palette = { volatility: "#2f7cf6", zscore: "#8a5cf6", slope: "#df8a22" };
    for (const { name, series: seriesKind } of seriesItems) {
      const line = chart.addLineSeries({ color: palette[seriesKind], lineWidth: 2, title: name });
      line.setData(seriesItems.find((item) => item.name === name)?.points
        ?.filter((point) => typeof point.value === "number" && Number.isFinite(point.value))
        .map((point) => ({ time: pointTime(point.time), value: point.value as number }))
        ?? bars.map((bar) => ({
          time: bar.time,
          value: seriesKind === "volatility" ? bar.volatility : seriesKind === "zscore" ? bar.zscore : bar.slope
        })));
    }
    chart.timeScale().fitContent();
    return chart;
  }, [bars, seriesItems]);
  useResponsiveChart(panelRef, createPanelChart);
  return (
    <section className="chart-panel lower-chart-panel">
      <header><strong>{panel.name}</strong><div className="chart-legend">{seriesItems.map(({ name }) => <span key={name}>{name}</span>)}</div></header>
      <div className="chart-host" ref={panelRef} />
    </section>
  );
}

export function TradingChart({ routes, panels = [{ id: "panel-1", name: "Lower panel 1" }], candles: runtimeCandles, runtimeSeries = [] }: TradingChartProps) {
  const bars = useMemo(() => createMarketBars(), []);
  const mainRef = useRef<HTMLDivElement | null>(null);
  const mainChartRef = useRef<IChartApi | null>(null);
  const normalizedRoutes = useMemo(() => Object.entries(routes).map(([name, placement]) => ({
    name,
    placement: placement === "lower" ? "panel:panel-1" as ChartPlacement : placement,
    series: (name.includes("zscore") || name.includes("__z") ? "zscore" : name.includes("slope") ? "slope" : "volatility") as RoutedSeries["series"],
    points: runtimeSeries.find((series) => series.label === name)?.points
  })) as RoutedSeries[], [routes, runtimeSeries]);
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
    candles.setData(runtimeCandles?.length
      ? runtimeCandles.map(({ time, open, high, low, close }) => ({ time: pointTime(time), open, high, low, close }))
      : bars.map(({ time, open, high, low, close }) => ({ time, open, high, low, close })));

    for (const [index, item] of mainSeries.entries()) {
      const line = chart.addLineSeries({ color: index % 2 ? "#8a5cf6" : "#2f7cf6", lineWidth: 2, priceScaleId: item.name });
      line.priceScale().applyOptions({ scaleMargins: { top: 0.78, bottom: 0.02 } });
      line.setData(item.points
        ?.filter((point) => typeof point.value === "number" && Number.isFinite(point.value))
        .map((point) => ({ time: pointTime(point.time), value: point.value as number }))
        ?? bars.map((bar) => ({ time: bar.time, value: item.series === "slope" ? bar.slope : bar.volatility })));
    }
    chart.timeScale().fitContent();
    return chart;
  }, [bars, mainSeries, runtimeCandles]);

  useResponsiveChart(mainRef, createMainChart);

  return (
    <div className="trading-chart-stack">
      <section className="chart-panel main-chart-panel">
        <header>
          <div><strong>SPX500</strong><span>30m · Candles</span></div>
          <div className="chart-legend"><span className="legend-candles">Price</span>{mainSeries.map(({ name }) => <span key={name}>{name}</span>)}</div>
        </header>
        <div className="chart-host" ref={mainRef} />
      </section>
      {panels.map((panel) => {
        const seriesItems = normalizedRoutes.filter(({ placement }) => placement === `panel:${panel.id}`);
        return seriesItems.length ? <LowerPanelChart key={panel.id} panel={panel} seriesItems={seriesItems} bars={bars} /> : null;
      })}
    </div>
  );
}
