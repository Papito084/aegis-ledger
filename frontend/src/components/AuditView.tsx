import React, { useState } from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  Play,
  RefreshCw,
  Hash,
  Link as LinkIcon,
  CheckCircle2,
  Lock,
  Layers,
} from 'lucide-react';
import { Transaction, AuditReport } from '../types';

interface AuditViewProps {
  transactions: Transaction[];
  onRunAudit: () => Promise<AuditReport>;
}

export const AuditView: React.FC<AuditViewProps> = ({ transactions, onRunAudit }) => {
  const [isRunning, setIsRunning] = useState(false);
  const [auditReport, setAuditReport] = useState<AuditReport | null>(null);

  const handleVerify = async () => {
    setIsRunning(true);
    try {
      const report = await onRunAudit();
      setAuditReport(report);
    } finally {
      setIsRunning(false);
    }
  };

  // Sort chronological for chain visualization
  const chain = [...transactions].sort((a, b) =>
    (a.posted_at || '').localeCompare(b.posted_at || '')
  );

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Header and Trigger */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              Sovereign Cryptography
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight mt-2">
            Cryptographic Audit Chain Explorer
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Deterministic SHA-256 recursive verification proving absolute historical immutability.
          </p>
        </div>

        <button
          onClick={handleVerify}
          disabled={isRunning}
          className="flex items-center gap-2 px-5 py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-sky-600 hover:from-indigo-500 hover:to-sky-500 text-white font-semibold text-sm transition-all shadow-lg shadow-indigo-600/20 disabled:opacity-50"
        >
          {isRunning ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" />
              <span>Verifying Ledger Blocks...</span>
            </>
          ) : (
            <>
              <Play className="w-4 h-4" />
              <span>Run Audit Verification</span>
            </>
          )}
        </button>
      </div>

      {/* Audit Report Banner (When run) */}
      {auditReport && (
        <div
          className={`p-6 rounded-2xl border backdrop-blur-md transition-all ${
            auditReport.is_valid
              ? 'bg-emerald-950/40 border-emerald-800/80 text-emerald-100'
              : 'bg-rose-950/40 border-rose-800/80 text-rose-100'
          }`}
        >
          <div className="flex items-start gap-4">
            <div
              className={`p-3 rounded-xl ${
                auditReport.is_valid ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
              }`}
            >
              {auditReport.is_valid ? (
                <ShieldCheck className="w-8 h-8" />
              ) : (
                <ShieldAlert className="w-8 h-8" />
              )}
            </div>
            <div className="space-y-1 flex-1">
              <div className="flex items-center gap-3">
                <h3 className="font-bold text-lg text-white">
                  {auditReport.is_valid
                    ? 'Cryptographic Ledger Integrity Verified'
                    : 'Cryptographic Integrity Violation Detected'}
                </h3>
                <span
                  className={`text-xs px-2.5 py-0.5 rounded-full font-mono font-bold ${
                    auditReport.is_valid
                      ? 'bg-emerald-500/20 text-emerald-300'
                      : 'bg-rose-500/20 text-rose-300'
                  }`}
                >
                  {auditReport.is_valid ? 'STATUS: VALID (100% SECURE)' : 'STATUS: TAMPERED'}
                </span>
              </div>
              <p className="text-sm opacity-90">{auditReport.details}</p>

              <div className="pt-3 flex flex-wrap gap-4 text-xs font-mono">
                <div className="px-3 py-1.5 rounded-lg bg-black/40 border border-white/10">
                  <span className="text-zinc-400">Total Blocks Verified: </span>
                  <span className="font-bold text-white">
                    {auditReport.total_transactions_verified}
                  </span>
                </div>
                {auditReport.broken_link_at && (
                  <div className="px-3 py-1.5 rounded-lg bg-rose-900/60 border border-rose-700">
                    <span className="text-rose-300">Fraud Detected at Tx: </span>
                    <span className="font-bold text-white">{auditReport.broken_link_at}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Visual Hash Chain Presentation */}
      <div className="space-y-4">
        <div className="flex items-center justify-between text-xs text-zinc-400 font-mono">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-sky-400" />
            <span>Block Chain Sequence ({chain.length} Blocks Recorded)</span>
          </div>
          <span className="text-[11px] text-zinc-500">Ordered by chronological confirmation</span>
        </div>

        {chain.length === 0 ? (
          <div className="p-12 text-center rounded-2xl bg-zinc-900/30 border border-zinc-800 text-zinc-500">
            No transactions in the ledger yet. Submit a new transfer to seal the first block from Genesis.
          </div>
        ) : (
          <div className="space-y-3 relative before:absolute before:inset-0 before:left-6 before:w-0.5 before:bg-gradient-to-b before:from-sky-500/20 before:via-indigo-500/20 before:to-transparent">
            {chain.map((tx, idx) => (
              <div
                key={tx.id}
                className="relative pl-14 group"
              >
                {/* Node Link Indicator */}
                <div className="absolute left-4 top-5 w-4 h-4 rounded-full bg-zinc-950 border-2 border-sky-500 flex items-center justify-center shadow-md shadow-sky-500/30">
                  <div className="w-1.5 h-1.5 rounded-full bg-sky-400" />
                </div>

                <div className="p-5 rounded-2xl bg-zinc-900/40 border border-zinc-800/80 hover:border-zinc-700 transition-all space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-zinc-800 text-zinc-300">
                        Block #{idx + 1}
                      </span>
                      <span className="font-medium text-white text-sm">{tx.description}</span>
                    </div>
                    <span className="text-[11px] font-mono text-zinc-500">
                      ID: {tx.id.slice(0, 8)}...{tx.id.slice(-6)}
                    </span>
                  </div>

                  {/* Hashes: Previous -> Current */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
                    <div className="p-3 rounded-xl bg-zinc-950/70 border border-zinc-800/60">
                      <span className="text-zinc-500 text-[10px] block mb-1">
                        PREV HASH (H_{idx})
                      </span>
                      <div className="text-zinc-400 break-all text-[11px] leading-relaxed">
                        {tx.prev_hash}
                      </div>
                    </div>

                    <div className="p-3 rounded-xl bg-zinc-950/70 border border-sky-500/20">
                      <span className="text-sky-400 text-[10px] block mb-1 font-semibold">
                        CURRENT HASH (H_{idx + 1} = SHA-256)
                      </span>
                      <div className="text-sky-200 break-all text-[11px] leading-relaxed font-bold">
                        {tx.current_hash}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
