"""Стратегия аутентификации, записывающая метаданные сессии.

DatabaseStrategy.write_token принимает только пользователя, поэтому запрос
попадает в стратегию через конструктор — get_database_strategy остаётся
FastAPI-зависимостью и получает Request штатным образом.
"""

from typing import Any, Optional, TYPE_CHECKING

from fastapi import Request
from fastapi_users import models
from fastapi_users.authentication.strategy import DatabaseStrategy

from utils.user_agent import parse_device_name

if TYPE_CHECKING:
    from fastapi_users.authentication.strategy.db import AccessTokenDatabase


class SessionDatabaseStrategy(DatabaseStrategy):
    """DatabaseStrategy, сохраняющая устройство и адрес входа в токене."""

    def __init__(
        self,
        database: "AccessTokenDatabase",
        lifetime_seconds: Optional[int] = None,
        request: Optional[Request] = None,
        trust_forwarded_for: bool = False,
    ):
        super().__init__(database, lifetime_seconds)
        self.request = request
        self.trust_forwarded_for = trust_forwarded_for

    def _create_access_token_dict(self, user: models.UP) -> dict[str, Any]:
        access_token_dict = super()._create_access_token_dict(user)

        # request отсутствует там, где токен только читается (websocket-хендлеры
        # резолвят стратегию вручную). Запись токена всегда идёт из HTTP-запроса.
        if self.request is None:
            return access_token_dict

        user_agent = self.request.headers.get("User-Agent") or ""
        access_token_dict["user_agent"] = user_agent[:512] or None
        access_token_dict["device_name"] = parse_device_name(user_agent)
        access_token_dict["ip_address"] = self._client_ip(self.request)

        return access_token_dict

    def _client_ip(self, request: Request) -> Optional[str]:
        """Адрес клиента.

        X-Forwarded-For учитывается только когда trust_forwarded_for включён
        явно. Заголовок подделывается тривиально, и если сервис доступен в
        обход gateway, доверие к нему превращает адрес в списке сессий в
        выдумку клиента.
        """
        if self.trust_forwarded_for:
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                # Левый узел цепочки — исходный клиент.
                client_ip = forwarded_for.split(",")[0].strip()
                if client_ip:
                    return client_ip[:45]

        if request.client is None:
            return None
        return request.client.host[:45]
