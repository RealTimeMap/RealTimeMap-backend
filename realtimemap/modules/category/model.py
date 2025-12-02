from typing import Optional

from jinja2 import Template
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_file import ImageField
from starlette.requests import Request

from modules.base import BaseSqlModel
from modules.mixins import IntIdMixin


class Category(BaseSqlModel, IntIdMixin):
    __tablename__ = "categories"
    category_name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    color: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    icon: Mapped[ImageField] = mapped_column(
        ImageField(upload_storage="category"), nullable=False
    )

    # Meta Fields
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    async def __admin_repr__(self, _: Request):
        return self.category_name

    async def __admin_select2_repr__(self, _: Request) -> str:
        temp = Template(
            """<div style="display: flex; flex-direction: column; gap: 4px;">
                <strong>{{category_name}}</strong>
                <span style="font-size: 0.9em; color: #666;">ID: {{id}}{% if color %} | Color: <span style="display: inline-block; width: 12px; height: 12px; background: {{color}}; border: 1px solid #ccc; border-radius: 2px; vertical-align: middle;"></span> {{color}}{% endif %}{% if not is_active %} | <span style="color: #f44336;">Inactive</span>{% endif %}</span>
            </div>""",
            autoescape=True,
        )
        return temp.render(
            category_name=self.category_name,
            id=self.id,
            color=self.color,
            is_active=self.is_active
        )
