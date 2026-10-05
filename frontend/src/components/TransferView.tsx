import React, { useState } from 'react';
import {
  ArrowLeftRight,
  ArrowRight,
  Key,
  RefreshCw,
  Sparkles,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import { Account, EntryDirection } from '../types';

interface TransferViewProps {
  accounts: Account[];
  onPostTransaction: (
    idempotencyKey: string,
    description: string,
    entries: { account_id: string; direction: EntryDirection; amount: number }[]
  ) => Promise<void>;
}

export const TransferView: React.FC<TransferViewProps> = ({
  accounts,
  onPostTransaction,
}) => {
  const [debitAccountId, setDebitAccountId] = useState(accounts[0]?.id || '');
  const [creditAccountId, setCreditAccountId] = useState(accounts[1]?.id || '');
  const [amountStr, setAmountStr] = useState('100.00');
  const [description, setDescription] = useState('Operating liquidity rebalancing');
  const [idempotencyKey, setIdempotencyKey] = useState<string>(() => crypto.randomUUID());

  const [isSubmitting, setIsSubmitting] = useState(false);

  const generateNewKey = () => {
    setIdempotencyKey(crypto.randomUUID());
  };

  const debitAccount = accounts.find((a) => a.id === debitAccountId);
  const creditAccount = accounts.find((a) => a.id === creditAccountId);

  const amountCents = Math.round(parseFloat(amountStr || '0') * 100);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!debitAccountId || !creditAccountId) return;
    if (debitAccountId === creditAccountId) {
      alert('Debit and Credit accounts must be distinct in a double-entry seat.');
      return;
    }
    if (amountCents <= 0) {
      alert('Transaction amount must be greater than zero.');
      return;
    }

    setIsSubmitting(true);
    try {
      await onPostTransaction(idempotencyKey, description, [
        {
          account_id: debitAccountId,
          direction: 'DEBIT',
          amount: amountCents,
        },
        {
          account_id: creditAccountId,
          direction: 'CREDIT',
          amount: amountCents,
        },
      ]);
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatCents = (cents: number) => {
    return new Intl.NumberFormat('en-IE', {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 2,
    }).format(cents / 100);
  };

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
            Double-Entry Seat
          </span>
        </div>
        <h1 className="text-2xl font-bold text-white tracking-tight mt-2">
          New Balanced Journal Transaction
        </h1>
        <p className="text-sm text-zinc-400 mt-1">
          Atomic double-entry transaction sealed into the continuous cryptographic SHA-256 chain.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Interactive Double-Entry Visualizer Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 relative">
          {/* DEBIT LEG CARD */}
          <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800 space-y-3 relative">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold font-mono px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
                DEBIT LEG (+)
              </span>
              <span className="text-[11px] text-zinc-500 font-mono">Normal Balance</span>
            </div>

            <label className="block text-xs font-semibold text-zinc-300">
              Account to DEBIT
            </label>
            <select
              value={debitAccountId}
              onChange={(e) => setDebitAccountId(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-800 text-sm text-white font-medium focus:border-sky-500 focus:outline-none"
            >
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} ({a.type}) - Bal: {formatCents(a.balance)}
                </option>
              ))}
            </select>

            {debitAccount && (
              <div className="p-3 rounded-xl bg-zinc-950/80 border border-zinc-800/80 text-xs space-y-1 font-mono">
                <div className="flex justify-between text-zinc-400">
                  <span>Current Balance:</span>
                  <span className="text-white">{formatCents(debitAccount.balance)}</span>
                </div>
                <div className="flex justify-between text-sky-400 font-semibold">
                  <span>After Debit (+{amountStr || '0'}):</span>
                  <span>
                    {formatCents(
                      debitAccount.type === 'ASSET' || debitAccount.type === 'EXPENSE'
                        ? debitAccount.balance + amountCents
                        : debitAccount.balance - amountCents
                    )}
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* CREDIT LEG CARD */}
          <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800 space-y-3 relative">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                CREDIT LEG (-)
              </span>
              <span className="text-[11px] text-zinc-500 font-mono">Normal Balance</span>
            </div>

            <label className="block text-xs font-semibold text-zinc-300">
              Account to CREDIT
            </label>
            <select
              value={creditAccountId}
              onChange={(e) => setCreditAccountId(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-800 text-sm text-white font-medium focus:border-emerald-500 focus:outline-none"
            >
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} ({a.type}) - Bal: {formatCents(a.balance)}
                </option>
              ))}
            </select>

            {creditAccount && (
              <div className="p-3 rounded-xl bg-zinc-950/80 border border-zinc-800/80 text-xs space-y-1 font-mono">
                <div className="flex justify-between text-zinc-400">
                  <span>Current Balance:</span>
                  <span className="text-white">{formatCents(creditAccount.balance)}</span>
                </div>
                <div className="flex justify-between text-emerald-400 font-semibold">
                  <span>After Credit (-{amountStr || '0'}):</span>
                  <span>
                    {formatCents(
                      creditAccount.type === 'LIABILITY' ||
                        creditAccount.type === 'EQUITY' ||
                        creditAccount.type === 'REVENUE'
                        ? creditAccount.balance + amountCents
                        : creditAccount.balance - amountCents
                    )}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Transfer Parameters (Amount & Description) */}
        <div className="p-6 rounded-2xl bg-zinc-900/40 border border-zinc-800 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-zinc-300 mb-1">
                Monetary Amount (EUR)
              </label>
              <div className="relative">
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  value={amountStr}
                  onChange={(e) => setAmountStr(e.target.value)}
                  className="w-full pl-8 pr-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-800 text-sm text-white font-mono font-bold focus:border-sky-500 focus:outline-none"
                />
                <span className="absolute left-3 top-2.5 text-zinc-500 font-mono text-sm">€</span>
              </div>
              <span className="text-[10px] text-zinc-500 font-mono mt-1 block">
                Stored as integer cents: {amountCents.toLocaleString()}
              </span>
            </div>

            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold text-zinc-300 mb-1">
                Transaction Memo / Description
              </label>
              <input
                type="text"
                required
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="e.g. Vendor settlement Invoice #4091"
                className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-800 text-sm text-white focus:border-sky-500 focus:outline-none"
              />
            </div>
          </div>

          {/* Idempotency Controls */}
          <div className="pt-3 border-t border-zinc-800/80">
            <div className="flex items-center justify-between mb-1.5">
              <label className="flex items-center gap-1.5 text-xs font-semibold text-zinc-300">
                <Key className="w-3.5 h-3.5 text-sky-400" />
                <span>Distributed Idempotency-Key (Redis)</span>
              </label>
              <button
                type="button"
                onClick={generateNewKey}
                className="flex items-center gap-1 text-[11px] text-sky-400 hover:text-sky-300 font-mono"
              >
                <RefreshCw className="w-3 h-3" />
                <span>Regenerate UUID</span>
              </button>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="text"
                required
                value={idempotencyKey}
                onChange={(e) => setIdempotencyKey(e.target.value)}
                className="flex-1 px-3.5 py-2 rounded-xl bg-zinc-950 border border-zinc-800 text-xs font-mono text-zinc-300 focus:border-sky-500 focus:outline-none"
              />
            </div>
            <p className="text-[11px] text-zinc-500 mt-1 leading-relaxed">
              Submitting the exact same Idempotency-Key multiple times simulates network retries and
              returns the cached payload from Redis without re-executing against Postgres.
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center justify-between gap-4 pt-2">
          <div className="flex items-center gap-2 text-xs text-zinc-400 font-mono">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>Zero-Sum Check: Δ = 0 (Balanced)</span>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-sky-600 to-indigo-600 hover:from-sky-500 hover:to-indigo-500 text-white font-semibold text-sm transition-all shadow-lg shadow-sky-600/20 disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Executing ACID Posting...</span>
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4" />
                  <span>Post & Seal Transaction</span>
                </>
              )}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
};
