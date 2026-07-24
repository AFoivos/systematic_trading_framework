export type ChartPlacement = "main" | "lower" | "hidden";

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
