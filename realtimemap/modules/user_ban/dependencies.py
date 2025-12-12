from typing import Annotated, TYPE_CHECKING

from fastapi import Depends

from database import get_session
from database.adapter import PgAdapter
from .repository import PgUsersBanRepository
from .schemas import UpdateUsersBan, UsersBanCreate
from .. import UsersBan

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from core.common.repository import UsersBanRepository


def get_user_ban_repository(
    session: Annotated["AsyncSession", Depends(get_session)],
) -> "UsersBanRepository":
    adapter = PgAdapter[UsersBan, UsersBanCreate, UpdateUsersBan](session, UsersBan)
    return PgUsersBanRepository(adapter=adapter)
