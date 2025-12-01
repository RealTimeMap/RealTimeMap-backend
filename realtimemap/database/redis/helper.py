import logging
from typing import Optional, Type

from fastapi_cache import FastAPICache, Coder, JsonCoder, KeyBuilder
from fastapi_cache.backends.redis import RedisBackend
from fastapi_limiter import FastAPILimiter
from redis import asyncio as aioredis

from core.config import conf
from utils.cache import custom_key_builder

logger = logging.getLogger(__name__)


class RedisHelper:
    def __init__(
        self,
        url: str,
        max_connections: int = 50,
        socket_timeout: int = 5,
        socket_connect_timeout: int = 5,
        socket_keepalive: bool = True,
        health_check_interval: int = 30,
        decode_responses: bool = False,
        encoding: str = "utf-8",
    ):
        self._url = url
        self._max_connections = max_connections
        self._socket_timeout = socket_timeout
        self._socket_connect_timeout = socket_connect_timeout
        self._socket_keepalive = socket_keepalive
        self._health_check_interval = health_check_interval
        self._decode_responses = decode_responses
        self._encoding = encoding
        self._client: Optional[aioredis.Redis] = None
        self._initialized = False

    async def connect(self) -> None:
        try:
            self._client = aioredis.from_url(
                url=self._url,
                max_connections=self._max_connections,
                socket_timeout=self._socket_timeout,
                socket_connect_timeout=self._socket_connect_timeout,
                socket_keepalive=self._socket_keepalive,
                health_check_interval=self._health_check_interval,
                decode_responses=self._decode_responses,
                encoding=self._encoding,
            )
            await self.ping()
            self._initialized = True

            logger.info(f"Redis successfully connected")
        except Exception as e:
            logger.error("Unexpected error connecting Redis: %s", str(e))
            self._initialized = False
            self._client = None

    async def ping(self) -> bool:
        if self._client is None:
            logger.error("Redis is not connected")
            raise False

        try:
            await self._client.ping()
            return True
        except Exception as e:
            logger.error("Redis is not connected. Error: %s", str(e))
            return False

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._initialized

    @property
    def client(self) -> aioredis.Redis:
        if self._client is None:
            raise RuntimeError("Redis is not connected")
        return self._client

    async def close(self) -> None:

        if not self._client:
            logger.warning("Redis already closed")
            return

        try:

            try:
                await FastAPILimiter.close()
            except Exception as e:
                logger.error("FastAPILimiter cant be close: %s", str(e))

            logger.info("Closing Redis connection")

            await self._client.close()

        except Exception as e:
            logger.error("Error closing Redis connection: %s", str(e))

        finally:
            self._client = None
            self._initialized = False

    async def get_client(self) -> Optional[aioredis.Redis]:
        return self._client

    async def init_services(
        self,
        cache_prefix: str = "realtimemap_cache",
        cache_coder: Type[Coder] = JsonCoder,
        cache_key_builder: KeyBuilder = custom_key_builder,
    ) -> None:
        if not self.is_connected:
            raise RuntimeError("Redis is not connected")

        try:
            logger.info("Initializing Redis services")
            await FastAPILimiter.init(redis=self.client)

            FastAPICache.init(
                RedisBackend(redis=self.client),
                prefix=cache_prefix,
                coder=cache_coder,
                key_builder=cache_key_builder,
            )
            logger.info("Redis services initialized")
        except Exception as e:
            logger.error("Error initializing Redis services: %s", str(e))
            raise


redis_helper = RedisHelper(
    url=str(conf.redis.url),
    max_connections=conf.redis.max_connections,
    socket_timeout=conf.redis.socket_timeout,
    socket_connect_timeout=conf.redis.socket_connect_timeout,
    socket_keepalive=conf.redis.socket_keepalive,
    health_check_interval=conf.redis.health_check_interval,
    decode_responses=conf.redis.decode_responses,
    encoding=conf.redis.encoding,
)
