from collections.abc import AsyncGenerator
import redis.asyncio as aioredis
from app.core.config import settings

redis_pool = aioredis.ConnectionPool.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    max_connections=50,
)


def get_redis_client() -> aioredis.Redis:
    """Return an async Redis client backed by connection pooling."""
    return aioredis.Redis(connection_pool=redis_pool)


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """FastAPI dependency for accessing Redis asynchronously."""
    client = get_redis_client()
    try:
        yield client
    finally:
        await client.aclose()
