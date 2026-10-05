import React, { useState } from 'react';
import {
  Plus,
  Wallet,
  ArrowUpRight,
  ArrowDownLeft,
  ShieldAlert,
  CheckCircle2,
  Copy,
  Check,
} from 'lucide-react';
import { Account, AccountType } from '../types';

interface AccountsViewProps {
  accounts: Account[];
  onCreateAccount: (data: {
    name: string;
    currency: string;
    type: AccountType;
    allow_overdraft: boolean;
  }) => Promise<void>;
  onSelectForTransfer?: (accountId: string) => void;
}

export const AccountsView: React.FC<AccountsViewProps> = ({
  accounts,
  onCreateAccount,
  onSelectForTransfer,
}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [name, setName] = useState('');
  const [currency, setCurrency] = useState('EUR');
  const [type, setType] = useState<AccountType>('ASSET');
  const [allowOverdraft, setAllowOverdraft] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = (id: string) => {
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setIsSubmitting(true);
    try {
      await onCreateAccount({
        name: name.trim(),
        currency: currency.toUpperCase(),
        type,
        allow_overdraft: allowOverdraft,
      });
      setName('');
      setIsModalOpen(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Grouped stats
  const totalAssets = accounts
    .filter((a) => a.type === 'ASSET')
    .reduce((sum, a) => sum + a.balance, 0);

  const totalLiabilities = accounts
    .filter((a) => a.type === 'LIABILITY')
    .reduce((sum, a) => sum + a.balance, 0);

  const formatCents = (cents: number, cur = 'EUR') => {
    return new Intl.NumberFormat('en-IE', {
      style: 'currency',
      currency: cur,
      minimumFractionDigits: 2,
    }).format(cents / 100);
  };

  const getTypeColor = (t: AccountType) => {
    switch (t) {
      case 'ASSET':
        return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
      case 'LIABILITY':
        return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
      case 'EQUITY':
        return 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20';
      case 'EXPENSE':
        return 'text-rose-400 bg-rose-500/10 border-rose-500/20';
      case 'REVENUE':
        return 'text-teal-400 bg-teal-500/10 border-teal-500/20';
    }
  };

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Header & Create Button */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Financial Accounts</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Institutional general ledger wallets with strict real-time balance calculations.
          </p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-medium text-sm transition-all shadow-lg shadow-sky-600/20"
        >
          <Plus className="w-4 h-4" />
          <span>New Account</span>
        </button>
      </div>

      {/* Aggregate Balance Highlights */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-medium uppercase tracking-wider">
            <span>Total Operational Assets</span>
            <ArrowUpRight className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-3 text-2xl font-bold font-mono text-emerald-400">
            {formatCents(totalAssets)}
          </div>
          <p className="mt-1 text-xs text-zinc-500">Debits positive normal balance</p>
        </div>

        <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-medium uppercase tracking-wider">
            <span>Total Liabilities</span>
            <ArrowDownLeft className="w-4 h-4 text-amber-400" />
          </div>
          <div className="mt-3 text-2xl font-bold font-mono text-amber-400">
            {formatCents(totalLiabilities)}
          </div>
          <p className="mt-1 text-xs text-zinc-500">Credits positive normal balance</p>
        </div>

        <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-medium uppercase tracking-wider">
            <span>Active Ledger Wallets</span>
            <Wallet className="w-4 h-4 text-sky-400" />
          </div>
          <div className="mt-3 text-2xl font-bold font-mono text-zinc-100">
            {accounts.length}
          </div>
          <p className="mt-1 text-xs text-zinc-500">Operational accounts in ledger</p>
        </div>
      </div>

      {/* Account Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {accounts.map((acc) => (
          <div
            key={acc.id}
            className="p-6 rounded-2xl bg-zinc-900/40 border border-zinc-800/80 hover:border-zinc-700 transition-all flex flex-col justify-between group shadow-sm hover:shadow-xl hover:shadow-black/40"
          >
            <div>
              {/* Top row: Type badge & overdraft status */}
              <div className="flex items-center justify-between gap-2">
                <span
                  className={`text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full border ${getTypeColor(
                    acc.type
                  )}`}
                >
                  {acc.type}
                </span>
                <span
                  className={`text-[10px] px-2 py-0.5 rounded-full font-mono border ${
                    acc.allow_overdraft
                      ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                      : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                  }`}
                >
                  {acc.allow_overdraft ? 'OVERDRAFT OK' : 'NO OVERDRAFT'}
                </span>
              </div>

              {/* Account Title */}
              <h3 className="font-semibold text-lg text-white mt-3 group-hover:text-sky-400 transition-colors">
                {acc.name}
              </h3>

              {/* Account UUID copyable */}
              <div className="flex items-center gap-1.5 mt-1 text-xs text-zinc-500 font-mono">
                <span>{acc.id.slice(0, 8)}...{acc.id.slice(-6)}</span>
                <button
                  onClick={() => handleCopy(acc.id)}
                  className="p-1 hover:text-zinc-300 transition-colors"
                  title="Copy UUID"
                >
                  {copiedId === acc.id ? (
                    <Check className="w-3 h-3 text-emerald-400" />
                  ) : (
                    <Copy className="w-3 h-3" />
                  )}
                </button>
              </div>

              {/* Main Balance */}
              <div className="mt-5">
                <span className="text-[11px] font-medium text-zinc-400 uppercase tracking-wider">
                  Available Balance
                </span>
                <div className="text-3xl font-bold font-mono tracking-tight text-white mt-1">
                  {formatCents(acc.balance, acc.currency)}
                </div>
              </div>
            </div>

            {/* Bottom Accumulators */}
            <div className="mt-6 pt-4 border-t border-zinc-800/60 grid grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-zinc-500 text-[10px] block">CUMULATIVE DEBITS</span>
                <span className="font-mono text-zinc-300 font-medium">
                  {formatCents(acc.total_debit, acc.currency)}
                </span>
              </div>
              <div className="text-right">
                <span className="text-zinc-500 text-[10px] block">CUMULATIVE CREDITS</span>
                <span className="font-mono text-zinc-300 font-medium">
                  {formatCents(acc.total_credit, acc.currency)}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* New Account Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-6">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-lg text-white">Create Ledger Account</h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-zinc-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">
                  Account Name
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Treasury Liquidity Reserve"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-800 focus:border-sky-500 focus:outline-none text-sm text-white font-medium"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1">
                    Currency
                  </label>
                  <select
                    value={currency}
                    onChange={(e) => setCurrency(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-800 focus:border-sky-500 focus:outline-none text-sm text-white font-mono"
                  >
                    <option value="EUR">EUR (€)</option>
                    <option value="USD">USD ($)</option>
                    <option value="GBP">GBP (£)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1">
                    Accounting Type
                  </label>
                  <select
                    value={type}
                    onChange={(e) => setType(e.target.value as AccountType)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-800 focus:border-sky-500 focus:outline-none text-sm text-white"
                  >
                    <option value="ASSET">ASSET</option>
                    <option value="LIABILITY">LIABILITY</option>
                    <option value="EQUITY">EQUITY</option>
                    <option value="REVENUE">REVENUE</option>
                    <option value="EXPENSE">EXPENSE</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center gap-3 p-3 rounded-xl bg-zinc-950/60 border border-zinc-800">
                <input
                  type="checkbox"
                  id="overdraft"
                  checked={allowOverdraft}
                  onChange={(e) => setAllowOverdraft(e.target.checked)}
                  className="w-4 h-4 rounded text-sky-600 focus:ring-0 bg-zinc-900 border-zinc-700"
                />
                <label htmlFor="overdraft" className="text-xs text-zinc-300 leading-tight">
                  <span className="font-semibold block text-zinc-200">Allow Overdraft</span>
                  Permit account balance to drop below zero (e.g. for Capital / Equity).
                </label>
              </div>

              <div className="flex justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-sm font-medium text-zinc-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-sm font-semibold transition-all disabled:opacity-50"
                >
                  {isSubmitting ? 'Creating...' : 'Create Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
