import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.account import AccountType, AccountStatus


class AccountCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Name or identifier of the account")
    currency: str = Field(..., min_length=3, max_length=3, description="ISO-4217 Currency Code (e.g. EUR, USD)")
    type: AccountType = Field(..., description="Accounting type: ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE")
    allow_overdraft: bool = Field(default=False, description="Whether the account is allowed to carry a negative balance")


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    currency: str
    type: AccountType
    status: AccountStatus
    allow_overdraft: bool
    created_at: datetime


class AccountBalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_id: uuid.UUID
    name: str
    currency: str
    type: AccountType
    status: AccountStatus
    allow_overdraft: bool
    total_debit: int
    total_credit: int
    balance: int
