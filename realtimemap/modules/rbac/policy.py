"""Вычисление итоговых прав пользователя из грантов (без БД).

Deny сильнее allow; глобальный deny гасит и scoped allow.
Scoped-право записывается как `code@scope`, например `chat.ban@chat:12`.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Optional

from .model import PermissionEffect

WILDCARD = "*"
SCOPE_SEPARATOR = "@"

PERMISSION_CODE_RE = re.compile(r"^[a-z0-9_-]+(\.[a-z0-9_-]+)+$")
PERMISSION_PATTERN_RE = re.compile(r"^(\*|[a-z0-9_-]+(\.[a-z0-9_-]+)*(\.\*)?)$")
SCOPE_RE = re.compile(r"^[a-z0-9_-]+:[A-Za-z0-9_-]+$")
ROLE_SLUG_RE = re.compile(r"^[a-z0-9_-]+$")


def is_pattern(value: str) -> bool:
    return value.endswith(WILDCARD)


def matches(pattern: str, code: str) -> bool:
    """`mark.*` покрывает `mark.comment.delete`, но не сам `mark`."""
    if pattern == WILDCARD:
        return True
    if is_pattern(pattern):
        return code.startswith(pattern[:-1])
    return pattern == code


def expand(patterns: Iterable[str], catalog: Iterable[str]) -> set[str]:
    patterns = set(patterns)
    if not patterns:
        return set()
    if WILDCARD in patterns:
        return set(catalog)
    exact = {p for p in patterns if not is_pattern(p)}
    prefixes = tuple(p[:-1] for p in patterns if is_pattern(p))
    return {c for c in catalog if c in exact or (prefixes and c.startswith(prefixes))}


def scoped(code: str, scope: Optional[str]) -> str:
    return f"{code}{SCOPE_SEPARATOR}{scope}" if scope else code


@dataclass(frozen=True)
class Grant:
    permission: str
    effect: PermissionEffect


@dataclass(frozen=True)
class RoleNode:
    id: int
    slug: str
    priority: int
    grants: tuple[Grant, ...]
    parent_ids: tuple[int, ...]


@dataclass(frozen=True)
class RoleAssignment:
    role_id: int
    scope: Optional[str] = None
    expires_at: Optional[datetime] = None


@dataclass(frozen=True)
class DirectGrant:
    permission: str
    effect: PermissionEffect
    scope: Optional[str] = None
    expires_at: Optional[datetime] = None


@dataclass
class Access:
    """Итоговые права. Сериализуется в кэш и в заголовки gateway."""

    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    # Глобальный ранг: по нему решается, какими ролями можно управлять.
    priority: int = 0
    # Ближайший момент, когда набор прав сам изменится (истечёт грант).
    expires_at: Optional[datetime] = None

    def has(self, code: str, scope: Optional[str] = None) -> bool:
        perms = set(self.permissions)
        if WILDCARD in perms or code in perms:
            return True
        return scope is not None and scoped(code, scope) in perms

    def to_dict(self) -> dict:
        return {
            "roles": self.roles,
            "permissions": self.permissions,
            "priority": self.priority,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Access":
        expires_at = data.get("expires_at")
        return cls(
            roles=list(data.get("roles", [])),
            permissions=list(data.get("permissions", [])),
            priority=int(data.get("priority", 0)),
            expires_at=datetime.fromisoformat(expires_at) if expires_at else None,
        )


def superuser_access(base: Access) -> Access:
    return Access(
        roles=base.roles,
        permissions=[WILDCARD],
        priority=base.priority,
        expires_at=base.expires_at,
    )


def ancestors(role_id: int, roles: dict[int, RoleNode]) -> list[RoleNode]:
    """Роль и все её предки. Обход терпит цикл, если он всё же попал в БД."""
    seen: set[int] = set()
    stack = [role_id]
    result: list[RoleNode] = []
    while stack:
        current = stack.pop()
        if current in seen or current not in roles:
            continue
        seen.add(current)
        node = roles[current]
        result.append(node)
        stack.extend(node.parent_ids)
    return result


def creates_cycle(
    role_id: int, parent_ids: Iterable[int], roles: dict[int, RoleNode]
) -> bool:
    """Станет ли role_id своим же предком, если дать ей этих родителей."""
    for parent_id in parent_ids:
        if parent_id == role_id:
            return True
        if any(node.id == role_id for node in ancestors(parent_id, roles)):
            return True
    return False


def _active(expires_at: Optional[datetime], now: datetime) -> bool:
    return expires_at is None or expires_at > now


def _earliest(*values: Optional[datetime]) -> Optional[datetime]:
    present = [v for v in values if v is not None]
    return min(present) if present else None


def resolve(
    roles: dict[int, RoleNode],
    default_role_ids: Iterable[int],
    assignments: Iterable[RoleAssignment],
    direct: Iterable[DirectGrant],
    catalog: Iterable[str],
    now: datetime,
) -> Access:
    catalog = set(catalog)
    allow: dict[Optional[str], set[str]] = {}
    deny: dict[Optional[str], set[str]] = {}
    role_labels: set[str] = set()
    priority = 0
    expires_at: Optional[datetime] = None

    def add(permission: str, effect: PermissionEffect, scope: Optional[str]) -> None:
        bucket = allow if effect == PermissionEffect.allow else deny
        bucket.setdefault(scope, set()).add(permission)

    active = [RoleAssignment(role_id=r) for r in default_role_ids]
    for assignment in assignments:
        if _active(assignment.expires_at, now):
            active.append(assignment)
            expires_at = _earliest(expires_at, assignment.expires_at)

    for assignment in active:
        role = roles.get(assignment.role_id)
        if role is None:
            continue
        role_labels.add(scoped(role.slug, assignment.scope))
        if assignment.scope is None:
            priority = max(priority, role.priority)
        for node in ancestors(role.id, roles):
            for grant in node.grants:
                add(grant.permission, grant.effect, assignment.scope)

    for grant in direct:
        if _active(grant.expires_at, now):
            add(grant.permission, grant.effect, grant.scope)
            expires_at = _earliest(expires_at, grant.expires_at)

    global_denied = expand(deny.get(None, ()), catalog)
    global_allowed = expand(allow.get(None, ()), catalog) - global_denied

    # Полный каталог сворачивается в `*`, чтобы не раздувать заголовок.
    if catalog and global_allowed == catalog:
        return Access(
            roles=sorted(role_labels),
            permissions=[WILDCARD],
            priority=priority,
            expires_at=expires_at,
        )

    permissions = set(global_allowed)
    for scope, patterns in allow.items():
        if scope is None:
            continue
        denied = global_denied | expand(deny.get(scope, ()), catalog)
        for code in expand(patterns, catalog) - denied - global_allowed:
            permissions.add(scoped(code, scope))

    return Access(
        roles=sorted(role_labels),
        permissions=sorted(permissions),
        priority=priority,
        expires_at=expires_at,
    )
