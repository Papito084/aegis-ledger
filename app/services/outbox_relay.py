import asyncio
import json
import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
import redis.asyncio as aioredis
from app.core.database import async_session_factory
from app.core.redis import get_redis_client
from app.models.outbox import OutboxEvent, OutboxStatus

logger = logging.getLogger("aegis.outbox_relay")


class OutboxRelay:
    """
    Asynchronous Transactional Outbox Relay worker.
    Consumes pending domain events using SELECT ... FOR UPDATE SKIP LOCKED
    and dispatches them to Redis Streams with guaranteed at-least-once delivery.
    """
    STREAM_KEY = "stream:ledger_events"
    BATCH_SIZE = 50
    DEFAULT_POLL_INTERVAL = 0.5

    def __init__(
        self,
        session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
        redis_client: Optional[aioredis.Redis] = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        stream_key: str = STREAM_KEY,
    ):
        self.session_factory = session_factory or async_session_factory
        self._redis = redis_client
        self.poll_interval = poll_interval
        self.stream_key = stream_key
        self._is_running = False
        self._task: Optional[asyncio.Task] = None

    async def get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = get_redis_client()
        return self._redis

    async def process_batch(self) -> int:
        """
        Polls and dispatches a single batch of PENDING outbox events using SKIP LOCKED.
        Returns the number of events published.
        """
        redis = await self.get_redis()
        published_count = 0

        async with self.session_factory() as session:
            try:
                # Concurrent-safe row lock skipping rows locked by other worker instances
                stmt = (
                    select(OutboxEvent)
                    .where(OutboxEvent.status == OutboxStatus.PENDING)
                    .order_by(OutboxEvent.created_at.asc())
                    .with_for_update(skip_locked=True)
                    .limit(self.BATCH_SIZE)
                )
                result = await session.execute(stmt)
                events = result.scalars().all()

                # Update outbox queue depth metric
                try:
                    from app.core.metrics import LEDGER_OUTBOX_QUEUE_DEPTH
                    from sqlalchemy import func
                    depth_stmt = select(func.count()).select_from(OutboxEvent).where(OutboxEvent.status == OutboxStatus.PENDING)
                    depth_res = (await session.execute(depth_stmt)).scalar() or 0
                    LEDGER_OUTBOX_QUEUE_DEPTH.set(depth_res)
                except Exception:
                    pass

                if not events:
                    return 0


                for event in events:
                    try:
                        stream_payload = {
                            "event_id": str(event.id),
                            "event_type": event.event_type,
                            "aggregate_type": event.aggregate_type,
                            "aggregate_id": str(event.aggregate_id),
                            "payload": json.dumps(event.payload),
                            "created_at": event.created_at.isoformat(),
                        }
                        await redis.xadd(self.stream_key, stream_payload)
                        event.mark_published()
                        published_count += 1
                    except Exception as exc:
                        logger.error("Failed to relay outbox event %s to Redis: %s", event.id, exc)
                        event.mark_failed(str(exc))

                await session.commit()
            except Exception as exc:
                await session.rollback()
                logger.error("Error during outbox batch processing: %s", exc)

        return published_count

    async def run(self) -> None:
        """Continuous polling loop."""
        self._is_running = True
        logger.info("OutboxRelay started polling stream '%s'", self.stream_key)
        try:
            while self._is_running:
                try:
                    count = await self.process_batch()
                    if count == 0:
                        await asyncio.sleep(self.poll_interval)
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    logger.error("Unexpected error in OutboxRelay loop: %s", exc)
                    await asyncio.sleep(self.poll_interval * 2)
        finally:
            self._is_running = False
            logger.info("OutboxRelay loop stopped cleanly.")

    def start(self) -> asyncio.Task:
        """Launches the relay background worker task."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run())
        return self._task

    async def stop(self) -> None:
        """Gracefully halts the relay worker task."""
        self._is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._redis:
            await self._redis.aclose()
            self._redis = None
