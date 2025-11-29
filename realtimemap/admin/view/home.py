from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Literal, Union, Annotated

from pydantic import BaseModel, Field, computed_field, ConfigDict, model_validator
from sqlalchemy import select, cast, Date
from sqlalchemy.sql import func
from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView

from modules import User, UserExpHistory, Mark

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


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
        return self.change > 0

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


class HomeView(CustomView):
    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        session: "AsyncSession" = request.state.session
        active_data = await self._get_active_users_with_change(session)
        users_kpi = await self._get_users_with_change(session)
        marks_kpi = await self._get_marks_with_change(session)
        new_marks_kpi = await self._get_new_marks_kpi(session)
        content_maker_kpi = await self._get_content_maker_kpi(session)
        return templates.TemplateResponse(
            "home.html",
            {
                "request": request,
                "active_kpi": active_data.model_dump(mode="json"),
                "users_kpi": users_kpi.model_dump(mode="json"),
                "marks_kpi": marks_kpi.model_dump(mode="json"),
                "new_marks_kpi": new_marks_kpi.model_dump(mode="json"),
                "content_maker_kpi": content_maker_kpi.model_dump(mode="json"),
            },
        )

    async def _get_users_with_change(self, session: "AsyncSession") -> UsersKpi:
        total_users = await self._get_total_user(session)
        new_users_today = await self._get_today_register_user(session)
        new_users_yesterday = await self._get_yesterday_register_user(session)
        return UsersKpi(
            total_users=total_users,
            new_users_today=new_users_today,
            new_users_yesterday=new_users_yesterday,
        )

    @staticmethod
    async def _get_total_user(session: "AsyncSession") -> int:
        stmt = select(func.count(User.id))
        total_user = await session.scalar(stmt)
        return total_user

    @staticmethod
    async def _get_today_register_user(session: "AsyncSession") -> int:
        now = datetime.now()
        stmt = select(func.count(User.id)).where(
            cast(User.created_at, Date) == now.date()
        )
        total_user = await session.execute(stmt)
        return total_user.scalar()

    @staticmethod
    async def _get_yesterday_register_user(session: "AsyncSession") -> int:
        now = datetime.now()
        yesterday = now.date() - timedelta(days=1)
        stmt = select(func.count(User.id)).where(
            cast(User.created_at, Date) == yesterday
        )
        total_user = await session.execute(stmt)
        return total_user.scalar()

    @staticmethod
    async def _get_today_created_marks(session: "AsyncSession") -> int:
        """Подсчет меток созданных сегодня"""
        now = datetime.now()
        stmt = select(func.count(Mark.id)).where(
            cast(Mark.created_at, Date) == now.date()
        )
        result = await session.execute(stmt)
        return result.scalar()

    @staticmethod
    async def _get_yesterday_created_marks(session: "AsyncSession") -> int:
        """Подсчет меток созданных вчера"""
        now = datetime.now()
        yesterday = now.date() - timedelta(days=1)
        stmt = select(func.count(Mark.id)).where(
            cast(Mark.created_at, Date) == yesterday
        )
        result = await session.execute(stmt)
        return result.scalar()

    @staticmethod
    async def _get_total_marks(session: "AsyncSession") -> int:
        """Подсчет общего количества меток"""
        stmt = select(func.count(Mark.id))
        return await session.scalar(stmt)

    async def _get_new_marks_kpi(self, session: "AsyncSession") -> NewMarksKpi:
        """Получение KPI новых меток"""
        new_marks_today = await self._get_today_created_marks(session)
        new_marks_yesterday = await self._get_yesterday_created_marks(session)
        total_marks = await self._get_total_marks(session)
        return NewMarksKpi(
            new_marks_today=new_marks_today,
            new_marks_yesterday=new_marks_yesterday,
            total_marks=total_marks,
        )

    @staticmethod
    async def _get_active_users_with_change(session: "AsyncSession") -> ActivityKpi:
        """
        Количество активных пользователь за 24 часа
        """
        now = datetime.now()
        stmt = select(func.count(UserExpHistory.user_id.distinct())).where(
            UserExpHistory.created_at >= now - timedelta(hours=24),
            UserExpHistory.is_revoked == False,
        )
        active_24h = await session.scalar(stmt)

        active_prev_24h_stmt = select(
            func.count(UserExpHistory.user_id.distinct())
        ).where(
            UserExpHistory.created_at >= now - timedelta(hours=48),
            UserExpHistory.created_at < now - timedelta(hours=24),
            UserExpHistory.is_revoked == False,
        )
        active_prev_24h = await session.scalar(active_prev_24h_stmt)

        return ActivityKpi(
            active_24h=active_24h,
            active_prev_24h=active_prev_24h,
        )

    @staticmethod
    async def _get_marks_with_change(session: "AsyncSession") -> MarksKpi:
        now = datetime.now()
        today = now - timedelta(hours=24)
        active_marks_24h_stmt = select(func.count(Mark.id)).where(
            cast(Mark.start_at, Date) <= today,
            not Mark.is_ended,
        )
        active_marks_24h = await session.scalar(active_marks_24h_stmt)
        active_marks = await Mark.count(session, {"is_ended": False})
        ended_marks = await Mark.count(session, {"is_ended": True})
        total_marks = await Mark.count(session)
        return MarksKpi(
            active_marks_24h=active_marks_24h,
            active_marks=active_marks,
            ended_marks=ended_marks,
            total_marks=total_marks,
        )

    @staticmethod
    async def _get_today_content_makers(session: "AsyncSession") -> int:
        now = datetime.now()
        today_content_makers_stmt = select(func.count(Mark.owner_id.distinct())).where(
            cast(Mark.created_at, Date) == now.date()
        )
        today_content_makers = await session.scalar(today_content_makers_stmt)
        return today_content_makers

    @staticmethod
    async def _get_yesterday_content_makers(session: "AsyncSession") -> int:
        now = datetime.now()
        yesterday = now.date() - timedelta(days=1)
        stmt = select(func.count(Mark.owner_id.distinct())).where(
            cast(Mark.created_at, Date) == yesterday
        )
        yesterday_content_makers = await session.scalar(stmt)
        return yesterday_content_makers

    async def _get_content_maker_kpi(self, session: "AsyncSession") -> ContentMakerKpi:
        today_content_maker = await self._get_today_content_makers(session)
        yesterday_content_maker = await self._get_yesterday_content_makers(session)
        return ContentMakerKpi(
            create_maker_today=today_content_maker,
            create_maker_yesterday=yesterday_content_maker,
        )
