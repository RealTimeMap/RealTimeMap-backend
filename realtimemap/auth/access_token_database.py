"""Адаптер таблицы токенов, знающий про сессии.

Поверх стандартного SQLAlchemyAccessTokenDatabase добавлено одно поведение —
отметка времени последнего использования токена. Без неё список сессий
показывает только момент входа, а пользователю нужно понимать, какая сессия
живая, а какая забыта на чужом устройстве.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence, TYPE_CHECKING

from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyAccessTokenDatabase
from sqlalchemy import delete, select

if TYPE_CHECKING:
    import uuid

    from modules.user.model import AccessToken


class SessionAccessTokenDatabase(SQLAlchemyAccessTokenDatabase):
    """Таблица токенов с учётом активности и операциями над сессиями."""

    #: Как часто обновляется last_used_at.
    #:
    #: get_by_token вызывается на каждый запрос (в том числе на каждый
    #: /auth/token-validate от gateway), поэтому запись на каждое чтение
    #: означала бы UPDATE на каждый запрос приложения. Пятиминутная
    #: гранулярности достаточно для строки "был активен N минут назад".
    TOUCH_INTERVAL = timedelta(minutes=5)

    async def get_by_token(
        self, token: str, max_age: Optional[datetime] = None
    ) -> Optional["AccessToken"]:
        access_token = await super().get_by_token(token, max_age)
        if access_token is None:
            return None

        now = datetime.now(timezone.utc)
        last_used_at = access_token.last_used_at
        # Драйвер может вернуть naive datetime — сравнение с aware упало бы.
        if last_used_at is not None and last_used_at.tzinfo is None:
            last_used_at = last_used_at.replace(tzinfo=timezone.utc)

        if last_used_at is None or now - last_used_at >= self.TOUCH_INTERVAL:
            await self.update(access_token, {"last_used_at": now})

        return access_token

    async def get_by_session_id(
        self, user_id: int, session_id: "uuid.UUID"
    ) -> Optional["AccessToken"]:
        """Сессия пользователя по внешнему идентификатору.

        Фильтр по user_id обязателен: он и делает невозможным завершение чужой
        сессии по угаданному session_id.
        """
        statement = select(self.access_token_table).where(
            self.access_token_table.user_id == user_id,
            self.access_token_table.session_id == session_id,
        )
        results = await self.session.execute(statement)
        return results.scalar_one_or_none()

    async def list_by_user(
        self, user_id: int, max_age: Optional[datetime] = None
    ) -> Sequence["AccessToken"]:
        """Активные сессии пользователя, свежие сверху.

        max_age отсекает протухшие токены по тому же правилу, по которому их
        отвергает DatabaseStrategy — по created_at, а не по last_used_at.
        """
        statement = select(self.access_token_table).where(
            self.access_token_table.user_id == user_id
        )
        if max_age is not None:
            statement = statement.where(self.access_token_table.created_at >= max_age)
        statement = statement.order_by(self.access_token_table.last_used_at.desc())

        results = await self.session.execute(statement)
        return results.scalars().all()

    async def delete_by_user(
        self, user_id: int, exclude_token: Optional[str] = None
    ) -> int:
        """Удаляет сессии пользователя, кроме указанной. Возвращает их число.

        Одним DELETE, а не выборкой с последующим удалением по одной: строк
        может быть много, и промежуточное состояние никому не нужно.
        """
        statement = delete(self.access_token_table).where(
            self.access_token_table.user_id == user_id
        )
        if exclude_token is not None:
            statement = statement.where(self.access_token_table.token != exclude_token)

        result = await self.session.execute(statement)
        await self.session.commit()
        return result.rowcount or 0
