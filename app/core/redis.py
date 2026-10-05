from collections.abc import AsyncGenerator
import redis.asyncio as aioredis
from app.core.config import settings


def get_redis_client() -> aioredis.Redis:
    """Return an async Redis client safely bound to the active event loop."""
    return aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
    )


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """FastAPI dependency for accessing Redis asynchronously."""
    client = get_redis_client()
    try:
        yield client
    finally:
        await client.aclose()
