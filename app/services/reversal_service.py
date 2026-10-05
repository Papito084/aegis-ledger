import uuid
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import TransactionNotFoundError
from app.models.transaction import (
    Transaction,
    EntryDirection,
    TransactionStatus,
)
from app.services.ledger_service import LedgerService


class ReversalService:
    """
    Immutable Accounting Reversal Engine.
    Ensures that errors are rectified exclusively through compensatory journal seats (storno),
    maintaining complete auditability and continuous cryptographic hash chain integrity.
    """

    @classmethod
    async def reverse_transaction(
        cls,
        session: AsyncSession,
        transaction_id: uuid.UUID,
        idempotency_key: str,
        reason: str,
    ) -> Transaction:
        """
        Creates an immutable compensating transaction:
        - Swaps DEBIT <-> CREDIT for every leg of the target transaction.
        - Preserves identical amounts and accounts.
        - Calculates next cryptographic hash in the SHA-256 chain.
        - Atomically enqueues a 'TRANSACTION_REVERSED' OutboxEvent.
        """
        stmt = (
            select(Transaction)
            .where(Transaction.id == transaction_id)
            .options(selectinload(Transaction.entries))
        )
        original_tx = (await session.execute(stmt)).scalar_one_or_none()

        if not original_tx:
            raise TransactionNotFoundError(f"Transaction with ID {transaction_id} not found.")

        if original_tx.status != TransactionStatus.POSTED:
            raise ValueError(f"Only POSTED transactions can be reversed, current status: {original_tx.status}")

        # Invert entry directions to create compensating leg (storno)
        compensating_entries = []
        for entry in original_tx.entries:
            reversed_direction = (
                EntryDirection.CREDIT
                if entry.direction == EntryDirection.DEBIT
                else EntryDirection.DEBIT
            )
            compensating_entries.append({
                "account_id": entry.account_id,
                "direction": reversed_direction,
                "amount": entry.amount,
            })

        description = f"Reversal of [{original_tx.id}]: {reason}"

        # Post compensating transaction atomically with TRANSACTION_REVERSED event
        reversal_tx = await LedgerService.record_transaction(
            session=session,
            idempotency_key=idempotency_key,
            description=description,
            entries_data=compensating_entries,
            event_type="TRANSACTION_REVERSED",
        )

        return reversal_tx
