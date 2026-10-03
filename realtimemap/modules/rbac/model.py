from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, List, Optional

from fastapi import Request
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modules import BaseSqlModel
from modules.mixins import IntIdMixin, TimeMarkMixin

if TYPE_CHECKING:
    from modules import User


class PermissionEffect(str, PyEnum):
    allow = "allow"
    deny = "deny"


# Роль-потомок получает все гранты родителей. Граф ацикличен — это проверяет
# сервис при записи, БД сама цикл не поймает.
role_parents = Table(
    "role_parents",
    BaseSqlModel.metadata,
    Column(
        "role_id",
        Integer,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "parent_id",
        Integer,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    CheckConstraint("role_id <> parent_id", name="role_not_own_parent"),
)


class Permission(BaseSqlModel, IntIdMixin, TimeMarkMixin):
    """Право из каталога. Гранты ссылаются на него шаблоном, не FK."""

    code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    # Сервис-владелец: им группируется каталог и он же регистрирует права.
    service: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # Системные права объявлены в коде и пересоздаются при старте.
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    def __str__(self) -> str:
        return self.code

    async def __admin_repr__(self, _: Request) -> str:
        return self.code

    async def __admin_select2_repr__(self, _: Request) -> str:
        return self.code


class Role(BaseSqlModel, IntIdMixin, TimeMarkMixin):
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # Ранг роли: управлять ролью может только тот, чей ранг строго выше.
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    # Есть у каждого пользователя неявно, без строки в user_roles.
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    grants: Mapped[List["RolePermission"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    parents: Mapped[List["Role"]] = relationship(
        "Role",
        secondary=role_parents,
        primaryjoin="Role.id == role_parents.c.role_id",
        secondaryjoin="Role.id == role_parents.c.parent_id",
        lazy="selectin",
        # Связь ссылается на ту же Role, поэтому без join_depth selectin-загрузчик
        # молча отказывается работать (защита от бесконечной рекурсии), и parents
        # остаётся незагруженным — в async-сессии это MissingGreenlet при первом
        # обращении. Глубины 1 достаточно: графом выше ходит policy.ancestors
        # в памяти по уже загруженным ролям, ему нужны только прямые родители.
        join_depth=1,
    )

    def __str__(self) -> str:
        return self.slug

    async def __admin_repr__(self, _: Request) -> str:
        return self.slug

    async def __admin_select2_repr__(self, _: Request) -> str:
        return f"{self.slug} ({self.priority})"


class RolePermission(BaseSqlModel, IntIdMixin):
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Код права или шаблон: `mark.comment.delete`, `mark.*`, `*`.
    permission: Mapped[str] = mapped_column(String(128), nullable=False)
    effect: Mapped[PermissionEffect] = mapped_column(
        Enum(PermissionEffect, name="permission_effect"),
        nullable=False,
        default=PermissionEffect.allow,
        server_default=PermissionEffect.allow.value,
    )

    role: Mapped["Role"] = relationship(back_populates="grants")

    __table_args__ = (UniqueConstraint("role_id", "permission"),)

    async def __admin_repr__(self, _: Request) -> str:
        return f"{self.effect.value}:{self.permission}"


class UserRole(BaseSqlModel, IntIdMixin):
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Пусто — роль действует везде. `chat:12` — только в этом чате.
    scope: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # NULL — выдавший удалил аккаунт; назначение остаётся в силе.
    granted_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    role: Mapped["Role"] = relationship(lazy="joined")
    user: Mapped["User"] = relationship(foreign_keys=[user_id])

    __table_args__ = (
        # NULLS NOT DISTINCT: иначе глобальную роль можно выдать дважды.
        UniqueConstraint(
            "user_id", "role_id", "scope", postgresql_nulls_not_distinct=True
        ),
        Index("ix_user_roles_user_id", "user_id"),
    )


class UserPermission(BaseSqlModel, IntIdMixin):
    """Персональное переопределение права поверх ролей."""

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    permission: Mapped[str] = mapped_column(String(128), nullable=False)
    effect: Mapped[PermissionEffect] = mapped_column(
        Enum(PermissionEffect, name="permission_effect", create_type=False),
        nullable=False,
        default=PermissionEffect.allow,
        server_default=PermissionEffect.allow.value,
    )
    scope: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    granted_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    user: Mapped["User"] = relationship(foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint(
            "user_id", "permission", "scope", postgresql_nulls_not_distinct=True
        ),
        Index("ix_user_permissions_user_id", "user_id"),
    )
