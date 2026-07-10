import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type {
  ExecutionAssetSummary,
  ExecutionBotOption,
  ExecutionFeatureSnapshot,
  ExecutionStatus,
  JsonRecord
} from "../types/execution";
import { ExecutionChartWorkspace } from "./ExecutionChartWorkspace";

const POLL_MS = 15_000;
const SELECTED_BOT_STORAGE_KEY = "trading_dashboard.execution.selected_log_dir.v1";

function asRecord(value: unknown): JsonRecord {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? (value as JsonRecord) : {};
}

function asString(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return "";
}

function formatTime(value: unknown): string {
  const raw = asString(value);
  if (!raw) {
    return "n/a";
  }
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) {
    return raw;
  }
  return parsed.toLocaleString();
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "n/a";
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? value.toLocaleString(undefined, { maximumFractionDigits: 6 }) : "n/a";
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function numberValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function stateClass(state: unknown): string {
  const value = asString(state).toLowerCase();
  if (value === "running") {
    return "status-ok";
  }
  if (value === "stale") {
    return "status-warn";
  }
  return "status-muted";
}

function signalClass(value: unknown): string {
  const numeric = numberValue(value);
  if (numeric === null || numeric === 0) {
    return "signal-flat";
  }
  return numeric > 0 ? "signal-long" : "signal-short";
}

function objectEntries(record: JsonRecord): Array<[string, unknown]> {
  return Object.entries(record).filter(([, value]) => value !== undefined);
}

function ValueTable({ record, emptyLabel = "No records" }: { record: JsonRecord; emptyLabel?: string }) {
  const entries = objectEntries(record);
  if (entries.length === 0) {
    return <p className="empty-copy">{emptyLabel}</p>;
  }
  return (
    <div className="execution-kv-table">
      {entries.map(([key, value]) => (
        <div key={key} className="execution-kv-row">
          <span>{key}</span>
          <strong title={formatValue(value)}>{formatValue(value)}</strong>
        </div>
      ))}
    </div>
  );
}

function AssetGrid({
  assets,
  selectedAsset,
  onSelect
}: {
  assets: ExecutionAssetSummary[];
  selectedAsset: string;
  onSelect: (asset: string) => void;
}) {
  if (assets.length === 0) {
    return <p className="empty-copy">No execution symbols found</p>;
  }
  return (
    <div className="execution-table-shell">
      <table className="execution-table">
        <thead>
          <tr>
            <th>Asset</th>
            <th>MT5</th>
            <th>Bar</th>
            <th>Close</th>
            <th>Spread</th>
            <th>Signal</th>
            <th>Order</th>
          </tr>
        </thead>
        <tbody>
          {assets.map((asset) => (
            <tr key={asset.asset} className={asset.asset === selectedAsset ? "selected-row" : ""}>
              <td>
                <button className="link-button" type="button" onClick={() => onSelect(asset.asset)}>
                  {asset.asset}
                </button>
              </td>
              <td>{asset.mt5_symbol || "n/a"}</td>
              <td>{formatTime(asset.bar_time)}</td>
              <td>{formatValue(asset.close)}</td>
              <td>{formatValue(asset.spread)}</td>
              <td>
                <span className={`signal-pill ${signalClass(asset.signal_side)}`}>{formatValue(asset.signal_side)}</span>
              </td>
              <td>
                <span>{asset.order_status || asset.order_action || "n/a"}</span>
                {asset.order_reason ? <small>{asset.order_reason}</small> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EventsList({ records }: { records: JsonRecord[] }) {
  if (records.length === 0) {
    return <p className="empty-copy">No order or error events</p>;
  }
  return (
    <div className="execution-event-list">
      {records.slice(0, 30).map((event, index) => {
        const stream = asString(event.stream) || "event";
        const reason = asString(event.reason) || asString(event.error) || asString(event.status);
        return (
          <div key={`${stream}-${index}`} className="execution-event-row">
            <div>
              <strong>{stream}</strong>
              <span>{asString(event.asset) || asString(event.mt5_symbol) || "system"}</span>
            </div>
            <p>{reason || "recorded"}</p>
            <time>{formatTime(event.logged_at || event.bar_time)}</time>
          </div>
        );
      })}
    </div>
  );
}

function BotSourceSelector({
  options,
  selectedLogDir,
  statusLogDir,
  onSelect
}: {
  options: ExecutionBotOption[];
  selectedLogDir: string;
  statusLogDir?: string;
  onSelect: (logDir: string) => void;
}) {
  const selectedOption = options.find((option) => option.log_dir === selectedLogDir);
  return (
    <section className="execution-control-strip">
      <label className="execution-bot-select field">
        <span>Bot source</span>
        <select value={selectedLogDir} onChange={(event) => onSelect(event.target.value)}>
          {options.length === 0 ? <option value="">logs/mt5_demo</option> : null}
          {options.map((option) => (
            <option key={option.id} value={option.log_dir}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <div className="execution-bot-meta">
        <span>{selectedOption?.log_dir || statusLogDir || "logs/mt5_demo"}</span>
        <small>
          mode {selectedOption?.mode || "n/a"} · state {selectedOption?.state || "n/a"} · heartbeat{" "}
          {formatTime(selectedOption?.last_heartbeat_at)}
        </small>
      </div>
    </section>
  );
}

export function ExecutionMonitor() {
  const [botOptions, setBotOptions] = useState<ExecutionBotOption[]>([]);
  const [selectedLogDir, setSelectedLogDir] = useState(() => {
    try {
      return window.localStorage.getItem(SELECTED_BOT_STORAGE_KEY) || "";
    } catch {
      return "";
    }
  });
  const [status, setStatus] = useState<ExecutionStatus | null>(null);
  const [events, setEvents] = useState<JsonRecord[]>([]);
  const [decisions, setDecisions] = useState<JsonRecord[]>([]);
  const [featureSnapshot, setFeatureSnapshot] = useState<ExecutionFeatureSnapshot | null>(null);
  const [selectedAsset, setSelectedAsset] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      setLoading(true);
      api.executionBots()
        .then((botPayload) => {
          if (cancelled) {
            return;
          }
          const options = botPayload.options;
          setBotOptions(options);
          const nextLogDir =
            selectedLogDir && options.some((option) => option.log_dir === selectedLogDir)
              ? selectedLogDir
              : options[0]?.log_dir || selectedLogDir;
          if (nextLogDir && nextLogDir !== selectedLogDir) {
            setSelectedLogDir(nextLogDir);
            try {
              window.localStorage.setItem(SELECTED_BOT_STORAGE_KEY, nextLogDir);
            } catch {
              // localStorage can be unavailable in restricted browser contexts.
            }
          }
          return Promise.all([
            api.executionStatus({ log_dir: nextLogDir }),
            api.executionEvents({ log_dir: nextLogDir, limit: 100 })
          ]);
        })
        .then((payloads) => {
          if (cancelled || !payloads) {
            return;
          }
          const [statusPayload, eventPayload] = payloads;
          setStatus(statusPayload);
          setEvents(eventPayload.records);
          setError(null);
          setSelectedAsset((currentAsset) => {
            if (
              currentAsset &&
              statusPayload.latest_by_asset.some((asset) => asset.asset === currentAsset)
            ) {
              return currentAsset;
            }
            return statusPayload.latest_by_asset[0]?.asset || "";
          });
        })
        .catch((nextError: unknown) => {
          if (!cancelled) {
            setError(nextError instanceof Error ? nextError.message : String(nextError));
          }
        })
        .finally(() => {
          if (!cancelled) {
            setLoading(false);
          }
        });
    };
    load();
    const id = window.setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [selectedLogDir]);

  useEffect(() => {
    if (!selectedAsset) {
      setDecisions([]);
      setFeatureSnapshot(null);
      return;
    }
    let cancelled = false;
    Promise.all([
      api.executionDecisions({ log_dir: selectedLogDir, asset: selectedAsset, limit: 80 }),
      api.executionFeatures(selectedAsset, { log_dir: selectedLogDir })
    ])
      .then(([decisionPayload, featurePayload]) => {
        if (!cancelled) {
          setDecisions(decisionPayload.records);
          setFeatureSnapshot(featurePayload);
          setError(null);
        }
      })
      .catch((nextError: unknown) => {
        if (!cancelled) {
          setError(nextError instanceof Error ? nextError.message : String(nextError));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedAsset, selectedLogDir, status?.health?.last_heartbeat_at]);

  const handleBotSelect = (logDir: string) => {
    setSelectedLogDir(logDir);
    setSelectedAsset("");
    setDecisions([]);
    setFeatureSnapshot(null);
    try {
      window.localStorage.setItem(SELECTED_BOT_STORAGE_KEY, logDir);
    } catch {
      // localStorage can be unavailable in restricted browser contexts.
    }
  };

  const health = asRecord(status?.health);
  const account = asRecord(status?.account);
  const latestDecision = decisions[0] ?? null;
  const signal = asRecord(latestDecision?.signal);
  const signalChecks = asRecord(signal.checks);
  const order = asRecord(latestDecision?.order);
  const risk = asRecord(latestDecision?.risk);
  const riskLimits = asRecord(risk.limits);
  const riskState = asRecord(risk.state);
  const tradeParams = asRecord(risk.trade_params);
  const latestValues = asRecord(latestDecision?.latest_values);
  const strategy = asRecord(latestDecision?.strategy);
  const selectedSummary = useMemo(
    () => status?.latest_by_asset.find((asset) => asset.asset === selectedAsset),
    [selectedAsset, status?.latest_by_asset]
  );

  return (
    <main className="execution-monitor">
      {loading ? <div className="loading-banner">Refreshing execution monitor</div> : null}
      {error ? <div className="error-banner">{error}</div> : null}
      <BotSourceSelector
        options={botOptions}
        selectedLogDir={selectedLogDir}
        statusLogDir={status?.log_dir}
        onSelect={handleBotSelect}
      />
      <section className="execution-health-strip">
        <div className={`execution-health-card ${stateClass(health.state)}`}>
          <span>Bot</span>
          <strong>{formatValue(health.state)}</strong>
          <small>{formatTime(health.last_heartbeat_at)}</small>
        </div>
        <div className="execution-health-card">
          <span>Mode</span>
          <strong>{formatValue(health.execution_mode)}</strong>
          <small>pid {formatValue(health.pid)}</small>
        </div>
        <div className="execution-health-card">
          <span>Equity</span>
          <strong>{formatValue(account.equity)}</strong>
          <small>free {formatValue(account.margin_free)}</small>
        </div>
        <div className="execution-health-card">
          <span>Balance</span>
          <strong>{formatValue(account.balance)}</strong>
          <small>margin {formatValue(account.margin)}</small>
        </div>
      </section>

      <div className="execution-layout">
        <section className="execution-section execution-main-section">
          <div className="execution-section-header">
            <h2>Symbols</h2>
            <span>{selectedLogDir || status?.log_dir || "logs/mt5_demo"}</span>
          </div>
          <AssetGrid assets={status?.latest_by_asset ?? []} selectedAsset={selectedAsset} onSelect={setSelectedAsset} />
        </section>

        <section className="execution-section execution-detail-section">
          <div className="execution-section-header">
            <h2>{selectedAsset || "Symbol"} Decision</h2>
            <span>{formatTime(selectedSummary?.logged_at)}</span>
          </div>
          {latestDecision ? (
            <div className="execution-detail-grid">
              <div>
                <h3>Signal Checks</h3>
                <ValueTable record={signalChecks} />
              </div>
              <div>
                <h3>Order</h3>
                <ValueTable record={order} />
              </div>
              <div>
                <h3>Trade Params</h3>
                <ValueTable record={tradeParams} />
              </div>
              <div>
                <h3>Risk State</h3>
                <ValueTable record={riskState} />
              </div>
              <div className="wide-panel">
                <h3>Risk Limits</h3>
                <ValueTable record={riskLimits} />
              </div>
              <div className="wide-panel">
                <h3>Live Market &amp; Features</h3>
                <ExecutionChartWorkspace
                  snapshot={featureSnapshot}
                  emptyLabel="No MT5 feature snapshot yet"
                  sourceLabel="Updated"
                />
              </div>
              <div className="wide-panel">
                <h3>Latest Values</h3>
                <ValueTable record={latestValues} />
              </div>
              <div className="wide-panel">
                <h3>Strategy</h3>
                <ValueTable record={{ signal_kind: strategy.signal_kind, signal_params: strategy.signal_params }} />
              </div>
              <details className="wide-panel execution-raw-json">
                <summary>Raw decision JSON</summary>
                <pre>{JSON.stringify(latestDecision, null, 2)}</pre>
              </details>
            </div>
          ) : (
            <div className="execution-detail-grid">
              <div className="wide-panel">
                <p className="empty-copy">No decision_trace records yet</p>
              </div>
              <div className="wide-panel">
                <h3>Live Market &amp; Features</h3>
                <ExecutionChartWorkspace
                  snapshot={featureSnapshot}
                  emptyLabel="No MT5 feature snapshot yet"
                  sourceLabel="Updated"
                />
              </div>
            </div>
          )}
        </section>

        <aside className="execution-section execution-side-section">
          <div className="execution-section-header">
            <h2>Events</h2>
            <span>{events.length}</span>
          </div>
          <EventsList records={events} />
        </aside>
      </div>
    </main>
  );
}
