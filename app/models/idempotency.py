import enum
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Text, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class IdempotencyStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class IdempotencyRecord(Base):
    """
    Idempotency record to prevent duplicate financial transaction processing.
    Ensures safe retries by storing the request fingerprint and execution result.
    """
    __tablename__ = "idempotency_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    key: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    request_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    status: Mapped[IdempotencyStatus] = mapped_column(
        SAEnum(IdempotencyStatus, native_enum=False, length=20),
        default=IdempotencyStatus.PENDING,
        nullable=False,
    )
    response_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def is_locked(self) -> bool:
        if not self.locked_until:
            return False
        return datetime.now(timezone.utc) < self.locked_until

    def __repr__(self) -> str:
        return f"<IdempotencyRecord(key='{self.key}', status={self.status}, code={self.response_code})>"
