import uuid
from typing import Optional
from dataclasses import dataclass
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.account import Account, AccountType, AccountStatus
from app.models.transaction import (
    Entry,
    EntryDirection,
)
from app.core.exceptions import (
    AccountNotFoundError,
    InsufficientFundsError,
)


@dataclass(frozen=True)
class AccountBalanceSummary:
    account_id: uuid.UUID
    name: str
    currency: str
    type: AccountType
    status: AccountStatus
    allow_overdraft: bool
    total_debit: int
    total_credit: int
    balance: int


class AccountService:
    """
    Service responsible for account operations, balance calculations,
    and available funds validations following standard accounting principles.
    """

    @staticmethod
    def calculate_balance_by_type(
        account_type: AccountType,
        total_debit: int,
        total_credit: int,
    ) -> int:
        """
        Calculates normal balance based on fundamental accounting equation:
        - ASSET / EXPENSE: Balance = SUM(Debits) - SUM(Credits)
        - LIABILITY / EQUITY / REVENUE: Balance = SUM(Credits) - SUM(Debits)
        """
        if account_type in (AccountType.ASSET, AccountType.EXPENSE):
            return total_debit - total_credit
        else:
            return total_credit - total_debit

    @staticmethod
    def calculate_delta(
        account_type: AccountType,
        direction: EntryDirection,
        amount: int,
    ) -> int:
        """
        Calculates the net impact of an entry on an account balance:
        - For ASSET / EXPENSE: DEBIT increases (+), CREDIT decreases (-)
        - For LIABILITY / EQUITY / REVENUE: CREDIT increases (+), DEBIT decreases (-)
        """
        if account_type in (AccountType.ASSET, AccountType.EXPENSE):
            return amount if direction == EntryDirection.DEBIT else -amount
        else:
            return amount if direction == EntryDirection.CREDIT else -amount

    @classmethod
    async def get_account_balance(
        cls,
        session: AsyncSession,
        account_id: uuid.UUID,
    ) -> AccountBalanceSummary:
        """
        Computes the current real-time balance of an account in minor units (cents)
        by aggregating all posted journal entries.
        """
        # Fetch account metadata
        acc_stmt = select(Account).where(Account.id == account_id)
        account = (await session.execute(acc_stmt)).scalar_one_or_none()
        if not account:
            raise AccountNotFoundError(f"Account with ID {account_id} not found.")

        # Aggregate debits and credits
        debit_case = case(
            (Entry.direction == EntryDirection.DEBIT, Entry.amount),
            else_=0,
        )
        credit_case = case(
            (Entry.direction == EntryDirection.CREDIT, Entry.amount),
            else_=0,
        )

        agg_stmt = (
            select(
                func.coalesce(func.sum(debit_case), 0).label("total_debit"),
                func.coalesce(func.sum(credit_case), 0).label("total_credit"),
            )
            .where(Entry.account_id == account_id)
        )

        row = (await session.execute(agg_stmt)).one()
        total_debit = int(row.total_debit)
        total_credit = int(row.total_credit)

        balance = cls.calculate_balance_by_type(
            account_type=account.type,
            total_debit=total_debit,
            total_credit=total_credit,
        )

        return AccountBalanceSummary(
            account_id=account.id,
            name=account.name,
            currency=account.currency,
            type=account.type,
            status=account.status,
            allow_overdraft=account.allow_overdraft,
            total_debit=total_debit,
            total_credit=total_credit,
            balance=balance,
        )

    @classmethod
    async def validate_sufficient_funds_for_entries(
        cls,
        session: AsyncSession,
        account_map: dict[uuid.UUID, Account],
        entries: list[Entry],
    ) -> None:
        """
        Validates that no account with allow_overdraft=False ends up with a negative balance.
        Under SERIALIZABLE isolation in PostgreSQL, reading the aggregates will register
        SIREAD locks on the participating accounts, preventing concurrent double-spending.
        """
        # 1. Group entry deltas by account_id
        deltas_by_account: dict[uuid.UUID, int] = {}
        for entry in entries:
            acc = account_map[entry.account_id]
            delta = cls.calculate_delta(
                account_type=acc.type,
                direction=entry.direction,
                amount=entry.amount,
            )
            deltas_by_account[entry.account_id] = deltas_by_account.get(entry.account_id, 0) + delta

        # 2. Check accounts that have a net decrease and do not allow overdraft
        for acc_id, net_delta in deltas_by_account.items():
            acc = account_map[acc_id]
            if not acc.allow_overdraft and net_delta < 0:
                summary = await cls.get_account_balance(session, acc_id)
                projected_balance = summary.balance + net_delta
                if projected_balance < 0:
                    raise InsufficientFundsError(
                        f"Account {acc.id} ('{acc.name}') has insufficient funds: "
                        f"current balance = {summary.balance} {acc.currency}, "
                        f"requested deduction = {-net_delta} {acc.currency}, "
                        f"projected balance = {projected_balance} {acc.currency} (Overdraft disallowed)."
                    )
