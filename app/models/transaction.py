import enum
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    String,
    BigInteger,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Enum as SAEnum,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class LedgerDomainError(Exception):
    """Base exception for all domain invariant violations in Aegis Ledger."""
    pass


class UnbalancedTransactionError(LedgerDomainError):
    """Raised when sum(Debits) != sum(Credits)."""
    pass


class InvalidEntryAmountError(LedgerDomainError):
    """Raised when an entry amount is <= 0 or not an exact integer."""
    pass


class InsufficientEntriesError(LedgerDomainError):
    """Raised when a transaction does not contain at least two entries."""
    pass


class TransactionStatus(str, enum.Enum):
    PENDING = "PENDING"
    POSTED = "POSTED"
    REJECTED = "REJECTED"


class EntryDirection(str, enum.Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class Transaction(Base):
    """
    Transaction represents a balanced double-entry accounting journal seat.
    Maintains a cryptographic SHA-256 chain linking to the preceding transaction.
    """
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[TransactionStatus] = mapped_column(
        SAEnum(TransactionStatus, native_enum=False, length=20),
        default=TransactionStatus.PENDING,
        nullable=False,
        index=True,
    )
    posted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    current_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    entries: Mapped[list["Entry"]] = relationship(
        "Entry",
        back_populates="transaction",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def total_debit(self) -> int:
        return sum(
            entry.amount for entry in self.entries if entry.direction == EntryDirection.DEBIT
        )

    @property
    def total_credit(self) -> int:
        return sum(
            entry.amount for entry in self.entries if entry.direction == EntryDirection.CREDIT
        )

    @property
    def net_balance(self) -> int:
        """Net balance must evaluate to 0 in double-entry bookkeeping (Debits - Credits)."""
        return self.total_debit - self.total_credit

    def validate_invariants(self) -> None:
        """
        Validates double-entry accounting invariants:
        1. Minimum 2 entries.
        2. All entries must have amount > 0.
        3. sum(Debits) == sum(Credits) -> net balance == 0.
        """
        if len(self.entries) < 2:
            raise InsufficientEntriesError(
                f"Transaction requires at least 2 entries, found {len(self.entries)}."
            )

        for entry in self.entries:
            if entry.amount is None or entry.amount <= 0:
                raise InvalidEntryAmountError(
                    f"Entry amount must be a strictly positive integer, got: {entry.amount}."
                )

        if self.total_debit != self.total_credit:
            raise UnbalancedTransactionError(
                f"Double-entry invariant violated: total debits ({self.total_debit}) "
                f"does not match total credits ({self.total_credit}). "
                f"Difference: {self.net_balance}."
            )

    @staticmethod
    def compute_sha256_hash(
        prev_hash: str,
        idempotency_key: str,
        description: str,
        entries: list["Entry"],
    ) -> str:
        """
        Computes the deterministic SHA-256 hash chaining this transaction to the previous one.
        Orders entries canonical by account_id, direction and amount to guarantee reproducibility.
        """
        normalized_entries = sorted(
            [
                {
                    "account_id": str(e.account_id),
                    "direction": e.direction.value if isinstance(e.direction, EntryDirection) else str(e.direction),
                    "amount": int(e.amount),
                }
                for e in entries
            ],
            key=lambda x: (x["account_id"], x["direction"], x["amount"]),
        )

        payload = {
            "prev_hash": prev_hash,
            "idempotency_key": idempotency_key,
            "description": description,
            "entries": normalized_entries,
        }

        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def seal_and_post(self, prev_hash: str) -> None:
        """Validates invariants, computes cryptographic hash and marks transaction as POSTED."""
        self.validate_invariants()
        self.prev_hash = prev_hash
        self.current_hash = self.compute_sha256_hash(
            prev_hash=prev_hash,
            idempotency_key=self.idempotency_key,
            description=self.description,
            entries=self.entries,
        )
        self.status = TransactionStatus.POSTED
        self.posted_at = datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return (
            f"<Transaction(id={self.id}, idempotency_key='{self.idempotency_key}', "
            f"status={self.status}, debits={self.total_debit}, credits={self.total_credit})>"
        )


class Entry(Base):
    """
    Entry represents a single leg (Debit or Credit) of a Transaction assigned to an Account.
    Amount is stored in exact minor units (e.g. cents) as BigInteger to eliminate floating point issues.
    """
    __tablename__ = "entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id"),
        nullable=False,
        index=True,
    )
    direction: Mapped[EntryDirection] = mapped_column(
        SAEnum(EntryDirection, native_enum=False, length=10),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(
        BigInteger,
        CheckConstraint("amount > 0", name="chk_positive_entry_amount"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    transaction: Mapped["Transaction"] = relationship(
        "Transaction",
        back_populates="entries",
    )
    account: Mapped["Account"] = relationship(
        "Account",
        back_populates="entries",
    )

    __table_args__ = (
        Index("ix_entries_account_created", "account_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Entry(id={self.id}, account_id={self.account_id}, "
            f"direction={self.direction}, amount={self.amount})>"
        )
