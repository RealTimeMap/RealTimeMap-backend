from typing import Iterable, Optional, Sequence

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from core.common.repository import BaseRepository
from database.adapter import PgAdapter
from .model import Permission, Role, RolePermission, UserPermission, UserRole
from .policy import DirectGrant, Grant, RoleAssignment, RoleNode
from .schemas import RoleCreate, RoleUpdate


class PgRbacRepository(BaseRepository[Role, RoleCreate, RoleUpdate]):
    def __init__(self, adapter: PgAdapter[Role, RoleCreate, RoleUpdate]):
        super().__init__(adapter=adapter)
        self.adapter = adapter
        self.session = adapter.session

    # --- Каталог

    async def list_permissions(
        self, service: Optional[str] = None
    ) -> Sequence[Permission]:
        stmt = select(Permission).order_by(Permission.service, Permission.code)
        if service:
            stmt = stmt.where(Permission.service == service)
        return await self.adapter.execute_query(stmt)

    async def get_permission(self, code: str) -> Optional[Permission]:
        stmt = select(Permission).where(Permission.code == code)
        return await self.adapter.execute_query_one(stmt)

    async def catalog_codes(self) -> list[str]:
        result = await self.session.execute(select(Permission.code))
        return list(result.scalars().all())

    async def upsert_permissions(
        self,
        items: Iterable[tuple[str, str, Optional[str]]],
        is_system: bool,
    ) -> int:
        """ON CONFLICT: синхронизацию запускают все воркеры одновременно."""
        rows = [
            {"code": c, "service": s, "description": d, "is_system": is_system}
            for c, s, d in items
        ]
        if not rows:
            return 0
        stmt = insert(Permission).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Permission.code],
            set_={
                "service": stmt.excluded.service,
                "description": stmt.excluded.description,
            },
        )
        await self.session.execute(stmt)
        return len(rows)

    async def add_permission(self, permission: Permission) -> Permission:
        self.session.add(permission)
        await self.session.flush()
        return permission

    async def delete_permission(self, permission: Permission) -> None:
        await self.session.delete(permission)
        await self.session.flush()

    # --- Роли

    async def list_roles(self) -> Sequence[Role]:
        stmt = select(Role).order_by(Role.priority.desc(), Role.slug)
        return await self.adapter.execute_query(stmt)

    async def get_role(self, slug: str) -> Optional[Role]:
        stmt = select(Role).where(Role.slug == slug)
        return await self.adapter.execute_query_one(stmt)

    async def get_roles(self, slugs: Iterable[str]) -> Sequence[Role]:
        slugs = list(slugs)
        if not slugs:
            return []
        stmt = select(Role).where(Role.slug.in_(slugs))
        return await self.adapter.execute_query(stmt)

    async def add_role(self, role: Role) -> Role:
        self.session.add(role)
        await self.session.flush()
        return role

    async def delete_role(self, role: Role) -> None:
        await self.session.delete(role)
        await self.session.flush()

    async def role_graph(self) -> dict[int, RoleNode]:
        """Ролей немного — граф грузится целиком и обходится в памяти."""
        roles = await self.list_roles()
        return {
            role.id: RoleNode(
                id=role.id,
                slug=role.slug,
                priority=role.priority,
                grants=tuple(Grant(g.permission, g.effect) for g in role.grants),
                parent_ids=tuple(p.id for p in role.parents),
            )
            for role in roles
        }

    async def replace_grants(self, role: Role, grants: Iterable[Grant]) -> None:
        await self.session.execute(
            delete(RolePermission).where(RolePermission.role_id == role.id)
        )
        for grant in grants:
            self.session.add(
                RolePermission(
                    role_id=role.id, permission=grant.permission, effect=grant.effect
                )
            )
        await self.session.flush()
        await self.session.refresh(role, ["grants"])

    # --- Назначения

    async def list_user_roles(self, user_id: int) -> Sequence[UserRole]:
        stmt = (
            select(UserRole)
            .where(UserRole.user_id == user_id)
            .order_by(UserRole.granted_at.desc())
        )
        return await self.adapter.execute_query(stmt, unique=True)

    async def get_user_role(
        self, user_id: int, role_id: int, scope: Optional[str]
    ) -> Optional[UserRole]:
        stmt = select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
            UserRole.scope.is_(None) if scope is None else UserRole.scope == scope,
        )
        result = await self.session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_user_role_by_id(
        self, user_id: int, item_id: int
    ) -> Optional[UserRole]:
        stmt = select(UserRole).where(
            UserRole.id == item_id, UserRole.user_id == user_id
        )
        result = await self.session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def list_user_permissions(self, user_id: int) -> Sequence[UserPermission]:
        stmt = (
            select(UserPermission)
            .where(UserPermission.user_id == user_id)
            .order_by(UserPermission.granted_at.desc())
        )
        return await self.adapter.execute_query(stmt)

    async def get_user_permission(
        self, user_id: int, permission: str, scope: Optional[str]
    ) -> Optional[UserPermission]:
        stmt = select(UserPermission).where(
            UserPermission.user_id == user_id,
            UserPermission.permission == permission,
            UserPermission.scope.is_(None)
            if scope is None
            else UserPermission.scope == scope,
        )
        return await self.adapter.execute_query_one(stmt)

    async def get_user_permission_by_id(
        self, user_id: int, item_id: int
    ) -> Optional[UserPermission]:
        stmt = select(UserPermission).where(
            UserPermission.id == item_id, UserPermission.user_id == user_id
        )
        return await self.adapter.execute_query_one(stmt)

    async def save(self, obj) -> None:
        self.session.add(obj)
        await self.session.flush()

    async def remove(self, obj) -> None:
        await self.session.delete(obj)
        await self.session.flush()

    # --- Исходные данные для policy.resolve

    async def default_role_ids(self) -> list[int]:
        result = await self.session.execute(select(Role.id).where(Role.is_default))
        return list(result.scalars().all())

    async def user_assignments(self, user_id: int) -> list[RoleAssignment]:
        result = await self.session.execute(
            select(UserRole.role_id, UserRole.scope, UserRole.expires_at).where(
                UserRole.user_id == user_id
            )
        )
        return [RoleAssignment(r, s, e) for r, s, e in result.all()]

    async def user_direct_grants(self, user_id: int) -> list[DirectGrant]:
        result = await self.session.execute(
            select(
                UserPermission.permission,
                UserPermission.effect,
                UserPermission.scope,
                UserPermission.expires_at,
            ).where(UserPermission.user_id == user_id)
        )
        return [DirectGrant(p, e, s, x) for p, e, s, x in result.all()]
