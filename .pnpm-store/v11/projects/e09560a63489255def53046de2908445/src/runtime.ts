import type { StudioDocument } from "./studio";

export interface RuntimePoint {
  time: string;
  value: number | null;
}

export interface RuntimeSeries {
  seriesId: string;
  label: string;
  sourceType: string;
  points: RuntimePoint[];
}

export interface RuntimeCandle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number | null;
}

interface TransformResponse {
  series: Array<{ series_id: string; source_type: string; points: RuntimePoint[] }>;
  steps: Array<{ output_columns: string[] }>;
  metadata: Record<string, unknown>;
}

const DEFAULT_DATASET = "data/raw/dukascopy_30m_clean/spx500_30m.csv";

async function apiJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Runtime request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export async function executeFeatureRuntime(document: StudioDocument): Promise<{
  candles: RuntimeCandle[];
  series: RuntimeSeries[];
  metadata: Record<string, unknown>;
}> {
  const features = document.nodes
    .filter((node) => node.kind === "feature" && node.feature?.enabled)
    .map((node) => ({
      step: node.feature!.kind,
      params: node.feature!.registryParams ?? {},
      enabled: true
    }));
  if (!features.length) throw new Error("Add and enable at least one feature before running.");

  const [transform, candles] = await Promise.all([
    apiJson<TransformResponse>("/api/transform/series", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataset_id: DEFAULT_DATASET, limit: 500, features })
    }),
    apiJson<RuntimeCandle[]>(`/api/ohlcv?dataset_id=${encodeURIComponent(DEFAULT_DATASET)}&limit=500`)
  ]);

  const configuredLabels = document.nodes
    .filter((node) => node.kind === "feature" && node.feature?.enabled)
    .flatMap((node) => node.feature?.outputs ?? []);

  return {
    candles,
    series: transform.series.map((series, index) => ({
      seriesId: series.series_id,
      label: configuredLabels[index] || series.series_id,
      sourceType: series.source_type,
      points: series.points
    })),
    metadata: transform.metadata
  };
}
