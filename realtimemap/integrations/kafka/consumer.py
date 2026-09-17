"""Потребитель событий social-service.

Слушает топик social-service.events и держит username в актуальном состоянии:
профиль редактируется в social-service, но username участвует в выдаче этого
сервиса — gateway проставляет его в заголовок X-User-Name из user.username.
Без этого события там навсегда осталось бы имя с момента регистрации.

Зеркало публикации в services/social-service/internal/infrastructure/kafka.
"""

import asyncio
import logging
from typing import Any, Optional

import orjson
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError
from sqlalchemy import select, update

from core.config import conf
from database.helper import db_helper
from modules.user.model import User

from .events import PROFILE_UPDATED

logger = logging.getLogger(__name__)


def _extract(message_value: bytes) -> tuple[str, dict[str, Any]]:
    """Достаёт тип события и payload.

    Тип берётся из тела, а не из headers: заголовки может потерять
    промежуточный компонент (mirror-maker, прокси), тело — нет. Формат
    конверта общий с Go, см. events.make_envelope.
    """
    envelope = orjson.loads(message_value)
    if not isinstance(envelope, dict):
        raise ValueError("event is not an object")

    event_type = envelope.get("type") or envelope.get("event_type") or ""
    payload = envelope.get("payload")

    # Плоский формат кладёт поля в корень — payload там нет.
    if not isinstance(payload, dict):
        payload = envelope

    return event_type, payload


class SocialEventsConsumer:
    """Читает события social-service и применяет их к пользователю."""

    def __init__(self) -> None:
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if not conf.kafka.enabled or not conf.kafka.consumer_enabled:
            logger.info("Kafka consumer disabled by config")
            return

        consumer = AIOKafkaConsumer(
            conf.kafka.social_events_topic,
            bootstrap_servers=conf.kafka.bootstrap_servers,
            group_id=conf.kafka.consumer_group_id,
            client_id=conf.kafka.client_id,
            # Смещение коммитится после обработки, иначе сообщение считалось бы
            # обработанным сразу по вычитке и терялось при падении.
            enable_auto_commit=False,
            auto_offset_reset="earliest",
        )
        try:
            await consumer.start()
        except KafkaError as e:
            # Недоступная шина не должна ронять сервис: без событий username
            # разъедется с social-service, но авторизация продолжит работать.
            logger.warning("Kafka consumer failed to start: %s", e)
            return

        self._consumer = consumer
        self._task = asyncio.create_task(self._run())
        logger.info(
            "Kafka consumer started, topic=%s group=%s",
            conf.kafka.social_events_topic,
            conf.kafka.consumer_group_id,
        )

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            finally:
                self._task = None

        if self._consumer is not None:
            try:
                await self._consumer.stop()
                logger.info("Kafka consumer stopped")
            except KafkaError as e:
                logger.warning("Kafka consumer stop error: %s", e)
            finally:
                self._consumer = None

    async def _run(self) -> None:
        assert self._consumer is not None
        try:
            async for message in self._consumer:
                await self._process(message)
                await self._consumer.commit()
        except asyncio.CancelledError:
            raise
        except KafkaError as e:
            logger.error("Kafka consumer loop failed: %s", e, exc_info=True)

    async def _process(self, message: Any) -> None:
        """Разбирает сообщение и применяет знакомое событие.

        Любая ошибка обработки гасится логом: поднять её наверх значит уронить
        цикл чтения и остановить приём всех последующих событий. Битое
        сообщение пропускается — повтор его не починит.
        """
        try:
            event_type, payload = _extract(message.value)
        except (orjson.JSONDecodeError, ValueError) as e:
            logger.warning("Skipping malformed event: %s", e)
            return

        if event_type != PROFILE_UPDATED:
            # Событие чужого типа — не наше дело.
            return

        try:
            await self._apply_profile_updated(payload)
        except Exception:
            logger.exception("Failed to apply %s", PROFILE_UPDATED)

    @staticmethod
    async def _apply_profile_updated(payload: dict[str, Any]) -> None:
        """Переносит изменённый username в users.

        Пишется только username: остальные поля профиля (tag, аватар) живут в
        social-service и своей колонки здесь не имеют.
        """
        user_id = payload.get("user_id")
        username = payload.get("username")

        if not isinstance(user_id, int) or user_id <= 0:
            logger.warning("Skipping %s: bad user_id=%r", PROFILE_UPDATED, user_id)
            return

        if not isinstance(username, str) or not username:
            # Событие не про имя — применять нечего.
            return

        async with db_helper.session_factory() as session:
            current = await session.scalar(
                select(User.username).where(User.id == user_id)
            )
            if current is None:
                logger.warning(
                    "Skipping %s: user %s not found", PROFILE_UPDATED, user_id
                )
                return

            # Событие могло приехать повторно (Kafka at-least-once) или не
            # менять имени — лишний UPDATE и конфликт по unique не нужны.
            if current == username:
                return

            # Отдельная проверка занятости: username уникален, и гонка с чужой
            # регистрацией дала бы IntegrityError на весь цикл чтения.
            taken = await session.scalar(
                select(User.id).where(User.username == username, User.id != user_id)
            )
            if taken is not None:
                logger.warning(
                    "Skipping %s: username %r already taken by user %s",
                    PROFILE_UPDATED,
                    username,
                    taken,
                )
                return

            await session.execute(
                update(User).where(User.id == user_id).values(username=username)
            )
            await session.commit()

            logger.info("Username synced from social-service, user_id=%s", user_id)


social_events_consumer = SocialEventsConsumer()
