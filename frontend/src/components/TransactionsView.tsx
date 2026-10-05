import React, { useState } from 'react';
import {
  History,
  RotateCcw,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  Link as LinkIcon,
  Search,
} from 'lucide-react';
import { Transaction, Account } from '../types';

interface TransactionsViewProps {
  transactions: Transaction[];
  accounts: Account[];
  onReverseTransaction: (
    transactionId: string,
    reason: string,
    idempotencyKey: string
  ) => Promise<void>;
}

export const TransactionsView: React.FC<TransactionsViewProps> = ({
  transactions,
  accounts,
  onReverseTransaction,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [copiedHash, setCopiedHash] = useState<string | null>(null);
  const [expandedTxId, setExpandedTxId] = useState<string | null>(null);
  const [reversalTx, setReversalTx] = useState<Transaction | null>(null);
  const [reversalReason, setReversalReason] = useState('');
  const [isReversing, setIsReversing] = useState(false);

  const accountMap = new Map<string, Account>();
  accounts.forEach((a) => accountMap.set(a.id, a));

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(text);
    setTimeout(() => setCopiedHash(null), 1500);
  };

  const handleConfirmReversal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reversalTx || !reversalReason.trim()) return;

    setIsReversing(true);
    try {
      const idempotencyKey = `reversal-${crypto.randomUUID()}`;
      await onReverseTransaction(reversalTx.id, reversalReason.trim(), idempotencyKey);
      setReversalTx(null);
      setReversalReason('');
    } finally {
      setIsReversing(false);
    }
  };

  const filteredTransactions = transactions.filter((tx) => {
    const q = searchTerm.toLowerCase();
    return (
      tx.description.toLowerCase().includes(q) ||
      tx.id.toLowerCase().includes(q) ||
      tx.current_hash.toLowerCase().includes(q) ||
      tx.idempotency_key.toLowerCase().includes(q)
    );
  });

  const formatCents = (cents: number, cur = 'EUR') => {
    return new Intl.NumberFormat('en-IE', {
      style: 'currency',
      currency: cur,
      minimumFractionDigits: 2,
    }).format(cents / 100);
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Header and Search */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Journal Seats</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Immutable financial history sealed with sequential SHA-256 blocks.
          </p>
        </div>

        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 absolute left-3 top-3 text-zinc-500" />
          <input
            type="text"
            placeholder="Search memo, ID, or hash..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3.5 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-xs text-white focus:border-sky-500 focus:outline-none"
          />
        </div>
      </div>

      {/* Transactions Table */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-zinc-900/80 text-zinc-400 border-b border-zinc-800 font-semibold uppercase tracking-wider text-[10px]">
              <tr>
                <th className="py-3 px-4">Status & ID</th>
                <th className="py-3 px-4">Description</th>
                <th className="py-3 px-4">Total Amount</th>
                <th className="py-3 px-4">Cryptographic Hash</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60">
              {filteredTransactions.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-zinc-500">
                    No transactions found matching query.
                  </td>
                </tr>
              ) : (
                filteredTransactions.map((tx) => {
                  const isExpanded = expandedTxId === tx.id;
                  const totalTxAmount =
                    tx.entries
                      .filter((e) => e.direction === 'DEBIT')
                      .reduce((sum, e) => sum + e.amount, 0) || 0;

                  return (
                    <React.Fragment key={tx.id}>
                      <tr className="hover:bg-zinc-800/30 transition-colors group">
                        {/* Status & ID */}
                        <td className="py-3.5 px-4">
                          <div className="flex items-center gap-2">
                            <span
                              className={`text-[9px] font-mono px-2 py-0.5 rounded-full font-bold border ${
                                tx.status === 'POSTED'
                                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                                  : tx.status === 'PENDING'
                                  ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                                  : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                              }`}
                            >
                              {tx.status}
                            </span>
                            <span className="font-mono text-zinc-400 text-[11px]">
                              {tx.id.slice(0, 8)}
                            </span>
                          </div>
                        </td>

                        {/* Description & Memo */}
                        <td className="py-3.5 px-4">
                          <div className="font-medium text-white max-w-xs truncate">
                            {tx.description}
                          </div>
                          <div className="text-[10px] text-zinc-500 font-mono mt-0.5">
                            Key: {tx.idempotency_key}
                          </div>
                        </td>

                        {/* Total Amount */}
                        <td className="py-3.5 px-4 font-mono font-semibold text-white">
                          {formatCents(totalTxAmount)}
                        </td>

                        {/* SHA-256 Current Hash */}
                        <td className="py-3.5 px-4 font-mono">
                          <div className="flex items-center gap-1.5 text-zinc-400 group-hover:text-zinc-200">
                            <LinkIcon className="w-3 h-3 text-sky-400" />
                            <span className="text-[11px]">
                              {tx.current_hash.slice(0, 10)}...{tx.current_hash.slice(-8)}
                            </span>
                            <button
                              onClick={() => handleCopy(tx.current_hash)}
                              className="p-1 hover:text-white transition-colors"
                              title="Copy SHA-256 Hash"
                            >
                              {copiedHash === tx.current_hash ? (
                                <Check className="w-3 h-3 text-emerald-400" />
                              ) : (
                                <Copy className="w-3 h-3 text-zinc-500" />
                              )}
                            </button>
                          </div>
                        </td>

                        {/* Actions */}
                        <td className="py-3.5 px-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => setExpandedTxId(isExpanded ? null : tx.id)}
                              className="p-1.5 rounded-lg bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 transition-colors"
                              title="Inspect Legs"
                            >
                              {isExpanded ? (
                                <ChevronUp className="w-3.5 h-3.5" />
                              ) : (
                                <ChevronDown className="w-3.5 h-3.5" />
                              )}
                            </button>

                            <button
                              onClick={() => setReversalTx(tx)}
                              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/20 font-medium transition-colors"
                              title="Reverse (Storno Compensating Seat)"
                            >
                              <RotateCcw className="w-3 h-3" />
                              <span>Reverse</span>
                            </button>
                          </div>
                        </td>
                      </tr>

                      {/* Expanded Entries Breakdown */}
                      {isExpanded && (
                        <tr className="bg-zinc-950/60">
                          <td colSpan={5} className="p-4 pl-12 border-y border-zinc-800/80">
                            <div className="space-y-2">
                              <div className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
                                Double-Entry Postings (Legs)
                              </div>
                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                {tx.entries.map((entry, idx) => {
                                  const acc = accountMap.get(entry.account_id);
                                  const isDebit = entry.direction === 'DEBIT';
                                  return (
                                    <div
                                      key={idx}
                                      className="p-2.5 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-between"
                                    >
                                      <div>
                                        <div className="flex items-center gap-2">
                                          <span
                                            className={`text-[9px] font-mono px-1.5 py-0.5 rounded font-bold ${
                                              isDebit
                                                ? 'bg-sky-500/20 text-sky-400'
                                                : 'bg-emerald-500/20 text-emerald-400'
                                            }`}
                                          >
                                            {entry.direction}
                                          </span>
                                          <span className="font-medium text-white text-xs">
                                            {acc ? acc.name : entry.account_id.slice(0, 8)}
                                          </span>
                                        </div>
                                        <span className="text-[10px] font-mono text-zinc-500 block mt-0.5">
                                          Acc ID: {entry.account_id}
                                        </span>
                                      </div>
                                      <div className="font-mono font-bold text-white text-sm">
                                        {formatCents(entry.amount)}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>

                              <div className="pt-2 text-[10px] font-mono text-zinc-500 flex items-center gap-2">
                                <span>Previous Block Hash:</span>
                                <span className="text-zinc-400">{tx.prev_hash}</span>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Storno Reversal Modal */}
      {reversalTx && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-rose-400">
                <RotateCcw className="w-5 h-5" />
                <h3 className="font-bold text-lg text-white">Immutable Storno Reversal</h3>
              </div>
              <button
                onClick={() => setReversalTx(null)}
                className="text-zinc-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-zinc-400 leading-relaxed">
              In accordance with financial ledger immutability principles, this action does{' '}
              <strong className="text-white">NOT</strong> delete the original transaction [
              <span className="font-mono text-rose-400">{reversalTx.id.slice(0, 8)}</span>]. Instead, it
              generates a new compensating contra-entry swapping DEBITS and CREDITS and seals the next
              cryptographic hash in the chain.
            </p>

            <form onSubmit={handleConfirmReversal} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">
                  Audit Justification / Reversal Reason
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Inadvertent duplicate invoice disbursement"
                  value={reversalReason}
                  onChange={(e) => setReversalReason(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-800 focus:border-rose-500 focus:outline-none text-sm text-white"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setReversalTx(null)}
                  className="px-4 py-2 rounded-xl text-sm font-medium text-zinc-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isReversing || !reversalReason.trim()}
                  className="px-5 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-sm font-semibold transition-all disabled:opacity-50"
                >
                  {isReversing ? 'Posting Storno...' : 'Confirm Reversal'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
