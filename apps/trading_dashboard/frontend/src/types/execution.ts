export type JsonRecord = Record<string, unknown>;

export interface ExecutionAssetSummary {
  asset: string;
  mt5_symbol?: string | null;
  bar_time?: string | null;
  logged_at?: string | null;
  close?: number | null;
  spread?: number | null;
  signal_side?: number | string | null;
  order_action?: string | null;
  order_status?: string | null;
  order_reason?: string | null;
  has_decision_trace: boolean;
}

export interface ExecutionStatus {
  log_dir: string;
  health: JsonRecord;
  lock: JsonRecord;
  command?: string | null;
  account?: JsonRecord | null;
  latest_by_asset: ExecutionAssetSummary[];
  recent_events: JsonRecord[];
  files: JsonRecord[];
}

export interface ExecutionBotOption {
  id: string;
  label: string;
  log_dir: string;
  resolved_log_dir: string;
  config_path?: string | null;
  mode?: string | null;
  state: string;
  pid?: number | null;
  process_running?: boolean | null;
  last_heartbeat_at?: string | null;
  modified_at?: string | null;
  symbols: string[];
  has_logs: boolean;
  is_default: boolean;
}

export interface ExecutionBotOptionList {
  options: ExecutionBotOption[];
}

export interface ExecutionRecordList {
  log_dir: string;
  records: JsonRecord[];
}

export interface ExecutionFeatureSnapshot {
  log_dir: string;
  asset: string;
  mt5_symbol?: string | null;
  bar_time?: string | null;
  timeframe?: string | null;
  row_count: number;
  columns: string[];
  numeric_columns: string[];
  feature_columns: string[];
  market_columns: string[];
  records: JsonRecord[];
}

export interface MarketMakingSnapshot {
  run_dir: string;
  asset: string;
  row_count: number;
  columns: string[];
  numeric_columns: string[];
  feature_columns: string[];
  market_columns: string[];
  records: JsonRecord[];
  trades: JsonRecord[];
  summary: JsonRecord;
}
