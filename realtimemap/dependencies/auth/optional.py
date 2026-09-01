from typing import Annotated, Optional, TYPE_CHECKING

from fastapi import Depends, Request

from .manager import get_user_manager
from .strategy import get_database_strategy

if TYPE_CHECKING:
    from fastapi_users.authentication.strategy import DatabaseStrategy

    from auth.user_manager import UserManager
    from modules import User


def get_bearer_token(request: Request) -> Optional[str]:
    authorization = request.headers.get("Authorization")

    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token:
        return None

    return token


async def get_current_user_optional(
    strategy: Annotated["DatabaseStrategy", Depends(get_database_strategy)],
    manager: Annotated["UserManager", Depends(get_user_manager)],
    token: Annotated[Optional[str], Depends(get_bearer_token)],
) -> Optional["User"]:
    if not token:
        return None

    user = await strategy.read_token(token, user_manager=manager)

    if not user or not user.is_active:
        return None

    return user
