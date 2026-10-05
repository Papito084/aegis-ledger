# Aegis Ledger

> **Enterprise-grade Distributed & Immutable Financial Ledger**  
> Double-Entry Bookkeeping | Strict Idempotency | PostgreSQL Serializable Isolation | SHA-256 Audit Hash Chaining | Transactional Outbox Foundation

---

## 1. Architecture & Design Principles

Aegis Ledger is engineered to handle mission-critical financial accounting transactions with mathematical and cryptographic integrity:

1. **Double-Entry Bookkeeping Invariant**:
   - Every transaction consists of at least two legs (`DEBIT` and `CREDIT`).
   - All amounts are positive integers in minor currency units (`BigInteger`, e.g., cents) eliminating floating-point rounding errors.
   - Strictly enforced invariant: $\sum \text{Debits} - \sum \text{Credits} = 0$ (`net_balance == 0`). Any deviation aborts the transaction with an `UnbalancedTransactionError`.

2. **ACID Serializable Concurrency**:
   - PostgreSQL engine configured at the database level with `default_transaction_isolation = serializable` and `wal_level = logical`.
   - Protects against write skew, phantom reads, and non-repeatable reads in distributed concurrent seat posting.

3. **Cryptographic SHA-256 Chaining**:
   - Each posted transaction calculates a deterministic canonical hash linking to the preceding transaction's hash (`current_hash = SHA-256(canonical_payload + prev_hash)`).
   - Any tampering or retrospective alteration breaks the cryptographic verification chain.

4. **Strict Idempotency**:
   - Enforced by unique constraints (`idempotency_key`) and dedicated `IdempotencyRecord` tracking to guarantee at-most-once execution of payments and journal entries under network retries.

---

## 2. Directory Structure

```
aegis-ledger/
├── docker-compose.yml          # Infrastructure: PostgreSQL 16 (Serializable, logical WAL) + Redis 7
├── pyproject.toml              # Build & project metadata, pytest config
├── requirements.txt            # Production and testing dependencies
├── .env                        # Environment configuration
├── .gitignore                  # Git ignore definitions
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application & lifespan management
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # Pydantic Settings
│   │   ├── database.py         # SQLAlchemy 2.0 Async engine (isolation_level="SERIALIZABLE")
│   │   └── redis.py            # Async Redis connection pool & dependency
│   ├── models/
│   │   ├── __init__.py
│   │   ├── account.py          # Account model & Enums (AccountType, AccountStatus)
│   │   ├── transaction.py      # Transaction, Entry, Domain Exceptions & SHA-256 hashing
│   │   └── idempotency.py      # IdempotencyRecord model
│   ├── services/
│   │   ├── __init__.py
│   │   └── ledger_service.py   # LedgerService domain orchestrator
│   └── api/
│       ├── __init__.py
│       └── v1/
│           ├── __init__.py
│           ├── router.py       # API router aggregator
│           └── endpoints/
│               ├── __init__.py
│               └── health.py   # System health checks (Postgres + Redis)
└── tests/
    ├── __init__.py
    ├── conftest.py             # Pytest fixtures, test database lifecycle
    ├── test_double_entry.py    # Unit & Integration tests for double-entry invariants & chaining
    └── test_api.py             # HTTP endpoint integration tests
```

---

## 3. Quickstart & Verification

### 3.1 Start Infrastructure
```bash
docker compose up -d
```

Verify services:
```bash
docker compose ps
```

### 3.2 Run Test Suite
```bash
python -m pytest -v
```
