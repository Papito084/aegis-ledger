import React, { useState, useEffect, useCallback } from 'react';
import { Navbar } from './components/Navbar';
import { Sidebar, NavTab } from './components/Sidebar';
import { AccountsView } from './components/AccountsView';
import { TransferView } from './components/TransferView';
import { TransactionsView } from './components/TransactionsView';
import { AuditView } from './components/AuditView';
import { TelemetryWidget } from './components/TelemetryWidget';
import { ToastContainer, ToastMessage } from './components/Toast';
import { api, ApiError } from './api';
import {
  Account,
  AccountType,
  Transaction,
  AuditReport,
  SystemHealth,
  SystemTelemetry,
  EntryDirection,
} from './types';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<NavTab>('accounts');
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [telemetry, setTelemetry] = useState<SystemTelemetry | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = (
    type: 'success' | 'error' | 'info',
    title: string,
    message: string,
    detail?: string
  ) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, type, title, message, detail }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 6000);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const loadData = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const [accs, txs, h, telem] = await Promise.all([
        api.getAccounts().catch(() => []),
        api.getTransactions(50).catch(() => []),
        api.getHealth().catch(() => null),
        api.getTelemetry().catch(() => null),
      ]);
      setAccounts(accs);
      setTransactions(txs);
      if (h) setHealth(h);
      if (telem) setTelemetry(telem);
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 4000);
    return () => clearInterval(interval);
  }, [loadData]);

  const handleCreateAccount = async (data: {
    name: string;
    currency: string;
    type: AccountType;
    allow_overdraft: boolean;
  }) => {
    try {
      const created = await api.createAccount(data);
      addToast(
        'success',
        'Account Created',
        `Account "${created.name}" (${created.type}) has been initialized.`
      );
      await loadData();
    } catch (err: any) {
      if (err instanceof ApiError) {
        addToast('error', 'Failed to Create Account', err.message, err.detail);
      } else {
        addToast('error', 'Error', 'Failed to connect to ledger service');
      }
    }
  };

  const handlePostTransaction = async (
    idempotencyKey: string,
    description: string,
    entries: { account_id: string; direction: EntryDirection; amount: number }[]
  ) => {
    try {
      const tx = await api.createTransaction(idempotencyKey, description, entries);
      addToast(
        'success',
        'Transaction Sealed',
        `Seat "${tx.description}" posted. Hash: ${tx.current_hash.slice(0, 16)}...`
      );
      await loadData();
      setCurrentTab('transactions');
    } catch (err: any) {
      if (err instanceof ApiError) {
        let title = 'Transaction Error';
        if (err.errorType === 'InsufficientFundsError') {
          title = 'Insufficient Funds (Overdraft Disallowed)';
        } else if (err.errorType === 'ConcurrentTransactionConflictError') {
          title = 'Idempotency Conflict (409)';
        } else if (err.errorType === 'UnbalancedTransactionError') {
          title = 'Double-Entry Invariant Violation';
        }
        addToast('error', title, err.message, err.detail);
      } else {
        addToast('error', 'Execution Error', 'An unexpected error occurred while posting.');
      }
    }
  };

  const handleReverseTransaction = async (
    transactionId: string,
    reason: string,
    idempotencyKey: string
  ) => {
    try {
      const tx = await api.reverseTransaction(transactionId, reason, idempotencyKey);
      addToast(
        'success',
        'Storno Reversal Posted',
        `Compensating contra-entry posted. New Hash: ${tx.current_hash.slice(0, 16)}...`
      );
      await loadData();
    } catch (err: any) {
      if (err instanceof ApiError) {
        addToast('error', 'Reversal Failed', err.message, err.detail);
      } else {
        addToast('error', 'Error', 'Failed to process reversal contra-entry');
      }
    }
  };

  const handleRunAudit = async (): Promise<AuditReport> => {
    try {
      const report = await api.verifyAudit();
      if (report.is_valid) {
        addToast(
          'success',
          'Audit Completed',
          `Verified ${report.total_transactions_verified} consecutive cryptographic blocks from Genesis.`
        );
      } else {
        addToast(
          'error',
          'Cryptographic Tampering Detected',
          `Broken link identified at transaction ${report.broken_link_at}`
        );
      }
      return report;
    } catch (err: any) {
      addToast('error', 'Audit Execution Failed', err.message);
      throw err;
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans">
      {/* Top Navigation */}
      <Navbar
        health={health}
        onRefresh={loadData}
        isRefreshing={isRefreshing}
        activeCurrency="EUR"
      />

      {/* Main Body */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar */}
        <Sidebar
          currentTab={currentTab}
          onTabChange={setCurrentTab}
          accountsCount={accounts.length}
          transactionsCount={transactions.length}
        />

        {/* Dynamic Main View */}
        <main className="flex-1 overflow-y-auto">
          {currentTab === 'accounts' && (
            <AccountsView
              accounts={accounts}
              onCreateAccount={handleCreateAccount}
            />
          )}

          {currentTab === 'transfer' && (
            <TransferView
              accounts={accounts}
              onPostTransaction={handlePostTransaction}
            />
          )}

          {currentTab === 'transactions' && (
            <TransactionsView
              transactions={transactions}
              accounts={accounts}
              onReverseTransaction={handleReverseTransaction}
            />
          )}

          {currentTab === 'audit' && (
            <AuditView
              transactions={transactions}
              onRunAudit={handleRunAudit}
            />
          )}

          {currentTab === 'telemetry' && (
            <TelemetryWidget
              telemetry={telemetry}
              health={health}
            />
          )}
        </main>
      </div>

      {/* Enterprise Toast Notifications */}
      <ToastContainer toasts={toasts} onDismiss={removeToast} />
    </div>
  );
};
