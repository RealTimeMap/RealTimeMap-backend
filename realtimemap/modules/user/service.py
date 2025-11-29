import asyncio
from typing import TYPE_CHECKING, Optional

from errors.http2 import AuthenticationError
from modules.user_ban.schemas import ReadUsersBan
from .schemas import (
    UserRead,
    UserRequestParams,
    UserRelationShip,
    ReadUserSubscription,
    UserGamefication,
    UserUpdate,
)
from ..gamefication.schemas.level.crud import LevelRead

if TYPE_CHECKING:
    from modules import User
    from fastapi import Request
    from core.common.repository import (
        UserRepository,
        LevelRepository,
        UsersBanRepository,
        UserSubscriptionRepository,
    )


class UserService:
    def __init__(
        self,
        user_repo: "UserRepository",
        user_ban_repo: "UsersBanRepository",
        user_subs_repo: "UserSubscriptionRepository",
        level_repo: "LevelRepository",
    ):
        self.user_repo = user_repo
        self.user_ban_repo = user_ban_repo
        self.user_subs_repo = user_subs_repo
        self.level_repo = level_repo

    async def is_ban(self, user_id: int) -> bool:
        return await self.user_repo.user_is_banned(user_id)

    async def _load_subscription(
        self, user_id: int, request: "Request"
    ) -> Optional[ReadUserSubscription]:
        user_sub = await self.user_subs_repo.get_active_subscription(user_id)
        return ReadUserSubscription.model_validate(user_sub, context={"request": request}) if user_sub else None

    async def _load_ban(self, user_id: int, request: "Request") -> Optional[ReadUsersBan]:
        user_ban = await self.user_ban_repo.get_active_user_ban(user_id)
        return ReadUsersBan.model_validate(user_ban, context={"request": request}) if user_ban else None

    async def _load_gamefication(self, user: "User") -> Optional[UserGamefication]:
        next_level = None
        raw_level = await self.level_repo.get_next_level(user.level)
        current_level = await self.level_repo.get_level(
            user.level
        )  # Todo mb переделать надо будет
        if raw_level:
            next_level = LevelRead.model_validate(raw_level)
        return UserGamefication(
            current_level=user.level,
            current_exp=user.current_exp,
            next_level=next_level,
            current_level_color=current_level.color if current_level else None,
        )

    async def get_included_user_info(
        self, request: "Request", user: "User", params: UserRequestParams
    ) -> UserRead:
        if not user:
            raise AuthenticationError()

        user_response = UserRead.model_validate(user, context={"request": request})

        if not params.include:
            return user_response

        # Параллельная загрузка
        tasks = []
        include_mapping = {}

        if UserRelationShip.SUBSCRIPTION in params.include:
            tasks.append(self._load_subscription(user.id, request))
            include_mapping[len(tasks) - 1] = "subscription"

        if UserRelationShip.BAN in params.include:
            tasks.append(self._load_ban(user.id, request))
            include_mapping[len(tasks) - 1] = "ban"

        if UserRelationShip.GAMEFICATION in params.include:
            tasks.append(self._load_gamefication(user))
            include_mapping[len(tasks) - 1] = "gamefication"

        if tasks:
            results = await asyncio.gather(*tasks)
            for idx, result in enumerate(results):
                field_name = include_mapping[idx]
                if result:
                    setattr(user_response, field_name, result)

        return user_response

    async def get_leaderboard(self, request: "Request"):
        leaders = await self.user_repo.get_users_for_leaderboard()
        users = [
            UserRead.model_validate(leader, context={"request": request})
            for leader in leaders
        ]
        return users

    async def update_user(self, user_id: int, update_data: UserUpdate) -> "User":
        user = await self.user_repo.update(user_id, update_data)
        return user

    async def delete_user(self, user_id: int) -> None:
        await self.user_repo.delete(user_id)
