import { useMemo, useState, type DragEvent, type ReactNode } from "react";

type NodeKind = "data" | "feature" | "target" | "model" | "signal" | "backtest";
type InspectorTab = "base" | "normalizations" | "helpers" | "outputs";
type BottomTab = "preview" | "validation" | "results";

interface StudioNode {
  id: string;
  kind: NodeKind;
  title: string;
  subtitle: string;
  x: number;
  y: number;
}

interface Normalization {
  id: string;
  kind: string;
  window: number;
  shift: number;
  enabled: boolean;
}

interface Helper {
  id: string;
  kind: "slope" | "ratio";
  left: string;
  right: string;
  window?: number;
}

const palette = [
  { section: "Data", items: [["Dataset", "data"], ["Data loader", "data"], ["Data join", "data"]] },
  { section: "Features + helpers", items: [["Feature", "feature"], ["Feature group", "feature"]] },
  { section: "Targets", items: [["Target", "target"], ["Target transform", "target"]] },
  { section: "Models", items: [["Model", "model"], ["Model ensemble", "model"]] },
  { section: "Signals", items: [["Signal", "signal"], ["Signal logic", "signal"]] },
  { section: "Backtest", items: [["Backtest", "backtest"]] },
  { section: "Evaluation", items: [["Evaluator", "backtest"], ["Custom metric", "backtest"]] }
] as const;

const initialNodes: StudioNode[] = [
  { id: "dataset", kind: "data", title: "SPX500 30m", subtitle: "Dataset", x: 18, y: 172 },
  { id: "volatility", kind: "feature", title: "Volatility", subtitle: "1 normalization · 2 helpers", x: 145, y: 160 },
  { id: "target", kind: "target", title: "Forward return", subtitle: "Target · horizon 8", x: 272, y: 172 },
  { id: "model", kind: "model", title: "LightGBM", subtitle: "Model · walk-forward", x: 399, y: 172 },
  { id: "signal", kind: "signal", title: "Probability threshold", subtitle: "Signal · 0.60 / 0.40", x: 526, y: 172 },
  { id: "backtest", kind: "backtest", title: "Backtest", subtitle: "Costs · slippage", x: 653, y: 172 }
];

const kindMeta: Record<NodeKind, { color: string; mark: string }> = {
  data: { color: "#1fa866", mark: "D" },
  feature: { color: "#2f7cf6", mark: "ƒx" },
  target: { color: "#7457e8", mark: "T" },
  model: { color: "#e77824", mark: "M" },
  signal: { color: "#e24a51", mark: "S" },
  backtest: { color: "#297ac3", mark: "B" }
};

function Icon({ children }: { children: ReactNode }) {
  return <span className="icon" aria-hidden="true">{children}</span>;
}

function TopBar({
  onYaml,
  onValidate,
  onRun,
  running
}: {
  onYaml: () => void;
  onValidate: () => void;
  onRun: () => void;
  running: boolean;
}) {
  return (
    <header className="topbar">
      <div className="brand"><Icon>≡</Icon><strong>Trading Studio</strong></div>
      <div className="experiment-name">SPX500 Momentum Research <button className="icon-button" aria-label="Rename experiment">✎</button></div>
      <div className="autosave"><span /> Autosaved just now</div>
      <div className="top-actions">
        <button className="dark-button" onClick={onYaml}>&lt;/&gt; YAML</button>
        <button className="dark-button" onClick={onValidate}>✓ Validate</button>
        <button className="run-button" onClick={onRun} disabled={running}>{running ? "Running…" : "▶ Run"}</button>
      </div>
    </header>
  );
}

function ComponentLibrary({ query, onQuery }: { query: string; onQuery: (value: string) => void }) {
  return (
    <aside className="library">
      <div className="panel-heading"><strong>Components</strong><button className="icon-button">«</button></div>
      <label className="search">
        <input value={query} onChange={(event) => onQuery(event.target.value)} placeholder="Search components…" />
        <span>⌕</span>
      </label>
      <div className="library-scroll">
        {palette.map((group) => {
          const items = group.items.filter(([label]) => label.toLowerCase().includes(query.toLowerCase()));
          if (!items.length) return null;
          return (
            <section className="palette-group" key={group.section}>
              <h2>{group.section}</h2>
              {items.map(([label, kind]) => (
                <button
                  className="palette-item"
                  draggable
                  key={`${group.section}-${label}`}
                  onDragStart={(event) => {
                    event.dataTransfer.setData("application/x-studio-kind", kind);
                    event.dataTransfer.setData("text/plain", label);
                  }}
                >
                  <span>{label}</span><span className="grip">⠿</span>
                </button>
              ))}
            </section>
          );
        })}
      </div>
    </aside>
  );
}

function PipelineNode({
  node,
  selected,
  onSelect
}: {
  node: StudioNode;
  selected: boolean;
  onSelect: () => void;
}) {
  const meta = kindMeta[node.kind];
  return (
    <button
      className={`pipeline-node ${selected ? "selected" : ""}`}
      style={{ left: node.x, top: node.y, "--node-color": meta.color } as React.CSSProperties}
      onClick={onSelect}
    >
      <span className="node-valid">✓</span>
      <span className="node-mark">{meta.mark}</span>
      <span className="node-copy"><small>{node.subtitle}</small><strong>{node.title}</strong></span>
      {node.kind !== "data" ? <span className="port input-port" /> : null}
      {node.kind !== "backtest" ? <span className="port output-port" /> : null}
      <span className="node-menu">•••</span>
    </button>
  );
}

function Canvas({
  nodes,
  selectedId,
  onSelect,
  onDropNode
}: {
  nodes: StudioNode[];
  selectedId: string;
  onSelect: (id: string) => void;
  onDropNode: (node: StudioNode) => void;
}) {
  const ordered = [...nodes].sort((a, b) => a.x - b.x);
  return (
    <main
      className="canvas"
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        const kind = event.dataTransfer.getData("application/x-studio-kind") as NodeKind;
        const label = event.dataTransfer.getData("text/plain");
        if (!kind) return;
        const bounds = event.currentTarget.getBoundingClientRect();
        onDropNode({
          id: `${kind}-${Date.now()}`,
          kind,
          title: label,
          subtitle: kind[0].toUpperCase() + kind.slice(1),
          x: Math.max(16, event.clientX - bounds.left - 78),
          y: Math.max(74, event.clientY - bounds.top - 48)
        });
      }}
    >
      <div className="canvas-toolbar">
        <button className="tool active">↖</button><button className="tool">✋</button><button className="tool">⌕</button>
        <span className="zoom">− &nbsp; 100% &nbsp; +</span><button className="tool">⛶</button>
        <span className="toolbar-spacer" /><button className="tool">↶</button><button className="tool">↷</button>
      </div>
      <div className="canvas-stage">
        <svg className="connections" aria-hidden="true">
          {ordered.slice(0, -1).map((node, index) => {
            const next = ordered[index + 1];
            return <line key={`${node.id}-${next.id}`} x1={node.x + 112} y1={node.y + 60} x2={next.x} y2={next.y + 60} />;
          })}
        </svg>
        {nodes.map((node) => <PipelineNode key={node.id} node={node} selected={node.id === selectedId} onSelect={() => onSelect(node.id)} />)}
        <div className="minimap">{nodes.map((node) => <span key={node.id} style={{ left: `${node.x / 12}px`, top: `${node.y / 12}px` }} />)}</div>
      </div>
    </main>
  );
}

function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return <label className="field"><span>{label}{hint ? <em title={hint}>i</em> : null}</span>{children}</label>;
}

function NestedBlock({
  title,
  enabled,
  onToggle,
  onRemove,
  children
}: {
  title: string;
  enabled: boolean;
  onToggle: () => void;
  onRemove: () => void;
  children: ReactNode;
}) {
  return (
    <div className="nested-block">
      <div className="nested-head"><span className="grip">⠿</span><strong>{title}</strong><button className={`switch ${enabled ? "on" : ""}`} onClick={onToggle}><span /></button><button className="icon-button" onClick={onRemove} aria-label={`Remove ${title}`}>⌫</button></div>
      {enabled ? <div className="nested-body">{children}</div> : null}
    </div>
  );
}

function FeatureInspector({
  tab,
  setTab,
  normalizations,
  setNormalizations,
  helpers,
  setHelpers
}: {
  tab: InspectorTab;
  setTab: (tab: InspectorTab) => void;
  normalizations: Normalization[];
  setNormalizations: (items: Normalization[]) => void;
  helpers: Helper[];
  setHelpers: (items: Helper[]) => void;
}) {
  return (
    <>
      <nav className="inspector-tabs">
        {(["base", "normalizations", "helpers", "outputs"] as const).map((item) => <button className={tab === item ? "active" : ""} onClick={() => setTab(item)} key={item}>{item[0].toUpperCase() + item.slice(1)}</button>)}
      </nav>
      <div className="inspector-scroll">
        {tab === "base" ? (
          <section className="inspector-section">
            <div className="section-title"><h2>Feature parameters</h2></div>
            <Field label="Feature kind"><select><option>volatility</option><option>trend</option><option>momentum</option></select></Field>
            <Field label="Rolling windows (bars)" hint="One or more windows can be emitted"><input defaultValue="96, 252" /></Field>
            <Field label="Returns column"><select><option>close_ret</option><option>close_logret</option></select></Field>
            <Field label="Annualization factor"><input defaultValue="auto" /></Field>
            <Field label="Enabled"><select><option>true</option><option>false</option></select></Field>
          </section>
        ) : null}
        {tab === "normalizations" ? (
          <section className="inspector-section">
            <div className="section-title"><h2>Normalizations</h2><button onClick={() => setNormalizations([...normalizations, { id: crypto.randomUUID(), kind: "rolling_zscore", window: 96, shift: 1, enabled: true }])}>＋ Add normalization</button></div>
            {normalizations.map((item, index) => (
              <NestedBlock key={item.id} title={`${index + 1} · ${item.kind}`} enabled={item.enabled} onToggle={() => setNormalizations(normalizations.map((next) => next.id === item.id ? { ...next, enabled: !next.enabled } : next))} onRemove={() => setNormalizations(normalizations.filter((next) => next.id !== item.id))}>
                <Field label="Method"><select value={item.kind} onChange={(event) => setNormalizations(normalizations.map((next) => next.id === item.id ? { ...next, kind: event.target.value } : next))}><option>rolling_zscore</option><option>range_position</option><option>rolling_clip</option></select></Field>
                <div className="field-row">
                  <Field label="Window"><input type="number" value={item.window} onChange={(event) => setNormalizations(normalizations.map((next) => next.id === item.id ? { ...next, window: Number(event.target.value) } : next))} /></Field>
                  <Field label="Shift"><input type="number" value={item.shift} onChange={(event) => setNormalizations(normalizations.map((next) => next.id === item.id ? { ...next, shift: Number(event.target.value) } : next))} /></Field>
                </div>
              </NestedBlock>
            ))}
          </section>
        ) : null}
        {tab === "helpers" ? (
          <section className="inspector-section">
            <div className="section-title"><h2>Helpers / transforms</h2><button onClick={() => setHelpers([...helpers, { id: crypto.randomUUID(), kind: "slope", left: "vol_rolling_96", right: "", window: 8 }])}>＋ Add helper</button></div>
            {helpers.map((item, index) => (
              <NestedBlock key={item.id} title={`${index + 1} · ${item.kind}`} enabled onToggle={() => undefined} onRemove={() => setHelpers(helpers.filter((next) => next.id !== item.id))}>
                <Field label="Helper kind"><select value={item.kind} onChange={(event) => setHelpers(helpers.map((next) => next.id === item.id ? { ...next, kind: event.target.value as Helper["kind"] } : next))}><option>slope</option><option>ratio</option></select></Field>
                <Field label={item.kind === "ratio" ? "Numerator column" : "Source column"}><input value={item.left} onChange={(event) => setHelpers(helpers.map((next) => next.id === item.id ? { ...next, left: event.target.value } : next))} /></Field>
                {item.kind === "ratio" ? <Field label="Denominator column"><input value={item.right} onChange={(event) => setHelpers(helpers.map((next) => next.id === item.id ? { ...next, right: event.target.value } : next))} /></Field> : <Field label="Window"><input type="number" value={item.window} /></Field>}
              </NestedBlock>
            ))}
            <p className="section-note">Helpers run in this order. Drag rows to reorder in the production workflow.</p>
          </section>
        ) : null}
        {tab === "outputs" ? (
          <section className="inspector-section">
            <div className="section-title"><h2>Generated outputs</h2></div>
            {["vol_rolling_96", "vol_rolling_96__zscore", "vol_slope_8", "vol_slope_over_close"].map((output) => <div className="output-row" key={output}><code>{output}</code><span>numeric</span></div>)}
            <button className="secondary-wide">＋ Add output mapping</button>
          </section>
        ) : null}
      </div>
    </>
  );
}

function Inspector({
  selected,
  tab,
  setTab,
  normalizations,
  setNormalizations,
  helpers,
  setHelpers
}: {
  selected?: StudioNode;
  tab: InspectorTab;
  setTab: (tab: InspectorTab) => void;
  normalizations: Normalization[];
  setNormalizations: (items: Normalization[]) => void;
  helpers: Helper[];
  setHelpers: (items: Helper[]) => void;
}) {
  return (
    <aside className="inspector">
      <div className="inspector-heading"><span className="inspector-mark">ƒx</span><div><small>{selected?.kind ?? "component"}</small><strong>{selected?.title ?? "Select a component"}</strong></div><span className="heading-actions">⧉ &nbsp; ⌫</span></div>
      {selected?.kind === "feature" ? <FeatureInspector tab={tab} setTab={setTab} normalizations={normalizations} setNormalizations={setNormalizations} helpers={helpers} setHelpers={setHelpers} /> : (
        <div className="generic-inspector">
          <h2>{selected?.subtitle}</h2>
          <Field label="Kind"><input value={selected?.kind ?? ""} readOnly /></Field>
          <Field label="Name"><input value={selected?.title ?? ""} readOnly /></Field>
          <p>Select the feature node to configure nested normalizations, helpers and outputs.</p>
        </div>
      )}
    </aside>
  );
}

const previewRows = [
  ["2024-05-10 13:00", "5257.75", "5261.25", "5252.25", "5257.00", "0.00317", "-0.8123", "0.0132"],
  ["2024-05-10 13:30", "5257.00", "5260.50", "5251.75", "5255.75", "-0.00024", "-0.8451", "0.0204"],
  ["2024-05-10 14:00", "5255.75", "5262.25", "5255.25", "5261.25", "0.00105", "-0.7649", "0.0278"],
  ["2024-05-10 14:30", "5261.25", "5264.00", "5256.25", "5263.50", "0.00043", "-0.7432", "0.0312"]
];

function BottomDrawer({ tab, setTab, validationStamp, hasResults }: { tab: BottomTab; setTab: (tab: BottomTab) => void; validationStamp: string; hasResults: boolean }) {
  return (
    <section className="bottom-drawer">
      <nav className="bottom-tabs">
        {(["preview", "validation", "results"] as const).map((item) => <button key={item} onClick={() => setTab(item)} className={tab === item ? "active" : ""}>{item[0].toUpperCase() + item.slice(1)}{item === "validation" ? <span className="count">0</span> : null}</button>)}
        <span className="drawer-spacer" /><span>Rows <select><option>100</option><option>500</option></select></span><span>↻ Live <i /></span>
      </nav>
      {tab === "preview" ? (
        <div className="table-wrap"><table><thead><tr>{["timestamp", "open", "high", "low", "close", "returns", "vol_96_z", "slope_8"].map((h) => <th key={h}>{h}</th>)}</tr></thead><tbody>{previewRows.map((row) => <tr key={row[0]}>{row.map((cell) => <td key={cell}>{cell}</td>)}</tr>)}</tbody></table></div>
      ) : null}
      {tab === "validation" ? <div className="validation-view"><strong>✓ Validation passed</strong><span>Schema, dependencies, leakage and execution checks completed {validationStamp}.</span></div> : null}
      {tab === "results" ? <div className="results-view">{hasResults ? <><strong>Run completed</strong><span>4 folds · 1,248 OOS rows · artifacts ready for comparison</span><button>Open full results</button></> : <><strong>No run yet</strong><span>Validate the experiment and start a run to populate results.</span></>}</div> : null}
    </section>
  );
}

function YamlModal({ onClose, yaml }: { onClose: () => void; yaml: string }) {
  return <div className="modal-backdrop" onMouseDown={onClose}><section className="yaml-modal" onMouseDown={(event) => event.stopPropagation()}><header><div><small>Canonical experiment document</small><h2>YAML preview</h2></div><button className="icon-button" onClick={onClose}>×</button></header><pre>{yaml}</pre><footer><span>Visual graph and YAML are synchronized.</span><button onClick={() => navigator.clipboard?.writeText(yaml)}>Copy YAML</button></footer></section></div>;
}

export function App() {
  const [query, setQuery] = useState("");
  const [nodes, setNodes] = useState(initialNodes);
  const [selectedId, setSelectedId] = useState("volatility");
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("normalizations");
  const [bottomTab, setBottomTab] = useState<BottomTab>("preview");
  const [normalizations, setNormalizations] = useState<Normalization[]>([{ id: "norm-1", kind: "rolling_zscore", window: 252, shift: 1, enabled: true }]);
  const [helpers, setHelpers] = useState<Helper[]>([
    { id: "helper-1", kind: "slope", left: "vol_rolling_96", right: "", window: 8 },
    { id: "helper-2", kind: "ratio", left: "vol_slope_8", right: "close" }
  ]);
  const [yamlOpen, setYamlOpen] = useState(false);
  const [validationStamp, setValidationStamp] = useState("just now");
  const [running, setRunning] = useState(false);
  const [hasResults, setHasResults] = useState(false);
  const selected = nodes.find((node) => node.id === selectedId);

  const yaml = useMemo(() => `name: spx500_momentum_research
dataset:
  id: spx500_30m
features:
  - step: volatility
    enabled: true
    params:
      returns_col: close_ret
      rolling_windows: [96, 252]
    normalizations:
${normalizations.map((item) => `      ${item.kind}:
        params: { window: ${item.window}, shift: ${item.shift} }`).join("\n")}
    transforms:
${helpers.map((item) => `      ${item.kind}:
        params: { source_col: ${item.left}${item.right ? `, denominator_col: ${item.right}` : ""} }`).join("\n")}
model:
  kind: lightgbm_clf
  split: { method: walk_forward }
signals:
  kind: probability_threshold
`, [helpers, normalizations]);

  const run = () => {
    setRunning(true);
    setBottomTab("results");
    window.setTimeout(() => {
      setRunning(false);
      setHasResults(true);
    }, 900);
  };

  return (
    <div className="app">
      <TopBar onYaml={() => setYamlOpen(true)} onValidate={() => { setValidationStamp("just now"); setBottomTab("validation"); }} onRun={run} running={running} />
      <div className="workspace">
        <ComponentLibrary query={query} onQuery={setQuery} />
        <Canvas nodes={nodes} selectedId={selectedId} onSelect={setSelectedId} onDropNode={(node) => { setNodes((current) => [...current, node]); setSelectedId(node.id); }} />
        <Inspector selected={selected} tab={inspectorTab} setTab={setInspectorTab} normalizations={normalizations} setNormalizations={setNormalizations} helpers={helpers} setHelpers={setHelpers} />
        <BottomDrawer tab={bottomTab} setTab={setBottomTab} validationStamp={validationStamp} hasResults={hasResults} />
      </div>
      <footer className="statusbar"><span><i /> Validation passed</span><span>Last run: {hasResults ? "just now" : "not started"}</span><span className="status-spacer" /><span>Engine: v2.1.0</span><span>Config: visual + YAML</span></footer>
      {yamlOpen ? <YamlModal yaml={yaml} onClose={() => setYamlOpen(false)} /> : null}
    </div>
  );
}
