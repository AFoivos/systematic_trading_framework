import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { MarketMakingSnapshot } from "../types/execution";
import type { TradeRecord } from "../types/market";
import { ExecutionChartWorkspace } from "./ExecutionChartWorkspace";

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
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

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "n/a";
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? value.toLocaleString(undefined, { maximumFractionDigits: 6 }) : "n/a";
  }
  return String(value);
}

function asTradeRecord(record: Record<string, unknown>): TradeRecord | null {
  const entryTime = asString(record.entry_time);
  if (!entryTime) {
    return null;
  }
  return {
    entry_time: entryTime,
    exit_time: asString(record.exit_time) || null,
    side: asString(record.side) || "long",
    entry_price: numberValue(record.entry_price),
    exit_price: numberValue(record.exit_price),
    pnl: numberValue(record.pnl),
    return: numberValue(record.return),
    size: numberValue(record.size),
    exit_reason: asString(record.exit_reason) || null
  };
}

function objectEntries(record: Record<string, unknown>): Array<[string, unknown]> {
  return Object.entries(record).filter(([, value]) => value !== undefined);
}

function ValueTable({ record, emptyLabel }: { record: Record<string, unknown>; emptyLabel: string }) {
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

export function MarketMakingExperimentPanel() {
  const [snapshot, setSnapshot] = useState<MarketMakingSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .marketMakingSnapshot()
      .then((payload) => {
        if (!cancelled) {
          setSnapshot(payload);
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
  }, []);

  const trades = useMemo(
    () => (snapshot?.trades ?? []).map((item) => asTradeRecord(asRecord(item))).filter(Boolean) as TradeRecord[],
    [snapshot?.trades]
  );
  const summary = asRecord(snapshot?.summary);

  return (
    <section className="execution-section research-experiment-panel">
      <div className="execution-section-header">
        <h2>Market Making Experiment</h2>
        <span>{snapshot?.run_dir || "logs/experiments/market_making"}</span>
      </div>
      {error ? <div className="error-banner">{error}</div> : null}
      <div className="execution-detail-grid">
        <div className="wide-panel">
          <h3>Order Book &amp; Fills</h3>
          <ExecutionChartWorkspace
            snapshot={snapshot}
            trades={trades}
            emptyLabel="No market making report found yet"
            sourceLabel="Last event"
          />
        </div>
        <div>
          <h3>Run Summary</h3>
          <ValueTable record={summary} emptyLabel="No market making summary yet" />
        </div>
        <div>
          <h3>Fills</h3>
          <ValueTable
            record={{
              asset: snapshot?.asset ?? null,
              fills: trades.length,
              total_pnl: summary.total_pnl,
              realized_pnl: summary.realized_pnl,
              unrealized_pnl: summary.unrealized_pnl,
              fees: summary.fees
            }}
            emptyLabel="No fills yet"
          />
        </div>
      </div>
    </section>
  );
}
