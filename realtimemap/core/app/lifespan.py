import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_limiter import FastAPILimiter
from redis import asyncio as aioredis
from yookassa import Configuration

from core.config import conf
from database.helper import db_helper
from integrations.payment.yookassa import YookassaClient
from modules.events.bus import EventType, event_bus
from modules.events.gamefication_handler import GameFicationEventHandler
from utils.cache import OrJsonEncoder, custom_key_builder
from .templating import TemplateManager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_client = None
    try:
        redis_client = aioredis.from_url(
            str(conf.redis.url),
            encoding="utf-8",
            decode_responses=False,  # ⚠️ КРИТИЧНО для fastapi-cache!
            max_connections=conf.redis.max_connections,
            socket_timeout=conf.redis.socket_timeout,
            socket_connect_timeout=conf.redis.socket_connect_timeout,
            socket_keepalive=conf.redis.socket_keepalive,
            health_check_interval=conf.redis.health_check_interval,
        )
        await redis_client.ping()
        logger.info(f"Redis connection established")

        await FastAPILimiter.init(redis=redis_client)
        FastAPICache.init(
            RedisBackend(redis_client),
            prefix=conf.redis.prefix,
            coder=OrJsonEncoder,
            key_builder=custom_key_builder,
        )
    except Exception as e:
        logger.error(f"Redis connection failed, {e}")
        redis_client = None

    app.state.redis = redis_client
    app.state.templates = TemplateManager(conf.template_dir)

    Configuration.secret_key = conf.payment.secret_key
    Configuration.account_id = conf.payment.shop_id
    yookassa_client = YookassaClient()
    app.state.yookassa_client = yookassa_client

    gamefication_handler = GameFicationEventHandler()

    for event_type in [
        EventType.MARK_CREATE,
    ]:
        event_bus.subscribe(event_type, gamefication_handler.handle_exp_event)

    yield

    if redis_client:
        try:
            await FastAPILimiter.close()
            await redis_client.close()
            logger.info("Redis connections closed")
        except Exception as e:

            logger.error(f"Error closing Redis: {e}")

    await FastAPILimiter.close()
    await db_helper.dispose()
