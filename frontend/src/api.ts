import {
  Account,
  AccountType,
  Transaction,
  AuditReport,
  SystemHealth,
  SystemTelemetry,
  EntryDirection,
} from './types';

export class ApiError extends Error {
  statusCode: number;
  errorType?: string;
  detail?: string;

  constructor(statusCode: number, message: string, errorType?: string, detail?: string) {
    super(message);
    this.statusCode = statusCode;
    this.errorType = errorType;
    this.detail = detail;
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = 'Unknown server error';
    let errorType = 'Error';
    try {
      const data = await res.json();
      errorDetail = data.detail || data.message || JSON.stringify(data);
      errorType = data.error_type || res.statusText;
    } catch {
      errorDetail = await res.text();
    }
    throw new ApiError(res.status, errorDetail, errorType, errorDetail);
  }
  return res.json();
}

export const api = {
  async getAccounts(): Promise<Account[]> {
    const res = await fetch('/api/v1/accounts');
    return handleResponse<Account[]>(res);
  },

  async createAccount(data: {
    name: string;
    currency: string;
    type: AccountType;
    allow_overdraft: boolean;
  }): Promise<Account> {
    const res = await fetch('/api/v1/accounts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return handleResponse<Account>(res);
  },

  async getTransactions(limit = 50): Promise<Transaction[]> {
    const res = await fetch(`/api/v1/transactions?limit=${limit}`);
    return handleResponse<Transaction[]>(res);
  },

  async createTransaction(
    idempotencyKey: string,
    description: string,
    entries: { account_id: string; direction: EntryDirection; amount: number }[]
  ): Promise<Transaction> {
    const res = await fetch('/api/v1/transactions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify({ description, entries }),
    });
    return handleResponse<Transaction>(res);
  },

  async reverseTransaction(
    transactionId: string,
    reason: string,
    idempotencyKey: string
  ): Promise<Transaction> {
    const res = await fetch(`/api/v1/transactions/${transactionId}/reversal`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify({ reason }),
    });
    return handleResponse<Transaction>(res);
  },

  async verifyAudit(): Promise<AuditReport> {
    const res = await fetch('/api/v1/ledger/audit');
    return handleResponse<AuditReport>(res);
  },

  async getHealth(): Promise<SystemHealth> {
    const res = await fetch('/api/v1/health');
    return handleResponse<SystemHealth>(res);
  },

  async getTelemetry(): Promise<SystemTelemetry> {
    const res = await fetch('/metrics');
    if (!res.ok) {
      return {
        outboxQueueDepth: 0,
        totalTransactionsPosted: 0,
        serializationRetries: 0,
        idempotencyHits: 0,
      };
    }
    const text = await res.text();

    const parseMetric = (regex: RegExp): number => {
      const match = text.match(regex);
      return match ? parseFloat(match[1]) : 0;
    };

    return {
      outboxQueueDepth: parseMetric(/ledger_outbox_queue_depth\s+([0-9.]+)/),
      totalTransactionsPosted: parseMetric(/ledger_transactions_total\{status="POSTED",type="REGULAR"\}\s+([0-9.]+)/),
      serializationRetries: parseMetric(/ledger_serialization_retries_total\s+([0-9.]+)/),
      idempotencyHits: parseMetric(/ledger_idempotency_hits_total\s+([0-9.]+)/),
    };
  },
};
