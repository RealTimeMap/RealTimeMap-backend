import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from modules.user.model import AccessToken


class SessionRead(BaseModel):
    """Сессия в списке устройств пользователя.

    Токена здесь нет и быть не должно: он действующий bearer, и выдача его в
    списке сессий равносильна выдаче доступа. Снаружи сессия адресуется по
    session_id.
    """

    session_id: Annotated[uuid.UUID, Field(description="Идентификатор сессии")]
    device_name: Annotated[
        Optional[str], Field(None, description="Устройство, как его показать человеку")
    ]
    user_agent: Annotated[Optional[str], Field(None, description="Полный User-Agent")]
    ip_address: Annotated[Optional[str], Field(None, description="IP-адрес входа")]
    created_at: Annotated[datetime, Field(description="Когда был выполнен вход")]
    last_used_at: Annotated[
        datetime, Field(description="Последняя активность (с точностью до 5 минут)")
    ]
    expires_at: Annotated[datetime, Field(description="Когда сессия истечёт")]
    is_current: Annotated[
        bool, Field(description="Сессия, из которой сделан этот запрос")
    ]

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_model(
        cls,
        access_token: "AccessToken",
        *,
        is_current: bool,
        lifetime_seconds: int,
    ) -> "SessionRead":
        """Собирает ответ из строки таблицы токенов.

        expires_at вычисляется, а не хранится: DatabaseStrategy проверяет
        возраст токена по created_at, и хранение второй копии срока жизни
        разошлось бы с этой проверкой при смене настройки.
        """
        created_at = _as_utc(access_token.created_at)
        return cls(
            session_id=access_token.session_id,
            device_name=access_token.device_name,
            user_agent=access_token.user_agent,
            ip_address=access_token.ip_address,
            created_at=created_at,
            last_used_at=_as_utc(access_token.last_used_at),
            expires_at=created_at + timedelta(seconds=lifetime_seconds),
            is_current=is_current,
        )


class SessionRevokedResponse(BaseModel):
    """Результат массового завершения сессий."""

    revoked: Annotated[int, Field(description="Сколько сессий было завершено")]


def _as_utc(value: datetime) -> datetime:
    """Приводит время к aware-UTC.

    Драйвер может отдать naive datetime, а вычитание naive и aware падает.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
