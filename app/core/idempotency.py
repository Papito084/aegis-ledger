import json
from contextlib import asynccontextmanager
from typing import Optional, Any
from dataclasses import dataclass
import redis.asyncio as aioredis
from app.core.exceptions import ConcurrentTransactionConflictError


@dataclass
class IdempotencyResult:
    is_cached: bool
    payload: Optional[dict[str, Any]] = None
    handle: Optional["IdempotencyHandle"] = None


class IdempotencyHandle:
    def __init__(self, manager: "DistributedIdempotencyManager", key: str):
        self.manager = manager
        self.key = key
        self.completed = False

    async def complete(self, payload: dict[str, Any]) -> None:
        """Mark the operation as COMPLETED with its cached payload."""
        await self.manager.complete(self.key, payload)
        self.completed = True


class DistributedIdempotencyManager:
    """
    Redis-backed distributed idempotency manager ensuring at-most-once execution
    across concurrent processes and cluster nodes.
    """
    PREFIX = "idempotency:"
    TTL_IN_PROGRESS = 30  # 30 seconds processing timeout
    TTL_COMPLETED = 86400  # 24 hours retention for completed transactions

    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    def _format_key(self, key: str) -> str:
        return f"{self.PREFIX}{key}"

    async def acquire(self, key: str) -> tuple[bool, Optional[dict[str, Any]]]:
        """
        Attempts to acquire the idempotency lock.
        - If acquired: returns (True, None)
        - If already completed: returns (False, cached_payload)
        - If already in progress: raises ConcurrentTransactionConflictError
        """
        redis_key = self._format_key(key)
        in_progress_value = json.dumps({"status": "IN_PROGRESS"})

        # Atomic SET with NX (set only if not exists) and expiration
        acquired = await self.redis.set(
            redis_key,
            in_progress_value,
            nx=True,
            ex=self.TTL_IN_PROGRESS,
        )

        if acquired:
            return True, None

        # Key already exists: check whether it is IN_PROGRESS or COMPLETED
        raw_val = await self.redis.get(redis_key)
        if raw_val is None:
            # Race condition: key expired exactly between set and get; retry once
            acquired = await self.redis.set(
                redis_key,
                in_progress_value,
                nx=True,
                ex=self.TTL_IN_PROGRESS,
            )
            if acquired:
                return True, None
            raw_val = await self.redis.get(redis_key)
            if raw_val is None:
                raise ConcurrentTransactionConflictError(key)

        try:
            data = json.loads(raw_val)
        except json.JSONDecodeError:
            # Corrupted value; release and acquire fresh
            await self.redis.delete(redis_key)
            return True, None

        status = data.get("status")
        if status == "IN_PROGRESS":
            raise ConcurrentTransactionConflictError(key)
        elif status == "COMPLETED":
            return False, data.get("payload")
        else:
            raise ConcurrentTransactionConflictError(key)

    async def complete(self, key: str, payload: dict[str, Any]) -> None:
        """Stores the successful payload with 24-hour TTL."""
        redis_key = self._format_key(key)
        data = {
            "status": "COMPLETED",
            "payload": payload,
        }
        await self.redis.set(
            redis_key,
            json.dumps(data),
            ex=self.TTL_COMPLETED,
        )

    async def release(self, key: str) -> None:
        """Releases the key from Redis, allowing future retries after failure."""
        redis_key = self._format_key(key)
        await self.redis.delete(redis_key)

    @asynccontextmanager
    async def transaction_scope(self, key: str):
        """
        Context manager wrapping an idempotent operation:
        - If cached: yields IdempotencyResult(is_cached=True, payload=...)
        - If new: acquires lock and yields IdempotencyResult(is_cached=False, handle=...)
        - If exception occurs: releases lock so the client can retry with corrections.
        """
        is_new, cached_payload = await self.acquire(key)
        if not is_new:
            yield IdempotencyResult(is_cached=True, payload=cached_payload)
            return

        handle = IdempotencyHandle(self, key)
        try:
            yield IdempotencyResult(is_cached=False, handle=handle)
        except Exception:
            if not handle.completed:
                await self.release(key)
            raise
