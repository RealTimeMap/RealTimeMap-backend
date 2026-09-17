import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from yookassa import Configuration

from core.config import conf
from database.helper import db_helper
from database.redis.helper import redis_helper
from integrations.kafka import kafka_producer, social_events_consumer
from integrations.payment.yookassa import YookassaClient
from modules.events.bus import EventType, event_bus
from modules.events.gamefication_handler import GameFicationEventHandler
from .templating import TemplateManager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):

    try:
        await redis_helper.connect()
        await redis_helper.init_services()
    except RuntimeError:
        logger.warning(
            "Redis connection failed continue without cache and rate limiter"
        )

    await kafka_producer.start()
    # Консьюмер после продюсера: обработка события может сама что-то
    # опубликовать, и продюсер к тому моменту должен быть поднят.
    await social_events_consumer.start()

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
    # Останавливается первым: цикл чтения не должен пережить продюсер и БД.
    await social_events_consumer.stop()
    await kafka_producer.stop()
    await redis_helper.close()

    await db_helper.dispose()
