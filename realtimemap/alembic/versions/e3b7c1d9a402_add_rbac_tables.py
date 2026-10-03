"""add rbac tables

Revision ID: e3b7c1d9a402
Revises: d7e2a4c9b015
Create Date: 2026-10-02 12:00:00.000000

Системные роли сеет modules/rbac/sync.py. NULLS NOT DISTINCT требует PG 15+.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e3b7c1d9a402"
down_revision: Union[str, None] = "d7e2a4c9b015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

effect_enum = postgresql.ENUM(
    "allow", "deny", name="permission_effect", create_type=False
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    """Upgrade schema."""
    effect_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("service", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column(
            "is_system", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_permissions")),
        sa.UniqueConstraint("code", name=op.f("uq_permissions_code")),
    )
    op.create_index(op.f("ix_permissions_service"), "permissions", ["service"])

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column(
            "priority", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "is_system", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("slug", name=op.f("uq_roles_slug")),
    )

    op.create_table(
        "role_parents",
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "role_id <> parent_id", name=op.f("ck_role_parents_role_not_own_parent")
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name=op.f("fk_role_parents_role_id_roles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["roles.id"],
            name=op.f("fk_role_parents_parent_id_roles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("role_id", "parent_id", name=op.f("pk_role_parents")),
    )

    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=128), nullable=False),
        sa.Column("effect", effect_enum, server_default="allow", nullable=False),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name=op.f("fk_role_permissions_role_id_roles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_role_permissions")),
        sa.UniqueConstraint(
            "role_id", "permission", name=op.f("uq_role_permissions_role_id_permission")
        ),
    )
    op.create_index(
        op.f("ix_role_permissions_role_id"), "role_permissions", ["role_id"]
    )

    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=128), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(length=256), nullable=True),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("granted_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_roles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name=op.f("fk_user_roles_role_id_roles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["users.id"],
            name=op.f("fk_user_roles_granted_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_roles")),
        sa.UniqueConstraint(
            "user_id",
            "role_id",
            "scope",
            name=op.f("uq_user_roles_user_id_role_id_scope"),
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
    op.create_index(op.f("ix_user_roles_role_id"), "user_roles", ["role_id"])

    op.create_table(
        "user_permissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=128), nullable=False),
        sa.Column("effect", effect_enum, server_default="allow", nullable=False),
        sa.Column("scope", sa.String(length=128), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(length=256), nullable=True),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("granted_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_permissions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["users.id"],
            name=op.f("fk_user_permissions_granted_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_permissions")),
        sa.UniqueConstraint(
            "user_id",
            "permission",
            "scope",
            name=op.f("uq_user_permissions_user_id_permission_scope"),
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index("ix_user_permissions_user_id", "user_permissions", ["user_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("user_permissions")
    op.drop_table("user_roles")
    op.drop_table("role_permissions")
    op.drop_table("role_parents")
    op.drop_table("roles")
    op.drop_table("permissions")
    effect_enum.drop(op.get_bind(), checkfirst=True)
