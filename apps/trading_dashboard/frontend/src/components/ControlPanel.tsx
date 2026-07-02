import type { CatalogItem, DatasetSummary, FeatureCatalog } from "../types/market";
import type { ExperimentSummary } from "../types/experiment";
import type { BuilderDefinition, BuilderSourceType, TransformStepConfig } from "../types/transforms";
import type { DashboardSelection, LayoutSummary } from "../types/visualization";
import { BacktestOverlaySelector } from "./BacktestOverlaySelector";
import { BuilderConfigurator } from "./BuilderConfigurator";
import { DateRangeSelector } from "./DateRangeSelector";
import { FeatureSelector } from "./FeatureSelector";
import { LayoutManager } from "./LayoutManager";
import { PredictionSelector } from "./PredictionSelector";
import { SignalSelector } from "./SignalSelector";
import { TargetSelector } from "./TargetSelector";

interface ControlPanelProps {
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

function datasetGroupLabel(dataset: DatasetSummary): string {
  const parts = dataset.relative_path.split("/").filter(Boolean);
  const folders = parts.slice(0, -1);
  return folders.length > 0 ? folders.join(" / ") : "data";
}

function datasetOptionLabel(dataset: DatasetSummary): string {
  const parts = dataset.relative_path.split("/").filter(Boolean);
  return parts[parts.length - 1] || dataset.id;
}

function groupDatasets(datasets: DatasetSummary[]): Array<{ label: string; items: DatasetSummary[] }> {
  const groups = new Map<string, DatasetSummary[]>();
  for (const dataset of datasets) {
    const label = datasetGroupLabel(dataset);
    groups.set(label, [...(groups.get(label) ?? []), dataset]);
  }
  return Array.from(groups, ([label, items]) => ({ label, items }));
}

function selectionFromDataset(datasetId: string, datasets: DatasetSummary[]): Partial<DashboardSelection> {
  const dataset = datasets.find((item) => item.id === datasetId);
  return {
    datasetId,
    asset: dataset?.assets[0] ?? "",
    timeframe: dataset?.timeframe ?? "",
    source: dataset?.source ?? dataset?.stage ?? ""
  };
}

function selectionFromExperiment(experimentRunId: string, experiments: ExperimentSummary[], datasets: DatasetSummary[]): Partial<DashboardSelection> {
  const experiment = experiments.find((item) => item.run_id === experimentRunId);
  if (!experiment) {
    return { runId: experimentRunId };
  }
  if (experiment.run_type === "market_making") {
    return { runId: experimentRunId };
  }
  const processedDataset = experiment.processed_dataset_id
    ? datasets.find((dataset) => dataset.id === experiment.processed_dataset_id)
    : null;
  return {
    runId: experimentRunId,
    datasetId: processedDataset?.id ?? "",
    asset: processedDataset?.assets[0] ?? experiment.asset ?? "",
    timeframe: processedDataset?.timeframe ?? experiment.timeframe ?? "",
    source: processedDataset?.source ?? (processedDataset ? processedDataset.stage : "")
  };
}

export function ControlPanel({
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
  const datasetGroups = groupDatasets(datasets);

  return (
    <aside className="left-panel">
      <section className="control-section">
        <h2>Data</h2>
        <label className="field">
          <span>Dataset</span>
          <select value={selection.datasetId} onChange={(event) => onSelectionChange(selectionFromDataset(event.target.value, datasets))}>
            <option value="" disabled={datasets.length > 0}>
              {datasets.length > 0 ? "Select dataset" : "No datasets found"}
            </option>
            {datasetGroups.map((group) => (
              <optgroup key={group.label} label={group.label}>
                {group.items.map((dataset) => (
                  <option key={dataset.id} value={dataset.id}>
                    {datasetOptionLabel(dataset)}
                  </option>
                ))}
              </optgroup>
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
      <PredictionSelector
        experiments={experiments}
        selectedRunId={selection.runId}
        onRunChange={(runId) => onSelectionChange(selectionFromExperiment(runId, experiments, datasets))}
      />
      <BacktestOverlaySelector experiments={experiments} selectedRunId={selection.runId} onRunChange={(runId) => onSelectionChange({ runId })} />
      <LayoutManager layouts={layouts} onSave={onSaveLayout} onLoad={onLoadLayout} />
    </aside>
  );
}
