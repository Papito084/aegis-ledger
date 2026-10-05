from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as aioredis
from app.core.database import get_db_session
from app.core.redis import get_redis

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check(
    db: AsyncSession = Depends(get_db_session),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Health check verifying database connection and redis status.
    """
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    redis_status = "healthy"
    try:
        pong = await redis.ping()
        if not pong:
            redis_status = "unresponsive"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"

    overall = "ok" if db_status == "healthy" and redis_status == "healthy" else "degraded"

    return {
        "status": overall,
        "database": db_status,
        "redis": redis_status,
    }
