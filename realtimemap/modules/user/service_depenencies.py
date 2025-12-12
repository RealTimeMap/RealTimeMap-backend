from typing import Annotated, TYPE_CHECKING

from fastapi import Depends

from modules.gamefication.dependencies import get_pg_level_repository
from modules.user_ban.dependencies import get_user_ban_repository
from modules.user_subscription.dependencies import get_user_subscription_repository
from .dependencies import get_pg_user_repository
from .service import UserService

if TYPE_CHECKING:
    from core.common.repository import (
        UserRepository,
        LevelRepository,
        UsersBanRepository,
        UserSubscriptionRepository,
    )
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_user_service(
    user_repo: Annotated["UserRepository", Depends(get_pg_user_repository)],
    user_ban_repo: Annotated["UsersBanRepository", Depends(get_user_ban_repository)],
    user_subs_repo: Annotated[
        "UserSubscriptionRepository", Depends(get_user_subscription_repository)
    ],
    level_repo: Annotated["LevelRepository", Depends(get_pg_level_repository)],
) -> "UserService":
    return UserService(user_repo, user_ban_repo, user_subs_repo, level_repo)


# Для gRPC!
async def create_user_service(session: "AsyncSession") -> "UserService":
    user_repo = get_pg_user_repository(session)
    user_ban_repo = get_user_ban_repository(session)
    user_subs_repo = get_user_subscription_repository(session)
    level_repo = get_pg_level_repository(session)

    return UserService(user_repo, user_ban_repo, user_subs_repo, level_repo)
