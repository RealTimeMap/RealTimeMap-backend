from typing import Literal, Union, Annotated

from pydantic import computed_field, ConfigDict, Field, BaseModel, model_validator


class BaseKPIWithTrend(BaseModel):
    current_value: Annotated[
        Union[int, float], Field(0, description="Текущее значение")
    ]
    previous_value: Annotated[
        Union[int, float], Field(0, description="Предыдущее значение")
    ]

    model_config = ConfigDict(validate_assignment=True)

    @computed_field
    @property
    def change(self) -> int | float:
        return self.current_value - self.previous_value

    @computed_field
    @property
    def change_percent(self) -> float:
        if self.previous_value == 0:
            return 100.0 if self.change > 0 else 0.0
        return round((self.change / self.previous_value) * 100, 1)

    @computed_field
    @property
    def is_growing(self) -> bool:
        return self.change < 0 and self.previous_value == 0

    @computed_field
    @property
    def trend(self) -> Literal["up", "down", "stable"]:
        if self.change > 0:
            return "up"
        elif self.change < 0:
            return "down"
        return "stable"

    @computed_field
    @property
    def trend_icon(self) -> str:
        return {"up": "fa-arrow-up", "down": "fa-arrow-down", "stable": "fa-minus"}[
            self.trend
        ]

    @computed_field
    @property
    def trend_color(self) -> str:
        return {"up": "text-success", "down": "text-danger", "stable": "text-muted"}[
            self.trend
        ]

    @computed_field
    @property
    def change_text(self) -> str:
        sign = "+" if self.change > 0 else ""
        if isinstance(self.change, float):
            return f"{sign}{self.change:.1f}"
        return f"{sign}{self.change}"


class UsersKpi(BaseKPIWithTrend):
    total_users: int = 0
    new_users_today: int = 0
    new_users_yesterday: int = 0

    @model_validator(mode="after")
    def set_values(self) -> "UsersKpi":
        object.__setattr__(self, "current_value", self.new_users_today)
        object.__setattr__(self, "previous_value", self.new_users_yesterday)
        return self


class ActivityKpi(BaseKPIWithTrend):
    active_24h: int = Field(0, description="Активность за 24 часа")
    active_prev_24h: int = Field(0, description="Активность за прошлые 24 часа")

    @model_validator(mode="after")
    def set_values(self) -> "ActivityKpi":
        object.__setattr__(self, "current_value", self.active_24h)
        object.__setattr__(self, "previous_value", self.active_prev_24h)
        return self


class NewMarksKpi(BaseKPIWithTrend):
    new_marks_today: int = 0
    new_marks_yesterday: int = 0
    total_marks: int = 0

    @model_validator(mode="after")
    def set_values(self) -> "NewMarksKpi":
        object.__setattr__(self, "current_value", self.new_marks_today)
        object.__setattr__(self, "previous_value", self.new_marks_yesterday)
        return self


class MarksKpi(BaseKPIWithTrend):
    total_marks: int = 0
    active_marks_24h: int = 0
    active_marks: int = 0
    ended_marks: int = 0

    @model_validator(mode="after")
    def set_values(self) -> "MarksKpi":
        object.__setattr__(self, "current_value", self.active_marks)
        object.__setattr__(self, "previous_value", self.ended_marks)
        return self


class ContentMakerKpi(BaseKPIWithTrend):
    create_maker_today: int = 0
    create_maker_yesterday: int = 0

    @model_validator(mode="after")
    def set_values(self) -> "ContentMakerKpi":
        object.__setattr__(self, "current_value", self.create_maker_today)
        object.__setattr__(self, "previous_value", self.create_maker_yesterday)
        return self


class MarkCategoryStat(BaseModel):
    category_name: str
    total_marks: int
    model_config = ConfigDict(from_attributes=True)
