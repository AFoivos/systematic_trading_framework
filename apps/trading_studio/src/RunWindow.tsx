import { useMemo } from "react";
import { TradingChart } from "./TradingChart";
import { getRun } from "./runStore";

export function RunWindow({ runId }: { runId: string }) {
  const run = useMemo(() => getRun(runId), [runId]);

  if (!run) {
    return <main className="run-missing"><h1>Run not found</h1><p>This saved run is not available in this browser.</p><button onClick={() => window.close()}>Close window</button></main>;
  }

  return (
    <div className="run-window">
      <header className="run-header">
        <div>
          <small>Trading Studio · Saved run</small>
          <h1>{run.experimentName}</h1>
        </div>
        <div className="run-meta">
          <span>{run.asset}</span><span>{run.timeframe}</span><span>{new Date(run.createdAt).toLocaleString()}</span>
          <button onClick={() => window.print()}>Export</button>
        </div>
      </header>
      <nav className="run-summary">
        <span className="run-status">✓ Completed</span>
        <span>{run.nodes.length} pipeline components</span>
        <span>{Object.values(run.chartRoutes).filter((placement) => placement !== "hidden").length} visible series</span>
      </nav>
      <main className="run-content">
        <TradingChart routes={run.chartRoutes} />
        <aside className="run-sidebar">
          <section><h2>Experiment pipeline</h2>{run.nodes.map((node) => <div className="run-node" key={node.id}><small>{node.kind}</small><strong>{node.title}</strong><span>{node.subtitle}</span></div>)}</section>
          <details><summary>Canonical YAML</summary><pre>{run.yaml}</pre></details>
        </aside>
      </main>
    </div>
  );
}
