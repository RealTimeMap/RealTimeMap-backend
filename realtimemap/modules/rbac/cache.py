"""Кэш итоговых прав в Redis.

Правка политики увеличивает глобальную версию в ключе вместо перебора
ключей. Без Redis кэш выключается и права считаются из БД.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import orjson

from database.redis.helper import redis_helper
from .policy import Access

logger = logging.getLogger(__name__)

VERSION_KEY = "rbac:version"
MAX_TTL_SECONDS = 300


def _key(version: int, user_id: int) -> str:
    return f"rbac:access:{version}:{user_id}"


async def _version() -> int:
    raw = await redis_helper.client.get(VERSION_KEY)
    return int(raw) if raw else 0


def _ttl(access: Access) -> int:
    # Запись не должна пережить ближайший истекающий грант.
    if access.expires_at is None:
        return MAX_TTL_SECONDS
    left = (access.expires_at - datetime.now(timezone.utc)).total_seconds()
    return max(1, min(MAX_TTL_SECONDS, int(left)))


async def get(user_id: int) -> Optional[Access]:
    if not redis_helper.is_connected:
        return None
    try:
        raw = await redis_helper.client.get(_key(await _version(), user_id))
    except Exception as e:
        logger.warning("RBAC cache read failed: %s", e)
        return None
    return Access.from_dict(orjson.loads(raw)) if raw else None


async def put(user_id: int, access: Access) -> None:
    if not redis_helper.is_connected:
        return
    try:
        await redis_helper.client.set(
            _key(await _version(), user_id),
            orjson.dumps(access.to_dict()),
            ex=_ttl(access),
        )
    except Exception as e:
        logger.warning("RBAC cache write failed: %s", e)


async def drop_user(user_id: int) -> None:
    if not redis_helper.is_connected:
        return
    try:
        await redis_helper.client.delete(_key(await _version(), user_id))
    except Exception as e:
        logger.warning("RBAC cache drop failed: %s", e)


async def bump_version() -> None:
    """Сбрасывает кэш всех пользователей разом."""
    if not redis_helper.is_connected:
        return
    try:
        await redis_helper.client.incr(VERSION_KEY)
    except Exception as e:
        logger.warning("RBAC cache version bump failed: %s", e)
