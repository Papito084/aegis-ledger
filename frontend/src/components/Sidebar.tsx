import React from 'react';
import {
  Wallet,
  ArrowLeftRight,
  History,
  ShieldCheck,
  BarChart3,
  Cpu,
} from 'lucide-react';

export type NavTab = 'accounts' | 'transfer' | 'transactions' | 'audit' | 'telemetry';

interface SidebarProps {
  currentTab: NavTab;
  onTabChange: (tab: NavTab) => void;
  accountsCount: number;
  transactionsCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onTabChange,
  accountsCount,
  transactionsCount,
}) => {
  const navItems = [
    {
      id: 'accounts' as NavTab,
      label: 'Wallets & Accounts',
      icon: Wallet,
      count: accountsCount,
      badge: 'Ledger',
    },
    {
      id: 'transfer' as NavTab,
      label: 'New Transfer',
      icon: ArrowLeftRight,
      badge: 'Double-Entry',
    },
    {
      id: 'transactions' as NavTab,
      label: 'Journal Seats',
      icon: History,
      count: transactionsCount,
      badge: 'Immutable',
    },
    {
      id: 'audit' as NavTab,
      label: 'Cryptographic Audit',
      icon: ShieldCheck,
      badge: 'SHA-256',
    },
    {
      id: 'telemetry' as NavTab,
      label: 'System Telemetry',
      icon: BarChart3,
      badge: 'Prometheus',
    },
  ];

  return (
    <aside className="w-64 border-r border-zinc-800 bg-zinc-950 flex flex-col justify-between shrink-0 h-[calc(100vh-4rem)]">
      {/* Navigation Links */}
      <div className="p-4 space-y-1">
        <div className="text-[11px] font-semibold text-zinc-500 uppercase tracking-wider px-3 mb-2">
          Ledger Operations
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
                isActive
                  ? 'bg-sky-500/10 text-sky-400 border border-sky-500/20 shadow-sm shadow-sky-500/5'
                  : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900 border border-transparent'
              }`}
            >
              <div className="flex items-center gap-3">
                <Icon className={`w-4 h-4 ${isActive ? 'text-sky-400' : 'text-zinc-400'}`} />
                <span>{item.label}</span>
              </div>
              <div className="flex items-center gap-1.5">
                {item.count !== undefined && (
                  <span className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300">
                    {item.count}
                  </span>
                )}
                {item.badge && (
                  <span
                    className={`text-[9px] px-1.5 py-0.5 rounded font-mono ${
                      isActive
                        ? 'bg-sky-500/20 text-sky-300'
                        : 'bg-zinc-900 text-zinc-500 border border-zinc-800'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* Engine Status Footer */}
      <div className="p-4 m-4 rounded-xl bg-zinc-900/60 border border-zinc-800 text-xs text-zinc-400">
        <div className="flex items-center gap-2 text-zinc-300 font-semibold mb-1">
          <Cpu className="w-3.5 h-3.5 text-emerald-400" />
          <span>SSI Concurrency Active</span>
        </div>
        <p className="text-[11px] text-zinc-500 leading-relaxed font-mono">
          Advisory write-linearization with full jitter collision retries.
        </p>
      </div>
    </aside>
  );
};
