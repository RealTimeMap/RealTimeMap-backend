from typing import TYPE_CHECKING, Annotated, List, Optional

from fastapi import APIRouter, Depends, Path, Query, status

from modules.rbac.catalog import (
    RBAC_PERMISSION_MANAGE,
    RBAC_PERMISSION_READ,
    RBAC_ROLE_MANAGE,
    RBAC_ROLE_READ,
    RBAC_USER_ASSIGN,
    RBAC_USER_READ,
)
from modules.rbac.dependencies import get_rbac_service
from modules.rbac.schemas import (
    AccessRead,
    PermissionCheckRead,
    PermissionCreate,
    PermissionRead,
    PermissionUpdate,
    RoleCreate,
    RoleGrantsUpdate,
    RoleParentsUpdate,
    RoleRead,
    RoleUpdate,
    UserPermissionAssign,
    UserPermissionRead,
    UserRoleAssign,
    UserRoleRead,
)
from ..auth.fastapi_users import get_current_user
from ..auth.permissions import require_permission

if TYPE_CHECKING:
    from modules.rbac.service import RbacService
    from modules.user.model import User


router = APIRouter(prefix="/rbac", tags=["RBAC"])

Service = Annotated["RbacService", Depends(get_rbac_service)]
RoleSlug = Annotated[str, Path(description="Слаг роли")]
UserId = Annotated[int, Path(description="ID пользователя")]


def _actor(code: str):
    return Depends(require_permission(code))


# --- Свои права


@router.get("/me", response_model=AccessRead, summary="Мои роли и права")
async def my_access(
    user: Annotated["User", Depends(get_current_user)],
    service: Service,
):
    access = await service.get_access(user)
    return AccessRead(
        user_id=user.id,
        is_superuser=user.is_superuser,
        roles=access.roles,
        permissions=access.permissions,
        priority=access.priority,
    )


# --- Каталог прав


@router.get(
    "/permissions",
    response_model=List[PermissionRead],
    summary="Каталог прав",
    dependencies=[_actor(RBAC_PERMISSION_READ)],
)
async def list_permissions(
    service: Service,
    service_name: Annotated[
        Optional[str], Query(alias="service", description="Фильтр по сервису")
    ] = None,
):
    return await service.list_permissions(service_name)


@router.post(
    "/permissions",
    response_model=PermissionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить право в каталог",
    dependencies=[_actor(RBAC_PERMISSION_MANAGE)],
)
async def create_permission(data: PermissionCreate, service: Service):
    return await service.create_permission(data)


@router.patch(
    "/permissions/{code}",
    response_model=PermissionRead,
    summary="Изменить описание права",
    dependencies=[_actor(RBAC_PERMISSION_MANAGE)],
)
async def update_permission(code: str, data: PermissionUpdate, service: Service):
    return await service.update_permission(code, data)


@router.delete(
    "/permissions/{code}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить право из каталога",
    dependencies=[_actor(RBAC_PERMISSION_MANAGE)],
)
async def delete_permission(code: str, service: Service):
    await service.delete_permission(code)


# --- Роли


@router.get(
    "/roles",
    response_model=List[RoleRead],
    summary="Список ролей",
    dependencies=[_actor(RBAC_ROLE_READ)],
)
async def list_roles(service: Service):
    return [RoleRead.from_model(r) for r in await service.list_roles()]


@router.get(
    "/roles/{slug}",
    response_model=RoleRead,
    summary="Роль",
    dependencies=[_actor(RBAC_ROLE_READ)],
)
async def get_role(slug: RoleSlug, service: Service):
    return RoleRead.from_model(await service.get_role(slug))


@router.post(
    "/roles",
    response_model=RoleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать роль",
)
async def create_role(
    data: RoleCreate,
    service: Service,
    actor: Annotated["User", _actor(RBAC_ROLE_MANAGE)],
):
    return RoleRead.from_model(await service.create_role(data, actor))


@router.patch("/roles/{slug}", response_model=RoleRead, summary="Изменить роль")
async def update_role(
    slug: RoleSlug,
    data: RoleUpdate,
    service: Service,
    actor: Annotated["User", _actor(RBAC_ROLE_MANAGE)],
):
    return RoleRead.from_model(await service.update_role(slug, data, actor))


@router.delete(
    "/roles/{slug}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить роль"
)
async def delete_role(
    slug: RoleSlug,
    service: Service,
    actor: Annotated["User", _actor(RBAC_ROLE_MANAGE)],
):
    await service.delete_role(slug, actor)


@router.put(
    "/roles/{slug}/grants",
    response_model=RoleRead,
    summary="Заменить гранты роли",
)
async def set_role_grants(
    slug: RoleSlug,
    data: RoleGrantsUpdate,
    service: Service,
    actor: Annotated["User", _actor(RBAC_ROLE_MANAGE)],
):
    return RoleRead.from_model(await service.set_grants(slug, data.grants, actor))


@router.put(
    "/roles/{slug}/parents",
    response_model=RoleRead,
    summary="Заменить родителей роли",
)
async def set_role_parents(
    slug: RoleSlug,
    data: RoleParentsUpdate,
    service: Service,
    actor: Annotated["User", _actor(RBAC_ROLE_MANAGE)],
):
    return RoleRead.from_model(await service.set_parents(slug, data.parents, actor))


# --- Пользователи


@router.get(
    "/users/{user_id}/access",
    response_model=AccessRead,
    summary="Итоговые права пользователя",
    dependencies=[_actor(RBAC_USER_READ)],
)
async def user_access(user_id: UserId, service: Service):
    user = await service.get_user(user_id)
    access = await service.get_access(user)
    return AccessRead(
        user_id=user.id,
        is_superuser=user.is_superuser,
        roles=access.roles,
        permissions=access.permissions,
        priority=access.priority,
    )


@router.get(
    "/users/{user_id}/check",
    response_model=PermissionCheckRead,
    summary="Проверить право пользователя",
    dependencies=[_actor(RBAC_USER_READ)],
)
async def check_user_permission(
    user_id: UserId,
    service: Service,
    permission: Annotated[str, Query(description="Код права")],
    scope: Annotated[
        Optional[str], Query(description="Ресурс, например chat:12")
    ] = None,
):
    user = await service.get_user(user_id)
    allowed = await service.check(user, permission, scope)
    return PermissionCheckRead(permission=permission, scope=scope, allowed=allowed)


@router.get(
    "/users/{user_id}/roles",
    response_model=List[UserRoleRead],
    summary="Роли пользователя",
    dependencies=[_actor(RBAC_USER_READ)],
)
async def list_user_roles(user_id: UserId, service: Service):
    return [UserRoleRead.from_model(i) for i in await service.list_user_roles(user_id)]


@router.post(
    "/users/{user_id}/roles",
    response_model=UserRoleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Выдать роль",
)
async def assign_user_role(
    user_id: UserId,
    data: UserRoleAssign,
    service: Service,
    actor: Annotated["User", _actor(RBAC_USER_ASSIGN)],
):
    return UserRoleRead.from_model(await service.assign_role(user_id, data, actor))


@router.delete(
    "/users/{user_id}/roles/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Отозвать роль",
)
async def revoke_user_role(
    user_id: UserId,
    assignment_id: int,
    service: Service,
    actor: Annotated["User", _actor(RBAC_USER_ASSIGN)],
):
    await service.revoke_role(user_id, assignment_id, actor)


@router.get(
    "/users/{user_id}/permissions",
    response_model=List[UserPermissionRead],
    summary="Персональные права пользователя",
    dependencies=[_actor(RBAC_USER_READ)],
)
async def list_user_permissions(user_id: UserId, service: Service):
    return await service.list_user_permissions(user_id)


@router.post(
    "/users/{user_id}/permissions",
    response_model=UserPermissionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Выдать или запретить право",
)
async def grant_user_permission(
    user_id: UserId,
    data: UserPermissionAssign,
    service: Service,
    actor: Annotated["User", _actor(RBAC_USER_ASSIGN)],
):
    return await service.grant_permission(user_id, data, actor)


@router.delete(
    "/users/{user_id}/permissions/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Отозвать персональное право",
)
async def revoke_user_permission(
    user_id: UserId,
    assignment_id: int,
    service: Service,
    actor: Annotated["User", _actor(RBAC_USER_ASSIGN)],
):
    await service.revoke_permission(user_id, assignment_id, actor)
