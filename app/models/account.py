import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class AccountType(str, enum.Enum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"


class AccountStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    CLOSED = "CLOSED"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    type: Mapped[AccountType] = mapped_column(
        SAEnum(AccountType, native_enum=False, length=20),
        nullable=False,
    )
    status: Mapped[AccountStatus] = mapped_column(
        SAEnum(AccountStatus, native_enum=False, length=20),
        default=AccountStatus.ACTIVE,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    entries: Mapped[list["Entry"]] = relationship(
        "Entry",
        back_populates="account",
        lazy="selectin",
    )

    def is_operational(self) -> bool:
        """Check if account is active and can receive entries."""
        return self.status == AccountStatus.ACTIVE

    def __repr__(self) -> str:
        return f"<Account(id={self.id}, name='{self.name}', currency='{self.currency}', type={self.type}, status={self.status})>"
