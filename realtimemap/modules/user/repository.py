from datetime import datetime
from typing import TYPE_CHECKING, Sequence, Optional, List, Tuple

from sqlalchemy import select, and_, or_, func

from core.common.repository import UserRepository
from database.adapter import PgAdapter
from modules.gamefication.model import Level
from modules.user.schemas import UserCreate, UserUpdate
from modules.user_ban.model import UsersBan
from .model import User

if TYPE_CHECKING:
    pass


class PgUserRepository(UserRepository):
    def __init__(self, adapter: PgAdapter[User, UserCreate, UserUpdate]):
        super().__init__(adapter)
        self.adapter = adapter

    async def user_is_banned(self, user_id: int) -> bool:
        """
        Check if the user is banned.

        Args:
            user_id (int): The id of the user.

        Returns:
            bool: Whether the user is banned.
        """
        current_time = datetime.now()
        stmt = (
            select(UsersBan)
            .where(
                and_(
                    UsersBan.user_id == user_id,
                    or_(
                        UsersBan.is_permanent,
                        and_(
                            not UsersBan.is_permanent,
                            UsersBan.banned_until > current_time,
                        ),
                    ),
                )
            )
            .order_by(UsersBan.banned_at.desc())
        )
        active_ban = await self.adapter.execute_query_one(stmt)

        return active_ban is not None

    async def get_level_up(self, user_id: int) -> int:
        user = await self.get_by_id(user_id)
        level_stmt = select(Level).where(Level.is_active).order_by(Level.level.asc())
        levels: List[Level] = await self.adapter.execute_query(level_stmt)

        if not levels:
            return user.level  # noqa

        new_level = 0
        for level in levels:
            if user.total_exp >= level.required_exp:
                new_level = level.level
            else:
                break

        if new_level > 0:
            current_level = next(
                (level for level in levels if level.level == new_level), None
            )
            if current_level:
                user.current_exp = user.total_exp - current_level.required_exp
        else:
            user.current_exp = user.total_exp

        user.level = new_level

        return new_level

    async def get_users_for_leaderboard(self) -> Optional[Sequence[User]]:
        stmt = select(User).where(User.is_active).order_by(User.level.desc()).limit(10)
        users = await self.adapter.execute_query(stmt)
        return users

    async def list_for_admin(
        self,
        offset: int,
        limit: int,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_superuser: Optional[bool] = None,
    ) -> Tuple[Sequence[User], int]:
        conditions = []
        if search:
            pattern = f"%{search}%"
            conditions.append(
                or_(
                    User.username.ilike(pattern),
                    User.email.ilike(pattern),
                    User.phone.ilike(pattern),
                )
            )
        if is_active is not None:
            conditions.append(User.is_active.is_(is_active))
        if is_superuser is not None:
            conditions.append(User.is_superuser.is_(is_superuser))

        total = await self.adapter.execute_scalar(
            select(func.count(User.id)).where(*conditions)
        )
        stmt = (
            select(User)
            .where(*conditions)
            .order_by(User.id.desc())
            .offset(offset)
            .limit(limit)
        )
        # oauth_accounts грузится joined — без unique строки задвоятся.
        items = await self.adapter.execute_query(stmt, unique=True)
        return items, total or 0
