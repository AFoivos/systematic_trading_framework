import { type CSSProperties, useEffect, useRef } from "react";
import {
  createChart,
  LineStyle,
  type IChartApi,
  type Range,
  type Time,
  type TimeRangeChangeEventHandler
} from "lightweight-charts";
import type { OHLCVCandle, TimeValuePoint, TradeRecord } from "../types/market";
import type { VisualizationConfig } from "../types/visualization";
import type { LowerPanelGroup } from "../utils/transforms";
import { toCandles, toHistogramData, toLineData, toTradeMarkers, toWhitespaceData } from "../utils/chartAdapters";
import { seriesKey } from "../utils/transforms";

export type ChartSizeMode = "standard" | "expanded";

export interface ManualPriceLine {
  id: string;
  kind: "stop_loss" | "take_profit";
  price: number;
  title: string;
  color: string;
  lineWidth: 1 | 2 | 3 | 4;
}

interface ChartProps {
  candles: OHLCVCandle[];
  overlays: VisualizationConfig[];
  seriesData: Record<string, TimeValuePoint[]>;
  trades: TradeRecord[];
  priceLines?: ManualPriceLine[];
  sizeMode?: ChartSizeMode;
}

interface SeriesPanelChartProps {
  title: string;
  configs: VisualizationConfig[];
  seriesData: Record<string, TimeValuePoint[]>;
}

interface LinkedChartStackProps {
  candles: OHLCVCandle[];
  overlays: VisualizationConfig[];
  panels: LowerPanelGroup[];
  seriesData: Record<string, TimeValuePoint[]>;
  trades: TradeRecord[];
  priceLines?: ManualPriceLine[];
  sizeMode?: ChartSizeMode;
}

interface ChartHeights {
  main: number;
  linkedMain: number;
  lower: number;
}

function chartHeights(sizeMode: ChartSizeMode): ChartHeights {
  if (sizeMode === "expanded") {
    return {
      main: 720,
      linkedMain: 620,
      lower: 224
    };
  }
  return {
    main: 520,
    linkedMain: 430,
    lower: 176
  };
}

function baseOptions(height: number, showTimeScale = true) {
  return {
    height,
    layout: {
      background: { color: "#ffffff" },
      textColor: "#2f3742",
      fontSize: 11,
      fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    },
    grid: {
      vertLines: { color: "#eef1f4" },
      horzLines: { color: "#eef1f4" }
    },
    rightPriceScale: {
      borderColor: "#d9dee5"
    },
    timeScale: {
      borderColor: "#d9dee5",
      visible: showTimeScale,
      timeVisible: true,
      secondsVisible: false
    },
    crosshair: {
      mode: 1
    }
  };
}

function chartHeight(container: HTMLDivElement, fallbackHeight: number): number {
  return Math.max(container.clientHeight || fallbackHeight, 1);
}

function resizeChart(chart: IChartApi, container: HTMLDivElement | null, fallbackHeight: number) {
  if (!container) {
    return;
  }
  chart.applyOptions({
    width: Math.max(container.clientWidth, 1),
    height: chartHeight(container, fallbackHeight)
  });
}

function observeChartContainer(chart: IChartApi, container: HTMLDivElement, fallbackHeight: number) {
  resizeChart(chart, container, fallbackHeight);

  if (typeof ResizeObserver === "undefined") {
    const onResize = () => resizeChart(chart, container, fallbackHeight);
    window.addEventListener("resize", onResize, { passive: true });
    return () => window.removeEventListener("resize", onResize);
  }

  const observer = new ResizeObserver(() => resizeChart(chart, container, fallbackHeight));
  observer.observe(container);
  return () => observer.disconnect();
}

function addConfiguredSeries(
  chart: IChartApi,
  configs: VisualizationConfig[],
  seriesData: Record<string, TimeValuePoint[]>
) {
  configs
    .filter((config) => config.visible)
    .forEach((config) => {
      const key = seriesKey(config.source_type, config.series_id);
      const points = seriesData[key] ?? [];
      const color = config.style.color ?? "#0f766e";
      if (config.render_type === "horizontal_level") {
        return;
      }
      if (config.render_type === "histogram") {
        const series = chart.addHistogramSeries({ color, priceScaleId: config.style.priceScaleId ?? "" });
        series.setData(toHistogramData(points, color));
        return;
      }
      const series = chart.addLineSeries({
        color,
        lineWidth: (config.style.lineWidth ?? 2) as 1 | 2 | 3 | 4,
        priceLineVisible: false,
        priceScaleId: config.style.priceScaleId ?? undefined
      });
      series.setData(toLineData(points));
    });
}

function syncVisibleTimeRanges(charts: IChartApi[]) {
  let syncing = false;
  const handlers: Array<[IChartApi, TimeRangeChangeEventHandler<Time>]> = [];
  const applyRange = (source: IChartApi, range: Range<Time> | null) => {
    if (syncing || range === null) {
      return;
    }
    syncing = true;
    charts.forEach((chart) => {
      if (chart !== source) {
        chart.timeScale().setVisibleRange(range);
      }
    });
    syncing = false;
  };

  charts.forEach((chart) => {
    const handler: TimeRangeChangeEventHandler<Time> = (range) => applyRange(chart, range);
    chart.timeScale().subscribeVisibleTimeRangeChange(handler);
    handlers.push([chart, handler]);
  });

  return () => {
    handlers.forEach(([chart, handler]) => chart.timeScale().unsubscribeVisibleTimeRangeChange(handler));
  };
}

function addManualPriceLines(candleSeries: ReturnType<IChartApi["addCandlestickSeries"]>, priceLines: ManualPriceLine[]) {
  priceLines.forEach((line) => {
    candleSeries.createPriceLine({
      price: line.price,
      color: line.color,
      lineWidth: line.lineWidth,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
      title: line.title
    });
  });
}

export function CandlestickChart({ candles, overlays, seriesData, trades, priceLines = [], sizeMode = "standard" }: ChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const heights = chartHeights(sizeMode);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }
    const container = containerRef.current;
    const chart = createChart(container, {
      ...baseOptions(chartHeight(container, heights.main)),
      width: Math.max(container.clientWidth, 1)
    });
    const candleSeries = chart.addCandlestickSeries({
      upColor: "#0f9f6e",
      downColor: "#d14f3f",
      borderVisible: false,
      wickUpColor: "#0f9f6e",
      wickDownColor: "#d14f3f"
    });
    candleSeries.setData(toCandles(candles));
    if (trades.length > 0) {
      candleSeries.setMarkers(toTradeMarkers(trades));
    }
    addManualPriceLines(candleSeries, priceLines);

    addConfiguredSeries(chart, overlays, seriesData);

    chart.timeScale().fitContent();
    const unobserve = observeChartContainer(chart, container, heights.main);
    return () => {
      unobserve();
      chart.remove();
    };
  }, [candles, overlays, priceLines, seriesData, sizeMode, trades, heights.main]);

  return <div className="chart-canvas main-canvas" ref={containerRef} style={{ height: `${heights.main}px` }} />;
}

export function LinkedChartStack({
  candles,
  overlays,
  panels,
  seriesData,
  trades,
  priceLines = [],
  sizeMode = "standard"
}: LinkedChartStackProps) {
  const mainRef = useRef<HTMLDivElement | null>(null);
  const panelRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const heights = chartHeights(sizeMode);
  const hasLowerPanels = panels.length > 0;

  useEffect(() => {
    if (!mainRef.current) {
      return;
    }

    const charts: IChartApi[] = [];
    const panelContainers = panels
      .map((panel) => ({ ...panel, container: panelRefs.current[panel.id] }))
      .filter((panel): panel is LowerPanelGroup & { container: HTMLDivElement } => {
        return panel.container !== null;
      });
    const mainFallbackHeight = hasLowerPanels ? heights.linkedMain : heights.main;
    const mainChart = createChart(mainRef.current, {
      ...baseOptions(chartHeight(mainRef.current, mainFallbackHeight), !hasLowerPanels),
      width: Math.max(mainRef.current.clientWidth, 1)
    });
    charts.push(mainChart);

    const candleSeries = mainChart.addCandlestickSeries({
      upColor: "#0f9f6e",
      downColor: "#d14f3f",
      borderVisible: false,
      wickUpColor: "#0f9f6e",
      wickDownColor: "#d14f3f"
    });
    candleSeries.setData(toCandles(candles));
    if (trades.length > 0) {
      candleSeries.setMarkers(toTradeMarkers(trades));
    }
    addManualPriceLines(candleSeries, priceLines);
    addConfiguredSeries(mainChart, overlays, seriesData);

    panelContainers.forEach(({ configs, container }, index) => {
      const isBottomPanel = index === panelContainers.length - 1;
      const chart = createChart(container, {
        ...baseOptions(chartHeight(container, heights.lower), isBottomPanel),
        width: Math.max(container.clientWidth, 1)
      });
      const timeAnchor = chart.addLineSeries({
        color: "rgba(0, 0, 0, 0)",
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false
      });
      timeAnchor.setData(toWhitespaceData(candles));
      addConfiguredSeries(chart, configs, seriesData);
      charts.push(chart);
    });

    charts[0]?.timeScale().fitContent();
    const unsubscribeSync = syncVisibleTimeRanges(charts);
    const initialRange = charts[0]?.timeScale().getVisibleRange();
    if (initialRange) {
      charts.slice(1).forEach((chart) => chart.timeScale().setVisibleRange(initialRange));
    }

    const unobserveCharts = [
      observeChartContainer(mainChart, mainRef.current, mainFallbackHeight),
      ...panelContainers.map(({ container }, index) => observeChartContainer(charts[index + 1], container, heights.lower))
    ];
    return () => {
      unobserveCharts.forEach((unobserve) => unobserve());
      unsubscribeSync();
      charts.forEach((chart) => chart.remove());
    };
  }, [candles, heights.linkedMain, heights.lower, heights.main, overlays, panels, priceLines, seriesData, sizeMode, trades]);

  const shellClassName = [
    "linked-chart-shell",
    hasLowerPanels ? "linked-chart-shell-with-panels" : "",
    sizeMode === "expanded" ? "linked-chart-shell-expanded" : ""
  ]
    .filter(Boolean)
    .join(" ");
  const mainHeight = sizeMode === "expanded" ? "100%" : `${hasLowerPanels ? heights.linkedMain : heights.main}px`;
  const lowerHeight = sizeMode === "expanded" ? "100%" : `${heights.lower}px`;

  return (
    <section className={shellClassName}>
      <div
        className="chart-canvas main-canvas linked-main-canvas"
        ref={mainRef}
        style={{ height: mainHeight }}
      />
      {panels.length > 0 ? (
        <div className="linked-lower-stack" style={{ "--lower-panel-count": panels.length } as CSSProperties}>
          {panels.map((panel) => (
            <section className="linked-lower-chart" key={panel.id}>
              <div className="panel-title">{panel.title}</div>
              <div
                className="chart-canvas lower-canvas linked-lower-canvas"
                style={{ height: lowerHeight }}
                ref={(node) => {
                  panelRefs.current[panel.id] = node;
                }}
              />
            </section>
          ))}
        </div>
      ) : null}
    </section>
  );
}

export function SeriesPanelChart({ title, configs, seriesData }: SeriesPanelChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }
    const container = containerRef.current;
    const chart = createChart(container, {
      ...baseOptions(chartHeight(container, 190)),
      width: Math.max(container.clientWidth, 1)
    });

    configs.forEach((config) => {
      const key = seriesKey(config.source_type, config.series_id);
      const points = seriesData[key] ?? [];
      const color = config.style.color ?? "#0f766e";
      if (config.render_type === "histogram") {
        const histogram = chart.addHistogramSeries({ color });
        histogram.setData(toHistogramData(points, color));
        return;
      }
      const line = chart.addLineSeries({
        color,
        lineWidth: (config.style.lineWidth ?? 2) as 1 | 2 | 3 | 4,
        priceLineVisible: false
      });
      line.setData(toLineData(points));
    });

    chart.timeScale().fitContent();
    const unobserve = observeChartContainer(chart, container, 190);
    return () => {
      unobserve();
      chart.remove();
    };
  }, [configs, seriesData]);

  return (
    <section className="lower-chart">
      <div className="panel-title">{title}</div>
      <div className="chart-canvas lower-canvas" ref={containerRef} />
    </section>
  );
}
