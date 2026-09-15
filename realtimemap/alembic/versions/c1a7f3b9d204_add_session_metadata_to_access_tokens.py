"""add session metadata to access tokens

Revision ID: c1a7f3b9d204
Revises: 89dd248e73ab
Create Date: 2026-09-14 12:00:00.000000

Метаданные сессий для таблицы токенов.

Колонки nullable: у уже выданных токенов метаданных нет и взяться им неоткуда
— такие сессии клиент показывает как неизвестное устройство. Ломать живые
сессии ради полноты данных не стоит.

У session_id и last_used_at есть server_default, хотя приложение всегда
заполняет их само. Это развязка порядка выката: между "миграция применена" и
"приложение перезапущено" старый код продолжает вставлять токены запросом без
новых колонок, и без server_default каждый такой вход падал бы на NOT NULL.
Цена — в схеме живёт default, которым приложение не пользуется.

gen_random_uuid() встроен начиная с PostgreSQL 13; на более старом сервере
миграции понадобится расширение pgcrypto.

Бэкфилл существующих строк сделан на стороне Python: он идёт до установки
server_default и не должен зависеть от версии сервера.
"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1a7f3b9d204"
down_revision: Union[str, None] = "89dd248e73ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "access_tokens",
        sa.Column(
            "session_id",
            sa.Uuid(),
            nullable=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
    )
    op.add_column(
        "access_tokens",
        sa.Column("user_agent", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "access_tokens",
        sa.Column("ip_address", sa.String(length=45), nullable=True),
    )
    op.add_column(
        "access_tokens",
        sa.Column("device_name", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "access_tokens",
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
        ),
    )

    # Существующие сессии: идентификатор — случайный, активность приравнивается
    # к моменту входа, другого источника для неё нет.
    connection = op.get_bind()
    tokens = (
        connection.execute(
            sa.text("SELECT token FROM access_tokens WHERE session_id IS NULL")
        )
        .scalars()
        .all()
    )
    for token in tokens:
        connection.execute(
            sa.text(
                "UPDATE access_tokens SET session_id = :session_id WHERE token = :token"
            ),
            {"session_id": uuid.uuid4(), "token": token},
        )

    op.execute(
        "UPDATE access_tokens SET last_used_at = created_at WHERE last_used_at IS NULL"
    )

    op.alter_column("access_tokens", "session_id", nullable=False)
    op.alter_column("access_tokens", "last_used_at", nullable=False)

    op.create_index(
        op.f("ix_access_tokens_session_id"),
        "access_tokens",
        ["session_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_access_tokens_user_id"),
        "access_tokens",
        ["user_id"],
        unique=False,
    )
    # Список сессий: выборка по владельцу, сортировка по активности.
    op.create_index(
        "ix_access_tokens_user_id_last_used_at",
        "access_tokens",
        ["user_id", "last_used_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_access_tokens_user_id_last_used_at", table_name="access_tokens")
    op.drop_index(op.f("ix_access_tokens_user_id"), table_name="access_tokens")
    op.drop_index(op.f("ix_access_tokens_session_id"), table_name="access_tokens")
    op.drop_column("access_tokens", "last_used_at")
    op.drop_column("access_tokens", "device_name")
    op.drop_column("access_tokens", "ip_address")
    op.drop_column("access_tokens", "user_agent")
    op.drop_column("access_tokens", "session_id")
