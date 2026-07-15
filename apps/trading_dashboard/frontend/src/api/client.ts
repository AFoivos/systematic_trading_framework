import type {
  AssetSummary,
  CatalogItem,
  DatasetSummary,
  FeatureCatalog,
  OHLCVCandle,
  SeriesResponse,
  TradeRecord,
  TimeValuePoint
} from "../types/market";
import type {
  ExecutionBotOptionList,
  ExecutionFeatureSnapshot,
  ExecutionRecordList,
  ExecutionStatus,
  MarketMakingSnapshot
} from "../types/execution";
import type { DashboardLayout, LayoutSummary } from "../types/visualization";
import type { ExperimentDetail, ExperimentSummary } from "../types/experiment";
import type { BuilderDefinition, TransformSeriesRequest, TransformSeriesResponse } from "../types/transforms";

function resolveApiBase(): string {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  if (import.meta.env.DEV) {
    return "http://127.0.0.1:8000";
  }
  return window.location.origin;
}

const API_BASE = resolveApiBase();

type Params = Record<string, string | number | null | undefined>;

function buildUrl(path: string, params?: Params): string {
  const url = new URL(path, API_BASE);
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value !== null && value !== undefined && String(value).trim() !== "") {
      url.searchParams.set(key, String(value));
    }
  });
  return url.toString();
}

async function request<T>(path: string, params?: Params, init?: RequestInit): Promise<T> {
  const response = await fetch(buildUrl(path, params), {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    ...init
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => undefined);
    const detail = payload?.detail ?? `${response.status} ${response.statusText}`;
    throw new Error(String(detail));
  }
  return response.json() as Promise<T>;
}

export const api = {
  assets: () => request<AssetSummary[]>("/api/assets"),
  timeframes: (asset: string) => request<string[]>("/api/timeframes", { asset }),
  datasets: () => request<DatasetSummary[]>("/api/datasets"),
  ohlcv: (params: Params) => request<OHLCVCandle[]>("/api/ohlcv", params),
  featureCatalog: (params: Params) => request<FeatureCatalog>("/api/features/catalog", params),
  featureSeries: (params: Params) => request<SeriesResponse>("/api/features/series", params),
  featureBuilders: () => request<BuilderDefinition[]>("/api/features/builders"),
  predictionCatalog: (params: Params) => request<CatalogItem[]>("/api/predictions/catalog", params),
  predictionSeries: (params: Params) => request<SeriesResponse>("/api/predictions/series", params),
  signalCatalog: (params: Params) => request<CatalogItem[]>("/api/signals/catalog", params),
  signalSeries: (params: Params) => request<SeriesResponse>("/api/signals/series", params),
  signalBuilders: () => request<BuilderDefinition[]>("/api/signals/builders"),
  targetCatalog: (params: Params) => request<CatalogItem[]>("/api/targets/catalog", params),
  targetSeries: (params: Params) => request<SeriesResponse>("/api/targets/series", params),
  targetBuilders: () => request<BuilderDefinition[]>("/api/targets/builders"),
  transformSeries: (payload: TransformSeriesRequest) =>
    request<TransformSeriesResponse>("/api/transform/series", undefined, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  experiments: () => request<ExperimentSummary[]>("/api/experiments"),
  experiment: (runId: string) => request<ExperimentDetail>(`/api/experiments/${encodeURIComponent(runId)}`),
  trades: (runId: string, params?: Params) => request<TradeRecord[]>(`/api/backtests/${encodeURIComponent(runId)}/trades`, params),
  equity: (runId: string) => request<TimeValuePoint[]>(`/api/backtests/${encodeURIComponent(runId)}/equity`),
  executionBots: () => request<ExecutionBotOptionList>("/api/execution/bots"),
  executionStatus: (params?: Params) => request<ExecutionStatus>("/api/execution/status", params),
  executionDecisions: (params?: Params) => request<ExecutionRecordList>("/api/execution/decisions", params),
  executionEvents: (params?: Params) => request<ExecutionRecordList>("/api/execution/events", params),
  executionFeatures: (asset: string, params?: Params) =>
    request<ExecutionFeatureSnapshot>(`/api/execution/features/${encodeURIComponent(asset)}`, params),
  marketMakingSnapshot: (params?: Params) => request<MarketMakingSnapshot>("/api/execution/market-making", params),
  layouts: () => request<LayoutSummary[]>("/api/layouts"),
  layout: (layoutId: string) => request<DashboardLayout>(`/api/layouts/${encodeURIComponent(layoutId)}`),
  saveLayout: (layout: DashboardLayout) =>
    request<DashboardLayout>("/api/layouts", undefined, {
      method: "POST",
      body: JSON.stringify(layout)
    })
};
