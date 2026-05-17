import type { OHLCVCandle, TimeValuePoint, TradeRecord } from "../types/market";
import type { VisualizationConfig } from "../types/visualization";
import { groupLowerPanelConfigs } from "../utils/transforms";
import { LinkedChartStack } from "./CandlestickChart";

interface ChartWorkspaceProps {
  candles: OHLCVCandle[];
  configs: VisualizationConfig[];
  seriesData: Record<string, TimeValuePoint[]>;
  trades: TradeRecord[];
  loadingMessage: string | null;
  errorMessage: string | null;
}

export function ChartWorkspace({
  candles,
  configs,
  seriesData,
  trades,
  loadingMessage,
  errorMessage
}: ChartWorkspaceProps) {
  const mainOverlays = configs.filter((config) => config.chart_target === "main_price_chart");
  const lowerPanels = groupLowerPanelConfigs(configs);
  const lowerPanelEntries = Object.entries(lowerPanels);
  return (
    <main className="workspace">
      <div className="workspace-status">
        <span>{candles.length.toLocaleString()} candles</span>
        <span>{configs.filter((config) => config.visible).length} visible series</span>
        <span>{trades.length.toLocaleString()} trades</span>
      </div>
      {errorMessage ? <div className="error-banner">{errorMessage}</div> : null}
      {loadingMessage ? <div className="loading-banner">{loadingMessage}</div> : null}
      <LinkedChartStack
        candles={candles}
        overlays={mainOverlays}
        panels={lowerPanelEntries}
        seriesData={seriesData}
        trades={trades}
      />
    </main>
  );
}
