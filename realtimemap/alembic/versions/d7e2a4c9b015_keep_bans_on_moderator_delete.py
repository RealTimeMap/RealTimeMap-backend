"""keep bans on moderator delete

Revision ID: d7e2a4c9b015
Revises: c1a7f3b9d204
Create Date: 2026-09-26 12:00:00.000000

Бан переживает удаление аккаунта модератора, который его выдал.

До миграции moderator_id был NOT NULL с ON DELETE CASCADE: удаление аккаунта
модератора стирало все выданные им баны, и забаненные пользователи молча
получали доступ обратно. Теперь колонка nullable и ON DELETE SET NULL — так
же, как unbanned_by. Бан без модератора означает «выдан удалённым
пользователем».

Downgrade вернёт NOT NULL только если строк с NULL нет: иначе ALTER упадёт,
и это правильно — молча удалять баны откат не должен.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7e2a4c9b015"
down_revision: Union[str, None] = "c1a7f3b9d204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FK_NAME = "fk_users_bans_moderator_id_users"


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(FK_NAME, "users_bans", type_="foreignkey")
    op.alter_column(
        "users_bans", "moderator_id", existing_type=sa.Integer(), nullable=True
    )
    op.create_foreign_key(
        FK_NAME,
        "users_bans",
        "users",
        ["moderator_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(FK_NAME, "users_bans", type_="foreignkey")
    op.alter_column(
        "users_bans", "moderator_id", existing_type=sa.Integer(), nullable=False
    )
    op.create_foreign_key(
        FK_NAME,
        "users_bans",
        "users",
        ["moderator_id"],
        ["id"],
        ondelete="CASCADE",
    )
