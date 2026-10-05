export type AccountType = 'ASSET' | 'LIABILITY' | 'EQUITY' | 'REVENUE' | 'EXPENSE';
export type AccountStatus = 'ACTIVE' | 'FROZEN' | 'CLOSED';
export type EntryDirection = 'DEBIT' | 'CREDIT';

export interface Account {
  id: string;
  name: string;
  currency: string;
  type: AccountType;
  status: AccountStatus;
  allow_overdraft: boolean;
  created_at: string;
  balance: number;
  total_debit: number;
  total_credit: number;
}

export interface Entry {
  id?: string;
  account_id: string;
  direction: EntryDirection;
  amount: number;
  created_at?: string;
}

export interface Transaction {
  id: string;
  idempotency_key: string;
  description: string;
  status: 'PENDING' | 'POSTED' | 'REJECTED';
  posted_at?: string;
  prev_hash: string;
  current_hash: string;
  entries: Entry[];
}

export interface AuditReport {
  is_valid: boolean;
  total_transactions_verified: number;
  broken_link_at: string | null;
  details: string;
}

export interface SystemHealth {
  status: string;
  database: string;
  redis: string;
}

export interface SystemTelemetry {
  outboxQueueDepth: number;
  totalTransactionsPosted: number;
  serializationRetries: number;
  idempotencyHits: number;
}
