from typing import Any, Annotated

from fastapi import UploadFile
from pydantic import BaseModel, Field, field_validator, ConfigDict
from pydantic_core.core_schema import ValidationInfo
from pydantic_extra_types.color import Color

from utils.url_generator import generate_full_image_url


class BaseCategory(BaseModel):
    category_name: Annotated[
        str, Field(..., max_length=64, description="Category name")
    ]
    color: Annotated[str, Field(..., max_length=7, description="Hex code for color")]

    @field_validator("color", mode="before")
    def validate_and_convert_color_to_hex(cls, v: Any) -> str:
        """
        Convert color to hex format.

        Handles:
        1. Already hex string (from cache) → pass through
        2. Color name or other format (from input) → convert to hex
        """
        # Already a hex string (from cache)
        if isinstance(v, str) and v.startswith("#") and len(v) == 7:
            return v

        # Convert to hex
        try:
            color_obj = Color(v)
            return color_obj.as_hex()
        except ValueError as e:
            raise ValueError(f"Invalid color value: '{v}'") from e


class CreateCategory(BaseCategory):
    icon: Annotated[UploadFile, Field(..., description="Upload image")]


class UpdateCategory(CreateCategory):
    pass


class ReadCategory(BaseCategory):
    id: Annotated[int, Field(ge=0, description="Category id")]
    icon: Annotated[str, Field(..., description="Image icon url")]

    @field_validator("icon", mode="before")
    @classmethod
    def validate_icon(cls, v, info: ValidationInfo):
        return generate_full_image_url(v, info)

    model_config = ConfigDict(from_attributes=True)
