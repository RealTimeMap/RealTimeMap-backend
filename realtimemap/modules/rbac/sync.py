import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from database.adapter import PgAdapter
from database.helper import db_helper
from . import cache
from .catalog import PERMISSIONS, ROLES
from .model import Role, RolePermission, role_parents
from .repository import PgRbacRepository

logger = logging.getLogger(__name__)


async def sync_catalog() -> None:
    """Создаёт системные права и роли из catalog.py.

    Идемпотентно (ON CONFLICT): запускается всеми воркерами сразу.
    Существующие роли не трогаются, чтобы рестарт не откатывал правки.
    """
    async with db_helper.session_factory() as session:
        repo = PgRbacRepository(PgAdapter(session, Role))
        await repo.upsert_permissions(
            ((p.code, p.service, p.description) for p in PERMISSIONS),
            is_system=True,
        )

        for spec in ROLES:
            result = await session.execute(
                insert(Role)
                .values(
                    slug=spec.slug,
                    title=spec.title,
                    description=spec.description or None,
                    priority=spec.priority,
                    is_default=spec.is_default,
                    is_system=True,
                )
                .on_conflict_do_nothing(index_elements=[Role.slug])
                .returning(Role.id)
            )
            role_id = result.scalar_one_or_none()
            if role_id is None:
                continue

            for permission, effect in spec.grants:
                session.add(
                    RolePermission(
                        role_id=role_id, permission=permission, effect=effect
                    )
                )
            if spec.parents:
                parent_ids = (
                    await session.execute(
                        select(Role.id).where(Role.slug.in_(spec.parents))
                    )
                ).scalars()
                await session.execute(
                    insert(role_parents).values(
                        [{"role_id": role_id, "parent_id": p} for p in parent_ids]
                    )
                )
            logger.info("RBAC: system role %s created", spec.slug)

        await session.commit()

    await cache.bump_version()
