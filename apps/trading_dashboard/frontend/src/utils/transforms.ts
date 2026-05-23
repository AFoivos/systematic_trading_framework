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

function isFeatureSourceType(sourceType: string): boolean {
  return sourceType === "feature" || sourceType === "computed_feature" || sourceType.endsWith("_feature");
}

function isIndicatorFeature(sourceType: VisualizationConfig["source_type"], name: string): boolean {
  if (!isFeatureSourceType(sourceType)) {
    return false;
  }
  const lowered = name.toLowerCase();
  return ["adx", "mfi", "bollinger", "bb_", "support", "resistance", "volume", "vwap"].some((token) =>
    lowered.includes(token)
  );
}

function defaultPlacement(
  sourceType: VisualizationConfig["source_type"],
  name: string
): Pick<VisualizationConfig, "chart_target" | "render_type" | "panel_id"> {
  const lowered = name.toLowerCase();
  if (isFeatureSourceType(sourceType)) {
    if (lowered === "vwap" || lowered.startsWith("vwap_")) {
      return { chart_target: "main_price_chart", render_type: "line", panel_id: null };
    }
    if (lowered.includes("shock") || lowered.includes("hist") || lowered.includes("regime") || lowered.includes("state")) {
      return { chart_target: "lower_panel", render_type: "histogram", panel_id: null };
    }
    return { chart_target: "lower_panel", render_type: "line", panel_id: null };
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
  const placement = defaultPlacement(sourceType, seriesId);
  return {
    series_id: seriesId,
    source_type: sourceType,
    display_name: seriesId,
    chart_target: placement.chart_target,
    render_type: placement.render_type,
    panel_id: placement.panel_id,
    y_axis: "right",
    visible: !isIndicatorFeature(sourceType, seriesId),
    style: {
      color: SERIES_COLORS[index % SERIES_COLORS.length],
      lineWidth: 2,
      opacity: 0.85,
      extra: {}
    }
  };
}

export interface LowerPanelGroup {
  id: string;
  title: string;
  configs: VisualizationConfig[];
}

function formatPanelTitle(panelId: string): string {
  return panelId
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function groupLowerPanelConfigs(configs: VisualizationConfig[]): LowerPanelGroup[] {
  const groups: LowerPanelGroup[] = [];
  const groupedById = new Map<string, LowerPanelGroup>();

  configs
    .filter((config) => config.visible && config.chart_target === "lower_panel")
    .forEach((config) => {
      const panelId = config.panel_id?.trim() || null;

      if (isFeatureSourceType(config.source_type) && !panelId) {
        groups.push({
          id: seriesKey(config.source_type, config.series_id),
          title: config.display_name,
          configs: [config]
        });
        return;
      }

      const resolvedPanelId = panelId || "signals";
      const existing = groupedById.get(resolvedPanelId);
      if (existing) {
        existing.configs.push(config);
        return;
      }
      const group = {
        id: resolvedPanelId,
        title: formatPanelTitle(resolvedPanelId),
        configs: [config]
      };
      groupedById.set(resolvedPanelId, group);
      groups.push(group);
    });

  return groups;
}
