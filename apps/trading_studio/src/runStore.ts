export type ChartPlacement = "main" | "hidden" | "lower" | `panel:${string}`;

export interface ChartPanelDefinition {
  id: string;
  name: string;
}

export interface StoredRun {
  id: string;
  experimentName: string;
  createdAt: string;
  status: "completed";
  asset: string;
  timeframe: string;
  nodes: Array<{
    id: string;
    kind: string;
    title: string;
    subtitle: string;
  }>;
  chartRoutes: Record<string, ChartPlacement>;
  chartPanels?: ChartPanelDefinition[];
  candles?: Array<{ time: string; open: number; high: number; low: number; close: number; volume?: number | null }>;
  series?: Array<{
    seriesId: string;
    label: string;
    sourceType: string;
    points: Array<{ time: string; value: number | null }>;
  }>;
  runtimeMetadata?: Record<string, unknown>;
  yaml: string;
}

const STORAGE_KEY = "trading-studio:runs:v1";

export function listRuns(): StoredRun[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]") as StoredRun[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function getRun(runId: string): StoredRun | null {
  return listRuns().find((run) => run.id === runId) ?? null;
}

export function saveRun(run: StoredRun): void {
  const previous = listRuns().filter((item) => item.id !== run.id);
  localStorage.setItem(STORAGE_KEY, JSON.stringify([run, ...previous].slice(0, 50)));
}
