import { useEffect, useRef } from "react";
import {
  createChart,
  type IChartApi,
  type Range,
  type Time,
  type TimeRangeChangeEventHandler
} from "lightweight-charts";
import type { OHLCVCandle, TimeValuePoint, TradeRecord } from "../types/market";
import type { VisualizationConfig } from "../types/visualization";
import { toCandles, toHistogramData, toLineData, toTradeMarkers, toWhitespaceData } from "../utils/chartAdapters";
import { seriesKey } from "../utils/transforms";

interface ChartProps {
  candles: OHLCVCandle[];
  overlays: VisualizationConfig[];
  seriesData: Record<string, TimeValuePoint[]>;
  trades: TradeRecord[];
}

interface SeriesPanelChartProps {
  title: string;
  configs: VisualizationConfig[];
  seriesData: Record<string, TimeValuePoint[]>;
}

interface LinkedChartStackProps {
  candles: OHLCVCandle[];
  overlays: VisualizationConfig[];
  panels: Array<[string, VisualizationConfig[]]>;
  seriesData: Record<string, TimeValuePoint[]>;
  trades: TradeRecord[];
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

function resizeChart(chart: IChartApi, container: HTMLDivElement | null) {
  if (!container) {
    return;
  }
  chart.applyOptions({ width: container.clientWidth });
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

export function CandlestickChart({ candles, overlays, seriesData, trades }: ChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }
    const chart = createChart(containerRef.current, { ...baseOptions(520), width: containerRef.current.clientWidth });
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

    addConfiguredSeries(chart, overlays, seriesData);

    chart.timeScale().fitContent();
    const onResize = () => resizeChart(chart, containerRef.current);
    window.addEventListener("resize", onResize, { passive: true });
    return () => {
      window.removeEventListener("resize", onResize);
      chart.remove();
    };
  }, [candles, overlays, seriesData, trades]);

  return <div className="chart-canvas main-canvas" ref={containerRef} />;
}

export function LinkedChartStack({ candles, overlays, panels, seriesData, trades }: LinkedChartStackProps) {
  const mainRef = useRef<HTMLDivElement | null>(null);
  const panelRefs = useRef<Record<string, HTMLDivElement | null>>({});

  useEffect(() => {
    if (!mainRef.current) {
      return;
    }

    const charts: IChartApi[] = [];
    const panelContainers = panels
      .map(([panelId, configs]) => ({ panelId, configs, container: panelRefs.current[panelId] }))
      .filter((panel): panel is { panelId: string; configs: VisualizationConfig[]; container: HTMLDivElement } => {
        return panel.container !== null;
      });
    const hasLowerPanels = panelContainers.length > 0;
    const mainChart = createChart(mainRef.current, {
      ...baseOptions(hasLowerPanels ? 430 : 520, !hasLowerPanels),
      width: mainRef.current.clientWidth
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
    addConfiguredSeries(mainChart, overlays, seriesData);

    panelContainers.forEach(({ configs, container }, index) => {
      const isBottomPanel = index === panelContainers.length - 1;
      const chart = createChart(container, { ...baseOptions(176, isBottomPanel), width: container.clientWidth });
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

    const onResize = () => {
      resizeChart(mainChart, mainRef.current);
      panelContainers.forEach(({ panelId, container }) => {
        const chartIndex = panelContainers.findIndex((panel) => panel.panelId === panelId) + 1;
        resizeChart(charts[chartIndex], container);
      });
    };
    window.addEventListener("resize", onResize, { passive: true });
    return () => {
      window.removeEventListener("resize", onResize);
      unsubscribeSync();
      charts.forEach((chart) => chart.remove());
    };
  }, [candles, overlays, panels, seriesData, trades]);

  return (
    <section className="linked-chart-shell">
      <div className="chart-canvas main-canvas linked-main-canvas" ref={mainRef} />
      {panels.map(([panelId]) => (
        <section className="linked-lower-chart" key={panelId}>
          <div className="panel-title">{panelId}</div>
          <div
            className="chart-canvas lower-canvas linked-lower-canvas"
            ref={(node) => {
              panelRefs.current[panelId] = node;
            }}
          />
        </section>
      ))}
    </section>
  );
}

export function SeriesPanelChart({ title, configs, seriesData }: SeriesPanelChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }
    const chart = createChart(containerRef.current, { ...baseOptions(190), width: containerRef.current.clientWidth });

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
    const onResize = () => resizeChart(chart, containerRef.current);
    window.addEventListener("resize", onResize, { passive: true });
    return () => {
      window.removeEventListener("resize", onResize);
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
