import type { AssetSummary, CatalogItem, DatasetSummary, FeatureCatalog } from "../types/market";
import type { ExperimentSummary } from "../types/experiment";
import type { BuilderDefinition, BuilderSourceType, TransformStepConfig } from "../types/transforms";
import type { DashboardSelection, LayoutSummary } from "../types/visualization";
import { AssetSelector } from "./AssetSelector";
import { BacktestOverlaySelector } from "./BacktestOverlaySelector";
import { BuilderConfigurator } from "./BuilderConfigurator";
import { DateRangeSelector } from "./DateRangeSelector";
import { FeatureSelector } from "./FeatureSelector";
import { LayoutManager } from "./LayoutManager";
import { PredictionSelector } from "./PredictionSelector";
import { SignalSelector } from "./SignalSelector";
import { TargetSelector } from "./TargetSelector";
import { TimeframeSelector } from "./TimeframeSelector";

interface ControlPanelProps {
  assets: AssetSummary[];
  timeframes: string[];
  datasets: DatasetSummary[];
  experiments: ExperimentSummary[];
  layouts: LayoutSummary[];
  selection: DashboardSelection;
  featureCatalog: FeatureCatalog;
  signalCatalog: CatalogItem[];
  targetCatalog: CatalogItem[];
  featureBuilders: BuilderDefinition[];
  signalBuilders: BuilderDefinition[];
  targetBuilders: BuilderDefinition[];
  featureSteps: TransformStepConfig[];
  signalSteps: TransformStepConfig[];
  targetSteps: TransformStepConfig[];
  selectedFeatureIds: string[];
  selectedSignalIds: string[];
  selectedTargetIds: string[];
  onSelectionChange: (selection: Partial<DashboardSelection>) => void;
  onSelectedSeriesChange: (sourceType: "feature" | "signal" | "target", ids: string[]) => void;
  onTransformStepsChange: (sourceType: BuilderSourceType, steps: TransformStepConfig[]) => void;
  onRunTransform: () => void;
  onSaveLayout: (name: string) => void;
  onLoadLayout: (layoutId: string) => void;
}

export function ControlPanel({
  assets,
  timeframes,
  datasets,
  experiments,
  layouts,
  selection,
  featureCatalog,
  signalCatalog,
  targetCatalog,
  featureBuilders,
  signalBuilders,
  targetBuilders,
  featureSteps,
  signalSteps,
  targetSteps,
  selectedFeatureIds,
  selectedSignalIds,
  selectedTargetIds,
  onSelectionChange,
  onSelectedSeriesChange,
  onTransformStepsChange,
  onRunTransform,
  onSaveLayout,
  onLoadLayout
}: ControlPanelProps) {
  const visibleDatasets = datasets.filter((dataset) => {
    const assetMatch = !selection.asset || dataset.assets.includes(selection.asset);
    const timeframeMatch = !selection.timeframe || dataset.timeframe === selection.timeframe;
    return assetMatch && timeframeMatch;
  });

  return (
    <aside className="left-panel">
      <section className="control-section">
        <h2>Data</h2>
        <AssetSelector assets={assets} value={selection.asset} onChange={(asset) => onSelectionChange({ asset, datasetId: "" })} />
        <TimeframeSelector timeframes={timeframes} value={selection.timeframe} onChange={(timeframe) => onSelectionChange({ timeframe, datasetId: "" })} />
        <label className="field">
          <span>Data source</span>
          <select value={selection.source} onChange={(event) => onSelectionChange({ source: event.target.value, datasetId: "" })}>
            <option value="raw">raw</option>
            <option value="processed">processed</option>
            <option value="all">all</option>
            {Array.from(new Set(datasets.map((dataset) => dataset.source))).map((source) => (
              <option key={source} value={source}>
                {source}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Dataset</span>
          <select value={selection.datasetId} onChange={(event) => onSelectionChange({ datasetId: event.target.value })}>
            <option value="">Auto</option>
            {visibleDatasets.map((dataset) => (
              <option key={dataset.id} value={dataset.id}>
                {dataset.relative_path}
              </option>
            ))}
          </select>
        </label>
        <DateRangeSelector start={selection.start} end={selection.end} onChange={onSelectionChange} />
      </section>
      <FeatureSelector
        title="Dataset Features"
        catalog={featureCatalog}
        selected={selectedFeatureIds}
        onChange={(ids) => onSelectedSeriesChange("feature", ids)}
      />
      <SignalSelector
        signals={signalCatalog}
        selected={selectedSignalIds}
        onChange={(ids) => onSelectedSeriesChange("signal", ids)}
      />
      <TargetSelector
        targets={targetCatalog}
        selected={selectedTargetIds}
        onChange={(ids) => onSelectedSeriesChange("target", ids)}
      />
      <BuilderConfigurator
        title="Parameterized Features"
        sourceType="feature"
        builders={featureBuilders}
        steps={featureSteps}
        onChange={(steps) => onTransformStepsChange("feature", steps)}
      />
      <BuilderConfigurator
        title="Parameterized Signals"
        sourceType="signal"
        builders={signalBuilders}
        steps={signalSteps}
        onChange={(steps) => onTransformStepsChange("signal", steps)}
      />
      <BuilderConfigurator
        title="Parameterized Targets"
        sourceType="target"
        builders={targetBuilders}
        steps={targetSteps}
        onChange={(steps) => onTransformStepsChange("target", steps)}
      />
      <section className="control-section">
        <button className="primary-button full-button" type="button" onClick={onRunTransform}>
          Run parameterized series
        </button>
      </section>
      <PredictionSelector experiments={experiments} selectedRunId={selection.runId} onRunChange={(runId) => onSelectionChange({ runId })} />
      <BacktestOverlaySelector experiments={experiments} selectedRunId={selection.runId} onRunChange={(runId) => onSelectionChange({ runId })} />
      <LayoutManager layouts={layouts} onSave={onSaveLayout} onLoad={onLoadLayout} />
    </aside>
  );
}
