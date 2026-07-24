export type NodeKind = "data" | "feature" | "target" | "model" | "signal" | "backtest";
export type NormalizationKind = "rolling_zscore" | "range_position" | "rolling_clip";
export type HelperKind = "slope" | "ratio";

export interface Normalization {
  id: string;
  kind: NormalizationKind;
  window: number;
  shift: number;
  enabled: boolean;
}

export interface Helper {
  id: string;
  kind: HelperKind;
  left: string;
  right: string;
  window?: number;
  enabled: boolean;
}

export interface FeatureConfig {
  kind: "volatility" | "trend" | "momentum";
  rollingWindows: number[];
  returnsCol: string;
  annualizationFactor: string;
  enabled: boolean;
  normalizations: Normalization[];
  helpers: Helper[];
  outputs: string[];
}

export interface StudioNode {
  id: string;
  kind: NodeKind;
  title: string;
  subtitle: string;
  x: number;
  y: number;
  feature?: FeatureConfig;
}

export interface StudioDocument {
  version: 2;
  name: string;
  nodes: StudioNode[];
}

export interface ValidationIssue {
  id: string;
  level: "error" | "warning";
  message: string;
  nodeId?: string;
}

export interface StudioRunResult {
  runId: string;
  startedAt: string;
  completedAt: string;
  durationMs: number;
  nodeCount: number;
  featureCount: number;
  normalizationCount: number;
  helperCount: number;
  previewRowCount: number;
  previewMetrics: PreviewMetrics;
  outputColumns: string[];
  warnings: string[];
}

export interface PreviewMetrics {
  startTimestamp: string;
  endTimestamp: string;
  durationMinutes: number;
  closeChangePct: number;
  meanAbsoluteReturnPct: number;
  missingValueCount: number;
}

export interface PreviewRow {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  returns: number;
  vol_96_z: number;
  slope_8: number;
}

export const previewRows: PreviewRow[] = [
  { timestamp: "2024-05-10 13:00", open: 5257.75, high: 5261.25, low: 5252.25, close: 5257.0, returns: 0.00317, vol_96_z: -0.8123, slope_8: 0.0132 },
  { timestamp: "2024-05-10 13:30", open: 5257.0, high: 5260.5, low: 5251.75, close: 5255.75, returns: -0.00024, vol_96_z: -0.8451, slope_8: 0.0204 },
  { timestamp: "2024-05-10 14:00", open: 5255.75, high: 5262.25, low: 5255.25, close: 5261.25, returns: 0.00105, vol_96_z: -0.7649, slope_8: 0.0278 },
  { timestamp: "2024-05-10 14:30", open: 5261.25, high: 5264.0, low: 5256.25, close: 5263.5, returns: 0.00043, vol_96_z: -0.7432, slope_8: 0.0312 }
];

export function summarizePreviewRows(rows: PreviewRow[]): PreviewMetrics {
  if (!rows.length) {
    return {
      startTimestamp: "",
      endTimestamp: "",
      durationMinutes: 0,
      closeChangePct: 0,
      meanAbsoluteReturnPct: 0,
      missingValueCount: 0
    };
  }
  const first = rows[0];
  const last = rows[rows.length - 1];
  const startMs = Date.parse(first.timestamp.replace(" ", "T"));
  const endMs = Date.parse(last.timestamp.replace(" ", "T"));
  let missingValueCount = 0;
  let absoluteReturnTotal = 0;
  for (const row of rows) {
    for (const value of Object.values(row)) {
      if (value === null || value === undefined || (typeof value === "number" && !Number.isFinite(value))) {
        missingValueCount += 1;
      }
    }
    absoluteReturnTotal += Math.abs(row.returns);
  }
  return {
    startTimestamp: first.timestamp,
    endTimestamp: last.timestamp,
    durationMinutes: Number.isFinite(startMs) && Number.isFinite(endMs)
      ? Math.max(0, Math.round((endMs - startMs) / 60_000))
      : 0,
    closeChangePct: first.close === 0 ? 0 : ((last.close / first.close) - 1) * 100,
    meanAbsoluteReturnPct: (absoluteReturnTotal / rows.length) * 100,
    missingValueCount
  };
}

const STORAGE_KEY = "trading-studio:document:v2";
const KIND_ORDER: NodeKind[] = ["data", "feature", "target", "model", "signal", "backtest"];
const REQUIRED_KINDS = new Set<NodeKind>(KIND_ORDER);
const NODE_WIDTH = 112;
const NODE_HEIGHT = 120;

export function newId(prefix: string): string {
  const suffix = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${suffix}`;
}

export function createDefaultFeatureConfig(): FeatureConfig {
  return {
    kind: "volatility",
    rollingWindows: [96, 252],
    returnsCol: "close_ret",
    annualizationFactor: "auto",
    enabled: true,
    normalizations: [
      { id: newId("norm"), kind: "rolling_zscore", window: 252, shift: 1, enabled: true }
    ],
    helpers: [
      { id: newId("helper"), kind: "slope", left: "vol_rolling_96", right: "", window: 8, enabled: true },
      { id: newId("helper"), kind: "ratio", left: "vol_slope_8", right: "close", enabled: true }
    ],
    outputs: ["vol_rolling_96", "vol_rolling_96__zscore", "vol_slope_8", "vol_slope_over_close"]
  };
}

export function createNode(kind: NodeKind, title: string, x: number, y: number): StudioNode {
  return {
    id: newId(kind),
    kind,
    title,
    subtitle: kind[0].toUpperCase() + kind.slice(1),
    x,
    y,
    feature: kind === "feature" ? createDefaultFeatureConfig() : undefined
  };
}

export function createInitialDocument(): StudioDocument {
  return {
    version: 2,
    name: "SPX500 Momentum Research",
    nodes: [
      { id: "dataset", kind: "data", title: "SPX500 30m", subtitle: "Dataset", x: 18, y: 172 },
      {
        id: "volatility",
        kind: "feature",
        title: "Volatility",
        subtitle: "Feature",
        x: 145,
        y: 160,
        feature: createDefaultFeatureConfig()
      },
      { id: "target", kind: "target", title: "Forward return", subtitle: "Target · horizon 8", x: 272, y: 172 },
      { id: "model", kind: "model", title: "LightGBM", subtitle: "Model · walk-forward", x: 399, y: 172 },
      { id: "signal", kind: "signal", title: "Probability threshold", subtitle: "Signal · 0.60 / 0.40", x: 526, y: 172 },
      { id: "backtest", kind: "backtest", title: "Backtest", subtitle: "Costs · slippage", x: 653, y: 172 }
    ]
  };
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isStoredDocument(value: unknown): value is StudioDocument {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<StudioDocument>;
  if (candidate.version !== 2 || typeof candidate.name !== "string" || !Array.isArray(candidate.nodes)) return false;
  return candidate.nodes.every((node) => {
    if (!node || typeof node !== "object") return false;
    const item = node as Partial<StudioNode>;
    const validNode = (
      typeof item.id === "string" &&
      typeof item.title === "string" &&
      typeof item.subtitle === "string" &&
      KIND_ORDER.includes(item.kind as NodeKind) &&
      isFiniteNumber(item.x) &&
      isFiniteNumber(item.y)
    );
    if (!validNode || item.kind !== "feature") return validNode;
    const feature = item.feature as Partial<FeatureConfig> | undefined;
    return Boolean(
      feature &&
      ["volatility", "trend", "momentum"].includes(String(feature.kind)) &&
      Array.isArray(feature.rollingWindows) &&
      feature.rollingWindows.every(isFiniteNumber) &&
      typeof feature.returnsCol === "string" &&
      typeof feature.annualizationFactor === "string" &&
      typeof feature.enabled === "boolean" &&
      Array.isArray(feature.normalizations) &&
      Array.isArray(feature.helpers) &&
      Array.isArray(feature.outputs) &&
      feature.outputs.every((output) => typeof output === "string")
    );
  });
}

export function loadStoredDocument(): StudioDocument {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return createInitialDocument();
    const parsed: unknown = JSON.parse(raw);
    return isStoredDocument(parsed) ? parsed : createInitialDocument();
  } catch {
    return createInitialDocument();
  }
}

export function saveStoredDocument(document: StudioDocument): boolean {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(document));
    return true;
  } catch {
    return false;
  }
}

export function nodeSubtitle(node: StudioNode): string {
  if (node.kind !== "feature" || !node.feature) return node.subtitle;
  const enabledNormalizations = node.feature.normalizations.filter((item) => item.enabled).length;
  const enabledHelpers = node.feature.helpers.filter((item) => item.enabled).length;
  return `${enabledNormalizations} normalization${enabledNormalizations === 1 ? "" : "s"} · ${enabledHelpers} helper${enabledHelpers === 1 ? "" : "s"}`;
}

function pushIssue(
  issues: ValidationIssue[],
  level: ValidationIssue["level"],
  message: string,
  nodeId?: string
): void {
  issues.push({ id: `${level}-${issues.length + 1}`, level, message, nodeId });
}

export function validateStudioDocument(document: StudioDocument): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  if (!document.name.trim()) {
    pushIssue(issues, "error", "Experiment name is required.");
  }
  if (!document.nodes.length) {
    pushIssue(issues, "error", "The pipeline is empty.");
    return issues;
  }

  const ids = new Set<string>();
  for (const node of document.nodes) {
    if (ids.has(node.id)) {
      pushIssue(issues, "error", `Duplicate node id "${node.id}".`, node.id);
    }
    ids.add(node.id);
    if (!node.title.trim()) {
      pushIssue(issues, "error", `${node.kind} node requires a name.`, node.id);
    }
    if (!Number.isFinite(node.x) || !Number.isFinite(node.y) || node.x < 0 || node.y < 0) {
      pushIssue(issues, "error", `${node.title || node.kind} has an invalid canvas position.`, node.id);
    }
  }

  for (const kind of REQUIRED_KINDS) {
    if (!document.nodes.some((node) => node.kind === kind)) {
      pushIssue(issues, "error", `Pipeline requires at least one ${kind} node.`);
    }
  }

  const ordered = [...document.nodes].sort((left, right) => left.x - right.x || left.y - right.y);
  let previousOrder = -1;
  for (const node of ordered) {
    const currentOrder = KIND_ORDER.indexOf(node.kind);
    if (currentOrder < previousOrder) {
      pushIssue(
        issues,
        "error",
        `${node.title} is out of pipeline order. Expected data → feature → target → model → signal → backtest.`,
        node.id
      );
    }
    previousOrder = Math.max(previousOrder, currentOrder);
  }

  for (let leftIndex = 0; leftIndex < document.nodes.length; leftIndex += 1) {
    const left = document.nodes[leftIndex];
    for (let rightIndex = leftIndex + 1; rightIndex < document.nodes.length; rightIndex += 1) {
      const right = document.nodes[rightIndex];
      const overlaps =
        left.x < right.x + NODE_WIDTH &&
        left.x + NODE_WIDTH > right.x &&
        left.y < right.y + NODE_HEIGHT &&
        left.y + NODE_HEIGHT > right.y;
      if (overlaps) {
        pushIssue(issues, "warning", `${left.title} overlaps ${right.title} on the canvas.`, right.id);
      }
    }
  }

  const featureNodes = document.nodes.filter((node) => node.kind === "feature");
  if (featureNodes.length && !featureNodes.some((node) => node.feature?.enabled)) {
    pushIssue(issues, "error", "At least one feature node must be enabled.");
  }
  for (const node of featureNodes) {
    const feature = node.feature;
    if (!feature) {
      pushIssue(issues, "error", `${node.title} is missing feature configuration.`, node.id);
      continue;
    }
    if (!feature.rollingWindows.length || feature.rollingWindows.some((window) => !Number.isInteger(window) || window < 2)) {
      pushIssue(issues, "error", `${node.title}: rolling windows must be integers greater than 1.`, node.id);
    }
    if (!feature.returnsCol.trim()) {
      pushIssue(issues, "error", `${node.title}: returns column is required.`, node.id);
    }
    for (const normalization of feature.normalizations) {
      if (!normalization.enabled) continue;
      if (!Number.isInteger(normalization.window) || normalization.window < 2) {
        pushIssue(issues, "error", `${node.title}: ${normalization.kind} window must be an integer greater than 1.`, node.id);
      }
      if (!Number.isInteger(normalization.shift) || normalization.shift < 1) {
        pushIssue(
          issues,
          "error",
          `${node.title}: ${normalization.kind} shift must be at least 1 to preserve temporal causality.`,
          node.id
        );
      }
    }
    for (const helper of feature.helpers) {
      if (!helper.enabled) continue;
      if (!helper.left.trim()) {
        pushIssue(issues, "error", `${node.title}: ${helper.kind} source column is required.`, node.id);
      }
      if (helper.kind === "slope" && (!Number.isInteger(helper.window) || Number(helper.window) < 2)) {
        pushIssue(issues, "error", `${node.title}: slope window must be an integer greater than 1.`, node.id);
      }
      if (helper.kind === "ratio") {
        if (!helper.right.trim()) {
          pushIssue(issues, "error", `${node.title}: ratio denominator column is required.`, node.id);
        } else if (helper.left.trim() === helper.right.trim()) {
          pushIssue(issues, "warning", `${node.title}: ratio numerator and denominator are identical.`, node.id);
        }
      }
    }
    const outputs = feature.outputs.map((output) => output.trim());
    if (outputs.some((output) => !output)) {
      pushIssue(issues, "error", `${node.title}: output names cannot be empty.`, node.id);
    }
    if (new Set(outputs).size !== outputs.length) {
      pushIssue(issues, "error", `${node.title}: output names must be unique.`, node.id);
    }
  }

  return issues;
}

function yamlString(value: string): string {
  return JSON.stringify(value);
}

function yamlBoolean(value: boolean): string {
  return value ? "true" : "false";
}

export function serializeStudioYaml(document: StudioDocument): string {
  const lines = [
    "studio_version: 2",
    "experiment:",
    `  name: ${yamlString(document.name)}`,
    "pipeline:"
  ];

  for (const node of [...document.nodes].sort((left, right) => left.x - right.x || left.y - right.y)) {
    lines.push(
      `  - id: ${yamlString(node.id)}`,
      `    kind: ${node.kind}`,
      `    name: ${yamlString(node.title)}`,
      `    position: { x: ${Math.round(node.x)}, y: ${Math.round(node.y)} }`
    );
    if (node.kind !== "feature" || !node.feature) continue;
    const feature = node.feature;
    lines.push(
      "    config:",
      `      feature_kind: ${feature.kind}`,
      `      enabled: ${yamlBoolean(feature.enabled)}`,
      `      returns_col: ${yamlString(feature.returnsCol)}`,
      `      rolling_windows: [${feature.rollingWindows.join(", ")}]`,
      `      annualization_factor: ${yamlString(feature.annualizationFactor)}`,
      "      normalizations:"
    );
    if (!feature.normalizations.length) {
      lines.push("        []");
    } else {
      for (const item of feature.normalizations) {
        lines.push(
          `        - kind: ${item.kind}`,
          `          enabled: ${yamlBoolean(item.enabled)}`,
          `          window: ${item.window}`,
          `          shift: ${item.shift}`
        );
      }
    }
    lines.push("      helpers:");
    if (!feature.helpers.length) {
      lines.push("        []");
    } else {
      for (const item of feature.helpers) {
        lines.push(
          `        - kind: ${item.kind}`,
          `          enabled: ${yamlBoolean(item.enabled)}`,
          `          source_col: ${yamlString(item.left)}`
        );
        if (item.kind === "slope") lines.push(`          window: ${item.window ?? 0}`);
        if (item.kind === "ratio") lines.push(`          denominator_col: ${yamlString(item.right)}`);
      }
    }
    lines.push("      outputs:");
    if (!feature.outputs.length) {
      lines.push("        []");
    } else {
      for (const output of feature.outputs) lines.push(`        - ${yamlString(output)}`);
    }
  }
  return `${lines.join("\n")}\n`;
}

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "studio-run";
}

export function executeStudioDocument(
  document: StudioDocument,
  startedAtMs: number,
  completedAtMs: number
): StudioRunResult {
  const issues = validateStudioDocument(document);
  const errors = issues.filter((issue) => issue.level === "error");
  if (errors.length) {
    throw new Error(errors.map((issue) => issue.message).join(" "));
  }
  const features = document.nodes
    .filter((node) => node.kind === "feature" && node.feature?.enabled)
    .map((node) => node.feature as FeatureConfig);
  const outputColumns = [...new Set(features.flatMap((feature) => feature.outputs.filter(Boolean)))];
  const completedAt = Math.max(startedAtMs, completedAtMs);
  return {
    runId: `${slugify(document.name)}-${startedAtMs}`,
    startedAt: new Date(startedAtMs).toISOString(),
    completedAt: new Date(completedAt).toISOString(),
    durationMs: completedAt - startedAtMs,
    nodeCount: document.nodes.length,
    featureCount: features.length,
    normalizationCount: features.reduce(
      (total, feature) => total + feature.normalizations.filter((item) => item.enabled).length,
      0
    ),
    helperCount: features.reduce(
      (total, feature) => total + feature.helpers.filter((item) => item.enabled).length,
      0
    ),
    previewRowCount: previewRows.length,
    previewMetrics: summarizePreviewRows(previewRows),
    outputColumns,
    warnings: issues.filter((issue) => issue.level === "warning").map((issue) => issue.message)
  };
}
