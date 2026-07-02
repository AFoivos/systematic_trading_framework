import type { ExperimentSummary } from "../types/experiment";

interface PredictionSelectorProps {
  experiments: ExperimentSummary[];
  selectedRunId: string;
  onRunChange: (runId: string) => void;
}

export function PredictionSelector({ experiments, selectedRunId, onRunChange }: PredictionSelectorProps) {
  return (
    <section className="control-section">
      <h2>Experiments</h2>
      <label className="field">
        <span>Experiment run</span>
        <select value={selectedRunId} onChange={(event) => onRunChange(event.target.value)}>
          <option value="">None</option>
          {experiments.map((experiment) => (
            <option key={experiment.run_id} value={experiment.run_id}>
              {experiment.run_type === "market_making" ? "market_making_latest" : experiment.name}
            </option>
          ))}
        </select>
      </label>
    </section>
  );
}
