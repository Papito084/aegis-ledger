import React from 'react';
import { Shield, Database, RefreshCw, Activity, Layers } from 'lucide-react';
import { SystemHealth } from '../types';

interface NavbarProps {
  health: SystemHealth | null;
  onRefresh: () => void;
  isRefreshing: boolean;
  activeCurrency: string;
}

export const Navbar: React.FC<NavbarProps> = ({
  health,
  onRefresh,
  isRefreshing,
  activeCurrency,
}) => {
  const isHealthy = health?.status === 'ok';

  return (
    <header className="h-16 border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-30">
      {/* Brand Identity */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-sky-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/20">
          <Shield className="w-5 h-5 text-white" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold text-base tracking-tight text-white">AEGIS LEDGER</span>
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-400 border border-sky-500/20">
              v0.1.0-RC
            </span>
          </div>
          <p className="text-xs text-zinc-400 font-mono">Institutional Double-Entry Core</p>
        </div>
      </div>

      {/* Cluster Health & Controls */}
      <div className="flex items-center gap-4">
        {/* Serializable Isolation Tag */}
        <div className="hidden md:flex items-center gap-1.5 px-3 py-1 rounded-lg bg-zinc-900 border border-zinc-800 text-xs text-zinc-300">
          <Layers className="w-3.5 h-3.5 text-indigo-400" />
          <span className="font-mono text-[11px]">SERIALIZABLE (SSI)</span>
        </div>

        {/* PostgreSQL Node */}
        <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-zinc-900 border border-zinc-800 text-xs">
          <Database className="w-3.5 h-3.5 text-zinc-400" />
          <span className="text-zinc-300">PG 16</span>
          <span
            className={`w-2 h-2 rounded-full ${
              health?.database === 'healthy' ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'
            }`}
          />
        </div>

        {/* Redis Cache & Streams Node */}
        <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-zinc-900 border border-zinc-800 text-xs">
          <Activity className="w-3.5 h-3.5 text-zinc-400" />
          <span className="text-zinc-300">Redis 7</span>
          <span
            className={`w-2 h-2 rounded-full ${
              health?.redis === 'healthy' ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'
            }`}
          />
        </div>

        {/* Currency Tag */}
        <div className="px-2.5 py-1 rounded-md bg-zinc-800 text-xs font-mono font-medium text-zinc-200">
          {activeCurrency}
        </div>

        {/* Manual Refresh */}
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="p-2 rounded-lg bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 hover:border-zinc-700 text-zinc-300 transition-all disabled:opacity-50"
          title="Refresh Ledger State"
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-sky-400' : ''}`} />
        </button>
      </div>
    </header>
  );
};
