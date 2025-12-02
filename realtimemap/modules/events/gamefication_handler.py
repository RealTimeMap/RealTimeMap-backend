import logging
from contextlib import asynccontextmanager

from database import get_session
from .bus import EventType, DomainEvent
from ..gamefication.dependencies import get_gamefication_service

logger = logging.getLogger(__name__)

get_session_context = asynccontextmanager(get_session)


class GameFicationEventHandler:

    EVENT_TO_ACTION = {
        EventType.MARK_CREATE: "create_mark",
    }

    async def handle_exp_event(self, event: DomainEvent):
        action_type = self.EVENT_TO_ACTION.get(event.event_type)

        if not action_type:
            logger.debug(f"Unknown event type: {event.event_type}")
            return

        async with get_session_context() as session:
            try:
                service = await get_gamefication_service(session)
                await service.great_user_exp(event.user, event.event_type.value)
            except Exception as e:
                logger.error(f"Error getting gamefication service: {e}")
                return
