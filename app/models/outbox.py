import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, Any
from sqlalchemy import String, Integer, DateTime, Text, JSON, Enum as SAEnum, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class OutboxStatus(str, enum.Enum):
    PENDING = "PENDING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class OutboxEvent(Base):
    """
    Transactional Outbox model.
    Guarantees atomic persistence of domain events alongside state modifications,
    enabling reliable, at-least-once distributed asynchronous publishing.
    """
    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    aggregate_type: Mapped[str] = mapped_column(
        String(50),
        default="TRANSACTION",
        nullable=False,
    )
    aggregate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    status: Mapped[OutboxStatus] = mapped_column(
        SAEnum(OutboxStatus, native_enum=False, length=20),
        default=OutboxStatus.PENDING,
        nullable=False,
        index=True,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_outbox_pending_relay", "status", "created_at"),
    )

    def mark_published(self) -> None:
        self.status = OutboxStatus.PUBLISHED
        self.published_at = datetime.now(timezone.utc)
        self.error_message = None

    def mark_failed(self, error: str) -> None:
        self.retry_count += 1
        self.error_message = error
        if self.retry_count >= 5:
            self.status = OutboxStatus.FAILED

    def __repr__(self) -> str:
        return f"<OutboxEvent(id={self.id}, type='{self.event_type}', status={self.status})>"
