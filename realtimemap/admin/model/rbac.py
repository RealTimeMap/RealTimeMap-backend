from typing import Any

from starlette.requests import Request

from admin.model.base import BaseModelAdmin
from modules import Permission, Role, RolePermission, UserPermission, UserRole
from modules.rbac import cache


class _PolicyAdmin(BaseModelAdmin):
    """Правка в админке идёт мимо RbacService, поэтому кэш сбрасывается здесь.

    Проверки против эскалации здесь не нужны: в админку пускают только
    суперпользователя (см. AdminAuthProvider).
    """

    async def after_create(self, request: Request, obj: Any) -> None:
        await cache.bump_version()

    async def after_edit(self, request: Request, obj: Any) -> None:
        await cache.bump_version()

    async def after_delete(self, request: Request, obj: Any) -> None:
        await cache.bump_version()


class AdminPermission(_PolicyAdmin):
    fields = [
        Permission.id,
        Permission.code,
        Permission.service,
        Permission.description,
        Permission.is_system,
    ]
    searchable_fields = [Permission.code, Permission.service]
    sortable_fields = [Permission.code, Permission.service]


class AdminRole(_PolicyAdmin):
    fields = [
        Role.id,
        Role.slug,
        Role.title,
        Role.description,
        Role.priority,
        Role.is_system,
        Role.is_default,
        Role.parents,
        Role.grants,
    ]
    searchable_fields = [Role.slug, Role.title]
    sortable_fields = [Role.slug, Role.priority]


class AdminRolePermission(_PolicyAdmin):
    fields = [
        RolePermission.id,
        RolePermission.role,
        RolePermission.permission,
        RolePermission.effect,
    ]
    searchable_fields = [RolePermission.permission]


class AdminUserRole(_PolicyAdmin):
    fields = [
        UserRole.id,
        UserRole.user,
        UserRole.role,
        UserRole.scope,
        UserRole.expires_at,
        UserRole.reason,
        UserRole.granted_at,
        UserRole.granted_by,
    ]
    exclude_fields_from_create = [UserRole.granted_at]
    exclude_fields_from_edit = [UserRole.granted_at]


class AdminUserPermission(_PolicyAdmin):
    fields = [
        UserPermission.id,
        UserPermission.user,
        UserPermission.permission,
        UserPermission.effect,
        UserPermission.scope,
        UserPermission.expires_at,
        UserPermission.reason,
        UserPermission.granted_at,
        UserPermission.granted_by,
    ]
    exclude_fields_from_create = [UserPermission.granted_at]
    exclude_fields_from_edit = [UserPermission.granted_at]
    searchable_fields = [UserPermission.permission]
