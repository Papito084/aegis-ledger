from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1.router import api_router
from app.core.exceptions import (
    LedgerDomainError,
    AccountNotFoundError,
    TransactionNotFoundError,
    ConcurrentTransactionConflictError,
)
from app.services.outbox_relay import OutboxRelay
import app.core.metrics  # noqa: F401 - Initialize Prometheus metrics


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables are created (in development/tests/multi-worker)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        pass


    # Initialize and start OutboxRelay background worker
    outbox_relay = OutboxRelay()
    outbox_relay.start()
    app.state.outbox_relay = outbox_relay

    yield

    # Shutdown: cleanly stop OutboxRelay and dispose engine
    await outbox_relay.stop()
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Distributed immutable financial ledger with double-entry accounting and cryptographic audit trail.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ConcurrentTransactionConflictError)
async def concurrency_conflict_handler(request: Request, exc: ConcurrentTransactionConflictError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "error_type": "ConcurrentTransactionConflictError",
            "detail": str(exc),
        },
    )


@app.exception_handler(AccountNotFoundError)
async def account_not_found_handler(request: Request, exc: AccountNotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error_type": "AccountNotFoundError",
            "detail": str(exc),
        },
    )


@app.exception_handler(TransactionNotFoundError)
async def transaction_not_found_handler(request: Request, exc: TransactionNotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error_type": "TransactionNotFoundError",
            "detail": str(exc),
        },
    )



@app.exception_handler(LedgerDomainError)
async def domain_exception_handler(request: Request, exc: LedgerDomainError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error_type": exc.__class__.__name__,
            "detail": str(exc),
        },
    )


app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}


@app.get("/metrics", tags=["Observability"])
async def metrics():
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

