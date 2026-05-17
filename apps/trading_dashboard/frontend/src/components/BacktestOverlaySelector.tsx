import type { ExperimentSummary } from "../types/experiment";

interface BacktestOverlaySelectorProps {
  experiments: ExperimentSummary[];
  selectedRunId: string;
  onRunChange: (runId: string) => void;
}

export function BacktestOverlaySelector({ experiments, selectedRunId, onRunChange }: BacktestOverlaySelectorProps) {
  const eligible = experiments.filter((experiment) => experiment.has_trades || experiment.has_equity);
  return (
    <section className="control-section">
      <h2>Backtests</h2>
      <label className="field">
        <span>Trade overlay</span>
        <select value={selectedRunId} onChange={(event) => onRunChange(event.target.value)}>
          <option value="">None</option>
          {eligible.map((experiment) => (
            <option key={experiment.run_id} value={experiment.run_id}>
              {experiment.name}
            </option>
          ))}
        </select>
      </label>
    </section>
  );
}

