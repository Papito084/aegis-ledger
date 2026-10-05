import React from 'react';
import {
  Activity,
  Layers,
  Inbox,
  CheckCircle2,
  Cpu,
  BarChart,
  Repeat,
} from 'lucide-react';
import { SystemTelemetry, SystemHealth } from '../types';

interface TelemetryWidgetProps {
  telemetry: SystemTelemetry | null;
  health: SystemHealth | null;
}

export const TelemetryWidget: React.FC<TelemetryWidgetProps> = ({ telemetry, health }) => {
  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            OpenMetrics & Prometheus
          </span>
        </div>
        <h1 className="text-2xl font-bold text-white tracking-tight mt-2">
          System Observability & Telemetry
        </h1>
        <p className="text-sm text-zinc-400 mt-1">
          Real-time cluster telemetry scraped directly from the <code className="text-zinc-200">/metrics</code> exposition endpoint.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Outbox Queue Depth */}
        <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800 space-y-2">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-medium uppercase">
            <span>Outbox Queue Depth</span>
            <Inbox className="w-4 h-4 text-sky-400" />
          </div>
          <div className="text-3xl font-bold font-mono text-white">
            {telemetry?.outboxQueueDepth ?? 0}
          </div>
          <p className="text-xs text-zinc-500 font-mono">
            {telemetry?.outboxQueueDepth === 0
              ? 'All events published to Redis Streams'
              : 'Events awaiting asynchronous relay'}
          </p>
        </div>

        {/* Metric 2: Total Posted Transactions */}
        <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800 space-y-2">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-medium uppercase">
            <span>Sealed Transactions</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-3xl font-bold font-mono text-emerald-400">
            {telemetry?.totalTransactionsPosted ?? 0}
          </div>
          <p className="text-xs text-zinc-500 font-mono">
            ledger_transactions_total(status=POSTED)
          </p>
        </div>

        {/* Metric 3: Idempotency Hits */}
        <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800 space-y-2">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-medium uppercase">
            <span>Idempotency Deduplications</span>
            <Repeat className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-3xl font-bold font-mono text-indigo-400">
            {telemetry?.idempotencyHits ?? 0}
          </div>
          <p className="text-xs text-zinc-500 font-mono">
            Redis cached responses without DB hit
          </p>
        </div>

        {/* Metric 4: SSI Collision Retries */}
        <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800 space-y-2">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-medium uppercase">
            <span>Serializable Retries</span>
            <Cpu className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-3xl font-bold font-mono text-amber-400">
            {telemetry?.serializationRetries ?? 0}
          </div>
          <p className="text-xs text-zinc-500 font-mono">
            SQLSTATE 40001 handled with full jitter
          </p>
        </div>
      </div>

      {/* Cluster Node Status Cards */}
      <div className="p-6 rounded-2xl bg-zinc-900/40 border border-zinc-800 space-y-4">
        <h3 className="font-semibold text-white text-base">Infrastructure Topography</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono">
          <div className="p-4 rounded-xl bg-zinc-950/70 border border-zinc-800 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-white">PostgreSQL 16 Alpine</span>
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            </div>
            <div className="text-zinc-400 text-[11px] space-y-1">
              <div>Isolation: SERIALIZABLE (SSI)</div>
              <div>WAL: Logical (Outbox ready)</div>
              <div>Health: {health?.database || 'healthy'}</div>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-zinc-950/70 border border-zinc-800 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-white">Redis 7 Alpine</span>
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            </div>
            <div className="text-zinc-400 text-[11px] space-y-1">
              <div>Mode: AOF (everysec)</div>
              <div>Streams: stream:ledger_events</div>
              <div>Health: {health?.redis || 'healthy'}</div>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-zinc-950/70 border border-zinc-800 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-white">Outbox Worker</span>
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            </div>
            <div className="text-zinc-400 text-[11px] space-y-1">
              <div>Concurrency: SKIP LOCKED</div>
              <div>Batch Size: 50 events</div>
              <div>Poll Interval: 0.5s</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
