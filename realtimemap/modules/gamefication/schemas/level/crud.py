from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class BaseLevel(BaseModel):
    level: int
    required_exp: int
    color: Optional[str] = None


class LevelRead(BaseLevel):

    model_config = ConfigDict(from_attributes=True)


class LevelCreate(BaseLevel):
    description: Optional[str] = None
    is_active: Optional[bool] = True
    required_exp: Optional[int] = 500

    @field_validator("required_exp", mode="before")
    def required_exp_multiplier(cls, value):
        if isinstance(value, int):
            result = value * Decimal("1.5")
            return int(result.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        return 500
