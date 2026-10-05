import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.account import Account, AccountType, AccountStatus
from app.models.transaction import (
    Transaction,
    Entry,
    EntryDirection,
    TransactionStatus,
    UnbalancedTransactionError,
    InvalidEntryAmountError,
    InsufficientEntriesError,
)
from app.services.ledger_service import LedgerService


class TestDoubleEntryDomainUnit:
    """Unit tests validating double-entry bookkeeping domain invariants in-memory."""

    def test_unbalanced_transaction_raises_exception(self):
        """
        GIVEN a transaction with unbalanced legs (Debit: 100 EUR, Credit: 80 EUR)
        WHEN validation or sealing is attempted
        THEN UnbalancedTransactionError MUST be raised.
        """
        tx = Transaction(
            idempotency_key="tx-unit-unbalanced-001",
            description="Payment with discrepancy",
            prev_hash="0" * 64,
            current_hash="pending",
        )

        acc1 = uuid.uuid4()
        acc2 = uuid.uuid4()

        # 100.00 EUR (10000 cents) Debit vs 80.00 EUR (8000 cents) Credit
        tx.entries = [
            Entry(account_id=acc1, direction=EntryDirection.DEBIT, amount=10000),
            Entry(account_id=acc2, direction=EntryDirection.CREDIT, amount=8000),
        ]

        assert tx.net_balance != 0
        assert tx.net_balance == 2000

        with pytest.raises(UnbalancedTransactionError) as exc_info:
            tx.validate_invariants()

        assert "Double-entry invariant violated" in str(exc_info.value)
        assert "Difference: 2000" in str(exc_info.value)

    def test_balanced_transaction_calculates_zero_net_balance_and_seals_hash(self):
        """
        GIVEN a transaction with balanced legs (Debit: 100 EUR, Credit: 100 EUR)
        WHEN invariants are validated and transaction is sealed
        THEN net balance MUST be 0 and current_hash MUST be a valid 64-character SHA-256 string.
        """
        tx = Transaction(
            idempotency_key="tx-unit-balanced-001",
            description="Balanced inter-account settlement",
            prev_hash="0" * 64,
            current_hash="pending",
        )

        acc1 = uuid.uuid4()
        acc2 = uuid.uuid4()

        # 100.00 EUR (10000 cents) on both legs
        tx.entries = [
            Entry(account_id=acc1, direction=EntryDirection.DEBIT, amount=10000),
            Entry(account_id=acc2, direction=EntryDirection.CREDIT, amount=10000),
        ]

        # Invariant checks
        assert tx.total_debit == 10000
        assert tx.total_credit == 10000
        assert tx.net_balance == 0

        # Validate domain invariants without raising exceptions
        tx.validate_invariants()

        # Seal and post with genesis hash
        genesis_hash = "0" * 64
        tx.seal_and_post(prev_hash=genesis_hash)

        assert tx.status == TransactionStatus.POSTED
        assert tx.posted_at is not None
        assert tx.prev_hash == genesis_hash
        assert len(tx.current_hash) == 64
        assert tx.current_hash != genesis_hash

    def test_transaction_with_non_positive_amount_raises_exception(self):
        """Entries with amount <= 0 must be rejected."""
        tx = Transaction(
            idempotency_key="tx-unit-zero-amount",
            description="Zero amount test",
            prev_hash="0" * 64,
            current_hash="pending",
        )
        acc1 = uuid.uuid4()
        acc2 = uuid.uuid4()

        tx.entries = [
            Entry(account_id=acc1, direction=EntryDirection.DEBIT, amount=0),
            Entry(account_id=acc2, direction=EntryDirection.CREDIT, amount=0),
        ]

        with pytest.raises(InvalidEntryAmountError):
            tx.validate_invariants()

    def test_transaction_with_insufficient_entries_raises_exception(self):
        """Single-legged transactions violate double-entry accounting."""
        tx = Transaction(
            idempotency_key="tx-unit-single-leg",
            description="Single leg test",
            prev_hash="0" * 64,
            current_hash="pending",
        )
        tx.entries = [
            Entry(account_id=uuid.uuid4(), direction=EntryDirection.DEBIT, amount=1000),
        ]

        with pytest.raises(InsufficientEntriesError):
            tx.validate_invariants()


class TestDoubleEntryIntegration:
    """Integration tests with database session and LedgerService."""

    async def test_service_rejects_unbalanced_transaction(
        self,
        db_session: AsyncSession,
        sample_accounts: tuple[Account, Account],
    ):
        cash_acc, ap_acc = sample_accounts

        unbalanced_entries = [
            {"account_id": cash_acc.id, "direction": EntryDirection.DEBIT, "amount": 10000},
            {"account_id": ap_acc.id, "direction": EntryDirection.CREDIT, "amount": 8000},
        ]

        with pytest.raises(UnbalancedTransactionError):
            await LedgerService.record_transaction(
                session=db_session,
                idempotency_key="idemp-unbalanced-integration",
                description="Should fail due to mismatch",
                entries_data=unbalanced_entries,
            )

    async def test_service_posts_balanced_transaction_with_hash_chaining(
        self,
        db_session: AsyncSession,
        sample_accounts: tuple[Account, Account],
    ):
        cash_acc, ap_acc = sample_accounts

        # First transaction (chained to genesis hash)
        entries_tx1 = [
            {"account_id": cash_acc.id, "direction": EntryDirection.DEBIT, "amount": 10000},
            {"account_id": ap_acc.id, "direction": EntryDirection.CREDIT, "amount": 10000},
        ]

        tx1 = await LedgerService.record_transaction(
            session=db_session,
            idempotency_key="idemp-tx-1",
            description="Initial funding",
            entries_data=entries_tx1,
        )

        assert tx1.status == TransactionStatus.POSTED
        assert tx1.net_balance == 0
        assert tx1.prev_hash == "0" * 64
        assert len(tx1.current_hash) == 64

        # Second transaction (chained to tx1.current_hash)
        entries_tx2 = [
            {"account_id": ap_acc.id, "direction": EntryDirection.DEBIT, "amount": 5000},
            {"account_id": cash_acc.id, "direction": EntryDirection.CREDIT, "amount": 5000},
        ]

        tx2 = await LedgerService.record_transaction(
            session=db_session,
            idempotency_key="idemp-tx-2",
            description="Partial payment",
            entries_data=entries_tx2,
        )

        assert tx2.status == TransactionStatus.POSTED
        assert tx2.net_balance == 0
        assert tx2.prev_hash == tx1.current_hash
        assert tx2.current_hash != tx1.current_hash

    async def test_strict_idempotency_returns_same_transaction(
        self,
        db_session: AsyncSession,
        sample_accounts: tuple[Account, Account],
    ):
        cash_acc, ap_acc = sample_accounts
        idempotency_key = "idemp-strictly-unique-key-123"

        entries = [
            {"account_id": cash_acc.id, "direction": EntryDirection.DEBIT, "amount": 15000},
            {"account_id": ap_acc.id, "direction": EntryDirection.CREDIT, "amount": 15000},
        ]

        tx_first = await LedgerService.record_transaction(
            session=db_session,
            idempotency_key=idempotency_key,
            description="First attempt",
            entries_data=entries,
        )

        tx_second = await LedgerService.record_transaction(
            session=db_session,
            idempotency_key=idempotency_key,
            description="Duplicate retry",
            entries_data=entries,
        )

        assert tx_first.id == tx_second.id
        assert tx_first.current_hash == tx_second.current_hash
