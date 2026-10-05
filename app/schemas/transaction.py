import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.transaction import EntryDirection, TransactionStatus


class EntryCreate(BaseModel):
    account_id: uuid.UUID = Field(..., description="Target Account UUID")
    direction: EntryDirection = Field(..., description="DEBIT or CREDIT")
    amount: int = Field(..., gt=0, description="Amount in minor units (e.g. cents), strictly > 0")


class TransactionCreate(BaseModel):
    description: str = Field(..., min_length=1, max_length=500, description="Human readable description of the seat")
    entries: list[EntryCreate] = Field(..., min_length=2, description="At least two balanced entries")


class EntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    direction: EntryDirection
    amount: int
    created_at: datetime


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    idempotency_key: str
    description: str
    status: TransactionStatus
    posted_at: Optional[datetime]
    prev_hash: str
    current_hash: str
    created_at: datetime
    entries: list[EntryResponse]


class TransactionReversalRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500, description="Mandatory audit explanation for reversing the transaction")


class AuditReportResponse(BaseModel):
    is_valid: bool
    total_transactions_verified: int
    broken_link_at: Optional[uuid.UUID] = None
    details: str

