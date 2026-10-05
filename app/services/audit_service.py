import uuid
from typing import Optional, Any
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.transaction import Transaction, TransactionStatus


class AuditService:
    """
    Cryptographic verification service for Aegis Ledger.
    Traverses the historical journal chain, verifying block-by-block hash continuity
    and proving the mathematical immutability of recorded financial transactions.
    """

    @classmethod
    async def verify_ledger_integrity(cls, session: AsyncSession) -> dict[str, Any]:
        """
        Validates the entire cryptographic chain:
        1. Confirms the genesis transaction points to GENESIS_HASH.
        2. Recalculates deterministic SHA-256 for every transaction and compares to current_hash.
        3. Confirms prev_hash of every transaction matches current_hash of the preceding transaction.
        """
        stmt = (
            select(Transaction)
            .where(Transaction.status == TransactionStatus.POSTED)
            .order_by(Transaction.created_at.asc(), Transaction.id.asc())
            .options(selectinload(Transaction.entries))
        )
        result = await session.execute(stmt)
        transactions = result.scalars().all()

        if not transactions:
            return {
                "is_valid": True,
                "total_transactions_verified": 0,
                "broken_link_at": None,
                "details": "Ledger is empty (valid genesis state).",
            }

        previous_hash = settings.GENESIS_HASH

        for idx, tx in enumerate(transactions):
            # 1. Verify link to previous block
            if tx.prev_hash != previous_hash:
                return {
                    "is_valid": False,
                    "total_transactions_verified": idx,
                    "broken_link_at": tx.id,
                    "details": (
                        f"Cryptographic link broken at transaction {tx.id} (index {idx}): "
                        f"prev_hash '{tx.prev_hash}' does not match expected '{previous_hash}'."
                    ),
                }

            # 2. Re-compute payload SHA-256 hash deterministically
            recomputed_hash = Transaction.compute_sha256_hash(
                prev_hash=tx.prev_hash,
                idempotency_key=tx.idempotency_key,
                description=tx.description,
                entries=tx.entries,
            )

            if tx.current_hash != recomputed_hash:
                return {
                    "is_valid": False,
                    "total_transactions_verified": idx,
                    "broken_link_at": tx.id,
                    "details": (
                        f"Tampered transaction payload detected at {tx.id} (index {idx}): "
                        f"current_hash '{tx.current_hash}' diverges from recomputed '{recomputed_hash}'."
                    ),
                }

            # Advance chain pointer
            previous_hash = tx.current_hash

        return {
            "is_valid": True,
            "total_transactions_verified": len(transactions),
            "broken_link_at": None,
            "details": f"Successfully verified {len(transactions)} cryptographic ledger blocks.",
        }
