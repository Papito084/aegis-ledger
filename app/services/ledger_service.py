import uuid
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.account import Account, AccountType, AccountStatus
from app.models.transaction import (
    Transaction,
    Entry,
    EntryDirection,
    TransactionStatus,
)
from app.core.exceptions import (
    LedgerDomainError,
    AccountNotFoundError,
    InactiveAccountError,
    CurrencyMismatchError,
    InsufficientFundsError,
    UnbalancedTransactionError,
)
from app.models.outbox import OutboxEvent, OutboxStatus
from app.services.account_service import AccountService


class LedgerService:
    """
    Core ledger service orchestrating double-entry journal operations,
    enforcing serializable consistency, idempotency, and cryptographic audit hashing.
    """

    @staticmethod
    async def create_account(
        session: AsyncSession,
        name: str,
        currency: str,
        account_type: AccountType,
        allow_overdraft: bool = False,
    ) -> Account:
        """Creates a new financial account."""
        account = Account(
            name=name,
            currency=currency.upper(),
            type=account_type,
            status=AccountStatus.ACTIVE,
            allow_overdraft=allow_overdraft,
        )
        session.add(account)
        await session.flush()
        return account

    @staticmethod
    async def get_account(
        session: AsyncSession,
        account_id: uuid.UUID,
    ) -> Optional[Account]:
        """Fetch account by UUID."""
        stmt = select(Account).where(Account.id == account_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_latest_transaction_hash(session: AsyncSession) -> str:
        """
        Retrieves the cryptographic hash of the most recently posted transaction.
        If no transactions exist, returns the predefined GENESIS_HASH.
        """
        stmt = (
            select(Transaction.current_hash)
            .where(Transaction.status == TransactionStatus.POSTED)
            .order_by(Transaction.created_at.desc(), Transaction.id.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        latest_hash = result.scalar_one_or_none()
        return latest_hash if latest_hash is not None else settings.GENESIS_HASH

    @classmethod
    async def record_transaction(
        cls,
        session: AsyncSession,
        idempotency_key: str,
        description: str,
        entries_data: list[dict],
        event_type: str = "TRANSACTION_POSTED",
    ) -> Transaction:
        """
        Executes a double-entry transaction posting with strict audit chain and idempotency.

        entries_data format:
        [
            {"account_id": uuid.UUID, "direction": EntryDirection, "amount": int},
            ...
        ]
        """
        # 1. Linear cryptographic audit chain sequencing
        # Acquire transaction-level advisory lock immediately to serialize audit ledger execution
        # and prevent concurrent branch forks and SSI pivot collisions
        await session.execute(select(func.pg_advisory_xact_lock(424242)))

        # 2. Idempotency Check
        stmt = select(Transaction).where(Transaction.idempotency_key == idempotency_key)
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            return existing

        # 2. Account verification and currency validation
        account_ids = {item["account_id"] for item in entries_data}
        accounts_stmt = select(Account).where(Account.id.in_(account_ids))
        accounts_res = (await session.execute(accounts_stmt)).scalars().all()
        account_map = {acc.id: acc for acc in accounts_res}

        if len(account_map) != len(account_ids):
            missing_ids = account_ids - set(account_map.keys())
            raise AccountNotFoundError(f"Accounts not found: {missing_ids}")

        currencies = {acc.currency for acc in account_map.values()}
        if len(currencies) > 1:
            raise CurrencyMismatchError(
                f"Multi-currency transactions in single seat not permitted: {currencies}"
            )

        for acc in account_map.values():
            if not acc.is_operational():
                raise InactiveAccountError(
                    f"Account {acc.id} ({acc.name}) is {acc.status}, transactions forbidden."
                )

        # 3. Instantiate Transaction & Entries
        tx = Transaction(
            id=uuid.uuid4(),
            idempotency_key=idempotency_key,
            description=description,
            status=TransactionStatus.PENDING,
            prev_hash=settings.GENESIS_HASH,
            current_hash="pending",
        )


        for item in entries_data:
            direction = (
                item["direction"]
                if isinstance(item["direction"], EntryDirection)
                else EntryDirection(item["direction"])
            )
            entry = Entry(
                account_id=item["account_id"],
                direction=direction,
                amount=int(item["amount"]),
            )
            tx.entries.append(entry)

        # 4. Invariant Validation (Debits == Credits, positive amounts, min 2 legs)
        tx.validate_invariants()

        # 5. Overdraft / Sufficient Funds Validation
        await AccountService.validate_sufficient_funds_for_entries(
            session=session,
            account_map=account_map,
            entries=tx.entries,
        )

        # 6. Fetch previous hash & Seal cryptographic block
        prev_hash = await LedgerService.get_latest_transaction_hash(session)
        tx.seal_and_post(prev_hash=prev_hash)

        # 7. Persist within the current serializable transaction
        session.add(tx)

        # 8. Transactional Outbox Event (Atomic with transaction persistence)
        outbox_event = OutboxEvent(
            event_type=event_type,
            aggregate_type="TRANSACTION",
            aggregate_id=tx.id,
            payload={
                "transaction_id": str(tx.id),
                "idempotency_key": tx.idempotency_key,
                "description": tx.description,
                "status": tx.status.value,
                "posted_at": tx.posted_at.isoformat() if tx.posted_at else None,
                "prev_hash": tx.prev_hash,
                "current_hash": tx.current_hash,
                "entries": [
                    {
                        "account_id": str(e.account_id),
                        "direction": e.direction.value,
                        "amount": e.amount,
                    }
                    for e in tx.entries
                ],
            },
            status=OutboxStatus.PENDING,
        )
        session.add(outbox_event)

        await session.flush()
        return tx
