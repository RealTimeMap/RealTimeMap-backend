from datetime import datetime
from typing import TYPE_CHECKING, Optional, Sequence

from sqlalchemy import select, func

from core.common.repository import (
    LevelRepository,
    ExpActionRepository,
    UserExpHistoryRepository,
)
from database.adapter import PgAdapter
from modules import Level, ExpAction, UserExpHistory
from modules.gamefication.schemas import CreateUserExpHistory, UpdateUserExpHistory

if TYPE_CHECKING:
    pass


class PgLevelRepository(LevelRepository):
    def __init__(self, adapter: PgAdapter[Level, None, None]):
        super().__init__(adapter)  # noqa
        self.adapter = adapter

    async def get_next_level(self, current_level: int) -> Optional[Level]:
        stmt = select(Level).where(Level.level == current_level + 1, Level.is_active)
        result = await self.adapter.execute_query_one(stmt)
        return result

    async def get_max_level(self) -> Optional[Level]:
        stmt = select(Level).order_by(Level.level.desc()).limit(1)
        result = await self.adapter.execute_query_one(stmt)
        return result

    async def get_levels(self) -> Sequence[Level]:
        pass

    async def get_level(self, level: int) -> Optional[Level]:
        stmt = select(Level).where(Level.level == level, Level.is_active)
        result = await self.adapter.execute_query_one(stmt)
        return result


class PgExpActionRepository(ExpActionRepository):
    def __init__(self, adapter: PgAdapter[ExpAction, None, None]):
        super().__init__(adapter)  # noqa
        self.adapter = adapter

    async def get_action_by_type(self, action_type: str) -> Optional[ExpAction]:
        stmt = select(ExpAction).where(
            ExpAction.action_type == action_type, ExpAction.is_active
        )
        result = await self.adapter.execute_query_one(stmt)
        return result


class PgUserExpHistoryRepository(UserExpHistoryRepository):
    def __init__(
        self,
        adapter: PgAdapter[UserExpHistory, CreateUserExpHistory, UpdateUserExpHistory],
    ):
        super().__init__(adapter)
        self.adapter = adapter

    async def get_user_daily_limit_by_action(
        self, user_id: int, action_id: int
    ) -> Optional[int]:
        now = datetime.now()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

        stmt = select(func.count(UserExpHistory.id)).where(
            UserExpHistory.user_id == user_id,
            UserExpHistory.action_id == action_id,
            UserExpHistory.created_at >= day_start,
            UserExpHistory.created_at <= day_end,
        )
        result = await self.adapter.execute_query_one(stmt)
        return result

    async def check_if_user_alredy_granted(self, user_id: int, action_id: int) -> bool:
        stmt = (
            select(func.count())
            .select_from(UserExpHistory)
            .where(
                UserExpHistory.user_id == user_id,
                UserExpHistory.action_id == action_id,
                not UserExpHistory.is_revoked,
            )
        )
        result = await self.adapter.execute_scalar(stmt)
        return result > 0
