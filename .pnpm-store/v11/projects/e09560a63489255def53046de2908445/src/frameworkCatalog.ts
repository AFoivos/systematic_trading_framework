import rawCatalog from "./frameworkCatalog.generated.json";
import type { NodeKind } from "./studio";

export type ParameterValue = string | number | boolean | null | unknown[] | Record<string, unknown>;

export interface ParameterDefinition {
  name: string;
  kind?: "string" | "integer" | "number" | "boolean" | "list" | "object" | "any";
  required: boolean;
  default_value?: ParameterValue;
  default?: ParameterValue;
  annotation?: string | null;
  options?: ParameterValue[] | null;
  description?: string | null;
}

export interface ComponentDefinition {
  name: string;
  display_name?: string | null;
  description?: string | null;
  source_type: string;
  import_path?: string;
  parameters: ParameterDefinition[];
  docstring?: string | null;
}

export const frameworkCatalog = rawCatalog as Record<"features" | "signals" | "targets" | "models", ComponentDefinition[]>;

const catalogKey: Partial<Record<NodeKind, keyof typeof frameworkCatalog>> = {
  feature: "features",
  signal: "signals",
  target: "targets",
  model: "models"
};

export function definitionsFor(kind: NodeKind): ComponentDefinition[] {
  const key = catalogKey[kind];
  return key ? frameworkCatalog[key] : [];
}

export function definitionFor(kind: NodeKind, name: string): ComponentDefinition | undefined {
  const definitions = definitionsFor(kind);
  const normalized = name.trim().toLowerCase().replace(/[\s-]+/g, "_");
  return definitions.find((item) => item.name === name)
    ?? definitions.find((item) => item.name === normalized)
    ?? definitions.find((item) => item.name.startsWith(`${normalized}_`));
}

export function defaultsFor(definition: ComponentDefinition | undefined): Record<string, ParameterValue> {
  return Object.fromEntries((definition?.parameters ?? []).map((parameter) => [
    parameter.name,
    parameter.default_value ?? parameter.default ?? (parameter.kind === "boolean" ? false : "")
  ]));
}
