from datetime import datetime

from sqlalchemy import func, DateTime
from sqlalchemy.orm import Mapped, mapped_column


class CreateMixin:
    """
    Mixin class to add a `created_at` timestamp column to a SQLAlchemy model.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )


class UpdateMixin:
    """
    Mixin class to add an `updated_at` timestamp column to a SQLAlchemy model.
    The `updated_at` column is automatically updated whenever the row is modified.
    """

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )


class TimeMarkMixin(CreateMixin, UpdateMixin):
    """
    Mixin class that combines `CreateMixin` and `UpdateMixin`, providing both
    `created_at` and `updated_at` timestamp columns to a SQLAlchemy model.
    """

    pass
