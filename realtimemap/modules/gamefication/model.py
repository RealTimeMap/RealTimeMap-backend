from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING, List

from sqlalchemy import (
    Integer,
    String,
    Boolean,
    Index,
    ForeignKey,
    Numeric,
    DateTime,
    func,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modules.base import BaseSqlModel
from modules.mixins import IntIdMixin, TimeMarkMixin

if TYPE_CHECKING:
    from modules.user.model import User
    from starlette.requests import Request


class Level(BaseSqlModel, IntIdMixin, TimeMarkMixin):
    """
    Модель для управлениея уровнями
    """

    level: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    required_exp: Mapped[int] = mapped_column(Integer, nullable=False)

    description: Mapped[str] = mapped_column(String(256), nullable=True)

    color: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("required_exp >= 0", name="check_positive_exp"),
        Index("ix_levels_level_active", "level", "is_active"),
    )


class ExpAction(BaseSqlModel, IntIdMixin, TimeMarkMixin):
    """
    Моедль для настройки опыта за различные действия
    """

    action_type: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )

    base_exp: Mapped[int] = mapped_column(Integer, nullable=False)

    name: Mapped[str] = mapped_column(String(64), nullable=True)
    description: Mapped[str] = mapped_column(String(256), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    is_repeatable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    max_per_day: Mapped[int] = mapped_column(Integer, nullable=False)

    history_records: Mapped[List["UserExpHistory"]] = relationship(
        "UserExpHistory", back_populates="action", lazy="noload"
    )

    async def __admin_repr__(self, _: "Request") -> str:
        return self.action_type

    async def __admin_select2_repr__(self, _: "Request") -> str:
        return self.action_type


class UserExpHistory(BaseSqlModel, IntIdMixin, TimeMarkMixin):
    """
    Модель истории начислений
    """

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    action_id: Mapped[int] = mapped_column(
        ForeignKey("exp_actions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    is_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    base_exp: Mapped[int] = mapped_column(Integer, nullable=False)

    multiplier: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("1.0"), nullable=False
    )

    total_exp: Mapped[int] = mapped_column(Integer, nullable=False)

    source_type: Mapped[str] = mapped_column(
        String(32), nullable=True, index=True
    )  # Название таблицы от которой мы начислели опыт

    source_id: Mapped[int] = mapped_column(
        Integer, nullable=True
    )  # id записи той таблицы за что мы начислили опыт

    revoked_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=True, onupdate=func.now()
    )
    revoked_reason: Mapped[str] = mapped_column(String(255), nullable=True)

    level_before: Mapped[int] = mapped_column(Integer, nullable=False)
    level_after: Mapped[int] = mapped_column(Integer, nullable=False)

    exp_before: Mapped[int] = mapped_column(Integer, nullable=False)

    subscription_plan_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subscription_plans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user: Mapped["User"] = relationship("User", back_populates="experience_history")
    action: Mapped["ExpAction"] = relationship(
        "ExpAction", back_populates="history_records"
    )
    __table_args__ = (
        # Быстрая проверка лимитов
        Index(
            "ix_exp_hist_user_action_date",
            "user_id",
            "action_id",
            "created_at",
            postgresql_where=(not is_revoked),
        ),
        # Поиск по источнику
        Index("ix_exp_hist_source", "source_type", "source_id"),
        # Активные начисления пользователя
        Index("ix_exp_hist_user_active", "user_id", "is_revoked", "created_at"),
        # Аналитика по подпискам
        Index("ix_exp_hist_subscription", "subscription_plan_id", "created_at"),
        # Поиск повышений уровня
        Index(
            "ix_exp_hist_level_up",
            "user_id",
            "level_after",
            postgresql_where=(level_before != level_after),
        ),
        CheckConstraint("total_exp >= 0", name="check_positive_total"),
        CheckConstraint("multiplier > 0", name="check_positive_multiplier"),
    )
