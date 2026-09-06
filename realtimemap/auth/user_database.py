from typing import Optional, Any, TYPE_CHECKING

from fastapi_users_db_sqlalchemy import (
    SQLAlchemyUserDatabase,
    SQLAlchemyBaseOAuthAccountTable,
)
from sqlalchemy import select, func, or_

if TYPE_CHECKING:
    from modules.user.model import User


class MySQLAlchemyUserDatabase(SQLAlchemyUserDatabase):
    def __init__(
        self,
        session,
        user_table,
        oauth_account_table: Optional[type[SQLAlchemyBaseOAuthAccountTable]],
    ):
        super().__init__(session, user_table, oauth_account_table)

    async def get_by_username(self, username: Optional[str]):
        if not username:
            return None
        stmt = select(self.user_table).where(
            func.lower(self.user_table.username) == username.strip().lower()
        )
        return await self._get_user(stmt)

    async def validate_user_credentials(self, username: str, email: str):
        stmt = select(self.user_table).where(
            or_(
                func.lower(self.user_table.username) == username.strip().lower(),
                func.lower(self.user_table.email) == email.strip().lower(),
            )
        )
        return await self._get_user(stmt)

    async def get_by_phone(self, phone: str):
        stmt = select(self.user_table).where(self.user_table.phone == phone)
        return await self._get_user(stmt)

    async def create(self, create_dict: dict[str, Any]) -> "User":
        return await super().create(create_dict)
