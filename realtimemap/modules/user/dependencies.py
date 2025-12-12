from typing import Annotated, TYPE_CHECKING

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from database.adapter import PgAdapter
from .model import User
from .repository import PgUserRepository
from .schemas import UserUpdate, UserCreate

if TYPE_CHECKING:
    from core.common.repository import UserRepository

DBSession = Annotated[AsyncSession, Depends(get_session)]


def get_pg_user_repository(
    session: DBSession,
) -> "UserRepository":
    adapter = PgAdapter[User, UserCreate, UserUpdate](session, User)
    return PgUserRepository(adapter=adapter)
