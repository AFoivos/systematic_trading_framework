import type { DashboardTransformations } from "./transforms";

export type RenderType =
  | "candlestick"
  | "line"
  | "area"
  | "histogram"
  | "marker"
  | "background_band"
  | "horizontal_level"
  | "trade_marker"
  | "prediction_line"
  | "probability_band";

export type ChartTarget = "main_price_chart" | "lower_panel" | "candle_marker" | "background";

export interface SeriesStyle {
  color?: string | null;
  lineWidth?: number | null;
  opacity?: number | null;
  priceScaleId?: string | null;
  extra?: Record<string, unknown>;
}

export interface VisualizationConfig {
  series_id: string;
  source_type: "feature" | "signal" | "target" | "prediction" | string;
  display_name: string;
  chart_target: ChartTarget;
  panel_id?: string | null;
  render_type: RenderType;
  y_axis: "left" | "right";
  visible: boolean;
  style: SeriesStyle;
}

export interface DashboardSelection {
  asset: string;
  timeframe: string;
  source: string;
  datasetId: string;
  start: string;
  end: string;
  runId: string;
}

export interface DashboardLayout {
  layout_id?: string | null;
  name: string;
  description?: string | null;
  selection: Partial<DashboardSelection>;
  series: VisualizationConfig[];
  panels: Record<string, unknown>;
  transformations?: Partial<DashboardTransformations>;
  updated_at?: string | null;
}

export interface LayoutSummary {
  layout_id: string;
  name: string;
  path: string;
  updated_at: string | null;
}
