import { useEffect, useMemo, useState } from "react";
import "./styles.css";
import { api } from "./api/client";
import { ChartWorkspace } from "./components/ChartWorkspace";
import { ControlPanel } from "./components/ControlPanel";
import { ExecutionMonitor } from "./components/ExecutionMonitor";
import { SeriesStyleEditor } from "./components/SeriesStyleEditor";
import { useDashboardStore } from "./state/dashboardStore";
import type { NamedSeries } from "./types/market";
import { seriesKey } from "./utils/transforms";

const DEFAULT_CANDLE_LIMIT = 5000;

function seriesParams(selection: ReturnType<typeof useDashboardStore.getState>["selection"]) {
  if (selection.datasetId) {
    return {
      dataset_id: selection.datasetId,
      start: selection.start || undefined,
      end: selection.end || undefined
    };
  }
  return {
    asset: selection.asset || undefined,
    timeframe: selection.timeframe || undefined,
    source: selection.source || undefined,
    start: selection.start || undefined,
    end: selection.end || undefined
  };
}

function chartWindowLimit(selection: ReturnType<typeof useDashboardStore.getState>["selection"]): number | undefined {
  return selection.start || selection.end || selection.runId ? undefined : DEFAULT_CANDLE_LIMIT;
}

function chartWindowLabel(selection: ReturnType<typeof useDashboardStore.getState>["selection"], limit: number | undefined): string {
  if (selection.start || selection.end) {
    return `${selection.start || "start"} -> ${selection.end || "latest"}`;
  }
  if (selection.runId) {
    return "full range for selected run";
  }
  return `latest ${limit?.toLocaleString() ?? "all"} bars`;
}

function mergeSeries(sourceType: string, series: NamedSeries[]): Record<string, NamedSeries["points"]> {
  return series.reduce<Record<string, NamedSeries["points"]>>((acc, item) => {
    acc[seriesKey(sourceType, item.series_id)] = item.points;
    return acc;
  }, {});
}

export default function App() {
  const [activeView, setActiveView] = useState<"research" | "execution">("research");
  const state = useDashboardStore();
  const {
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
    seriesConfigs,
    activeSeriesKey,
    candles,
    seriesData,
    trades,
    loadingMessage,
    errorMessage
  } = state;

  useEffect(() => {
    let cancelled = false;
    state.setLoadingMessage("Loading local catalogs");
    Promise.all([
      api.datasets(),
      api.experiments(),
      api.layouts(),
      api.featureBuilders(),
      api.signalBuilders(),
      api.targetBuilders()
    ])
      .then(([datasetData, experimentData, layoutData, featureBuilderData, signalBuilderData, targetBuilderData]) => {
        if (!cancelled) {
          state.setBootstrapData({
            datasets: datasetData,
            experiments: experimentData,
            layouts: layoutData
          });
          state.setBuilderDefinitions({
            featureBuilders: featureBuilderData,
            signalBuilders: signalBuilderData,
            targetBuilders: targetBuilderData
          });
          state.setErrorMessage(null);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          state.setErrorMessage(error instanceof Error ? error.message : String(error));
        }
      })
      .finally(() => {
        if (!cancelled) {
          state.setLoadingMessage(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const dataParams = useMemo(
    () => seriesParams(selection),
    [selection.asset, selection.datasetId, selection.end, selection.source, selection.start, selection.timeframe]
  );
  const dataLimit = useMemo(() => chartWindowLimit(selection), [selection.end, selection.runId, selection.start]);
  const dataWindowLabel = useMemo(() => chartWindowLabel(selection, dataLimit), [dataLimit, selection.end, selection.runId, selection.start]);
  const selectedDataset = useMemo(
    () => datasets.find((dataset) => dataset.id === selection.datasetId),
    [datasets, selection.datasetId]
  );

  useEffect(() => {
    if (!selection.datasetId && !selection.asset) {
      return;
    }
    let cancelled = false;
    state.setLoadingMessage("Loading candles and catalogs");
    state.setMarketData({ candles: [], seriesData: {} });
    state.setTransformRun(null);
    Promise.all([
      api.ohlcv({
        ...dataParams,
        limit: dataLimit
      }),
      api.featureCatalog(dataParams),
      api.signalCatalog(dataParams),
      api.targetCatalog(dataParams)
    ])
      .then(([candleData, features, signals, targets]) => {
        if (!cancelled) {
          state.setMarketData({ candles: candleData });
          state.setCatalogs({ featureCatalog: features, signalCatalog: signals, targetCatalog: targets });
          state.setErrorMessage(null);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          state.setErrorMessage(error instanceof Error ? error.message : String(error));
        }
      })
      .finally(() => {
        if (!cancelled) {
          state.setLoadingMessage(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [dataLimit, dataParams]);

  useEffect(() => {
    if (!selection.datasetId && !selection.asset) {
      return;
    }
    let cancelled = false;
    const requests: Array<Promise<Record<string, NamedSeries["points"]>>> = [];
    if (selectedFeatureIds.length > 0) {
      requests.push(api.featureSeries({ ...dataParams, features: selectedFeatureIds.join(","), limit: dataLimit }).then((payload) => mergeSeries("feature", payload.series)));
    }
    if (selectedSignalIds.length > 0) {
      requests.push(api.signalSeries({ ...dataParams, signals: selectedSignalIds.join(","), limit: dataLimit }).then((payload) => mergeSeries("signal", payload.series)));
    }
    if (selectedTargetIds.length > 0) {
      requests.push(api.targetSeries({ ...dataParams, targets: selectedTargetIds.join(","), limit: dataLimit }).then((payload) => mergeSeries("target", payload.series)));
    }
    if (requests.length === 0) {
      state.setMarketData({ seriesData: {} });
      return;
    }
    state.setLoadingMessage("Loading selected series");
    Promise.all(requests)
      .then((responses) => {
        if (!cancelled) {
          state.setMarketData({ seriesData: Object.assign({}, ...responses) });
          state.setErrorMessage(null);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          state.setErrorMessage(error instanceof Error ? error.message : String(error));
        }
      })
      .finally(() => {
        if (!cancelled) {
          state.setLoadingMessage(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [dataLimit, dataParams, selectedFeatureIds.join("|"), selectedSignalIds.join("|"), selectedTargetIds.join("|")]);

  useEffect(() => {
    if (!selection.runId) {
      state.setMarketData({ trades: [], equity: [] });
      return;
    }
    let cancelled = false;
    Promise.all([api.trades(selection.runId, { asset: selection.asset || undefined }), api.equity(selection.runId)])
      .then(([tradeData, equityData]) => {
        if (!cancelled) {
          state.setMarketData({ trades: tradeData, equity: equityData });
          state.setErrorMessage(null);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          state.setErrorMessage(error instanceof Error ? error.message : String(error));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selection.asset, selection.runId]);

  const saveLayout = (name: string) => {
    api
      .saveLayout(state.toLayout(name))
      .then(() => api.layouts())
      .then((layoutData) => state.setBootstrapData({ datasets, experiments, layouts: layoutData }))
      .catch((error: unknown) => state.setErrorMessage(error instanceof Error ? error.message : String(error)));
  };

  const loadLayout = (layoutId: string) => {
    api
      .layout(layoutId)
      .then((layout) => state.applyLayout(layout))
      .catch((error: unknown) => state.setErrorMessage(error instanceof Error ? error.message : String(error)));
  };

  const runParameterizedSeries = () => {
    if (!selection.datasetId && !selection.asset) {
      state.setErrorMessage("Select a dataset before running parameterized series.");
      return;
    }
    const enabledCount = [...featureSteps, ...signalSteps, ...targetSteps].filter((step) => step.enabled).length;
    if (enabledCount === 0) {
      state.setErrorMessage("Add at least one enabled feature, signal, or target builder.");
      return;
    }
    state.setLoadingMessage("Running parameterized builders");
    state.setTransformRun(null);
    api
      .transformSeries({
        ...dataParams,
        limit: dataLimit,
        features: featureSteps,
        signals: signalSteps,
        targets: targetSteps
      })
      .then((payload) => {
        state.mergeComputedSeries(payload.series);
        state.setTransformRun({
          steps: payload.steps,
          metadata: payload.metadata,
          ran_at: new Date().toISOString()
        });
        state.setErrorMessage(null);
      })
      .catch((error: unknown) => state.setErrorMessage(error instanceof Error ? error.message : String(error)))
      .finally(() => state.setLoadingMessage(null));
  };

  return (
    <div className="app-shell">
      <header className="top-bar">
        <div>
          <h1>Trading Research Dashboard</h1>
          <p>{selectedDataset?.relative_path || selection.datasetId || "No dataset"} · local artifacts</p>
        </div>
        <div className="view-tabs" role="tablist" aria-label="Dashboard view">
          <button
            type="button"
            role="tab"
            aria-selected={activeView === "research"}
            className={activeView === "research" ? "active" : ""}
            onClick={() => setActiveView("research")}
          >
            Research
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeView === "execution"}
            className={activeView === "execution" ? "active" : ""}
            onClick={() => setActiveView("execution")}
          >
            Execution
          </button>
        </div>
      </header>
      {activeView === "research" ? (
        <div className="dashboard-grid">
        <ControlPanel
          datasets={datasets}
          experiments={experiments}
          layouts={layouts}
          selection={selection}
          featureCatalog={featureCatalog}
          signalCatalog={signalCatalog}
          targetCatalog={targetCatalog}
          featureBuilders={featureBuilders}
          signalBuilders={signalBuilders}
          targetBuilders={targetBuilders}
          featureSteps={featureSteps}
          signalSteps={signalSteps}
          targetSteps={targetSteps}
          selectedFeatureIds={selectedFeatureIds}
          selectedSignalIds={selectedSignalIds}
          selectedTargetIds={selectedTargetIds}
          onSelectionChange={state.setSelection}
          onSelectedSeriesChange={state.setSelectedSeries}
          onTransformStepsChange={state.setTransformSteps}
          onRunTransform={runParameterizedSeries}
          onSaveLayout={saveLayout}
          onLoadLayout={loadLayout}
        />
        <ChartWorkspace
          candles={candles}
          configs={seriesConfigs}
          seriesData={seriesData}
          trades={trades}
          loadingMessage={loadingMessage}
          errorMessage={errorMessage}
          dataWindowLabel={dataWindowLabel}
        />
        <SeriesStyleEditor
          configs={seriesConfigs}
          activeKey={activeSeriesKey}
          onSelect={state.setActiveSeriesKey}
          onUpdate={state.updateSeriesConfig}
        />
        </div>
      ) : (
        <ExecutionMonitor />
      )}
    </div>
  );
}
