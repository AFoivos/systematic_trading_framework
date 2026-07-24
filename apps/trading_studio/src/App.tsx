import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type DragEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
  type RefObject
} from "react";
import {
  createNode,
  executeStudioDocument,
  loadStoredDocument,
  newId,
  nodeSubtitle,
  previewRows,
  saveStoredDocument,
  serializeStudioYaml,
  validateStudioDocument,
  type FeatureConfig,
  type Helper,
  type NodeKind,
  type Normalization,
  type PreviewRow,
  type StudioDocument,
  type StudioNode,
  type StudioRunResult,
  type ValidationIssue
} from "./studio";
import { RunWindow } from "./RunWindow";
import { listRuns, saveRun, type ChartPlacement, type StoredRun } from "./runStore";
import {
  defaultsFor,
  definitionFor,
  definitionsFor,
  type ComponentDefinition,
  type ParameterDefinition,
  type ParameterValue
} from "./frameworkCatalog";

type InspectorTab = "base" | "normalizations" | "helpers" | "outputs";
type BottomTab = "preview" | "validation" | "results";
type CanvasMode = "select" | "pan";

interface HistoryState {
  past: StudioDocument[];
  present: StudioDocument;
  future: StudioDocument[];
}

interface ValidationState {
  issues: ValidationIssue[];
  checkedAt: string;
}

type RunState =
  | { status: "idle" }
  | { status: "running"; startedAt: string }
  | { status: "failed"; error: string }
  | { status: "completed"; result: StudioRunResult };

const palette = [
  { section: "Data", items: [["Dataset", "data"], ["Data loader", "data"], ["Data join", "data"]] },
  { section: "Features + helpers", items: [["Feature", "feature"], ["Feature group", "feature"]] },
  { section: "Targets", items: [["Target", "target"], ["Target transform", "target"]] },
  { section: "Models", items: [["Model", "model"], ["Model ensemble", "model"]] },
  { section: "Signals", items: [["Signal", "signal"], ["Signal logic", "signal"]] },
  { section: "Backtest", items: [["Backtest", "backtest"]] },
  { section: "Evaluation", items: [["Evaluator", "backtest"], ["Custom metric", "backtest"]] }
] as const;

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
  experimentName,
  renaming,
  renameDraft,
  saveStatus,
  running,
  libraryCollapsed,
  onOpenRename,
  onRenameDraft,
  onCommitRename,
  onCancelRename,
  onToggleLibrary,
  onRuns,
  onYaml,
  onValidate,
  onRun
}: {
  experimentName: string;
  renaming: boolean;
  renameDraft: string;
  saveStatus: string;
  running: boolean;
  libraryCollapsed: boolean;
  onOpenRename: () => void;
  onRenameDraft: (value: string) => void;
  onCommitRename: () => void;
  onCancelRename: () => void;
  onToggleLibrary: () => void;
  onRuns: () => void;
  onYaml: () => void;
  onValidate: () => void;
  onRun: () => void;
}) {
  return (
    <header className="topbar">
      <div className="brand">
        <button
          type="button"
          className="menu-button"
          aria-label={libraryCollapsed ? "Open component library" : "Close component library"}
          aria-controls="component-library"
          aria-expanded={!libraryCollapsed}
          title={libraryCollapsed ? "Open Components" : "Close Components"}
          onClick={onToggleLibrary}
        >
          <Icon>☰</Icon>
        </button>
        <strong>Trading Studio</strong>
      </div>
      {renaming ? (
        <form
          className="rename-form"
          onSubmit={(event) => {
            event.preventDefault();
            onCommitRename();
          }}
        >
          <label>
            <span className="sr-only">Experiment name</span>
            <input
              aria-label="Experiment name"
              autoFocus
              value={renameDraft}
              onChange={(event) => onRenameDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Escape") onCancelRename();
              }}
            />
          </label>
          <button type="submit" aria-label="Save experiment name">✓</button>
          <button type="button" aria-label="Cancel rename" onClick={onCancelRename}>×</button>
        </form>
      ) : (
        <div className="experiment-name">
          <span>{experimentName}</span>
          <button className="icon-button" aria-label="Rename experiment" onClick={onOpenRename}>✎</button>
        </div>
      )}
      <div className="autosave" aria-live="polite"><span /> {saveStatus}</div>
      <div className="top-actions">
        <button className="dark-button" onClick={onRuns}>Runs</button>
        <button className="dark-button" onClick={onYaml}>&lt;/&gt; YAML</button>
        <button className="dark-button" onClick={onValidate}>✓ Validate</button>
        <button className="run-button" onClick={onRun} disabled={running}>
          {running ? "Running…" : "▶ Run preview"}
        </button>
      </div>
    </header>
  );
}

function ComponentLibrary({
  query,
  collapsed,
  searchInputRef,
  onQuery,
  onToggleCollapsed,
  onAdd
}: {
  query: string;
  collapsed: boolean;
  searchInputRef: RefObject<HTMLInputElement>;
  onQuery: (value: string) => void;
  onToggleCollapsed: () => void;
  onAdd: (kind: NodeKind, label: string) => void;
}) {
  if (collapsed) {
    return (
      <aside id="component-library" className="library collapsed">
        <button className="library-expand" aria-label="Expand component library" onClick={onToggleCollapsed}>»</button>
      </aside>
    );
  }
  return (
    <aside id="component-library" className="library">
      <div className="panel-heading">
        <strong>Components</strong>
        <button className="icon-button" aria-label="Collapse component library" onClick={onToggleCollapsed}>«</button>
      </div>
      <label className="search">
        <span className="sr-only">Search components</span>
        <input
          ref={searchInputRef}
          value={query}
          onChange={(event) => onQuery(event.target.value)}
          placeholder="Search components…"
        />
        <span aria-hidden="true">⌕</span>
      </label>
      <div className="library-scroll">
        {palette.map((group) => {
          const items = group.items.filter(([label]) => label.toLowerCase().includes(query.trim().toLowerCase()));
          if (!items.length) return null;
          return (
            <section className="palette-group" key={group.section}>
              <h2>{group.section}</h2>
              {items.map(([label, kind]) => (
                <button
                  type="button"
                  className="palette-item"
                  draggable
                  key={`${group.section}-${label}`}
                  onClick={() => onAdd(kind, label)}
                  onDragStart={(event) => {
                    event.dataTransfer.effectAllowed = "copy";
                    event.dataTransfer.setData("application/x-studio-kind", kind);
                    event.dataTransfer.setData("text/plain", label);
                  }}
                  title={`Click or drag to add ${label}`}
                >
                  <span>{label}</span><span className="grip" aria-hidden="true">⠿</span>
                </button>
              ))}
            </section>
          );
        })}
        {!palette.some((group) => group.items.some(([label]) => label.toLowerCase().includes(query.trim().toLowerCase()))) ? (
          <p className="empty-library">No components match “{query}”.</p>
        ) : null}
      </div>
    </aside>
  );
}

function PipelineNode({
  node,
  selected,
  draggable,
  zoom,
  onSelect,
  onMove,
  onDelete
}: {
  node: StudioNode;
  selected: boolean;
  draggable: boolean;
  zoom: number;
  onSelect: () => void;
  onMove: (x: number, y: number) => void;
  onDelete: () => void;
}) {
  const meta = kindMeta[node.kind];
  const wrapperRef = useRef<HTMLDivElement>(null);
  const dragGestureRef = useRef<{
    startX: number;
    startY: number;
    originX: number;
    originY: number;
    nextX: number;
    nextY: number;
  } | null>(null);

  const finishDrag = (event: ReactPointerEvent<HTMLButtonElement>) => {
    const gesture = dragGestureRef.current;
    if (!gesture) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    dragGestureRef.current = null;
    onMove(Math.round(gesture.nextX), Math.round(gesture.nextY));
  };

  return (
    <div
      ref={wrapperRef}
      className={`pipeline-node ${selected ? "selected" : ""}`}
      style={{ left: node.x, top: node.y, "--node-color": meta.color } as CSSProperties}
      data-node-id={node.id}
    >
      <button
        type="button"
        className="node-select"
        onClick={onSelect}
        aria-label={`Select ${node.title} ${node.kind} node`}
        onPointerDown={(event) => {
          if (!draggable || event.button !== 0) return;
          event.currentTarget.setPointerCapture(event.pointerId);
          dragGestureRef.current = {
            startX: event.clientX,
            startY: event.clientY,
            originX: node.x,
            originY: node.y,
            nextX: node.x,
            nextY: node.y
          };
          onSelect();
        }}
        onPointerMove={(event) => {
          const gesture = dragGestureRef.current;
          const wrapper = wrapperRef.current;
          if (!gesture || !wrapper) return;
          gesture.nextX = Math.max(0, gesture.originX + (event.clientX - gesture.startX) / zoom);
          gesture.nextY = Math.max(0, gesture.originY + (event.clientY - gesture.startY) / zoom);
          wrapper.style.left = `${gesture.nextX}px`;
          wrapper.style.top = `${gesture.nextY}px`;
        }}
        onPointerUp={finishDrag}
        onPointerCancel={finishDrag}
      >
        <span className="node-valid">✓</span>
        <span className="node-mark">{meta.mark}</span>
        <span className="node-copy"><small>{nodeSubtitle(node)}</small><strong>{node.title}</strong></span>
      </button>
      {node.kind !== "data" ? <span className="port input-port" /> : null}
      {node.kind !== "backtest" ? <span className="port output-port" /> : null}
      <button
        type="button"
        className="node-delete"
        aria-label={`Delete ${node.title}`}
        onClick={(event) => {
          event.stopPropagation();
          onDelete();
        }}
      >
        ×
      </button>
    </div>
  );
}

function Canvas({
  nodes,
  selectedId,
  canUndo,
  canRedo,
  onSelect,
  onAddNode,
  onMoveNode,
  onDeleteNode,
  onUndo,
  onRedo,
  onFocusSearch
}: {
  nodes: StudioNode[];
  selectedId: string | null;
  canUndo: boolean;
  canRedo: boolean;
  onSelect: (id: string | null) => void;
  onAddNode: (node: StudioNode) => void;
  onMoveNode: (id: string, x: number, y: number) => void;
  onDeleteNode: (id: string) => void;
  onUndo: () => void;
  onRedo: () => void;
  onFocusSearch: () => void;
}) {
  const [mode, setMode] = useState<CanvasMode>("select");
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const canvasRef = useRef<HTMLElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const panGestureRef = useRef<{
    startX: number;
    startY: number;
    originX: number;
    originY: number;
    nextX: number;
    nextY: number;
  } | null>(null);

  const ordered = useMemo(() => [...nodes].sort((left, right) => left.x - right.x || left.y - right.y), [nodes]);
  const transform = `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`;

  const setViewport = (nextZoom: number, nextPan = pan) => {
    const boundedZoom = Math.min(1.75, Math.max(0.5, nextZoom));
    setZoom(boundedZoom);
    setPan(nextPan);
  };

  const fitNodes = () => {
    const stage = stageRef.current;
    if (!stage || !nodes.length) {
      setViewport(1, { x: 0, y: 0 });
      return;
    }
    const minX = Math.min(...nodes.map((node) => node.x));
    const minY = Math.min(...nodes.map((node) => node.y));
    const maxX = Math.max(...nodes.map((node) => node.x + 112));
    const maxY = Math.max(...nodes.map((node) => node.y + 120));
    const availableWidth = Math.max(240, stage.clientWidth - 80);
    const availableHeight = Math.max(180, stage.clientHeight - 80);
    const nextZoom = Math.min(1.5, Math.max(0.5, Math.min(availableWidth / (maxX - minX), availableHeight / (maxY - minY))));
    setViewport(nextZoom, {
      x: (stage.clientWidth - (maxX - minX) * nextZoom) / 2 - minX * nextZoom,
      y: (stage.clientHeight - (maxY - minY) * nextZoom) / 2 - minY * nextZoom
    });
  };

  const finishPan = (event: ReactPointerEvent<HTMLDivElement>) => {
    const gesture = panGestureRef.current;
    if (!gesture) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    panGestureRef.current = null;
    setPan({ x: gesture.nextX, y: gesture.nextY });
  };

  return (
    <main ref={canvasRef} className="canvas">
      <div className="canvas-toolbar">
        <button
          type="button"
          className={`tool ${mode === "select" ? "active" : ""}`}
          aria-label="Select and move nodes"
          aria-pressed={mode === "select"}
          onClick={() => setMode("select")}
        >
          ↖
        </button>
        <button
          type="button"
          className={`tool ${mode === "pan" ? "active" : ""}`}
          aria-label="Pan canvas"
          aria-pressed={mode === "pan"}
          onClick={() => setMode("pan")}
        >
          ✋
        </button>
        <button type="button" className="tool" aria-label="Focus component search" onClick={onFocusSearch}>⌕</button>
        <div className="zoom" aria-label={`Canvas zoom ${Math.round(zoom * 100)} percent`}>
          <button type="button" aria-label="Zoom out" onClick={() => setViewport(zoom - 0.1)}>−</button>
          <button type="button" aria-label="Reset zoom" onClick={() => setViewport(1, { x: 0, y: 0 })}>
            {Math.round(zoom * 100)}%
          </button>
          <button type="button" aria-label="Zoom in" onClick={() => setViewport(zoom + 0.1)}>+</button>
        </div>
        <button type="button" className="tool" aria-label="Fit pipeline to canvas" onClick={fitNodes}>⛶</button>
        <button
          type="button"
          className="tool"
          aria-label="Enter canvas fullscreen"
          onClick={() => {
            void canvasRef.current?.requestFullscreen?.().catch(() => undefined);
          }}
        >
          ⤢
        </button>
        <span className="toolbar-spacer" />
        <button type="button" className="tool" aria-label="Undo" disabled={!canUndo} onClick={onUndo}>↶</button>
        <button type="button" className="tool" aria-label="Redo" disabled={!canRedo} onClick={onRedo}>↷</button>
      </div>
      <div
        ref={stageRef}
        className={`canvas-stage ${mode === "pan" ? "panning" : ""}`}
        onClick={(event) => {
          if (event.target === event.currentTarget) onSelect(null);
        }}
        onDragOver={(event) => {
          event.preventDefault();
          event.dataTransfer.dropEffect = event.dataTransfer.types.includes("application/x-studio-node-id") ? "move" : "copy";
        }}
        onDrop={(event) => {
          event.preventDefault();
          const bounds = event.currentTarget.getBoundingClientRect();
          const rawOffset = event.dataTransfer.getData("application/x-studio-offset");
          let offset = { x: 56, y: 60 };
          if (rawOffset) {
            try {
              const parsed = JSON.parse(rawOffset) as { x?: unknown; y?: unknown };
              if (typeof parsed.x === "number" && typeof parsed.y === "number") offset = { x: parsed.x, y: parsed.y };
            } catch {
              // Keep the centered default for malformed drag metadata.
            }
          }
          const x = Math.max(0, (event.clientX - bounds.left - pan.x) / zoom - offset.x);
          const y = Math.max(0, (event.clientY - bounds.top - pan.y) / zoom - offset.y);
          const nodeId = event.dataTransfer.getData("application/x-studio-node-id");
          if (nodeId) {
            onMoveNode(nodeId, Math.round(x), Math.round(y));
            return;
          }
          const kind = event.dataTransfer.getData("application/x-studio-kind") as NodeKind;
          const label = event.dataTransfer.getData("text/plain");
          if (kind && label) onAddNode(createNode(kind, label, Math.round(x), Math.round(y)));
        }}
        onPointerDown={(event) => {
          if (mode !== "pan" || (event.target as Element).closest(".pipeline-node")) return;
          event.currentTarget.setPointerCapture(event.pointerId);
          panGestureRef.current = {
            startX: event.clientX,
            startY: event.clientY,
            originX: pan.x,
            originY: pan.y,
            nextX: pan.x,
            nextY: pan.y
          };
        }}
        onPointerMove={(event) => {
          const gesture = panGestureRef.current;
          const content = contentRef.current;
          if (!gesture || !content) return;
          gesture.nextX = gesture.originX + event.clientX - gesture.startX;
          gesture.nextY = gesture.originY + event.clientY - gesture.startY;
          content.style.transform = `translate(${gesture.nextX}px, ${gesture.nextY}px) scale(${zoom})`;
        }}
        onPointerUp={finishPan}
        onPointerCancel={finishPan}
      >
        <div ref={contentRef} className="canvas-content" style={{ transform }}>
          <svg className="connections" aria-hidden="true">
            {ordered.slice(0, -1).map((node, index) => {
              const next = ordered[index + 1];
              return <line key={`${node.id}-${next.id}`} x1={node.x + 112} y1={node.y + 60} x2={next.x} y2={next.y + 60} />;
            })}
          </svg>
          {nodes.map((node) => (
            <PipelineNode
              key={node.id}
              node={node}
              selected={node.id === selectedId}
              draggable={mode === "select"}
              zoom={zoom}
              onSelect={() => onSelect(node.id)}
              onMove={(x, y) => onMoveNode(node.id, x, y)}
              onDelete={() => onDeleteNode(node.id)}
            />
          ))}
        </div>
        <div className="minimap" aria-hidden="true">
          {nodes.map((node) => (
            <span
              key={node.id}
              style={{
                left: `${Math.min(134, Math.max(1, node.x / 6))}px`,
                top: `${Math.min(60, Math.max(1, node.y / 6))}px`,
                borderColor: kindMeta[node.kind].color
              }}
            />
          ))}
        </div>
      </div>
    </main>
  );
}

function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return <label className="field"><span>{label}{hint ? <em title={hint}>i</em> : null}</span>{children}</label>;
}

function RollingWindowsInput({
  value,
  onCommit
}: {
  value: number[];
  onCommit: (windows: number[]) => void;
}) {
  const serializedValue = value.join(", ");
  const [draft, setDraft] = useState(serializedValue);
  useEffect(() => setDraft(serializedValue), [serializedValue]);

  const commit = () => {
    const windows = draft
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean)
      .map(Number);
    onCommit(windows);
  };

  return (
    <input
      value={draft}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === "Enter") event.currentTarget.blur();
      }}
    />
  );
}

function moveById<T extends { id: string }>(items: T[], sourceId: string, targetId: string): T[] {
  const sourceIndex = items.findIndex((item) => item.id === sourceId);
  const targetIndex = items.findIndex((item) => item.id === targetId);
  if (sourceIndex < 0 || targetIndex < 0 || sourceIndex === targetIndex) return items;
  const next = [...items];
  const [source] = next.splice(sourceIndex, 1);
  next.splice(targetIndex, 0, source);
  return next;
}

function moveAtIndex<T>(items: T[], index: number, offset: -1 | 1): T[] {
  const target = index + offset;
  if (target < 0 || target >= items.length) return items;
  const next = [...items];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

function NestedBlock({
  id,
  listType,
  title,
  enabled,
  index,
  count,
  onToggle,
  onRemove,
  onMove,
  onReorder,
  children
}: {
  id: string;
  listType: "normalization" | "helper";
  title: string;
  enabled: boolean;
  index: number;
  count: number;
  onToggle: () => void;
  onRemove: () => void;
  onMove: (offset: -1 | 1) => void;
  onReorder: (sourceId: string, targetId: string) => void;
  children: ReactNode;
}) {
  return (
    <div
      className="nested-block"
      data-list-id={id}
      onDragOver={(event) => {
        if (event.dataTransfer.types.includes("application/x-studio-list-id")) event.preventDefault();
      }}
      onDrop={(event) => {
        const sourceType = event.dataTransfer.getData("application/x-studio-list-type");
        const sourceId = event.dataTransfer.getData("application/x-studio-list-id");
        if (sourceType === listType && sourceId) {
          event.preventDefault();
          onReorder(sourceId, id);
        }
      }}
    >
      <div className="nested-head">
        <span
          className="grip draggable-grip"
          aria-label={`Drag ${title} to reorder`}
          draggable
          role="img"
          onDragStart={(event) => {
            event.dataTransfer.effectAllowed = "move";
            event.dataTransfer.setData("application/x-studio-list-type", listType);
            event.dataTransfer.setData("application/x-studio-list-id", id);
          }}
        >
          ⠿
        </span>
        <strong>{title}</strong>
        <span className="row-actions">
          <button type="button" className="icon-button" aria-label={`Move ${title} up`} disabled={index === 0} onClick={() => onMove(-1)}>↑</button>
          <button type="button" className="icon-button" aria-label={`Move ${title} down`} disabled={index === count - 1} onClick={() => onMove(1)}>↓</button>
          <button
            type="button"
            className={`switch ${enabled ? "on" : ""}`}
            aria-label={`${enabled ? "Disable" : "Enable"} ${title}`}
            aria-pressed={enabled}
            onClick={onToggle}
          >
            <span />
          </button>
          <button type="button" className="icon-button remove-action" onClick={onRemove} aria-label={`Remove ${title}`}>⌫</button>
        </span>
      </div>
      {enabled ? <div className="nested-body">{children}</div> : <p className="disabled-note">Disabled</p>}
    </div>
  );
}

function prettyRegistryName(name: string): string {
  return name.replace(/_/g, " ").replace(/\b\w/g, (letter: string) => letter.toUpperCase());
}

function parameterValue(parameter: ParameterDefinition, params: Record<string, unknown>): ParameterValue {
  return (params[parameter.name] ?? parameter.default_value ?? parameter.default ?? (parameter.kind === "boolean" ? false : "")) as ParameterValue;
}

function ParameterEditor({
  definition,
  params,
  onChange
}: {
  definition?: ComponentDefinition;
  params: Record<string, unknown>;
  onChange: (params: Record<string, unknown>) => void;
}) {
  if (!definition?.parameters.length) {
    return <p className="empty-section">This registry component exposes no configurable parameters.</p>;
  }
  return (
    <div className="registry-parameters">
      {definition.parameters.map((parameter) => {
        const value = parameterValue(parameter, params);
        const update = (next: unknown) => onChange({ ...params, [parameter.name]: next });
        return (
          <Field key={parameter.name} label={prettyRegistryName(parameter.name)} hint={parameter.description ?? parameter.annotation ?? undefined}>
            {parameter.options?.length ? (
              <select value={String(value ?? "")} onChange={(event) => {
                const selected = parameter.options?.find((option) => String(option) === event.target.value);
                update(selected ?? event.target.value);
              }}>
                {parameter.options.map((option) => <option key={String(option)} value={String(option)}>{String(option)}</option>)}
              </select>
            ) : parameter.kind === "boolean" || typeof value === "boolean" ? (
              <button type="button" className={`wide-switch ${value ? "on" : ""}`} aria-pressed={Boolean(value)} onClick={() => update(!value)}>
                {value ? "Enabled" : "Disabled"}
              </button>
            ) : parameter.kind === "integer" || parameter.kind === "number" || typeof value === "number" ? (
              <input type="number" step={parameter.kind === "integer" ? "1" : "any"} value={String(value ?? "")} onChange={(event) => update(event.target.value === "" ? "" : Number(event.target.value))} />
            ) : parameter.kind === "list" || parameter.kind === "object" || Array.isArray(value) || (value !== null && typeof value === "object") ? (
              <textarea value={JSON.stringify(value, null, 2)} onChange={(event) => {
                try { update(JSON.parse(event.target.value)); } catch { /* Keep the previous valid structured value. */ }
              }} />
            ) : (
              <input value={String(value ?? "")} onChange={(event) => update(event.target.value)} />
            )}
          </Field>
        );
      })}
    </div>
  );
}

function RegistrySelector({
  kind,
  value,
  onSelect
}: {
  kind: NodeKind;
  value: string;
  onSelect: (definition: ComponentDefinition) => void;
}) {
  const definitions = definitionsFor(kind);
  const selected = definitionFor(kind, value) ?? definitions[0];
  return (
    <Field label={`${prettyRegistryName(kind)} registry`} hint={`${definitions.length} registered components from src/${kind}s/registry.py`}>
      <select value={selected?.name ?? ""} onChange={(event) => {
        const definition = definitionFor(kind, event.target.value);
        if (definition) onSelect(definition);
      }}>
        {definitions.map((definition) => <option key={definition.name} value={definition.name}>{prettyRegistryName(definition.display_name || definition.name)}</option>)}
      </select>
    </Field>
  );
}

function FeatureInspector({
  node,
  tab,
  setTab,
  onUpdate,
  chartRoutes,
  onChartRouteChange
}: {
  node: StudioNode & { feature: FeatureConfig };
  tab: InspectorTab;
  setTab: (tab: InspectorTab) => void;
  onUpdate: (node: StudioNode) => void;
  chartRoutes: Record<string, ChartPlacement>;
  onChartRouteChange: (output: string, placement: ChartPlacement) => void;
}) {
  const feature = node.feature;
  const updateFeature = (next: FeatureConfig) => onUpdate({ ...node, feature: next });
  const updateNormalization = (id: string, update: (item: Normalization) => Normalization) => {
    updateFeature({
      ...feature,
      normalizations: feature.normalizations.map((item) => item.id === id ? update(item) : item)
    });
  };
  const updateHelper = (id: string, update: (item: Helper) => Helper) => {
    updateFeature({
      ...feature,
      helpers: feature.helpers.map((item) => item.id === id ? update(item) : item)
    });
  };

  return (
    <>
      <nav className="inspector-tabs" aria-label="Feature inspector sections">
        {(["base", "normalizations", "helpers", "outputs"] as const).map((item) => (
          <button
            type="button"
            className={tab === item ? "active" : ""}
            onClick={() => setTab(item)}
            aria-pressed={tab === item}
            key={item}
          >
            {item[0].toUpperCase() + item.slice(1)}
          </button>
        ))}
      </nav>
      <div className="inspector-scroll">
        {tab === "base" ? (
          <section className="inspector-section">
            <div className="section-title"><h2>Feature parameters</h2></div>
            <RegistrySelector kind="feature" value={feature.kind} onSelect={(definition) => updateFeature({
              ...feature,
              kind: definition.name,
              registryParams: defaultsFor(definition)
            })} />
            <ParameterEditor
              definition={definitionFor("feature", feature.kind)}
              params={feature.registryParams ?? {}}
              onChange={(registryParams) => updateFeature({ ...feature, registryParams })}
            />
            <Field label="Enabled">
              <button
                type="button"
                className={`wide-switch ${feature.enabled ? "on" : ""}`}
                aria-pressed={feature.enabled}
                onClick={() => updateFeature({ ...feature, enabled: !feature.enabled })}
              >
                {feature.enabled ? "Enabled" : "Disabled"}
              </button>
            </Field>
          </section>
        ) : null}
        {tab === "normalizations" ? (
          <section className="inspector-section">
            <div className="section-title">
              <h2>Normalizations</h2>
              <button
                type="button"
                onClick={() => updateFeature({
                  ...feature,
                  normalizations: [
                    ...feature.normalizations,
                    { id: newId("norm"), kind: "rolling_zscore", window: 96, shift: 1, enabled: true }
                  ]
                })}
              >
                ＋ Add normalization
              </button>
            </div>
            {feature.normalizations.map((item, index) => (
              <NestedBlock
                key={item.id}
                id={item.id}
                listType="normalization"
                title={`${index + 1} · ${item.kind}`}
                enabled={item.enabled}
                index={index}
                count={feature.normalizations.length}
                onToggle={() => updateNormalization(item.id, (current) => ({ ...current, enabled: !current.enabled }))}
                onRemove={() => updateFeature({ ...feature, normalizations: feature.normalizations.filter((current) => current.id !== item.id) })}
                onMove={(offset) => updateFeature({ ...feature, normalizations: moveAtIndex(feature.normalizations, index, offset) })}
                onReorder={(sourceId, targetId) => updateFeature({ ...feature, normalizations: moveById(feature.normalizations, sourceId, targetId) })}
              >
                <Field label="Method">
                  <select
                    value={item.kind}
                    onChange={(event) => updateNormalization(item.id, (current) => ({
                      ...current,
                      kind: event.target.value as Normalization["kind"]
                    }))}
                  >
                    <option value="rolling_zscore">rolling_zscore</option>
                    <option value="range_position">range_position</option>
                    <option value="rolling_clip">rolling_clip</option>
                  </select>
                </Field>
                <div className="field-row">
                  <Field label="Window">
                    <input
                      type="number"
                      min="2"
                      step="1"
                      value={item.window}
                      onChange={(event) => updateNormalization(item.id, (current) => ({ ...current, window: Number(event.target.value) }))}
                    />
                  </Field>
                  <Field label="Shift">
                    <input
                      type="number"
                      min="1"
                      step="1"
                      value={item.shift}
                      onChange={(event) => updateNormalization(item.id, (current) => ({ ...current, shift: Number(event.target.value) }))}
                    />
                  </Field>
                </div>
              </NestedBlock>
            ))}
            {!feature.normalizations.length ? <p className="empty-section">No normalizations configured.</p> : null}
          </section>
        ) : null}
        {tab === "helpers" ? (
          <section className="inspector-section">
            <div className="section-title">
              <h2>Helpers / transforms</h2>
              <button
                type="button"
                onClick={() => updateFeature({
                  ...feature,
                  helpers: [
                    ...feature.helpers,
                    { id: newId("helper"), kind: "slope", left: "vol_rolling_96", right: "", window: 8, enabled: true }
                  ]
                })}
              >
                ＋ Add helper
              </button>
            </div>
            {feature.helpers.map((item, index) => (
              <NestedBlock
                key={item.id}
                id={item.id}
                listType="helper"
                title={`${index + 1} · ${item.kind}`}
                enabled={item.enabled}
                index={index}
                count={feature.helpers.length}
                onToggle={() => updateHelper(item.id, (current) => ({ ...current, enabled: !current.enabled }))}
                onRemove={() => updateFeature({ ...feature, helpers: feature.helpers.filter((current) => current.id !== item.id) })}
                onMove={(offset) => updateFeature({ ...feature, helpers: moveAtIndex(feature.helpers, index, offset) })}
                onReorder={(sourceId, targetId) => updateFeature({ ...feature, helpers: moveById(feature.helpers, sourceId, targetId) })}
              >
                <Field label="Helper kind">
                  <select
                    value={item.kind}
                    onChange={(event) => {
                      const kind = event.target.value as Helper["kind"];
                      updateHelper(item.id, (current) => ({
                        ...current,
                        kind,
                        right: kind === "ratio" ? current.right || "close" : "",
                        window: kind === "slope" ? current.window ?? 8 : undefined
                      }));
                    }}
                  >
                    <option value="slope">slope</option>
                    <option value="ratio">ratio</option>
                  </select>
                </Field>
                <Field label={item.kind === "ratio" ? "Numerator column" : "Source column"}>
                  <input value={item.left} onChange={(event) => updateHelper(item.id, (current) => ({ ...current, left: event.target.value }))} />
                </Field>
                {item.kind === "ratio" ? (
                  <Field label="Denominator column">
                    <input value={item.right} onChange={(event) => updateHelper(item.id, (current) => ({ ...current, right: event.target.value }))} />
                  </Field>
                ) : (
                  <Field label="Window">
                    <input
                      type="number"
                      min="2"
                      step="1"
                      value={item.window ?? 8}
                      onChange={(event) => updateHelper(item.id, (current) => ({ ...current, window: Number(event.target.value) }))}
                    />
                  </Field>
                )}
              </NestedBlock>
            ))}
            {!feature.helpers.length ? <p className="empty-section">No helpers configured.</p> : null}
            <p className="section-note">Helpers execute in the displayed order. Drag the grip or use the arrow buttons to reorder.</p>
          </section>
        ) : null}
        {tab === "outputs" ? (
          <section className="inspector-section">
            <div className="section-title"><h2>Generated outputs</h2></div>
            {feature.outputs.map((output, index) => (
              <div className="output-row" key={index}>
                <input
                  aria-label={`Output ${index + 1}`}
                  value={output}
                  onChange={(event) => {
                    const outputs = [...feature.outputs];
                    outputs[index] = event.target.value;
                    updateFeature({ ...feature, outputs });
                  }}
                />
                <select
                  aria-label={`Chart placement for ${output}`}
                  value={chartRoutes[output] ?? "hidden"}
                  onChange={(event) => onChartRouteChange(output, event.target.value as ChartPlacement)}
                >
                  <option value="main">Main chart</option>
                  <option value="lower">Lower panel</option>
                  <option value="hidden">Not shown</option>
                </select>
                <span className="output-actions">
                  <button type="button" className="icon-button" aria-label={`Move output ${index + 1} up`} disabled={index === 0} onClick={() => updateFeature({ ...feature, outputs: moveAtIndex(feature.outputs, index, -1) })}>↑</button>
                  <button type="button" className="icon-button" aria-label={`Move output ${index + 1} down`} disabled={index === feature.outputs.length - 1} onClick={() => updateFeature({ ...feature, outputs: moveAtIndex(feature.outputs, index, 1) })}>↓</button>
                  <button type="button" className="icon-button remove-action" aria-label={`Remove output ${index + 1}`} onClick={() => updateFeature({ ...feature, outputs: feature.outputs.filter((_, outputIndex) => outputIndex !== index) })}>⌫</button>
                </span>
              </div>
            ))}
            <button
              type="button"
              className="secondary-wide"
              onClick={() => updateFeature({ ...feature, outputs: [...feature.outputs, `feature_output_${feature.outputs.length + 1}`] })}
            >
              ＋ Add output mapping
            </button>
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
  onUpdate,
  onDuplicate,
  onDelete,
  chartRoutes,
  onChartRouteChange
}: {
  selected?: StudioNode;
  tab: InspectorTab;
  setTab: (tab: InspectorTab) => void;
  onUpdate: (node: StudioNode) => void;
  onDuplicate: () => void;
  onDelete: () => void;
  chartRoutes: Record<string, ChartPlacement>;
  onChartRouteChange: (output: string, placement: ChartPlacement) => void;
}) {
  const meta = selected ? kindMeta[selected.kind] : kindMeta.feature;
  return (
    <aside className="inspector">
      <div className="inspector-heading">
        <span className="inspector-mark" style={{ color: meta.color }}>{selected ? meta.mark : "◇"}</span>
        <div><small>{selected?.kind ?? "component"}</small><strong>{selected?.title ?? "Select a component"}</strong></div>
        {selected ? (
          <span className="heading-actions">
            <button type="button" className="icon-button" aria-label={`Duplicate ${selected.title}`} onClick={onDuplicate}>⧉</button>
            <button type="button" className="icon-button remove-action" aria-label={`Delete selected ${selected.title}`} onClick={onDelete}>⌫</button>
          </span>
        ) : null}
      </div>
      {selected?.kind === "feature" && selected.feature ? (
        <FeatureInspector
          node={selected as StudioNode & { feature: FeatureConfig }}
          tab={tab}
          setTab={setTab}
          onUpdate={onUpdate}
          chartRoutes={chartRoutes}
          onChartRouteChange={onChartRouteChange}
        />
      ) : (
        <div className="generic-inspector">
          {selected ? (
            <>
              <h2>{definitionsFor(selected.kind).length ? `${definitionsFor(selected.kind).length} registered ${selected.kind}s` : selected.subtitle}</h2>
              {definitionsFor(selected.kind).length ? (
                <>
                  <RegistrySelector kind={selected.kind} value={selected.title} onSelect={(definition) => onUpdate({
                    ...selected,
                    title: definition.name,
                    subtitle: definition.description || prettyRegistryName(definition.name),
                    registryParams: defaultsFor(definition)
                  })} />
                  <ParameterEditor
                    definition={definitionFor(selected.kind, selected.title) ?? definitionsFor(selected.kind)[0]}
                    params={selected.registryParams ?? {}}
                    onChange={(registryParams) => onUpdate({ ...selected, registryParams })}
                  />
                </>
              ) : (
                <p>This pipeline component is configured by its dedicated runtime section.</p>
              )}
              <p>Drag the node on the canvas to reposition it. Delete/Backspace removes the selected node.</p>
            </>
          ) : (
            <div className="empty-inspector">
              <h2>No component selected</h2>
              <p>Select a pipeline node to edit it, or add a component from the library.</p>
            </div>
          )}
        </div>
      )}
    </aside>
  );
}

function formatCell(value: string | number, column: string): string {
  if (typeof value === "string") return value;
  if (column === "open" || column === "high" || column === "low" || column === "close") return value.toFixed(2);
  return value.toFixed(5).replace(/0+$/, "").replace(/\.$/, "");
}

type PreviewSeriesKey = "close" | "returns" | "vol_96_z" | "slope_8";

interface PreviewSeriesDefinition {
  key: PreviewSeriesKey;
  label: string;
  color: string;
  value: (row: PreviewRow) => number;
  format: (value: number) => string;
}

const PREVIEW_SERIES: PreviewSeriesDefinition[] = [
  {
    key: "close",
    label: "Close price",
    color: "#2878f6",
    value: (row) => row.close,
    format: (value) => value.toFixed(2)
  },
  {
    key: "returns",
    label: "Bar return",
    color: "#16a05d",
    value: (row) => row.returns,
    format: (value) => `${(value * 100).toFixed(3)}%`
  },
  {
    key: "vol_96_z",
    label: "Volatility z-score",
    color: "#7457e8",
    value: (row) => row.vol_96_z,
    format: (value) => value.toFixed(4)
  },
  {
    key: "slope_8",
    label: "Volatility slope",
    color: "#e77824",
    value: (row) => row.slope_8,
    format: (value) => value.toFixed(4)
  }
];

function PreviewSeriesChart({ series }: { series: PreviewSeriesDefinition }) {
  const width = 760;
  const height = 116;
  const padX = 22;
  const padY = 14;
  const values = previewRows.map(series.value);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const span = maximum - minimum || 1;
  const points = values.map((value, index) => {
    const x = values.length === 1
      ? width / 2
      : padX + (index / (values.length - 1)) * (width - padX * 2);
    const y = padY + ((maximum - value) / span) * (height - padY * 2);
    return { x, y, value };
  });
  return (
    <article className="preview-series-chart">
      <header>
        <span className="series-name"><i style={{ background: series.color }} />{series.label}</span>
        <span>
          latest <strong>{series.format(values[values.length - 1])}</strong>
          <small>{series.format(minimum)} – {series.format(maximum)}</small>
        </span>
      </header>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`${series.label} preview chart from ${previewRows[0]?.timestamp} to ${previewRows[previewRows.length - 1]?.timestamp}`}
      >
        {[0.25, 0.5, 0.75].map((ratio) => (
          <line
            key={ratio}
            className="chart-grid-line"
            x1={padX}
            x2={width - padX}
            y1={height * ratio}
            y2={height * ratio}
          />
        ))}
        <polyline
          fill="none"
          stroke={series.color}
          strokeWidth="3"
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
          points={points.map(({ x, y }) => `${x},${y}`).join(" ")}
        />
        {points.map(({ x, y, value }, index) => (
          <circle key={`${previewRows[index].timestamp}-${value}`} cx={x} cy={y} r="4" fill={series.color}>
            <title>{previewRows[index].timestamp}: {series.format(value)}</title>
          </circle>
        ))}
      </svg>
      <footer>
        <span>{previewRows[0]?.timestamp}</span>
        <span>{previewRows[previewRows.length - 1]?.timestamp}</span>
      </footer>
    </article>
  );
}

function BottomDrawer({
  tab,
  validation,
  runState,
  setTab,
  onOpenResults
}: {
  tab: BottomTab;
  validation: ValidationState | null;
  runState: RunState;
  setTab: (tab: BottomTab) => void;
  onOpenResults: () => void;
}) {
  const errors = validation?.issues.filter((issue) => issue.level === "error").length ?? 0;
  const columns = ["timestamp", "open", "high", "low", "close", "returns", "vol_96_z", "slope_8"] as const;
  return (
    <section className="bottom-drawer">
      <nav className="bottom-tabs" aria-label="Preview, validation and run results">
        {(["preview", "validation", "results"] as const).map((item) => (
          <button
            type="button"
            key={item}
            onClick={() => setTab(item)}
            className={tab === item ? "active" : ""}
            aria-pressed={tab === item}
          >
            {item[0].toUpperCase() + item.slice(1)}
            {item === "validation" && validation ? <span className={`count ${errors ? "error" : ""}`}>{errors}</span> : null}
          </button>
        ))}
        <span className="drawer-spacer" />
        <span>{previewRows.length} preview rows</span>
        <span>Local deterministic preview <i /></span>
      </nav>
      {tab === "preview" ? (
        <div className="table-wrap">
          <table>
            <thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
            <tbody>
              {previewRows.map((row) => (
                <tr key={row.timestamp}>
                  {columns.map((column) => <td key={column}>{formatCell(row[column], column)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {tab === "validation" ? (
        <div className="validation-view">
          {!validation ? (
            <div className="empty-result"><strong>Not validated</strong><span>Run validation after editing the pipeline.</span></div>
          ) : validation.issues.length === 0 ? (
            <div className="empty-result success"><strong>✓ Validation passed</strong><span>Pipeline order, fields and temporal-causality checks passed at {validation.checkedAt}.</span></div>
          ) : (
            <div className="issue-list">
              <div className="issue-summary">
                <strong>{errors ? `Validation failed · ${errors} error${errors === 1 ? "" : "s"}` : "Validation passed with warnings"}</strong>
                <span>Checked at {validation.checkedAt}</span>
              </div>
              <ul>
                {validation.issues.map((issue) => (
                  <li className={issue.level} key={issue.id}><strong>{issue.level}</strong><span>{issue.message}</span></li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : null}
      {tab === "results" ? (
        <div className="results-view" aria-live="polite">
          {runState.status === "idle" ? (
            <div className="empty-result"><strong>No run yet</strong><span>Validate the experiment and start a local Studio run.</span></div>
          ) : null}
          {runState.status === "running" ? (
            <div className="empty-result running-result"><strong>Preparing preview analytics…</strong><span>Validating the Studio document and summarizing the deterministic sample.</span></div>
          ) : null}
          {runState.status === "failed" ? (
            <div className="empty-result error-result"><strong>Run blocked</strong><span>{runState.error}</span></div>
          ) : null}
          {runState.status === "completed" ? (
            <>
              <div className="result-copy">
                <strong>Preview analytics ready</strong>
                <span>
                  {runState.result.previewRowCount} bars · {PREVIEW_SERIES.length} chart series · {runState.result.outputColumns.length} configured outputs
                </span>
              </div>
              <button type="button" onClick={onOpenResults}>Open metrics &amp; chart</button>
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function YamlModal({ onClose, yaml }: { onClose: () => void; yaml: string }) {
  const [copyStatus, setCopyStatus] = useState("Copy YAML");
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <section
        className="yaml-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="yaml-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div><small>Synchronized Studio document</small><h2 id="yaml-title">YAML preview</h2></div>
          <button type="button" className="icon-button" autoFocus onClick={onClose} aria-label="Close YAML preview">×</button>
        </header>
        <pre>{yaml}</pre>
        <footer>
          <span>Every visible node and feature setting is represented.</span>
          <button
            type="button"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(yaml);
                setCopyStatus("Copied");
              } catch {
                setCopyStatus("Copy failed");
              }
            }}
          >
            {copyStatus}
          </button>
        </footer>
      </section>
    </div>
  );
}

function RunsModal({ runs, onClose }: { runs: StoredRun[]; onClose: () => void }) {
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <section className="runs-modal" role="dialog" aria-modal="true" aria-labelledby="runs-title" onMouseDown={(event) => event.stopPropagation()}>
        <header><div><small>Persistent local history</small><h2 id="runs-title">Saved runs</h2></div><button className="icon-button" onClick={onClose}>×</button></header>
        <div className="runs-list">
          {runs.length ? runs.map((run) => (
            <a className="saved-run" key={run.id} href={`${window.location.pathname}?view=run&runId=${encodeURIComponent(run.id)}`} target="_blank" rel="noreferrer">
              <span><strong>{run.experimentName}</strong><small>{new Date(run.createdAt).toLocaleString()}</small></span>
              <span><small>{run.asset} · {run.timeframe}</small><b>Open results ↗</b></span>
            </a>
          )) : <div className="empty-runs"><strong>No saved runs yet</strong><span>Your completed experiments will appear here.</span></div>}
        </div>
      </section>
    </div>
  );
}

function ResultsModal({ result, onClose }: { result: StudioRunResult; onClose: () => void }) {
  const [visibleSeries, setVisibleSeries] = useState<Set<PreviewSeriesKey>>(
    () => new Set(["close", "vol_96_z", "slope_8"])
  );
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);
  const selectedSeries = PREVIEW_SERIES.filter((series) => visibleSeries.has(series.key));
  const toggleSeries = (key: PreviewSeriesKey) => {
    setVisibleSeries((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };
  const metrics = result.previewMetrics;
  const durationLabel = metrics.durationMinutes >= 60
    ? `${Math.floor(metrics.durationMinutes / 60)}h ${metrics.durationMinutes % 60}m`
    : `${metrics.durationMinutes}m`;
  const signedCloseChange = `${metrics.closeChangePct >= 0 ? "+" : ""}${metrics.closeChangePct.toFixed(3)}%`;
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <section
        className="results-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="results-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div><small>Deterministic local data sample</small><h2 id="results-title">Preview results</h2></div>
          <button type="button" className="icon-button" autoFocus onClick={onClose} aria-label="Close run results">×</button>
        </header>
        <section className="preview-scope-note" aria-label="Preview execution scope">
          <strong>Preview analytics — not an OOS backtest</strong>
          <span>
            These values come from the visible {result.previewRowCount}-row sample. Sharpe, PnL, drawdown and trade metrics
            are intentionally not calculated until Studio is connected to the framework runner.
          </span>
        </section>
        <section className="result-section metrics-section">
          <div className="result-section-heading">
            <div><h3>Sample metrics</h3><span>{metrics.startTimestamp} → {metrics.endTimestamp}</span></div>
            <code title={result.runId}>{result.runId}</code>
          </div>
          <div className="results-grid preview-metrics-grid">
            <div><span>Preview bars</span><strong>{result.previewRowCount}</strong><small>Bundled deterministic rows</small></div>
            <div><span>Sample window</span><strong>{durationLabel}</strong><small>First to last timestamp</small></div>
            <div>
              <span>Close change</span>
              <strong className={metrics.closeChangePct >= 0 ? "positive-metric" : "negative-metric"}>{signedCloseChange}</strong>
              <small>First close → last close</small>
            </div>
            <div><span>Mean |bar return|</span><strong>{metrics.meanAbsoluteReturnPct.toFixed(3)}%</strong><small>Descriptive, not annualized</small></div>
            <div><span>Missing values</span><strong>{metrics.missingValueCount}</strong><small>Across preview fields</small></div>
            <div><span>Warnings</span><strong>{result.warnings.length}</strong><small>Canvas/validation warnings</small></div>
          </div>
        </section>
        <section className="result-section chart-section">
          <div className="result-section-heading">
            <div><h3>Series explorer</h3><span>Select exactly which preview series are visible.</span></div>
            <span>{selectedSeries.length}/{PREVIEW_SERIES.length} visible</span>
          </div>
          <div className="series-selector" aria-label="Visible preview chart series">
            {PREVIEW_SERIES.map((series) => (
              <label key={series.key} className={visibleSeries.has(series.key) ? "selected" : ""}>
                <input
                  type="checkbox"
                  checked={visibleSeries.has(series.key)}
                  onChange={() => toggleSeries(series.key)}
                />
                <i style={{ background: series.color }} />
                <span>{series.label}</span>
              </label>
            ))}
          </div>
          <div className="preview-chart-stack" aria-live="polite">
            {selectedSeries.length ? (
              selectedSeries.map((series) => <PreviewSeriesChart key={series.key} series={series} />)
            ) : (
              <div className="empty-chart-selection">
                <strong>No visible series</strong>
                <span>Select one or more series above to display the chart.</span>
              </div>
            )}
          </div>
        </section>
        <section className="result-section configured-output-section">
          <div className="result-section-heading">
            <div><h3>Configured output mappings</h3><span>Columns requested by the visual feature configuration.</span></div>
            <span>{result.outputColumns.length} outputs</span>
          </div>
          {result.outputColumns.length ? (
            <div className="output-chips">{result.outputColumns.map((output) => <code key={output}>{output}</code>)}</div>
          ) : <p>No output mappings are enabled.</p>}
        </section>
        {result.warnings.length ? (
          <section className="result-section warnings">
            <h3>Warnings</h3>
            <ul>{result.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
          </section>
        ) : null}
      </section>
    </div>
  );
}

function StatusBar({
  validation,
  runState
}: {
  validation: ValidationState | null;
  runState: RunState;
}) {
  const errorCount = validation?.issues.filter((issue) => issue.level === "error").length ?? 0;
  const validationLabel = !validation
    ? "Not validated"
    : errorCount
      ? `${errorCount} validation error${errorCount === 1 ? "" : "s"}`
      : validation.issues.length
        ? "Validation passed with warnings"
        : "Validation passed";
  const runLabel = runState.status === "completed"
    ? `Last run: ${new Date(runState.result.completedAt).toLocaleTimeString()}`
    : runState.status === "running"
      ? "Run in progress"
      : runState.status === "failed"
        ? "Last run blocked"
        : "Last run: not started";
  return (
    <footer className={`statusbar ${errorCount ? "has-errors" : ""}`}>
      <span><i /> {validationLabel}</span>
      <span>{runLabel}</span>
      <span className="status-spacer" />
      <span>Engine: local Studio preview</span>
      <span>Config: visual + YAML</span>
    </footer>
  );
}

function StudioEditor() {
  const [history, setHistory] = useState<HistoryState>(() => ({
    past: [],
    present: loadStoredDocument(),
    future: []
  }));
  const [selectedId, setSelectedId] = useState<string | null>("volatility");
  const [query, setQuery] = useState("");
  const [libraryCollapsed, setLibraryCollapsed] = useState(false);
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("normalizations");
  const [bottomTab, setBottomTab] = useState<BottomTab>("preview");
  const [validation, setValidation] = useState<ValidationState | null>(null);
  const [runState, setRunState] = useState<RunState>({ status: "idle" });
  const [yamlOpen, setYamlOpen] = useState(false);
  const [runsOpen, setRunsOpen] = useState(false);
  const [savedRuns, setSavedRuns] = useState<StoredRun[]>(() => listRuns());
  const [latestRunId, setLatestRunId] = useState<string | null>(() => listRuns()[0]?.id ?? null);
  const [chartRoutes, setChartRoutes] = useState<Record<string, ChartPlacement>>({
    vol_rolling_96: "main",
    vol_rolling_96__zscore: "lower",
    vol_slope_8: "lower",
    vol_slope_over_close: "hidden"
  });
  const [saveStatus, setSaveStatus] = useState("Saved locally");
  const [renaming, setRenaming] = useState(false);
  const [renameDraft, setRenameDraft] = useState("");
  const searchInputRef = useRef<HTMLInputElement>(null);
  const runTokenRef = useRef(0);

  const studioDocument = history.present;
  const selected = studioDocument.nodes.find((node) => node.id === selectedId);
  const yaml = useMemo(() => serializeStudioYaml(studioDocument), [studioDocument]);

  const invalidateDerivedState = useCallback(() => {
    runTokenRef.current += 1;
    setValidation(null);
    setRunState({ status: "idle" });
  }, []);

  const commitDocument = useCallback((change: (current: StudioDocument) => StudioDocument) => {
    setHistory((current) => {
      const next = change(current.present);
      if (next === current.present) return current;
      return { past: [...current.past, current.present], present: next, future: [] };
    });
    invalidateDerivedState();
  }, [invalidateDerivedState]);

  const updateNode = useCallback((node: StudioNode) => {
    commitDocument((current) => ({
      ...current,
      nodes: current.nodes.map((item) => item.id === node.id ? node : item)
    }));
  }, [commitDocument]);

  const deleteNode = useCallback((id: string) => {
    commitDocument((current) => ({ ...current, nodes: current.nodes.filter((node) => node.id !== id) }));
    setSelectedId((current) => current === id ? null : current);
  }, [commitDocument]);

  const undo = useCallback(() => {
    setHistory((current) => {
      if (!current.past.length) return current;
      const previous = current.past[current.past.length - 1];
      return {
        past: current.past.slice(0, -1),
        present: previous,
        future: [current.present, ...current.future]
      };
    });
    invalidateDerivedState();
  }, [invalidateDerivedState]);

  const redo = useCallback(() => {
    setHistory((current) => {
      if (!current.future.length) return current;
      const [next, ...future] = current.future;
      return {
        past: [...current.past, current.present],
        present: next,
        future
      };
    });
    invalidateDerivedState();
  }, [invalidateDerivedState]);

  const deleteSelected = useCallback(() => {
    if (selectedId) deleteNode(selectedId);
  }, [deleteNode, selectedId]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const isEditing = target?.matches("input, textarea, select, [contenteditable='true']");
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        if (event.shiftKey) redo();
        else undo();
        return;
      }
      if (!isEditing && (event.key === "Delete" || event.key === "Backspace")) {
        event.preventDefault();
        deleteSelected();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [deleteSelected, redo, undo]);

  useEffect(() => {
    setSaveStatus("Saving…");
    const timeout = window.setTimeout(() => {
      setSaveStatus(saveStoredDocument(studioDocument) ? "Saved locally just now" : "Local save unavailable");
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [studioDocument]);

  const addNode = (node: StudioNode) => {
    commitDocument((current) => ({ ...current, nodes: [...current.nodes, node] }));
    setSelectedId(node.id);
  };

  const addFromPalette = (kind: NodeKind, label: string) => {
    const index = studioDocument.nodes.length;
    const definition = definitionsFor(kind)[0];
    const node = createNode(kind, definition?.name ?? label, 24 + (index % 5) * 128, 60 + Math.floor(index / 5) * 138);
    if (definition) {
      if (kind === "feature" && node.feature) {
        node.feature = { ...node.feature, kind: definition.name, registryParams: defaultsFor(definition) };
      } else {
        node.registryParams = defaultsFor(definition);
      }
    }
    addNode(node);
  };

  const duplicateSelected = () => {
    if (!selected) return;
    const copy: StudioNode = {
      ...selected,
      id: newId(selected.kind),
      title: `${selected.title} copy`,
      x: selected.x + 28,
      y: selected.y + 28,
      feature: selected.feature
        ? {
          ...selected.feature,
          normalizations: selected.feature.normalizations.map((item) => ({ ...item, id: newId("norm") })),
          helpers: selected.feature.helpers.map((item) => ({ ...item, id: newId("helper") })),
          outputs: [...selected.feature.outputs]
        }
        : undefined
    };
    addNode(copy);
  };

  const performValidation = (): ValidationIssue[] => {
    const issues = validateStudioDocument(studioDocument);
    setValidation({ issues, checkedAt: new Date().toLocaleTimeString() });
    setBottomTab("validation");
    return issues;
  };

  const run = () => {
    const issues = validateStudioDocument(studioDocument);
    setValidation({ issues, checkedAt: new Date().toLocaleTimeString() });
    const errors = issues.filter((issue) => issue.level === "error");
    if (errors.length) {
      setRunState({ status: "failed", error: errors.map((issue) => issue.message).join(" ") });
      setBottomTab("validation");
      return;
    }
    const token = runTokenRef.current + 1;
    runTokenRef.current = token;
    const startedAtMs = Date.now();
    const pendingRunWindow = window.open("about:blank", `studio-run-${token}`, "popup,width=1500,height=950");
    setRunState({ status: "running", startedAt: new Date(startedAtMs).toISOString() });
    setBottomTab("results");
    window.setTimeout(() => {
      if (runTokenRef.current !== token) return;
      try {
        const result = executeStudioDocument(studioDocument, startedAtMs, Date.now());
        setRunState({ status: "completed", result });
        const storedRun: StoredRun = {
          id: result.runId,
          experimentName: studioDocument.name,
          createdAt: result.completedAt,
          status: "completed",
          asset: "SPX500",
          timeframe: "30m",
          nodes: studioDocument.nodes.map(({ id, kind, title, subtitle }) => ({ id, kind, title, subtitle })),
          chartRoutes,
          yaml
        };
        saveRun(storedRun);
        setSavedRuns(listRuns());
        setLatestRunId(storedRun.id);
        const runUrl = `${window.location.pathname}?view=run&runId=${encodeURIComponent(storedRun.id)}`;
        if (pendingRunWindow) pendingRunWindow.location.href = runUrl;
        else window.open(runUrl, "_blank");
      } catch (error) {
        setRunState({ status: "failed", error: error instanceof Error ? error.message : String(error) });
      }
    }, 0);
  };

  return (
    <div className="app">
      <TopBar
        experimentName={studioDocument.name}
        renaming={renaming}
        renameDraft={renameDraft}
        saveStatus={saveStatus}
        running={runState.status === "running"}
        libraryCollapsed={libraryCollapsed}
        onOpenRename={() => {
          setRenameDraft(studioDocument.name);
          setRenaming(true);
        }}
        onRenameDraft={setRenameDraft}
        onCommitRename={() => {
          commitDocument((current) => ({ ...current, name: renameDraft.trim() }));
          setRenaming(false);
        }}
        onCancelRename={() => setRenaming(false)}
        onToggleLibrary={() => setLibraryCollapsed((current) => !current)}
        onRuns={() => {
          setSavedRuns(listRuns());
          setRunsOpen(true);
        }}
        onYaml={() => setYamlOpen(true)}
        onValidate={() => {
          performValidation();
        }}
        onRun={run}
      />
      <div className={`workspace ${libraryCollapsed ? "library-collapsed" : ""}`}>
        <ComponentLibrary
          query={query}
          collapsed={libraryCollapsed}
          searchInputRef={searchInputRef}
          onQuery={setQuery}
          onToggleCollapsed={() => setLibraryCollapsed((current) => !current)}
          onAdd={addFromPalette}
        />
        <Canvas
          nodes={studioDocument.nodes}
          selectedId={selectedId}
          canUndo={history.past.length > 0}
          canRedo={history.future.length > 0}
          onSelect={setSelectedId}
          onAddNode={addNode}
          onMoveNode={(id, x, y) => {
            const node = studioDocument.nodes.find((item) => item.id === id);
            if (node) updateNode({ ...node, x, y });
            setSelectedId(id);
          }}
          onDeleteNode={deleteNode}
          onUndo={undo}
          onRedo={redo}
          onFocusSearch={() => {
            if (libraryCollapsed) setLibraryCollapsed(false);
            window.setTimeout(() => searchInputRef.current?.focus(), 0);
          }}
        />
        <Inspector
          selected={selected}
          tab={inspectorTab}
          setTab={setInspectorTab}
          onUpdate={updateNode}
          onDuplicate={duplicateSelected}
          onDelete={deleteSelected}
          chartRoutes={chartRoutes}
          onChartRouteChange={(output, placement) => setChartRoutes((current) => ({ ...current, [output]: placement }))}
        />
        <BottomDrawer
          tab={bottomTab}
          validation={validation}
          runState={runState}
          setTab={setBottomTab}
          onOpenResults={() => {
            if (latestRunId) window.open(`${window.location.pathname}?view=run&runId=${encodeURIComponent(latestRunId)}`, `studio-run-${latestRunId}`, "popup,width=1500,height=950");
          }}
        />
      </div>
      <StatusBar validation={validation} runState={runState} />
      {yamlOpen ? <YamlModal yaml={yaml} onClose={() => setYamlOpen(false)} /> : null}
      {runsOpen ? <RunsModal runs={savedRuns} onClose={() => setRunsOpen(false)} /> : null}
    </div>
  );
}

export function App() {
  const params = new URLSearchParams(window.location.search);
  const runId = params.get("runId");
  return params.get("view") === "run" && runId ? <RunWindow runId={runId} /> : <StudioEditor />;
}
