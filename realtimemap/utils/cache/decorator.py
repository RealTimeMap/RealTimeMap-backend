import logging
from functools import wraps
from typing import Callable, Any

from fastapi_cache.decorator import cache as _cache
from redis import RedisError

logger = logging.getLogger(__name__)


def custom_cache(expire: int = 50, **cache_kwargs):
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        # Apply original @cache decorator
        cached_func = _cache(expire=expire, **cache_kwargs)(func)

        # Имена инжектированных параметров
        injected_dependency_namespace = cache_kwargs.get(
            "injected_dependency_namespace", "__fastapi_cache"
        )
        injected_request_name = f"{injected_dependency_namespace}_request"
        injected_response_name = f"{injected_dependency_namespace}_response"

        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                # Call cached function
                result = await cached_func(*args, **kwargs)
                return result
            except RedisError as e:
                logger.warning(
                    f"Cache unavailable for {func.__name__}: {e}. "
                    "Executing without cache."
                )
                # Очищаем инжектированные параметры
                clean_kwargs = {
                    k: v
                    for k, v in kwargs.items()
                    if k not in (injected_request_name, injected_response_name)
                }
                return await func(*args, **clean_kwargs)
            except Exception as e:
                logger.error(
                    f"Cache error for {func.__name__}: {e}. "
                    "Executing without cache.",
                    exc_info=True,
                )
                # Очищаем инжектированные параметры
                clean_kwargs = {
                    k: v
                    for k, v in kwargs.items()
                    if k not in (injected_request_name, injected_response_name)
                }
                return await func(*args, **clean_kwargs)

        # Copy signature from cached_func
        wrapper.__signature__ = cached_func.__signature__  # type: ignore

        return wrapper

    return decorator
