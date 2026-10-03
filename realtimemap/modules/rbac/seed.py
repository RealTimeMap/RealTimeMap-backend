"""Сидер базовых ролей и их грантов.

Чем отличается от sync_catalog (sync.py): тот создаёт роль только если её
ещё нет, и существующую не трогает — так рестарт сервиса не откатывает
правки, сделанные руками через админку. Побочный эффект: новое право,
добавленное в catalog.py, до уже созданных ролей не доезжает никогда.

Сидер закрывает именно это. Он приводит системные роли к тому, что
записано в каталоге: добавляет недостающие гранты и связи с родителями.
Запускается осознанно, а не на каждом старте:

    python -m modules.rbac.seed            # показать расхождения
    python -m modules.rbac.seed --apply    # применить

По умолчанию ничего не меняет — сначала показывает, что сделает.

Чего сидер НЕ делает намеренно:
  * не снимает гранты, которых нет в каталоге, — их могли выдать
    осознанно через админку, и молча отбирать права опасно;
  * не трогает priority, title и описание существующих ролей —
    это настройки, а не контракт кода;
  * не выдаёт роли пользователям — назначение владельца остаётся
    ручным действием (см. --owner).

Снять лишние гранты можно явным --prune, и он пишет в лог каждый.
"""

import argparse
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from database.adapter import PgAdapter
from database.helper import db_helper
from modules.user.model import User

from . import cache
from .catalog import PERMISSIONS, ROLE_OWNER, ROLES, RoleSpec
from .model import PermissionEffect, Role, RolePermission, UserRole, role_parents
from .repository import PgRbacRepository

logger = logging.getLogger(__name__)


class SeedError(RuntimeError):
    """Ошибка, которую стоит показать человеку строкой, а не трейсбеком."""


@dataclass
class RoleChanges:
    """Что сидер собирается сделать с одной ролью."""

    slug: str
    created: bool = False
    added_grants: list[str] = field(default_factory=list)
    removed_grants: list[str] = field(default_factory=list)
    added_parents: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (
            self.created
            or self.added_grants
            or self.removed_grants
            or self.added_parents
        )

    def describe(self) -> str:
        if self.created:
            head = f"{self.slug}: создана"
        else:
            head = f"{self.slug}:"

        parts = []
        if self.added_grants:
            parts.append("добавлены права " + ", ".join(sorted(self.added_grants)))
        if self.removed_grants:
            parts.append("сняты права " + ", ".join(sorted(self.removed_grants)))
        if self.added_parents:
            parts.append("добавлены родители " + ", ".join(sorted(self.added_parents)))

        return f"{head} {'; '.join(parts)}" if parts else head


@dataclass
class SeedReport:
    roles: list[RoleChanges] = field(default_factory=list)
    permissions_synced: int = 0
    owner_granted_to: Optional[int] = None

    @property
    def changed(self) -> list[RoleChanges]:
        return [r for r in self.roles if not r.is_empty]


def _grant_key(permission: str, effect: PermissionEffect) -> str:
    """Ключ гранта: одно и то же право может быть и allow, и deny."""
    return f"{effect.value}:{permission}"


async def _seed_role(
    session,
    spec: RoleSpec,
    *,
    prune: bool,
) -> RoleChanges:
    changes = RoleChanges(slug=spec.slug)

    # ON CONFLICT DO NOTHING + RETURNING не вернёт id существующей строки,
    # поэтому читаем роль отдельно, а не полагаемся на результат вставки.
    await session.execute(
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
    )

    role = (
        await session.execute(select(Role).where(Role.slug == spec.slug))
    ).scalar_one_or_none()

    if role is None:
        # Такого быть не должно: строку либо вставили, либо она уже была.
        raise SeedError(f"роль {spec.slug} не найдена после вставки")

    existing_rows = (
        (
            await session.execute(
                select(RolePermission).where(RolePermission.role_id == role.id)
            )
        )
        .scalars()
        .all()
    )

    # Роль считается созданной, если у неё ещё нет ни одного гранта
    # и каталог что-то обещает: так отчёт отличает новую роль от пустой.
    changes.created = not existing_rows and bool(spec.grants)

    existing = {_grant_key(row.permission, row.effect): row for row in existing_rows}
    wanted = {_grant_key(p, e): (p, e) for p, e in spec.grants}

    for key, (permission, effect) in wanted.items():
        if key in existing:
            continue
        session.add(
            RolePermission(role_id=role.id, permission=permission, effect=effect)
        )
        changes.added_grants.append(key)

    if prune:
        for key, row in existing.items():
            if key not in wanted:
                await session.delete(row)
                changes.removed_grants.append(key)

    if spec.parents:
        current_parents = set(
            (
                await session.execute(
                    select(Role.slug)
                    .join(role_parents, Role.id == role_parents.c.parent_id)
                    .where(role_parents.c.role_id == role.id)
                )
            ).scalars()
        )
        missing = [s for s in spec.parents if s not in current_parents]
        if missing:
            parent_ids = (
                (await session.execute(select(Role.id).where(Role.slug.in_(missing))))
                .scalars()
                .all()
            )
            if parent_ids:
                await session.execute(
                    insert(role_parents)
                    .values([{"role_id": role.id, "parent_id": p} for p in parent_ids])
                    .on_conflict_do_nothing()
                )
                changes.added_parents.extend(missing)

    return changes


async def _grant_owner(session, user_id: int) -> bool:
    """Выдаёт роль владельца. True — роль действительно добавлена."""
    owner_id = (
        await session.execute(select(Role.id).where(Role.slug == ROLE_OWNER))
    ).scalar_one_or_none()
    if owner_id is None:
        raise SeedError(f"роль {ROLE_OWNER} не найдена — сначала примените сидер")

    # Берём только id: у User есть joined-загрузки коллекций, и выборка
    # самой модели потребовала бы .unique() — для проверки существования
    # это лишняя работа.
    user_exists = (
        await session.execute(select(User.id).where(User.id == user_id))
    ).scalar_one_or_none()
    if user_exists is None:
        raise SeedError(f"пользователь {user_id} не найден")

    result = await session.execute(
        insert(UserRole)
        .values(user_id=user_id, role_id=owner_id, scope=None, reason="seed")
        # Повторный запуск не должен падать на уникальном индексе.
        .on_conflict_do_nothing()
        .returning(UserRole.id)
    )
    return result.scalar_one_or_none() is not None


async def seed_roles(
    *,
    apply: bool = False,
    prune: bool = False,
    owner_user_id: Optional[int] = None,
    specs: Sequence[RoleSpec] = ROLES,
    permissions: Iterable = PERMISSIONS,
) -> SeedReport:
    """Приводит системные роли к каталогу.

    apply=False (по умолчанию) считает расхождения и откатывает транзакцию:
    отчёт тот же, что и при apply=True, но в БД ничего не остаётся.
    """
    report = SeedReport()

    async with db_helper.session_factory() as session:
        repo = PgRbacRepository(PgAdapter(session, Role))
        report.permissions_synced = await repo.upsert_permissions(
            ((p.code, p.service, p.description) for p in permissions),
            is_system=True,
        )

        # Порядок важен: роль-потомок ссылается на родителя, и тот
        # к этому моменту должен существовать. В каталоге роли уже
        # перечислены от базовой к старшей.
        for spec in specs:
            report.roles.append(await _seed_role(session, spec, prune=prune))
            # Flush после каждой роли: следующая ищет родителя по slug.
            await session.flush()

        if owner_user_id is not None:
            granted = await _grant_owner(session, owner_user_id)
            report.owner_granted_to = owner_user_id if granted else None

        if apply:
            await session.commit()
        else:
            await session.rollback()

    if apply:
        # Кэш прав держит вычисленные наборы — после правки грантов
        # он обязан протухнуть, иначе изменения увидят только новые сессии.
        await cache.bump_version()

    return report


def _print(report: SeedReport, *, apply: bool) -> None:
    mode = "применено" if apply else "предпросмотр (ничего не изменено)"
    print(f"RBAC-сидер — {mode}")
    print(f"прав в каталоге: {report.permissions_synced}")

    changed = report.changed
    if not changed:
        print("роли уже соответствуют каталогу")
    else:
        for item in changed:
            print(" ", item.describe())

    if report.owner_granted_to is not None:
        print(f"роль {ROLE_OWNER} выдана пользователю {report.owner_granted_to}")

    if not apply and changed:
        print("\nприменить: python -m modules.rbac.seed --apply")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m modules.rbac.seed",
        description="Создаёт базовые роли и доводит их гранты до каталога.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="записать изменения; без него показывается только предпросмотр",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="снять гранты, которых нет в каталоге (по умолчанию не трогаются)",
    )
    parser.add_argument(
        "--owner",
        type=int,
        metavar="USER_ID",
        help=f"выдать роль {ROLE_OWNER} пользователю с этим id",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        report = asyncio.run(
            seed_roles(apply=args.apply, prune=args.prune, owner_user_id=args.owner)
        )
    except SeedError as error:
        # Ожидаемая ошибка ввода: трейсбек здесь только мешает.
        print(f"ошибка: {error}")
        return 1

    _print(report, apply=args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
