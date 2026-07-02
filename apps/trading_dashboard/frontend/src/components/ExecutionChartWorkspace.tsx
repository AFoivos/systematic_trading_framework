import { useEffect, useMemo, useState } from "react";
import type { ExecutionFeatureSnapshot, MarketMakingSnapshot } from "../types/execution";
import type { OHLCVCandle, TimeValuePoint, TradeRecord } from "../types/market";
import type { ChartTarget, RenderType, VisualizationConfig } from "../types/visualization";
import { buildDefaultSeriesConfig, groupLowerPanelConfigs, seriesKey } from "../utils/transforms";
import { LinkedChartStack } from "./CandlestickChart";

const EXECUTION_SOURCE = "execution_feature";
type ChartSnapshot = ExecutionFeatureSnapshot | MarketMakingSnapshot;
const chartTargets: Array<{ value: ChartTarget; label: string }> = [
  { value: "main_price_chart", label: "Main chart" },
  { value: "lower_panel", label: "Lower panel" }
];
const renderTypes: RenderType[] = ["line", "area", "histogram"];

function numericValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function recordTime(record: Record<string, unknown>): string | null {
  const value = record.time;
  return typeof value === "string" && value.trim() ? value : null;
}

function snapshotCandles(snapshot: ChartSnapshot): OHLCVCandle[] {
  return snapshot.records.flatMap((record) => {
    const time = recordTime(record);
    const open = numericValue(record.open);
    const high = numericValue(record.high);
    const low = numericValue(record.low);
    const close = numericValue(record.close);
    if (!time || open === null || high === null || low === null || close === null) {
      return [];
    }
    return [{ time, open, high, low, close, volume: numericValue(record.volume ?? record.tick_volume) }];
  });
}

function snapshotSeries(snapshot: ChartSnapshot): Record<string, TimeValuePoint[]> {
  return snapshot.feature_columns.reduce<Record<string, TimeValuePoint[]>>((result, column) => {
    result[seriesKey(EXECUTION_SOURCE, column)] = snapshot.records.flatMap((record) => {
      const time = recordTime(record);
      const value = numericValue(record[column]);
      return time && value !== null ? [{ time, value }] : [];
    });
    return result;
  }, {});
}

function newConfig(column: string, index: number): VisualizationConfig {
  if (column === "mid_price" || column === "mark_price") {
    return {
      ...buildDefaultSeriesConfig(EXECUTION_SOURCE, column, index),
      chart_target: "main_price_chart",
      render_type: "line",
      panel_id: null,
      visible: column === "mid_price"
    };
  }
  return {
    ...buildDefaultSeriesConfig(EXECUTION_SOURCE, column, index),
    visible: index === 0
  };
}

function syncConfigs(current: VisualizationConfig[], columns: string[]): VisualizationConfig[] {
  const available = new Set(columns);
  const retained = current.filter((config) => available.has(config.series_id));
  const existing = new Set(retained.map((config) => config.series_id));
  const additions = columns.flatMap((column, index) =>
    existing.has(column) ? [] : [newConfig(column, retained.length + index)]
  );
  return [...retained, ...additions];
}

interface ExecutionChartWorkspaceProps {
  snapshot: ChartSnapshot | null;
  trades?: TradeRecord[];
  emptyLabel?: string;
  sourceLabel?: string;
}

export function ExecutionChartWorkspace({
  snapshot,
  trades = [],
  emptyLabel = "No chart snapshot yet",
  sourceLabel = "Updated"
}: ExecutionChartWorkspaceProps) {
  const [configs, setConfigs] = useState<VisualizationConfig[]>([]);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [isExpanded, setIsExpanded] = useState(false);

  const columnsKey = snapshot?.feature_columns.join("|") ?? "";
  useEffect(() => {
    const columns = snapshot?.feature_columns ?? [];
    setConfigs((current) => syncConfigs(current, columns));
  }, [snapshot?.asset, columnsKey]);

  useEffect(() => {
    if (activeKey && configs.some((config) => seriesKey(config.source_type, config.series_id) === activeKey)) {
      return;
    }
    const first = configs[0];
    setActiveKey(first ? seriesKey(first.source_type, first.series_id) : null);
  }, [activeKey, configs]);

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

  const candles = useMemo(() => (snapshot ? snapshotCandles(snapshot) : []), [snapshot]);
  const seriesData = useMemo(() => (snapshot ? snapshotSeries(snapshot) : {}), [snapshot]);
  const overlays = useMemo(
    () => configs.filter((config) => config.visible && config.chart_target === "main_price_chart"),
    [configs]
  );
  const panels = useMemo(() => groupLowerPanelConfigs(configs), [configs]);
  const snapshotTime = useMemo(() => {
    if (!snapshot) {
      return null;
    }
    if ("bar_time" in snapshot && snapshot.bar_time) {
      return snapshot.bar_time;
    }
    const lastRecord = snapshot.records[snapshot.records.length - 1];
    return lastRecord ? recordTime(lastRecord) : null;
  }, [snapshot]);
  const active = configs.find((config) => seriesKey(config.source_type, config.series_id) === activeKey) ?? null;
  const normalizedQuery = query.trim().toLowerCase();
  const filteredConfigs = useMemo(
    () => configs.filter((config) => `${config.series_id} ${config.display_name}`.toLowerCase().includes(normalizedQuery)),
    [configs, normalizedQuery]
  );
  const visibleCount = configs.filter((config) => config.visible).length;

  const updateConfig = (key: string, patch: Partial<VisualizationConfig>) => {
    setConfigs((current) =>
      current.map((config) =>
        seriesKey(config.source_type, config.series_id) === key ? { ...config, ...patch } : config
      )
    );
  };

  if (!snapshot || snapshot.row_count === 0) {
    return <p className="empty-copy">{emptyLabel}</p>;
  }
  if (configs.length === 0) {
    return <p className="empty-copy">No numeric feature columns found</p>;
  }

  return (
    <>
    {isExpanded ? <div className="workspace-focus-backdrop" onClick={() => setIsExpanded(false)} /> : null}
    <div className={`execution-chart-workspace${isExpanded ? " execution-chart-workspace-expanded" : ""}`}>
      <div className="execution-chart-stage">
        <div className="execution-chart-toolbar">
          <div className="workspace-status execution-chart-status">
            <span>{candles.length.toLocaleString()} candles</span>
            <span>{visibleCount} visible features</span>
            <span>{"timeframe" in snapshot ? snapshot.timeframe || "timeframe n/a" : "event stream"}</span>
            <span>{sourceLabel} {snapshotTime ? new Date(snapshotTime).toLocaleString() : "n/a"}</span>
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
        {candles.length === 0 ? (
          <div className="warning-banner">The live snapshot does not contain complete OHLC rows; feature panels remain available.</div>
        ) : null}
        <LinkedChartStack
          candles={candles}
          overlays={overlays}
          panels={panels}
          seriesData={seriesData}
          trades={trades}
          sizeMode={isExpanded ? "expanded" : "standard"}
        />
        <div className="execution-chart-legend" aria-label="Visible feature legend">
          {configs.filter((config) => config.visible).map((config) => (
            <span key={seriesKey(config.source_type, config.series_id)}>
              <i style={{ backgroundColor: config.style.color ?? "#0f766e" }} />
              {config.display_name}
              <small>{config.chart_target === "main_price_chart" ? "main" : config.panel_id || "lower"}</small>
            </span>
          ))}
        </div>
      </div>

      <aside className="execution-feature-controls">
        <div className="section-heading-row">
          <h2>Live Features</h2>
          <span>{visibleCount}/{configs.length}</span>
        </div>
        <label className="field">
          <span>Search</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="feature name" />
        </label>
        <div className="execution-feature-list">
          {filteredConfigs.map((config) => {
            const key = seriesKey(config.source_type, config.series_id);
            return (
              <div className={`execution-feature-row${key === activeKey ? " active" : ""}`} key={key}>
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={config.visible}
                    onChange={(event) => updateConfig(key, { visible: event.target.checked })}
                  />
                  <span>{config.display_name}</span>
                </label>
                <button type="button" className="link-button" onClick={() => setActiveKey(key)}>Edit</button>
              </div>
            );
          })}
        </div>

        {active && activeKey ? (
          <div className="execution-feature-editor">
            <h3>Feature setup</h3>
            <label className="field">
              <span>Name</span>
              <input value={active.display_name} onChange={(event) => updateConfig(activeKey, { display_name: event.target.value })} />
            </label>
            <label className="field">
              <span>Placement</span>
              <select
                value={active.chart_target}
                onChange={(event) => updateConfig(activeKey, { chart_target: event.target.value as ChartTarget })}
              >
                {chartTargets.map((target) => <option key={target.value} value={target.value}>{target.label}</option>)}
              </select>
            </label>
            <label className="field">
              <span>Lower panel name</span>
              <input
                disabled={active.chart_target !== "lower_panel"}
                value={active.panel_id ?? ""}
                placeholder="empty = dedicated panel"
                onChange={(event) => updateConfig(activeKey, { panel_id: event.target.value || null })}
              />
              <small className="field-hint">Use the same name to place multiple features in one panel.</small>
            </label>
            <label className="field">
              <span>Render type</span>
              <select value={active.render_type} onChange={(event) => updateConfig(activeKey, { render_type: event.target.value as RenderType })}>
                {renderTypes.map((type) => <option key={type} value={type}>{type}</option>)}
              </select>
            </label>
            <div className="execution-feature-style-row">
              <label className="field">
                <span>Color</span>
                <input
                  type="color"
                  value={active.style.color ?? "#0f766e"}
                  onChange={(event) => updateConfig(activeKey, { style: { ...active.style, color: event.target.value } })}
                />
              </label>
              <label className="field">
                <span>Line width</span>
                <input
                  type="number"
                  min="1"
                  max="4"
                  value={active.style.lineWidth ?? 2}
                  onChange={(event) => updateConfig(activeKey, { style: { ...active.style, lineWidth: Number(event.target.value) } })}
                />
              </label>
            </div>
          </div>
        ) : null}
      </aside>
    </div>
    </>
  );
}
