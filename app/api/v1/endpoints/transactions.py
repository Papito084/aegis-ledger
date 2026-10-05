import uuid
from fastapi import APIRouter, Depends, Header, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
from app.core.database import get_db_session
from app.core.redis import get_redis
from app.core.idempotency import DistributedIdempotencyManager
from app.core.resilience import with_serialization_retry
from app.services.ledger_service import LedgerService
from app.services.reversal_service import ReversalService
from app.schemas.transaction import (
    TransactionCreate,
    TransactionResponse,
    TransactionReversalRequest,
)

router = APIRouter()


@router.post(
    "",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record and seal a double-entry financial transaction",
)
async def create_transaction(
    tx_in: TransactionCreate,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        description="Unique UUID or token preventing duplicate execution under retries",
    ),
    db: AsyncSession = Depends(get_db_session),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """
    Records a double-entry transaction:
    - Validates idempotency against Redis (returns cached result if completed, 409 if in progress).
    - Enforces strict debit/credit balance, currency parity, and available funds.
    - Employs serializable collision retries with exponential backoff and jitter.
    - Computes deterministic SHA-256 chain hash and seals the seat.
    """
    idempotency_mgr = DistributedIdempotencyManager(redis_client)

    async with idempotency_mgr.transaction_scope(idempotency_key) as idemp:
        if idemp.is_cached:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=idemp.payload,
            )

        @with_serialization_retry(max_retries=5, base_delay=0.05, max_delay=0.5)
        async def _execute_posting():
            return await LedgerService.record_transaction(
                session=db,
                idempotency_key=idempotency_key,
                description=tx_in.description,
                entries_data=[e.model_dump() for e in tx_in.entries],
            )

        tx = await _execute_posting()
        payload = TransactionResponse.model_validate(tx).model_dump(mode="json")
        await idemp.handle.complete(payload)

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=payload,
        )


@router.post(
    "/{transaction_id}/reversal",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an immutable compensating accounting reversal (storno)",
)
async def reverse_transaction(
    transaction_id: uuid.UUID,
    reversal_in: TransactionReversalRequest,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        description="Unique UUID or token preventing duplicate execution under retries",
    ),
    db: AsyncSession = Depends(get_db_session),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """
    Creates an immutable compensating transaction:
    - Reverses every leg (DEBIT -> CREDIT, CREDIT -> DEBIT).
    - Preserves previous transaction rows untouched.
    - Emits a 'TRANSACTION_REVERSED' outbox event.
    """
    idempotency_mgr = DistributedIdempotencyManager(redis_client)

    async with idempotency_mgr.transaction_scope(idempotency_key) as idemp:
        if idemp.is_cached:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=idemp.payload,
            )

        @with_serialization_retry(max_retries=5, base_delay=0.05, max_delay=0.5)
        async def _execute_reversal():
            return await ReversalService.reverse_transaction(
                session=db,
                transaction_id=transaction_id,
                idempotency_key=idempotency_key,
                reason=reversal_in.reason,
            )

        tx = await _execute_reversal()
        payload = TransactionResponse.model_validate(tx).model_dump(mode="json")
        await idemp.handle.complete(payload)

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=payload,
        )

