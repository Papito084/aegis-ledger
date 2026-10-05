import asyncio
import functools
import logging
import random
from typing import Any, Callable, Coroutine, TypeVar
import asyncpg
from sqlalchemy.exc import DBAPIError

logger = logging.getLogger("aegis.resilience")

T = TypeVar("T")


def is_serialization_error(exc: Exception) -> bool:
    """
    Identifies whether an exception was caused by a PostgreSQL SERIALIZABLE transaction collision
    (SQLSTATE 40001 - serialization_failure).
    """
    # Check asyncpg direct exceptions
    asyncpg_errors = tuple(
        cls for cls in (
            getattr(asyncpg.exceptions, "SerializationError", None),
            getattr(asyncpg.exceptions, "SerializationFailureError", None),
        )
        if cls is not None
    )
    if asyncpg_errors and isinstance(exc, asyncpg_errors):
        return True

    if isinstance(exc, DBAPIError):
        orig = getattr(exc, "orig", None)
        if orig is not None:
            if asyncpg_errors and isinstance(orig, asyncpg_errors):
                return True
            if getattr(orig, "sqlstate", None) == "40001" or getattr(orig, "pgcode", None) == "40001":
                return True
        if getattr(exc, "pgcode", None) == "40001" or getattr(exc, "sqlstate", None) == "40001":
            return True
        err_msg = str(exc).lower()
        if "40001" in err_msg or "could not serialize access" in err_msg:
            return True

    err_str = str(exc).lower()
    return "40001" in err_str or "could not serialize access" in err_str


def with_serialization_retry(
    max_retries: int = 5,
    base_delay: float = 0.05,
    max_delay: float = 0.5,
):
    """
    Asynchronous decorator that retries transactions failing due to PostgreSQL
    serialization collisions (SQLSTATE 40001) using exponential backoff with randomized jitter.
    """
    def decorator(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            attempt = 0
            while True:
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    if not is_serialization_error(exc):
                        raise
                    attempt += 1
                    if attempt > max_retries:
                        logger.error(
                            "Max serialization retries (%d) exceeded for %s: %s",
                            max_retries,
                            func.__name__,
                            exc,
                        )
                        raise
                    # Exponential backoff with full jitter
                    backoff = min(max_delay, base_delay * (2 ** (attempt - 1)))
                    jitter = random.uniform(0, base_delay)
                    sleep_time = backoff + jitter
                    logger.warning(
                        "Serialization collision in %s (attempt %d/%d). Retrying in %.4fs...",
                        func.__name__,
                        attempt,
                        max_retries,
                        sleep_time,
                    )
                    await asyncio.sleep(sleep_time)

        return wrapper

    return decorator
