"""Операции над сессиями пользователя.

Хранилище сессий — таблица токенов, поэтому отдельного репозитория здесь нет:
слой работает поверх SessionAccessTokenDatabase, того же адаптера, который
использует стратегия аутентификации. Две реализации доступа к одной таблице
разъехались бы при первом же изменении правил протухания.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence, TYPE_CHECKING

from errors.http2 import NotFoundError

if TYPE_CHECKING:
    from auth.access_token_database import SessionAccessTokenDatabase
    from modules.user.model import AccessToken

log = logging.getLogger(__name__)


class SessionService:
    def __init__(
        self,
        access_tokens_db: "SessionAccessTokenDatabase",
        lifetime_seconds: int,
    ):
        self.access_tokens_db = access_tokens_db
        self.lifetime_seconds = lifetime_seconds

    def _max_age(self) -> Optional[datetime]:
        """Граница, левее которой токен считается протухшим.

        Повторяет правило DatabaseStrategy.read_token: иначе список показывал
        бы сессии, по которым вход уже не работает.
        """
        if not self.lifetime_seconds:
            return None
        return datetime.now(timezone.utc) - timedelta(seconds=self.lifetime_seconds)

    async def list_sessions(self, user_id: int) -> Sequence["AccessToken"]:
        return await self.access_tokens_db.list_by_user(user_id, self._max_age())

    async def revoke_session(
        self, user_id: int, session_id: uuid.UUID
    ) -> "AccessToken":
        """Завершает одну сессию пользователя.

        Завершение уже мёртвой сессии — тоже 404: снаружи она неотличима от
        чужой, и отвечать по-разному значило бы подтверждать её существование.
        """
        access_token = await self.access_tokens_db.get_by_session_id(
            user_id, session_id
        )
        if access_token is None:
            raise NotFoundError(detail="Session not found.")

        await self.access_tokens_db.delete(access_token)
        log.info("Session %s of user %r revoked", session_id, user_id)
        return access_token

    async def revoke_all_sessions(self, user_id: int) -> int:
        """Завершает все сессии пользователя — административное действие.

        В отличие от revoke_other_sessions не щадит текущую сессию: модератор
        завершает чужие устройства, своей среди них нет.
        """
        revoked = await self.access_tokens_db.delete_by_user(user_id)
        log.info("Admin revoked all %d sessions of user %r", revoked, user_id)
        return revoked

    async def revoke_other_sessions(self, user_id: int, current_token: str) -> int:
        """Завершает все сессии, кроме текущей."""
        revoked = await self.access_tokens_db.delete_by_user(
            user_id, exclude_token=current_token
        )
        log.info("User %r revoked %d other sessions", user_id, revoked)
        return revoked
