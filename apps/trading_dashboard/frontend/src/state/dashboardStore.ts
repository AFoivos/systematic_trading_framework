import { create } from "zustand";
import type {
  AssetSummary,
  CatalogItem,
  DatasetSummary,
  FeatureCatalog,
  NamedSeries,
  OHLCVCandle,
  TimeValuePoint,
  TradeRecord
} from "../types/market";
import type { ExperimentSummary } from "../types/experiment";
import type { BuilderDefinition, BuilderSourceType, TransformStepConfig } from "../types/transforms";
import type { DashboardLayout, DashboardSelection, LayoutSummary, ManualLevelKind, VisualizationConfig } from "../types/visualization";
import { buildDefaultSeriesConfig, seriesKey } from "../utils/transforms";

interface DashboardState {
  assets: AssetSummary[];
  timeframes: string[];
  datasets: DatasetSummary[];
  experiments: ExperimentSummary[];
  layouts: LayoutSummary[];
  featureCatalog: FeatureCatalog;
  signalCatalog: CatalogItem[];
  targetCatalog: CatalogItem[];
  featureBuilders: BuilderDefinition[];
  signalBuilders: BuilderDefinition[];
  targetBuilders: BuilderDefinition[];
  featureSteps: TransformStepConfig[];
  signalSteps: TransformStepConfig[];
  targetSteps: TransformStepConfig[];
  selection: DashboardSelection;
  selectedFeatureIds: string[];
  selectedSignalIds: string[];
  selectedTargetIds: string[];
  seriesConfigs: VisualizationConfig[];
  activeSeriesKey: string | null;
  manualLevelCounter: number;
  candles: OHLCVCandle[];
  seriesData: Record<string, TimeValuePoint[]>;
  trades: TradeRecord[];
  equity: TimeValuePoint[];
  loadingMessage: string | null;
  errorMessage: string | null;
  setBootstrapData: (data: {
    assets?: AssetSummary[];
    datasets: DatasetSummary[];
    experiments: ExperimentSummary[];
    layouts: LayoutSummary[];
  }) => void;
  setTimeframes: (timeframes: string[]) => void;
  setCatalogs: (catalogs: {
    featureCatalog: FeatureCatalog;
    signalCatalog: CatalogItem[];
    targetCatalog: CatalogItem[];
  }) => void;
  setBuilderDefinitions: (builders: {
    featureBuilders: BuilderDefinition[];
    signalBuilders: BuilderDefinition[];
    targetBuilders: BuilderDefinition[];
  }) => void;
  setSelection: (selection: Partial<DashboardSelection>) => void;
  setSelectedSeries: (sourceType: "feature" | "signal" | "target", ids: string[]) => void;
  setTransformSteps: (sourceType: BuilderSourceType, steps: TransformStepConfig[]) => void;
  addManualLevel: (kind: ManualLevelKind, price: number) => void;
  removeSeriesConfig: (key: string) => void;
  mergeComputedSeries: (series: NamedSeries[]) => void;
  updateSeriesConfig: (key: string, patch: Partial<VisualizationConfig>) => void;
  setActiveSeriesKey: (key: string | null) => void;
  setMarketData: (payload: {
    candles?: OHLCVCandle[];
    seriesData?: Record<string, TimeValuePoint[]>;
    trades?: TradeRecord[];
    equity?: TimeValuePoint[];
  }) => void;
  setLoadingMessage: (message: string | null) => void;
  setErrorMessage: (message: string | null) => void;
  applyLayout: (layout: DashboardLayout) => void;
  toLayout: (name: string) => DashboardLayout;
}

const emptySelection: DashboardSelection = {
  asset: "",
  timeframe: "",
  source: "raw",
  datasetId: "",
  start: "",
  end: "",
  runId: ""
};

function selectedIdsForSource(state: DashboardState, sourceType: "feature" | "signal" | "target"): string[] {
  if (sourceType === "feature") {
    return state.selectedFeatureIds;
  }
  if (sourceType === "signal") {
    return state.selectedSignalIds;
  }
  return state.selectedTargetIds;
}

function ensureSeriesConfigs(
  configs: VisualizationConfig[],
  sourceType: "feature" | "signal" | "target",
  ids: string[]
): VisualizationConfig[] {
  const selectedKeys = new Set(ids.map((id) => seriesKey(sourceType, id)));
  const retained = configs.filter((config) => config.source_type !== sourceType || selectedKeys.has(seriesKey(config.source_type, config.series_id)));
  const existing = new Set(retained.map((config) => seriesKey(config.source_type, config.series_id)));
  const additions = ids.flatMap((id, index) =>
    existing.has(seriesKey(sourceType, id)) ? [] : [buildDefaultSeriesConfig(sourceType, id, retained.length + index)]
  );
  return [...retained, ...additions];
}

const manualLevelFormatter = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 6
});

function manualLevelLabel(kind: ManualLevelKind): string {
  return kind === "stop_loss" ? "Stop loss" : "Take profit";
}

function buildManualLevelConfig(kind: ManualLevelKind, price: number, index: number): VisualizationConfig {
  const label = manualLevelLabel(kind);
  return {
    series_id: `${kind}_${index}`,
    source_type: "manual_level",
    display_name: `${label} ${manualLevelFormatter.format(price)}`,
    chart_target: "main_price_chart",
    render_type: "horizontal_level",
    panel_id: null,
    y_axis: "right",
    visible: true,
    style: {
      color: kind === "stop_loss" ? "#c2410c" : "#0f766e",
      lineWidth: 2,
      opacity: 1,
      extra: {
        kind,
        price
      }
    }
  };
}

function nextActiveSeriesKey(configs: VisualizationConfig[]): string | null {
  const first = configs[0];
  return first ? seriesKey(first.source_type, first.series_id) : null;
}

function manualLevelCounterFromConfigs(configs: VisualizationConfig[]): number {
  return configs.reduce((current, config) => {
    if (config.source_type !== "manual_level") {
      return current;
    }
    const match = config.series_id.match(/_(\d+)$/);
    return match ? Math.max(current, Number(match[1])) : current;
  }, 0);
}

export const useDashboardStore = create<DashboardState>((set, get) => ({
  assets: [],
  timeframes: [],
  datasets: [],
  experiments: [],
  layouts: [],
  featureCatalog: {},
  signalCatalog: [],
  targetCatalog: [],
  featureBuilders: [],
  signalBuilders: [],
  targetBuilders: [],
  featureSteps: [],
  signalSteps: [],
  targetSteps: [],
  selection: emptySelection,
  selectedFeatureIds: [],
  selectedSignalIds: [],
  selectedTargetIds: [],
  seriesConfigs: [],
  activeSeriesKey: null,
  manualLevelCounter: 0,
  candles: [],
  seriesData: {},
  trades: [],
  equity: [],
  loadingMessage: null,
  errorMessage: null,
  setBootstrapData: ({ assets = [], datasets, experiments, layouts }) => {
    const firstDataset = datasets[0];
    set((state) => ({
      assets,
      datasets,
      experiments,
      layouts,
      selection: {
        ...state.selection,
        asset: state.selection.datasetId ? state.selection.asset : firstDataset?.assets[0] ?? "",
        timeframe: state.selection.datasetId ? state.selection.timeframe : firstDataset?.timeframe ?? "",
        source: state.selection.datasetId ? state.selection.source : firstDataset?.source ?? firstDataset?.stage ?? "",
        datasetId: state.selection.datasetId || firstDataset?.id || ""
      }
    }));
  },
  setTimeframes: (timeframes) => set({ timeframes }),
  setCatalogs: ({ featureCatalog, signalCatalog, targetCatalog }) =>
    set({ featureCatalog, signalCatalog, targetCatalog }),
  setBuilderDefinitions: ({ featureBuilders, signalBuilders, targetBuilders }) =>
    set({ featureBuilders, signalBuilders, targetBuilders }),
  setSelection: (selection) =>
    set((state) => ({
      selection: { ...state.selection, ...selection }
    })),
  setSelectedSeries: (sourceType, ids) =>
    set((state) => {
      const nextConfigs = ensureSeriesConfigs(state.seriesConfigs, sourceType, ids);
      return {
        selectedFeatureIds: sourceType === "feature" ? ids : state.selectedFeatureIds,
        selectedSignalIds: sourceType === "signal" ? ids : state.selectedSignalIds,
        selectedTargetIds: sourceType === "target" ? ids : state.selectedTargetIds,
        seriesConfigs: nextConfigs,
        activeSeriesKey:
          state.activeSeriesKey && nextConfigs.some((config) => seriesKey(config.source_type, config.series_id) === state.activeSeriesKey)
            ? state.activeSeriesKey
            : nextConfigs[0]
              ? seriesKey(nextConfigs[0].source_type, nextConfigs[0].series_id)
              : null
      };
    }),
  setTransformSteps: (sourceType, steps) =>
    set((state) => ({
      featureSteps: sourceType === "feature" ? steps : state.featureSteps,
      signalSteps: sourceType === "signal" ? steps : state.signalSteps,
      targetSteps: sourceType === "target" ? steps : state.targetSteps
    })),
  addManualLevel: (kind, price) =>
    set((state) => {
      const manualLevelCounter = state.manualLevelCounter + 1;
      const config = buildManualLevelConfig(kind, price, manualLevelCounter);
      return {
        manualLevelCounter,
        seriesConfigs: [...state.seriesConfigs, config],
        activeSeriesKey: seriesKey(config.source_type, config.series_id)
      };
    }),
  removeSeriesConfig: (key) =>
    set((state) => {
      const seriesConfigs = state.seriesConfigs.filter((config) => seriesKey(config.source_type, config.series_id) !== key);
      return {
        seriesConfigs,
        activeSeriesKey: state.activeSeriesKey === key ? nextActiveSeriesKey(seriesConfigs) : state.activeSeriesKey
      };
    }),
  mergeComputedSeries: (series) =>
    set((state) => {
      const nextData = { ...state.seriesData };
      const nextConfigs = [...state.seriesConfigs];
      const existing = new Set(nextConfigs.map((config) => seriesKey(config.source_type, config.series_id)));
      for (const item of series) {
        const sourceType = item.source_type.startsWith("computed_") ? item.source_type : `computed_${item.source_type}`;
        const key = seriesKey(sourceType, item.series_id);
        nextData[key] = item.points;
        if (!existing.has(key)) {
          nextConfigs.push(buildDefaultSeriesConfig(sourceType, item.series_id, nextConfigs.length));
          existing.add(key);
        }
      }
      return {
        seriesData: nextData,
        seriesConfigs: nextConfigs,
        activeSeriesKey:
          state.activeSeriesKey && nextConfigs.some((config) => seriesKey(config.source_type, config.series_id) === state.activeSeriesKey)
            ? state.activeSeriesKey
            : nextConfigs[0]
              ? seriesKey(nextConfigs[0].source_type, nextConfigs[0].series_id)
              : null
      };
    }),
  updateSeriesConfig: (key, patch) =>
    set((state) => ({
      seriesConfigs: state.seriesConfigs.map((config) =>
        seriesKey(config.source_type, config.series_id) === key ? { ...config, ...patch } : config
      )
    })),
  setActiveSeriesKey: (key) => set({ activeSeriesKey: key }),
  setMarketData: (payload) => set((state) => ({ ...state, ...payload })),
  setLoadingMessage: (message) => set({ loadingMessage: message }),
  setErrorMessage: (message) => set({ errorMessage: message }),
  applyLayout: (layout) =>
    set((state) => ({
      selection: { ...state.selection, ...layout.selection },
      seriesConfigs: layout.series,
      manualLevelCounter: Math.max(state.manualLevelCounter, manualLevelCounterFromConfigs(layout.series)),
      featureSteps: layout.transformations?.features ?? state.featureSteps,
      signalSteps: layout.transformations?.signals ?? state.signalSteps,
      targetSteps: layout.transformations?.targets ?? state.targetSteps,
      selectedFeatureIds: layout.series.filter((config) => config.source_type === "feature").map((config) => config.series_id),
      selectedSignalIds: layout.series.filter((config) => config.source_type === "signal").map((config) => config.series_id),
      selectedTargetIds: layout.series.filter((config) => config.source_type === "target").map((config) => config.series_id),
      activeSeriesKey: layout.series[0] ? seriesKey(layout.series[0].source_type, layout.series[0].series_id) : null
    })),
  toLayout: (name) => {
    const state = get();
    return {
      name,
      selection: state.selection,
      series: state.seriesConfigs,
      panels: {},
      transformations: {
        features: state.featureSteps,
        signals: state.signalSteps,
        targets: state.targetSteps
      },
      updated_at: new Date().toISOString()
    };
  }
}));

export function useSelectedIds(sourceType: "feature" | "signal" | "target"): string[] {
  return useDashboardStore((state) => selectedIdsForSource(state, sourceType));
}
