import logging
from functools import wraps
from typing import Callable, Any

from fastapi_cache.decorator import cache as _cache
from redis import RedisError

logger = logging.getLogger(__name__)


def custom_cache(expire: int = 50, **cache_kwargs):
    """
    Safe cache wrapper with fallback on Redis errors.

    This decorator wraps fastapi-cache's @cache decorator and:
    1. Preserves all original functionality (headers, response injection)
    2. Adds error handling with graceful degradation
    3. Logs cache operations for monitoring

    Args:
        expire: Cache expiration in seconds
        **cache_kwargs: Additional arguments for @cache (namespace, key_builder, etc.)

    Returns:
        Decorated function that caches responses safely
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        # Apply original @cache decorator
        cached_func = _cache(expire=expire, **cache_kwargs)(func)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                # Call cached function - it handles Response headers internally
                result = await cached_func(*args, **kwargs)
                return result
            except RedisError as e:
                # Redis unavailable - execute without cache
                logger.warning(
                    f"Cache unavailable for {func.__name__}: {e}. "
                    "Executing without cache."
                )
                return await func(*args, **kwargs)
            except Exception as e:
                # Other cache errors - execute without cache
                logger.error(
                    f"Cache error for {func.__name__}: {e}. "
                    "Executing without cache.",
                    exc_info=True,
                )
                return await func(*args, **kwargs)

        # Copy signature from cached_func to preserve dependency injection
        wrapper.__signature__ = cached_func.__signature__  # type: ignore

        return wrapper

    return decorator
