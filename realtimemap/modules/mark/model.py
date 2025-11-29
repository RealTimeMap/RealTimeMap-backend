from datetime import datetime, timedelta
from typing import TYPE_CHECKING, List

from geoalchemy2 import Geometry
from sqlalchemy import ForeignKey, String, Index, DateTime, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy_file import ImageField

from modules.base import BaseSqlModel
from modules.mixins import IntIdMixin, TimeMarkMixin

if TYPE_CHECKING:
    from modules.user.model import User
    from modules.category.model import Category
    from modules.mark_comment.model import Comment
    from fastapi import Request


class Mark(BaseSqlModel, IntIdMixin, TimeMarkMixin):
    mark_name: Mapped[str] = mapped_column(String(128), nullable=False)
    geom: Mapped[Geometry] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326), nullable=False
    )
    photo: Mapped[ImageField] = mapped_column(
        ImageField(upload_storage="marks", multiple=True), nullable=True
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    owner: Mapped["User"] = relationship(
        "User",
        foreign_keys=[owner_id],
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped["Category"] = relationship(
        "Category",
        foreign_keys=[category_id],
    )
    additional_info: Mapped[str] = mapped_column(String(256), nullable=True)

    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False, default=12)

    is_ended: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    geohash: Mapped[str] = mapped_column(String(64), nullable=False)

    # RS
    comments: Mapped[List["Comment"]] = relationship(back_populates="mark")
    __table_args__ = (Index("idx_locations_geom", geom, postgresql_using="gist"),)

    @property
    def check_ended(self) -> bool:
        if datetime.now() > self.end_at:
            return True
        return False

    @property
    def end_at(self) -> datetime:
        """
        Calculates the end datetime by adding the duration to the start datetime.

        Returns:
            datetime: The calculated end datetime, which is the start_at datetime plus
                     the duration in hours.
        """
        return self.start_at + timedelta(hours=self.duration)

    def __str__(self):
        return f"{self.mark_name}: {self.id}"

    def __admin_repr__(self, _: "Request") -> str:
        return f"Mark #{self.id}: {self.mark_name}"
