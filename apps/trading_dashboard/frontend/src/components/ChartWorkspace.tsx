import { type FormEvent, useEffect, useMemo, useState } from "react";
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
  onAddManualLevel: (kind: ManualLevelKind, price: number) => void;
  onRemoveSeries: (key: string) => void;
}

function parsePositivePrice(value: string): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
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

export function ChartWorkspace({
  candles,
  configs,
  seriesData,
  trades,
  loadingMessage,
  errorMessage,
  onAddManualLevel,
  onRemoveSeries
}: ChartWorkspaceProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [stopLossDraft, setStopLossDraft] = useState("");
  const [takeProfitDraft, setTakeProfitDraft] = useState("");
  const mainOverlays = useMemo(() => configs.filter((config) => config.chart_target === "main_price_chart"), [configs]);
  const lowerPanels: LowerPanelGroup[] = useMemo(() => groupLowerPanelConfigs(configs), [configs]);
  const visibleSeriesCount = useMemo(() => configs.filter((config) => config.visible).length, [configs]);
  const manualLevelConfigs = useMemo(() => configs.filter(isManualLevelConfig), [configs]);
  const priceLines = useMemo(() => manualLevelConfigs.flatMap((config) => manualPriceLineFromConfig(config) ?? []), [manualLevelConfigs]);
  const stopLossPrice = parsePositivePrice(stopLossDraft);
  const takeProfitPrice = parsePositivePrice(takeProfitDraft);

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

  const addPriceLine = (event: FormEvent<HTMLFormElement>, kind: ManualLevelKind) => {
    event.preventDefault();
    const price = kind === "stop_loss" ? stopLossPrice : takeProfitPrice;
    if (price === null) {
      return;
    }

    onAddManualLevel(kind, price);

    if (kind === "stop_loss") {
      setStopLossDraft("");
    } else {
      setTakeProfitDraft("");
    }
  };

  return (
    <>
      {isExpanded ? <div className="workspace-focus-backdrop" onClick={() => setIsExpanded(false)} /> : null}
      <main className={`workspace${isExpanded ? " workspace-expanded" : ""}`}>
        <div className="workspace-toolbar">
          <div className="workspace-status">
            <span>{candles.length.toLocaleString()} candles</span>
            <span>{visibleSeriesCount} visible series</span>
            <span>{trades.length.toLocaleString()} trades</span>
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
        <div className="price-line-controls" aria-label="Manual price levels">
          <form className="price-line-form" onSubmit={(event) => addPriceLine(event, "stop_loss")}>
            <label className="price-line-field">
              <span>Stop loss</span>
              <input
                type="number"
                inputMode="decimal"
                min="0"
                step="any"
                placeholder="Price"
                value={stopLossDraft}
                onChange={(event) => setStopLossDraft(event.target.value)}
              />
            </label>
            <button className="secondary-button price-line-add-button" type="submit" disabled={stopLossPrice === null}>
              Add
            </button>
          </form>
          <form className="price-line-form" onSubmit={(event) => addPriceLine(event, "take_profit")}>
            <label className="price-line-field">
              <span>Take profit</span>
              <input
                type="number"
                inputMode="decimal"
                min="0"
                step="any"
                placeholder="Price"
                value={takeProfitDraft}
                onChange={(event) => setTakeProfitDraft(event.target.value)}
              />
            </label>
            <button className="secondary-button price-line-add-button" type="submit" disabled={takeProfitPrice === null}>
              Add
            </button>
          </form>
          {manualLevelConfigs.length > 0 ? (
            <div className="price-line-list" aria-label="Active price levels">
              {manualLevelConfigs.map((config) => {
                const key = seriesKey(config.source_type, config.series_id);
                const kind = configKind(config);
                return (
                  <button
                    className={`price-line-chip price-line-chip-${kind}${config.visible ? "" : " price-line-chip-hidden"}`}
                    type="button"
                    key={key}
                    onClick={() => onRemoveSeries(key)}
                    title={`Remove ${config.display_name}`}
                  >
                    {config.display_name} x
                  </button>
                );
              })}
            </div>
          ) : null}
        </div>
        {isExpanded ? <div className="workspace-focus-copy">Esc closes the focused chart view.</div> : null}
        {errorMessage ? <div className="error-banner">{errorMessage}</div> : null}
        {loadingMessage ? <div className="loading-banner">{loadingMessage}</div> : null}
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
