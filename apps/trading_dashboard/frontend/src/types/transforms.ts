import type { NamedSeries } from "./market";

export type ParameterKind = "string" | "integer" | "number" | "boolean" | "list" | "object" | "any";
export type BuilderSourceType = "feature" | "signal" | "target";

export interface ParameterDefinition {
  name: string;
  kind: ParameterKind;
  required: boolean;
  default_value: unknown;
  annotation: string | null;
  options: unknown[] | null;
  description: string | null;
}

export interface BuilderDefinition {
  name: string;
  source_type: BuilderSourceType;
  import_path: string | null;
  parameters: ParameterDefinition[];
  docstring: string | null;
}

export interface TransformStepConfig {
  step: string;
  params: Record<string, unknown>;
  outputs?: Record<string, string> | null;
  enabled: boolean;
}

export interface DashboardTransformations {
  features: TransformStepConfig[];
  signals: TransformStepConfig[];
  targets: TransformStepConfig[];
}

export interface TransformSeriesRequest {
  asset: string;
  timeframe?: string | null;
  source?: string | null;
  dataset_id?: string | null;
  start?: string | null;
  end?: string | null;
  limit?: number | null;
  features: TransformStepConfig[];
  signals: TransformStepConfig[];
  targets: TransformStepConfig[];
}

export interface TransformStepResult {
  source_type: BuilderSourceType;
  step: string;
  output_columns: string[];
  metadata: Record<string, unknown>;
}

export interface TransformSeriesResponse {
  series: NamedSeries[];
  steps: TransformStepResult[];
  metadata: Record<string, unknown>;
}
