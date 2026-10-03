from typing import TYPE_CHECKING, Annotated

from fastapi import Depends

from database import get_session
from database.adapter import PgAdapter
from .model import Role
from .repository import PgRbacRepository
from .schemas import RoleCreate, RoleUpdate
from .service import RbacService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def create_rbac_service(session: "AsyncSession") -> RbacService:
    adapter = PgAdapter[Role, RoleCreate, RoleUpdate](session, Role)
    return RbacService(PgRbacRepository(adapter=adapter))


def get_rbac_service(
    session: Annotated["AsyncSession", Depends(get_session)],
) -> RbacService:
    return create_rbac_service(session)
