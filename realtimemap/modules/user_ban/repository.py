from datetime import datetime
from typing import TYPE_CHECKING, Sequence, Optional, List

from sqlalchemy import select, and_, or_, Select

from core.common.repository import UsersBanRepository
from database.adapter import PgAdapter
from .model import UsersBan
from .schemas import UsersBanCreate, UpdateUsersBan

if TYPE_CHECKING:
    pass


class PgUsersBanRepository(UsersBanRepository):
    def __init__(self, adapter: PgAdapter[UsersBan, UsersBanCreate, UpdateUsersBan]):
        super().__init__(adapter=adapter)
        self.adapter = adapter

    @staticmethod
    def _active_condition():
        return and_(
            UsersBan.unbanned_at.is_(None),
            or_(
                UsersBan.is_permanent,
                UsersBan.banned_until > datetime.now(),
            ),
        )

    @classmethod
    def _base_query(cls, user_id: int) -> Select:
        stmt = (
            select(UsersBan)
            .where(UsersBan.user_id == user_id, cls._active_condition())
            .order_by(UsersBan.banned_at.desc())
        )
        return stmt

    async def check_active_user_ban(self, user_id: int) -> bool:
        stmt = self._base_query(user_id)
        active_ban = await self.adapter.execute_query_one(stmt)
        return active_ban is not None

    async def ban_user(self, data: UsersBanCreate) -> UsersBan:
        result = await self.create(data)
        return result

    async def unban_user(self, user_id: int, data: UpdateUsersBan) -> UsersBan:
        stmt = self._base_query(user_id)
        active_ban = await self.adapter.execute_query_one(stmt)
        result = await self.update(active_ban.id, data)
        return result

    async def get_user_bans(self, user_id: int) -> Sequence[UsersBan]:
        stmt = (
            select(UsersBan)
            .where(UsersBan.user_id == user_id)
            .order_by(UsersBan.banned_at.desc())
        )
        active_bans = await self.adapter.execute_query(stmt)
        return active_bans

    async def get_active_user_ban(self, user_id: int) -> Optional[UsersBan]:
        stmt = self._base_query(user_id).limit(1)
        active_ban = await self.adapter.execute_query_one(stmt)
        return active_ban

    async def get_active_bans(self, user_ids: Sequence[int]) -> List[UsersBan]:
        if not user_ids:
            return []
        stmt = (
            select(UsersBan)
            .where(UsersBan.user_id.in_(user_ids), self._active_condition())
            .order_by(UsersBan.user_id, UsersBan.banned_at.desc())
            .distinct(UsersBan.user_id)
        )
        return await self.adapter.execute_query(stmt)
