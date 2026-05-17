export interface ExperimentSummary {
  run_id: string;
  name: string;
  path: string;
  created_at_utc: string | null;
  asset: string | null;
  timeframe: string | null;
  config_hash_sha256: string | null;
  has_trades: boolean;
  has_equity: boolean;
  metrics: Record<string, unknown>;
}

export interface ExperimentDetail {
  run_id: string;
  name: string;
  path: string;
  metadata: Record<string, unknown>;
  config: Record<string, unknown>;
  metrics: Record<string, unknown>;
  artifacts: Array<Record<string, unknown>>;
  available_predictions: string[];
  available_trades: string[];
  available_equity: string | null;
}

