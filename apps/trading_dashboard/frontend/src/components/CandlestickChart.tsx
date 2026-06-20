import { type CSSProperties, useEffect, useRef } from "react";
import {
  createChart,
  LineStyle,
  type IChartApi,
  type LogicalRangeChangeEventHandler
} from "lightweight-charts";
import type { OHLCVCandle, TimeValuePoint, TradeRecord } from "../types/market";
import type { VisualizationConfig } from "../types/visualization";
import { isFeatureSourceType, type LowerPanelGroup } from "../utils/transforms";
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

type RenderedSeriesApi =
  | ReturnType<IChartApi["addLineSeries"]>
  | ReturnType<IChartApi["addHistogramSeries"]>
  | ReturnType<IChartApi["addAreaSeries"]>;

const SHARED_PRICE_SCALE_WIDTH = 78;
const SHARED_TIME_SCALE_HEIGHT = 24;
const FEATURE_PRICE_FORMAT = {
  type: "price" as const,
  precision: 6,
  minMove: 0.000001
};

function priceFormatForConfig(config: VisualizationConfig) {
  return isFeatureSourceType(config.source_type) ? FEATURE_PRICE_FORMAT : undefined;
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
    leftPriceScale: {
      visible: false,
      minimumWidth: SHARED_PRICE_SCALE_WIDTH
    },
    rightPriceScale: {
      borderColor: "#d9dee5",
      minimumWidth: SHARED_PRICE_SCALE_WIDTH,
      scaleMargins: {
        top: 0.12,
        bottom: 0.12
      }
    },
    timeScale: {
      borderColor: "#d9dee5",
      visible: showTimeScale,
      timeVisible: true,
      secondsVisible: false,
      rightOffset: 0,
      barSpacing: 6,
      minBarSpacing: 0.5,
      lockVisibleTimeRangeOnResize: true,
      minimumHeight: SHARED_TIME_SCALE_HEIGHT
    },
    crosshair: {
      mode: 1,
      vertLine: {
        color: "#94a3b8",
        style: LineStyle.Dotted,
        width: 1 as 1
      },
      horzLine: {
        color: "#cbd5e1",
        style: LineStyle.Dotted,
        width: 1 as 1
      }
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

function rgbaColor(color: string, opacity: number): string {
  const normalized = color.trim();
  const match = normalized.match(/^#?([0-9a-f]{6})$/i);
  if (!match) {
    return normalized;
  }
  const value = match[1];
  const red = Number.parseInt(value.slice(0, 2), 16);
  const green = Number.parseInt(value.slice(2, 4), 16);
  const blue = Number.parseInt(value.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${opacity})`;
}

function isOscillatorConfig(config: VisualizationConfig): boolean {
  const lowered = config.series_id.toLowerCase();
  return ["rsi", "stoch", "mfi", "percent_b"].some((token) => lowered.includes(token));
}

function needsZeroReference(config: VisualizationConfig): boolean {
  const lowered = config.series_id.toLowerCase();
  return (
    config.render_type === "histogram" ||
    config.source_type.includes("signal") ||
    config.source_type.includes("target") ||
    ["zscore", "hist", "momentum", "ret", "return", "slope", "ratio"].some((token) => lowered.includes(token))
  );
}

function addPanelReferenceLines(referenceSeries: RenderedSeriesApi | undefined, configs: VisualizationConfig[]) {
  if (!referenceSeries) {
    return;
  }
  if (configs.some(needsZeroReference)) {
    referenceSeries.createPriceLine({
      price: 0,
      color: "#94a3b8",
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      axisLabelVisible: true,
      title: "0"
    });
  }
  if (configs.some(isOscillatorConfig)) {
    [30, 70].forEach((price) => {
      referenceSeries.createPriceLine({
        price,
        color: "#cbd5e1",
        lineWidth: 1,
        lineStyle: LineStyle.Dotted,
        axisLabelVisible: true,
        title: String(price)
      });
    });
  }
}

function addConfiguredSeries(
  chart: IChartApi,
  configs: VisualizationConfig[],
  seriesData: Record<string, TimeValuePoint[]>
) {
  const renderedSeries: RenderedSeriesApi[] = [];
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
        const series = chart.addHistogramSeries({
          color,
          priceFormat: priceFormatForConfig(config),
          priceScaleId: config.style.priceScaleId ?? ""
        });
        series.setData(toHistogramData(points, color));
        renderedSeries.push(series);
        return;
      }
      if (config.render_type === "area" || config.render_type === "probability_band") {
        const series = chart.addAreaSeries({
          lineColor: color,
          topColor: rgbaColor(color, config.style.opacity ?? 0.26),
          bottomColor: rgbaColor(color, 0.04),
          lineWidth: (config.style.lineWidth ?? 2) as 1 | 2 | 3 | 4,
          priceFormat: priceFormatForConfig(config),
          priceLineVisible: false,
          priceScaleId: config.style.priceScaleId ?? undefined
        });
        series.setData(toLineData(points));
        renderedSeries.push(series);
        return;
      }
      const series = chart.addLineSeries({
        color,
        lineWidth: (config.style.lineWidth ?? 2) as 1 | 2 | 3 | 4,
        priceFormat: priceFormatForConfig(config),
        priceLineVisible: false,
        priceScaleId: config.style.priceScaleId ?? undefined
      });
      series.setData(toLineData(points));
      renderedSeries.push(series);
    });
  return renderedSeries;
}

function syncVisibleLogicalRanges(charts: IChartApi[]) {
  let syncing = false;
  const handlers: Array<[IChartApi, LogicalRangeChangeEventHandler]> = [];
  const applyRange = (source: IChartApi, range: Parameters<LogicalRangeChangeEventHandler>[0]) => {
    if (syncing || range === null) {
      return;
    }
    syncing = true;
    charts.forEach((chart) => {
      if (chart !== source) {
        chart.timeScale().setVisibleLogicalRange(range);
      }
    });
    syncing = false;
  };

  charts.forEach((chart) => {
    const handler: LogicalRangeChangeEventHandler = (range) => applyRange(chart, range);
    chart.timeScale().subscribeVisibleLogicalRangeChange(handler);
    handlers.push([chart, handler]);
  });

  return () => {
    handlers.forEach(([chart, handler]) => chart.timeScale().unsubscribeVisibleLogicalRangeChange(handler));
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
      const renderedSeries = addConfiguredSeries(chart, configs, seriesData);
      addPanelReferenceLines(renderedSeries[0], configs);
      charts.push(chart);
    });

    charts[0]?.timeScale().fitContent();
    const unsubscribeSync = syncVisibleLogicalRanges(charts);
    const initialRange = charts[0]?.timeScale().getVisibleLogicalRange();
    if (initialRange) {
      charts.slice(1).forEach((chart) => chart.timeScale().setVisibleLogicalRange(initialRange));
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

    const renderedSeries = addConfiguredSeries(chart, configs, seriesData);
    addPanelReferenceLines(renderedSeries[0], configs);

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
