import { useEffect, useMemo, useState } from "react";
import type { OHLCVCandle, TimeValuePoint, TradeRecord } from "../types/market";
import type { ManualLevelKind, VisualizationConfig } from "../types/visualization";
import { groupLowerPanelConfigs, seriesKey, type LowerPanelGroup } from "../utils/transforms";
import { LinkedChartStack, type ManualPriceLine } from "./CandlestickChart";

interface ChartWorkspaceProps {
  candles: OHLCVCandle[];
  configs: VisualizationConfig[];
  seriesData: Record<string, TimeValuePoint[]>;
  trades: TradeRecord[];
  loadingMessage: string | null;
  errorMessage: string | null;
  dataWindowLabel: string;
}

function configPrice(config: VisualizationConfig): number | null {
  const price = config.style.extra?.price;
  const parsed = typeof price === "number" ? price : Number(price);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function configKind(config: VisualizationConfig): ManualLevelKind {
  return config.style.extra?.kind === "take_profit" ? "take_profit" : "stop_loss";
}

function lineWidth(value: number | null | undefined): 1 | 2 | 3 | 4 {
  if (!Number.isFinite(value)) {
    return 2;
  }
  if ((value ?? 2) <= 1) {
    return 1;
  }
  if ((value ?? 2) <= 2) {
    return 2;
  }
  if ((value ?? 2) <= 3) {
    return 3;
  }
  return 4;
}

function isManualLevelConfig(config: VisualizationConfig): boolean {
  return config.source_type === "manual_level" && config.render_type === "horizontal_level" && configPrice(config) !== null;
}

function manualPriceLineFromConfig(config: VisualizationConfig): ManualPriceLine | null {
  const price = configPrice(config);
  if (!config.visible || price === null) {
    return null;
  }
  return {
    id: seriesKey(config.source_type, config.series_id),
    kind: configKind(config),
    price,
    title: config.display_name,
    color: config.style.color ?? "#0f766e",
    lineWidth: lineWidth(config.style.lineWidth)
  };
}

function isDataBackedSeries(config: VisualizationConfig): boolean {
  return config.source_type !== "manual_level" && config.render_type !== "horizontal_level";
}

function missingVisibleSeries(configs: VisualizationConfig[], seriesData: Record<string, TimeValuePoint[]>): string[] {
  return configs
    .filter((config) => config.visible && isDataBackedSeries(config))
    .filter((config) => (seriesData[seriesKey(config.source_type, config.series_id)] ?? []).length === 0)
    .map((config) => config.display_name);
}

export function ChartWorkspace({
  candles,
  configs,
  seriesData,
  trades,
  loadingMessage,
  errorMessage,
  dataWindowLabel
}: ChartWorkspaceProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const mainOverlays = useMemo(() => configs.filter((config) => config.chart_target === "main_price_chart"), [configs]);
  const lowerPanels: LowerPanelGroup[] = useMemo(() => groupLowerPanelConfigs(configs), [configs]);
  const visibleSeriesCount = useMemo(() => configs.filter((config) => config.visible).length, [configs]);
  const manualLevelConfigs = useMemo(() => configs.filter(isManualLevelConfig), [configs]);
  const priceLines = useMemo(() => manualLevelConfigs.flatMap((config) => manualPriceLineFromConfig(config) ?? []), [manualLevelConfigs]);
  const missingSeries = useMemo(() => missingVisibleSeries(configs, seriesData), [configs, seriesData]);

  useEffect(() => {
    if (!isExpanded) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsExpanded(false);
      }
    };

    document.body.classList.add("dashboard-focus-active");
    window.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.classList.remove("dashboard-focus-active");
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [isExpanded]);

  return (
    <>
      {isExpanded ? <div className="workspace-focus-backdrop" onClick={() => setIsExpanded(false)} /> : null}
      <main className={`workspace${isExpanded ? " workspace-expanded" : ""}`}>
        <div className="workspace-toolbar">
          <div className="workspace-status">
            <span>{candles.length.toLocaleString()} candles</span>
            <span>{visibleSeriesCount} visible series</span>
            <span>{trades.length.toLocaleString()} trades</span>
            <span>{dataWindowLabel}</span>
          </div>
          <button
            className="secondary-button workspace-toggle-button"
            type="button"
            aria-pressed={isExpanded}
            onClick={() => setIsExpanded((value) => !value)}
          >
            {isExpanded ? "Exit fullscreen" : "Fullscreen chart"}
          </button>
        </div>
        {errorMessage ? <div className="error-banner">{errorMessage}</div> : null}
        {loadingMessage ? <div className="loading-banner">{loadingMessage}</div> : null}
        {missingSeries.length > 0 ? (
          <div className="warning-banner">
            No points in the current chart window for {missingSeries.slice(0, 4).join(", ")}
            {missingSeries.length > 4 ? ` and ${missingSeries.length - 4} more` : ""}.
          </div>
        ) : null}
        <LinkedChartStack
          candles={candles}
          overlays={mainOverlays}
          panels={lowerPanels}
          seriesData={seriesData}
          trades={trades}
          priceLines={priceLines}
          sizeMode={isExpanded ? "expanded" : "standard"}
        />
      </main>
    </>
  );
}
