from collections.abc import AsyncGenerator
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from app.core.config import settings
from app.core.database import Base
from app.models.account import Account, AccountType, AccountStatus


test_engine = create_async_engine(
    settings.DATABASE_URL,
    isolation_level="SERIALIZABLE",
    poolclass=NullPool,
    echo=False,
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
async def sample_accounts(db_session: AsyncSession) -> tuple[Account, Account]:
    """Fixture providing two active accounts: one Asset and one Liability."""
    cash_account = Account(
        name="Operating Cash Account",
        currency="EUR",
        type=AccountType.ASSET,
        status=AccountStatus.ACTIVE,
    )
    ap_account = Account(
        name="Accounts Payable",
        currency="EUR",
        type=AccountType.LIABILITY,
        status=AccountStatus.ACTIVE,
    )
    db_session.add_all([cash_account, ap_account])
    await db_session.flush()
    return cash_account, ap_account
