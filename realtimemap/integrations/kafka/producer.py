import logging
from typing import Any, Optional

import orjson
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

from core.config import conf

logger = logging.getLogger(__name__)


class KafkaProducerClient:
    def __init__(self) -> None:
        self._producer: Optional[AIOKafkaProducer] = None

    async def start(self) -> None:
        if not conf.kafka.enabled:
            logger.info("Kafka producer disabled by config")
            return

        producer = AIOKafkaProducer(
            bootstrap_servers=conf.kafka.bootstrap_servers,
            client_id=conf.kafka.client_id,
            request_timeout_ms=conf.kafka.request_timeout_ms,
            retry_backoff_ms=conf.kafka.retry_backoff_ms,
            value_serializer=lambda v: orjson.dumps(v),
            key_serializer=lambda k: k.encode("utf-8") if isinstance(k, str) else k,
        )
        try:
            await producer.start()
            self._producer = producer
            logger.info(
                "Kafka producer started, bootstrap=%s",
                conf.kafka.bootstrap_servers,
            )
        except KafkaError as e:
            logger.warning("Kafka producer failed to start: %s", e)

    async def stop(self) -> None:
        if self._producer is None:
            return
        try:
            await self._producer.stop()
            logger.info("Kafka producer stopped")
        except KafkaError as e:
            logger.warning("Kafka producer stop error: %s", e)
        finally:
            self._producer = None

    async def send(
        self,
        topic: str,
        value: dict[str, Any],
        key: Optional[str] = None,
        headers: Optional[list[tuple[str, bytes]]] = None,
    ) -> None:
        """Публикует событие.

        Сбой отправки логируется, но не поднимается наверх: вызывающий код
        (регистрация пользователя) уже применил своё изменение в БД, и падать
        из-за недоступной шины ему нельзя. Цена — потеря события при отказе
        брокера; починится выносом публикации в outbox, когда это станет
        критично.
        """
        if self._producer is None:
            logger.debug("Kafka producer not initialized, skip event topic=%s", topic)
            return
        try:
            await self._producer.send_and_wait(
                topic, value=value, key=key, headers=headers
            )
        except KafkaError as e:
            logger.error(
                "Failed to publish kafka event topic=%s key=%s err=%s",
                topic,
                key,
                e,
                exc_info=True,
            )


kafka_producer = KafkaProducerClient()
