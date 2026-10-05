from collections.abc import AsyncGenerator
import pytest_asyncio
import redis.asyncio as aioredis
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from app.core.config import settings
from app.core.database import Base
from app.main import app
from app.models.account import Account, AccountType, AccountStatus


test_engine = create_async_engine(
    settings.DATABASE_URL,
    isolation_level="SERIALIZABLE",
    poolclass=NullPool,
    echo=False,
)

test_session_factory = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def init_database():
    """Create all schema tables before test suite and drop after completion."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated database session per test backed by a rolled back transaction."""
    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        try:
            yield session
        finally:
            await session.close()
            if transaction.is_active:
                await transaction.rollback()


@pytest_asyncio.fixture
def session_factory():
    """Factory yielding dedicated AsyncSessions for concurrent stress tests."""
    return test_session_factory


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator[aioredis.Redis, None]:
    """Provides a cleanly flushed Redis client per test."""
    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await client.flushdb()
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Provides an ASGI test client connected to the FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def sample_accounts(db_session: AsyncSession) -> tuple[Account, Account]:
    """Fixture providing two active accounts: one Asset and one Liability."""
    cash_account = Account(
        name="Operating Cash Account",
        currency="EUR",
        type=AccountType.ASSET,
        status=AccountStatus.ACTIVE,
        allow_overdraft=False,
    )
    ap_account = Account(
        name="Accounts Payable",
        currency="EUR",
        type=AccountType.LIABILITY,
        status=AccountStatus.ACTIVE,
        allow_overdraft=False,
    )
    db_session.add_all([cash_account, ap_account])
    await db_session.flush()
    return cash_account, ap_account
