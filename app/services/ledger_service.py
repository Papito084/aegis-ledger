import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.account import Account, AccountType, AccountStatus
from app.models.transaction import (
    Transaction,
    Entry,
    EntryDirection,
    TransactionStatus,
    LedgerDomainError,
)


class AccountNotFoundError(LedgerDomainError):
    """Raised when an referenced account does not exist."""
    pass


class InactiveAccountError(LedgerDomainError):
    """Raised when trying to post an entry to a frozen or closed account."""
    pass


class CurrencyMismatchError(LedgerDomainError):
    """Raised when accounts in a single transaction have mismatched currencies."""
    pass


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
    ) -> Account:
        """Creates a new financial account."""
        account = Account(
            name=name,
            currency=currency.upper(),
            type=account_type,
            status=AccountStatus.ACTIVE,
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
    ) -> Transaction:
        """
        Executes a double-entry transaction posting with strict audit chain and idempotency.

        entries_data format:
        [
            {"account_id": uuid.UUID, "direction": EntryDirection, "amount": int},
            ...
        ]
        """
        # 1. Idempotency Check
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
                transaction=tx,
                account_id=item["account_id"],
                direction=direction,
                amount=int(item["amount"]),
            )
            tx.entries.append(entry)

        # 4. Invariant Validation (Debits == Credits, positive amounts, min 2 legs)
        tx.validate_invariants()

        # 5. Fetch previous hash & Seal cryptographic block
        prev_hash = await LedgerService.get_latest_transaction_hash(session)
        tx.seal_and_post(prev_hash=prev_hash)

        # 6. Persist within the current serializable transaction
        session.add(tx)
        await session.flush()
        return tx
