from typing import TYPE_CHECKING, Annotated, Callable, Optional

from fastapi import Depends, Request

from errors.http2 import UserPermissionError
from modules.rbac.dependencies import get_rbac_service
from modules.rbac.service import RbacService
from .fastapi_users import get_current_user

if TYPE_CHECKING:
    from modules.user.model import User


def require_permission(
    *codes: str,
    any_of: bool = False,
    scope_param: Optional[str] = None,
) -> Callable:
    """Гард по правам. scope_param='chat_id' проверяет `code@chat:<chat_id>`."""

    async def dependency(
        request: Request,
        user: Annotated["User", Depends(get_current_user)],
        service: Annotated[RbacService, Depends(get_rbac_service)],
    ) -> "User":
        scope = None
        if scope_param:
            value = request.path_params.get(scope_param)
            if value is not None:
                scope = f"{scope_param.removesuffix('_id')}:{value}"

        access = await service.get_access(user)
        checks = [access.has(code, scope) for code in codes]
        if not (any(checks) if any_of else all(checks)):
            raise UserPermissionError(detail=f"Permission required: {', '.join(codes)}")
        return user

    return dependency
