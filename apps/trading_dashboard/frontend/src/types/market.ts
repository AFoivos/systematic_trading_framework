export interface AssetSummary {
  symbol: string;
  dataset_count: number;
}

export interface DatasetSummary {
  id: string;
  path: string;
  relative_path: string;
  stage: string;
  source: string;
  assets: string[];
  timeframe: string | null;
  format: string;
  columns: string[];
  metadata_path: string | null;
}

export interface OHLCVCandle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
}

export interface CatalogItem {
  name: string;
  category: string;
  dtype: string;
  dataset_id?: string | null;
}

export type FeatureCatalog = Record<string, CatalogItem[]>;

export interface TimeValuePoint {
  time: string;
  value: number | string | boolean | null;
}

export interface NamedSeries {
  series_id: string;
  source_type: string;
  points: TimeValuePoint[];
}

export interface SeriesResponse {
  series: NamedSeries[];
}

export interface TradeRecord {
  entry_time: string | null;
  exit_time: string | null;
  side: "long" | "short" | string;
  entry_price: number | null;
  exit_price: number | null;
  pnl: number | null;
  return: number | null;
  size: number | null;
}

