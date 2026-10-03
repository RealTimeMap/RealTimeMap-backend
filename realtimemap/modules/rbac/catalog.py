"""Системные права и роли; синхронизируются в БД при старте (sync.py).

Права других сервисов сюда не добавляются — их регистрирует сам сервис
через gRPC RegisterPermissions.
"""

from dataclasses import dataclass, field

from .model import PermissionEffect

SERVICE = "auth"

RBAC_PERMISSION_READ = "rbac.permission.read"
RBAC_PERMISSION_MANAGE = "rbac.permission.manage"
RBAC_ROLE_READ = "rbac.role.read"
RBAC_ROLE_MANAGE = "rbac.role.manage"
RBAC_USER_READ = "rbac.user.read"
RBAC_USER_ASSIGN = "rbac.user.assign"

USER_BAN_READ = "user.ban.read"
USER_BAN_MANAGE = "user.ban.manage"
USER_SESSION_MANAGE = "user.session.manage"


@dataclass(frozen=True)
class PermissionSpec:
    code: str
    description: str
    service: str = SERVICE


@dataclass(frozen=True)
class RoleSpec:
    slug: str
    title: str
    priority: int
    description: str = ""
    is_default: bool = False
    grants: tuple[tuple[str, PermissionEffect], ...] = field(default_factory=tuple)
    parents: tuple[str, ...] = field(default_factory=tuple)


PERMISSIONS: tuple[PermissionSpec, ...] = (
    PermissionSpec(RBAC_PERMISSION_READ, "Просмотр каталога прав"),
    PermissionSpec(RBAC_PERMISSION_MANAGE, "Изменение каталога прав"),
    PermissionSpec(RBAC_ROLE_READ, "Просмотр ролей"),
    PermissionSpec(RBAC_ROLE_MANAGE, "Создание и изменение ролей"),
    PermissionSpec(RBAC_USER_READ, "Просмотр ролей и прав пользователей"),
    PermissionSpec(RBAC_USER_ASSIGN, "Выдача и отзыв ролей и прав пользователям"),
    PermissionSpec(USER_BAN_READ, "Просмотр банов пользователей"),
    PermissionSpec(USER_BAN_MANAGE, "Блокировка и разблокировка пользователей"),
    PermissionSpec(USER_SESSION_MANAGE, "Завершение сессий пользователей"),
)

ROLE_USER = "user"
ROLE_MODERATOR = "moderator"
ROLE_ADMIN = "admin"
ROLE_OWNER = "owner"

ROLES: tuple[RoleSpec, ...] = (
    RoleSpec(
        slug=ROLE_USER,
        title="Пользователь",
        priority=0,
        description="Базовая роль, есть у каждого пользователя",
        is_default=True,
    ),
    RoleSpec(
        slug=ROLE_MODERATOR,
        title="Модератор",
        priority=50,
        parents=(ROLE_USER,),
        grants=(
            (RBAC_ROLE_READ, PermissionEffect.allow),
            (RBAC_USER_READ, PermissionEffect.allow),
            # Блокировка пользователей — работа модератора, а не только админа.
            (USER_BAN_READ, PermissionEffect.allow),
            (USER_BAN_MANAGE, PermissionEffect.allow),
            (USER_SESSION_MANAGE, PermissionEffect.allow),
        ),
    ),
    RoleSpec(
        slug=ROLE_ADMIN,
        title="Администратор",
        priority=100,
        parents=(ROLE_MODERATOR,),
        grants=(("*", PermissionEffect.allow),),
    ),
    RoleSpec(
        slug=ROLE_OWNER,
        title="Владелец",
        priority=1000,
        description="Полный доступ, включая управление администраторами",
        parents=(ROLE_ADMIN,),
        # Права те же, что у администратора: шире, чем `*`, уже некуда.
        # Роль отличается приоритетом — управлять ролью может только тот,
        # чей ранг строго выше, и 1000 оставляет владельца единственным,
        # кто назначает и снимает администраторов.
        grants=(("*", PermissionEffect.allow),),
    ),
)
