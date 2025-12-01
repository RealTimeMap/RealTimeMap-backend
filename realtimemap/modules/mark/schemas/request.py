from datetime import datetime
from typing import Annotated, Optional

from pydantic import Field, model_validator

from .base import Coordinates, BaseMark, CoordinatesOptional, CommonMarkFields


class CreateMarkRequest(BaseMark, Coordinates, CommonMarkFields):
    """
    Class for create mark request.
    """

    category_id: Annotated[int, Field(description="Category id")]


class UpdateMarkRequest(BaseMark, CoordinatesOptional, CommonMarkFields):
    """
    Class for update mark request.
    """

    mark_name: Annotated[Optional[str], Field(None, description="Mark name")]
    start_at: Annotated[Optional[datetime], Field(None, description="Current date")]
    duration: Annotated[Optional[int], Field(None, description="Duration in hours.")]
    category_id: Annotated[Optional[int], Field(None, description="Category id")]

    @model_validator(mode="after")
    def check_lat_lon_pair(self) -> "UpdateMarkRequest":
        if (self.latitude is not None and self.longitude is None) or (
            self.latitude is None and self.longitude is not None
        ):
            raise ValueError(
                "Both latitude and longitude must be provided together or neither"
            )
        return self


class CreateTestMarkRequest(Coordinates):
    count: Annotated[int, Field(..., description="Count of test marks.", gt=0, lt=100)]
    radius: Annotated[
        int, Field(500, description="Search radius in meters.", gt=0, lt=5000)
    ]
