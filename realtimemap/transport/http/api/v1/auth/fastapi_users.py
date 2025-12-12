from typing import Annotated, Optional

from fastapi import Depends
from fastapi_users import FastAPIUsers

from dependencies.auth.backend import authentication_backend
from dependencies.auth.manager import get_user_manager
from errors.http2 import UserPermissionError
from modules import User
from modules.user_ban.dependencies import get_user_ban_repository
from modules.user_ban.repository import PgUsersBanRepository

fastapi_users = FastAPIUsers[User, int](
    get_user_manager,
    [authentication_backend],
)


current_active_user = fastapi_users.current_user(active=True)
current_active_superuser = fastapi_users.current_user(active=True, superuser=True)


async def get_current_user(
    user: Annotated[User, Depends(current_active_user)],
) -> Optional[User]:
    return user


async def get_current_user_without_ban(
    user_ban_repo: Annotated[PgUsersBanRepository, Depends(get_user_ban_repository)],
    user: Annotated[User, Depends(get_current_user)],
):
    user_ban = await user_ban_repo.check_active_user_ban(user.id)
    if user_ban:
        raise UserPermissionError(detail="You are banned at this time.")
    return user
