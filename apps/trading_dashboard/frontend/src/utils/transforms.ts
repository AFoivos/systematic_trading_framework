import type { CatalogItem } from "../types/market";
import type { VisualizationConfig } from "../types/visualization";

export const SERIES_COLORS = [
  "#0f766e",
  "#d97706",
  "#7c3aed",
  "#2563eb",
  "#be123c",
  "#4b5563",
  "#15803d",
  "#b45309"
];

export function seriesKey(sourceType: string, seriesId: string): string {
  return `${sourceType}:${seriesId}`;
}

export function flattenCatalog(catalog: Record<string, CatalogItem[]> | CatalogItem[] | null): CatalogItem[] {
  if (!catalog) {
    return [];
  }
  if (Array.isArray(catalog)) {
    return catalog;
  }
  return Object.values(catalog).flat();
}

function defaultPlacement(name: string): Pick<VisualizationConfig, "chart_target" | "render_type" | "panel_id"> {
  const lowered = name.toLowerCase();
  if (lowered.includes("ema") || lowered.includes("sma") || lowered.includes("trend")) {
    return { chart_target: "main_price_chart", render_type: "line", panel_id: null };
  }
  if (lowered.includes("shock") || lowered.includes("hist")) {
    return { chart_target: "lower_panel", render_type: "histogram", panel_id: "events" };
  }
  if (lowered.includes("rsi") || lowered.includes("stoch") || lowered.includes("osc")) {
    return { chart_target: "lower_panel", render_type: "line", panel_id: "oscillators" };
  }
  if (lowered.includes("regime") || lowered.includes("state")) {
    return { chart_target: "lower_panel", render_type: "histogram", panel_id: "regime" };
  }
  return { chart_target: "lower_panel", render_type: "line", panel_id: "features" };
}

export function buildDefaultSeriesConfig(
  sourceType: VisualizationConfig["source_type"],
  seriesId: string,
  index: number
): VisualizationConfig {
  const placement = defaultPlacement(seriesId);
  return {
    series_id: seriesId,
    source_type: sourceType,
    display_name: seriesId,
    chart_target: placement.chart_target,
    render_type: placement.render_type,
    panel_id: placement.panel_id,
    y_axis: "right",
    visible: true,
    style: {
      color: SERIES_COLORS[index % SERIES_COLORS.length],
      lineWidth: 2,
      opacity: 0.85,
      extra: {}
    }
  };
}

export function groupLowerPanelConfigs(configs: VisualizationConfig[]): Record<string, VisualizationConfig[]> {
  return configs
    .filter((config) => config.visible && config.chart_target === "lower_panel")
    .reduce<Record<string, VisualizationConfig[]>>((groups, config) => {
      const panelId = config.panel_id || "features";
      groups[panelId] = [...(groups[panelId] ?? []), config];
      return groups;
    }, {});
}

