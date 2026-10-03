import logging
from datetime import datetime, timezone
from typing import Iterable, Optional, Sequence

from core.config import conf
from errors.http2 import (
    IntegrityError,
    NotFoundError,
    UserPermissionError,
    ValidationError,
)
from integrations.kafka import (
    RBAC_POLICY_CHANGED,
    USER_ACCESS_CHANGED,
    kafka_producer,
    make_envelope,
    make_headers,
    rbac_policy_changed_payload,
    user_access_changed_payload,
)
from modules.user.model import User
from . import cache
from .model import Permission, Role, UserPermission, UserRole
from .policy import Access, Grant, creates_cycle, expand, resolve, superuser_access
from .repository import PgRbacRepository
from .schemas import (
    GrantItem,
    PermissionCreate,
    PermissionUpdate,
    RoleCreate,
    RoleUpdate,
    UserPermissionAssign,
    UserRoleAssign,
)

logger = logging.getLogger(__name__)


class RbacService:
    """Роли и права.

    Против эскалации: управлять можно только тем, что ниже своего ранга,
    и выдавать только то, что есть у самого. Суперпользователь — без ограничений.
    """

    def __init__(self, repo: PgRbacRepository):
        self.repo = repo

    # --- Вычисление прав

    async def compute_access(self, user_id: int) -> Access:
        return resolve(
            roles=await self.repo.role_graph(),
            default_role_ids=await self.repo.default_role_ids(),
            assignments=await self.repo.user_assignments(user_id),
            direct=await self.repo.user_direct_grants(user_id),
            catalog=await self.repo.catalog_codes(),
            now=datetime.now(timezone.utc),
        )

    async def get_access(self, user: User) -> Access:
        """is_superuser не кэшируется: снятие флага должно действовать сразу."""
        access = await cache.get(user.id)
        if access is None:
            access = await self.compute_access(user.id)
            await cache.put(user.id, access)
        return superuser_access(access) if user.is_superuser else access

    async def check(self, user: User, code: str, scope: Optional[str] = None) -> bool:
        return (await self.get_access(user)).has(code, scope)

    async def require(
        self, user: User, code: str, scope: Optional[str] = None
    ) -> Access:
        access = await self.get_access(user)
        if not access.has(code, scope):
            raise UserPermissionError(detail=f"Permission required: {code}")
        return access

    # --- Проверки против эскалации

    @staticmethod
    def _rank(actor: User, access: Access) -> float:
        return float("inf") if actor.is_superuser else access.priority

    def _ensure_rank(
        self, actor: User, access: Access, priority: int, what: str
    ) -> None:
        if priority >= self._rank(actor, access):
            raise UserPermissionError(
                detail=f"Cannot manage {what}: its priority is not below yours"
            )

    async def _ensure_holds(
        self, actor: User, access: Access, patterns: Iterable[str]
    ) -> None:
        if actor.is_superuser:
            return
        catalog = await self.repo.catalog_codes()
        for pattern in patterns:
            missing = {c for c in expand([pattern], catalog) if not access.has(c)}
            if missing:
                raise UserPermissionError(
                    detail=f"Cannot grant {pattern}: you lack {sorted(missing)[0]}"
                )

    async def _ensure_known(self, patterns: Iterable[str]) -> None:
        catalog = await self.repo.catalog_codes()
        for pattern in patterns:
            if not expand([pattern], catalog):
                raise ValidationError(
                    field="permission",
                    user_input=pattern,
                    input_type="value_error",
                    detail=f"Pattern {pattern!r} matches no registered permission",
                )

    async def _ensure_target(self, actor: User, access: Access, target: User) -> None:
        """Нельзя менять права тому, кто не ниже тебя по рангу."""
        if actor.is_superuser:
            return
        if target.is_superuser:
            raise UserPermissionError(detail="Cannot manage a superuser")
        target_access = await self.compute_access(target.id)
        self._ensure_rank(actor, access, target_access.priority, "this user")

    # --- Каталог

    async def list_permissions(
        self, service: Optional[str] = None
    ) -> Sequence[Permission]:
        return await self.repo.list_permissions(service)

    async def create_permission(self, data: PermissionCreate) -> Permission:
        if await self.repo.get_permission(data.code):
            raise IntegrityError(detail=f"Permission {data.code} already exists")
        permission = await self.repo.add_permission(
            Permission(
                code=data.code, service=data.service, description=data.description
            )
        )
        await self._policy_changed("permission_created")
        return permission

    async def update_permission(self, code: str, data: PermissionUpdate) -> Permission:
        permission = await self._permission(code)
        permission.description = data.description
        await self.repo.save(permission)
        await self.repo.session.commit()
        return permission

    async def delete_permission(self, code: str) -> None:
        permission = await self._permission(code)
        if permission.is_system:
            raise UserPermissionError(
                detail="System permission is declared in code and cannot be deleted"
            )
        await self.repo.delete_permission(permission)
        await self._policy_changed("permission_deleted")

    async def register_permissions(
        self, service: str, items: Iterable[tuple[str, Optional[str]]]
    ) -> int:
        """Регистрация прав сервисом при старте (через gRPC)."""
        count = await self.repo.upsert_permissions(
            ((code, service, description) for code, description in items),
            is_system=True,
        )
        await self._policy_changed("permissions_registered")
        return count

    # --- Роли

    async def list_roles(self) -> Sequence[Role]:
        return await self.repo.list_roles()

    async def get_role(self, slug: str) -> Role:
        role = await self.repo.get_role(slug)
        if role is None:
            raise NotFoundError(detail=f"Role {slug} not found")
        return role

    async def create_role(self, data: RoleCreate, actor: User) -> Role:
        access = await self.get_access(actor)
        self._ensure_rank(actor, access, data.priority, "a role of this priority")
        if await self.repo.get_role(data.slug):
            raise IntegrityError(detail=f"Role {data.slug} already exists")

        role = await self.repo.add_role(
            Role(
                slug=data.slug,
                title=data.title,
                description=data.description,
                priority=data.priority,
                is_default=data.is_default,
            )
        )
        if data.parents:
            await self._apply_parents(role, data.parents, actor, access)
        if data.grants:
            await self._apply_grants(role, data.grants, actor, access)
        await self._policy_changed("role_created", role.slug)
        return role

    async def update_role(self, slug: str, data: RoleUpdate, actor: User) -> Role:
        role = await self.get_role(slug)
        access = await self.get_access(actor)
        self._ensure_rank(actor, access, role.priority, "this role")
        if data.priority is not None:
            self._ensure_rank(actor, access, data.priority, "a role of this priority")
        # Роль по умолчанию раздаёт права всем — это решение уровня владельца.
        if data.is_default is not None and data.is_default != role.is_default:
            if not actor.is_superuser:
                raise UserPermissionError(
                    detail="Only superuser can change default roles"
                )

        for name, value in data.model_dump(
            exclude_unset=True, exclude_none=True
        ).items():
            setattr(role, name, value)
        await self.repo.save(role)
        await self._policy_changed("role_updated", role.slug)
        return role

    async def delete_role(self, slug: str, actor: User) -> None:
        role = await self.get_role(slug)
        if role.is_system:
            raise UserPermissionError(detail="System role cannot be deleted")
        access = await self.get_access(actor)
        self._ensure_rank(actor, access, role.priority, "this role")
        await self.repo.delete_role(role)
        await self._policy_changed("role_deleted", slug)

    async def set_grants(self, slug: str, grants: list[GrantItem], actor: User) -> Role:
        role = await self.get_role(slug)
        access = await self.get_access(actor)
        self._ensure_rank(actor, access, role.priority, "this role")
        await self._apply_grants(role, grants, actor, access)
        await self._policy_changed("role_grants_changed", role.slug)
        return role

    async def set_parents(self, slug: str, parents: list[str], actor: User) -> Role:
        role = await self.get_role(slug)
        access = await self.get_access(actor)
        self._ensure_rank(actor, access, role.priority, "this role")
        await self._apply_parents(role, parents, actor, access)
        await self._policy_changed("role_parents_changed", role.slug)
        return role

    async def _apply_grants(
        self, role: Role, grants: list[GrantItem], actor: User, access: Access
    ) -> None:
        patterns = [g.permission for g in grants]
        if len(set(patterns)) != len(patterns):
            raise ValidationError(
                field="grants",
                user_input=patterns,
                input_type="value_error",
                detail="Duplicate permission in grants",
            )
        await self._ensure_known(patterns)
        await self._ensure_holds(actor, access, patterns)
        await self.repo.replace_grants(
            role, (Grant(g.permission, g.effect) for g in grants)
        )

    async def _apply_parents(
        self, role: Role, slugs: list[str], actor: User, access: Access
    ) -> None:
        parents = list(await self.repo.get_roles(set(slugs)))
        missing = set(slugs) - {p.slug for p in parents}
        if missing:
            raise NotFoundError(detail=f"Role {sorted(missing)[0]} not found")
        # Унаследовать роль выше своего ранга — то же, что выдать её себе.
        for parent in parents:
            self._ensure_rank(actor, access, parent.priority, f"role {parent.slug}")
        if creates_cycle(
            role.id, [p.id for p in parents], await self.repo.role_graph()
        ):
            raise ValidationError(
                field="parents",
                user_input=slugs,
                input_type="value_error",
                detail="Role inheritance would form a cycle",
            )
        role.parents = parents
        await self.repo.save(role)

    # --- Назначения пользователям

    async def list_user_roles(self, user_id: int) -> Sequence[UserRole]:
        await self.get_user(user_id)
        return await self.repo.list_user_roles(user_id)

    async def list_user_permissions(self, user_id: int) -> Sequence[UserPermission]:
        await self.get_user(user_id)
        return await self.repo.list_user_permissions(user_id)

    async def assign_role(
        self, user_id: int, data: UserRoleAssign, actor: User
    ) -> UserRole:
        target = await self.get_user(user_id)
        role = await self.get_role(data.role)
        access = await self.get_access(actor)
        await self._ensure_target(actor, access, target)
        self._ensure_rank(actor, access, role.priority, f"role {role.slug}")

        # Повторная выдача продлевает или меняет срок, а не плодит дубли.
        item = await self.repo.get_user_role(user_id, role.id, data.scope)
        if item is None:
            item = UserRole(user_id=user_id, role_id=role.id, scope=data.scope)
        # Связь проставляется явно: ленивой подгрузки в async-сессии нет.
        item.role = role
        item.expires_at = data.expires_at
        item.reason = data.reason
        item.granted_by = actor.id
        await self.repo.save(item)
        await self._user_changed(target)
        return item

    async def revoke_role(self, user_id: int, item_id: int, actor: User) -> None:
        target = await self.get_user(user_id)
        item = await self.repo.get_user_role_by_id(user_id, item_id)
        if item is None:
            raise NotFoundError(detail="Role assignment not found")
        access = await self.get_access(actor)
        await self._ensure_target(actor, access, target)
        self._ensure_rank(actor, access, item.role.priority, f"role {item.role.slug}")
        await self.repo.remove(item)
        await self._user_changed(target)

    async def grant_permission(
        self, user_id: int, data: UserPermissionAssign, actor: User
    ) -> UserPermission:
        target = await self.get_user(user_id)
        access = await self.get_access(actor)
        await self._ensure_target(actor, access, target)
        await self._ensure_known([data.permission])
        await self._ensure_holds(actor, access, [data.permission])

        item = await self.repo.get_user_permission(user_id, data.permission, data.scope)
        if item is None:
            item = UserPermission(
                user_id=user_id, permission=data.permission, scope=data.scope
            )
        item.effect = data.effect
        item.expires_at = data.expires_at
        item.reason = data.reason
        item.granted_by = actor.id
        await self.repo.save(item)
        await self._user_changed(target)
        return item

    async def revoke_permission(self, user_id: int, item_id: int, actor: User) -> None:
        target = await self.get_user(user_id)
        item = await self.repo.get_user_permission_by_id(user_id, item_id)
        if item is None:
            raise NotFoundError(detail="Permission assignment not found")
        access = await self.get_access(actor)
        await self._ensure_target(actor, access, target)
        await self._ensure_holds(actor, access, [item.permission])
        await self.repo.remove(item)
        await self._user_changed(target)

    # --- Служебное

    async def get_user(self, user_id: int) -> User:
        user = await self.repo.session.get(User, user_id)
        if user is None:
            raise NotFoundError(detail=f"User {user_id} not found")
        return user

    async def _permission(self, code: str) -> Permission:
        permission = await self.repo.get_permission(code)
        if permission is None:
            raise NotFoundError(detail=f"Permission {code} not found")
        return permission

    async def _policy_changed(self, reason: str, role: Optional[str] = None) -> None:
        """Коммит до сброса кэша — иначе соседний запрос закэширует старые права."""
        await self.repo.session.commit()
        await cache.bump_version()
        await kafka_producer.send(
            topic=conf.kafka.user_events_topic,
            value=make_envelope(
                RBAC_POLICY_CHANGED, rbac_policy_changed_payload(reason, role)
            ),
            headers=make_headers(RBAC_POLICY_CHANGED),
        )

    async def _user_changed(self, user: User) -> None:
        await self.repo.session.commit()
        await cache.drop_user(user.id)
        access = await self.get_access(user)
        await kafka_producer.send(
            topic=conf.kafka.user_events_topic,
            value=make_envelope(
                USER_ACCESS_CHANGED,
                user_access_changed_payload(
                    user_id=user.id,
                    roles=access.roles,
                    permissions=access.permissions,
                    is_admin=user.is_superuser,
                ),
            ),
            key=str(user.id),
            headers=make_headers(
                USER_ACCESS_CHANGED, user_id=user.id, source_id=user.id
            ),
        )
