import uuid
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db_session
from app.core.exceptions import AccountNotFoundError
from app.services.ledger_service import LedgerService
from app.services.account_service import AccountService
from app.schemas.account import (
    AccountCreate,
    AccountResponse,
    AccountBalanceResponse,
)

router = APIRouter()


@router.post(
    "",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new account",
)
async def create_account(
    account_in: AccountCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """Creates a new financial account (Asset, Liability, Equity, Revenue, Expense)."""
    account = await LedgerService.create_account(
        session=db,
        name=account_in.name,
        currency=account_in.currency,
        account_type=account_in.type,
        allow_overdraft=account_in.allow_overdraft,
    )
    return account


@router.get(
    "/{account_id}/balance",
    response_model=AccountBalanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get real-time calculated balance of an account",
)
async def get_account_balance(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Computes the real-time balance of an account with full breakdown of debits, credits,
    and net balance calculated according to normal account balance principles.
    """
    try:
        summary = await AccountService.get_account_balance(db, account_id)
        return summary
    except AccountNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
