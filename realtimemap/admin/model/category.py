from typing import Dict, Any

from pydantic_core import PydanticCustomError
from pydantic_extra_types.color import Color
from starlette.requests import Request
from starlette_admin import ColorField
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError

from modules import Category


class AdminCategory(ModelView):
    label = "Categories"
    fields = [
        Category.id,
        Category.category_name,
        ColorField("color"),
        Category.icon,
        Category.is_active,
    ]

    async def validate(self, request: Request, data: Dict[str, Any]) -> None:
        errors: Dict[str, str] = dict()

        if data.get("color", None):
            color: str = data.get("color")
            try:
                Color(color)
            except PydanticCustomError:
                errors["color"] = "Invalid color"

        if len(errors) > 0:
            raise FormValidationError(errors)

        return await super().validate(request, data)
