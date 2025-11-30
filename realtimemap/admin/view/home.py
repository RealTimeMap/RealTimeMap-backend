import asyncio
from datetime import datetime, timedelta, date, timezone
from functools import lru_cache
from typing import TYPE_CHECKING, Tuple

from pydantic import BaseModel, computed_field
from sqlalchemy import select, func
from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView

from modules import User, UserExpHistory, Mark
from modules.kpi.schemas import (
    MarksKpi,
    ActivityKpi,
    NewMarksKpi,
    ContentMakerKpi,
    UsersKpi,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class MonthUserStat(BaseModel):
    timestamp: date
    count: int

    @computed_field
    @property
    def month(self) -> str:
        return self.timestamp.month


class HomeView(CustomView):
    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        session: "AsyncSession" = request.state.session

        active_data, users_kpi, marks_kpi, new_marks_kpi, content_maker_kpi = (
            await asyncio.gather(
                self.get_active_users_with_change(session),
                self.get_users_with_change(session),
                self.get_marks_with_change(session),
                self.get_new_marks_kpi(session),
                self.get_content_maker_kpi(session),
            )
        )
        # users_chart_data = await self.get_users_group(session)

        return templates.TemplateResponse(
            "home.html",
            {
                "request": request,
                # "users_chart_data": [
                #     chart_data.model_dump(mode="json")
                #     for chart_data in users_chart_data
                # ],
                "active_kpi": active_data.model_dump(mode="json"),
                "users_kpi": users_kpi.model_dump(mode="json"),
                "marks_kpi": marks_kpi.model_dump(mode="json"),
                "new_marks_kpi": new_marks_kpi.model_dump(mode="json"),
                "content_maker_kpi": content_maker_kpi.model_dump(mode="json"),
            },
        )

    @staticmethod
    @lru_cache(maxsize=1)
    def get_dates() -> Tuple[datetime, date, date]:
        """
        Возвращает текущее время, сегодняшнюю дату, вчерашнюю дату.

        Все даты рассчитываются в UTC timezone для консистентности.

        Returns:
            tuple: Кортеж из трех элементов:
                - now (datetime): Текущее время с timezone UTC
                - today (date): Сегодняшняя дата
                - yesterday (date): Вчерашняя дата
        """
        now = datetime.now(timezone.utc)
        today = now.date()
        yesterday = today - timedelta(days=1)
        return now, today, yesterday

    async def get_users_with_change(self, session: "AsyncSession") -> UsersKpi:
        """
        Получение KPI по пользователям.

        Сравнивает общее количество пользователей, новых пользователей сегодня
        и новых пользователей вчера.

        Args:
            session: Асинхронная сессия SQLAlchemy для выполнения запросов

        Returns:
            UsersKpi: Объект с метриками пользователей
        """
        _, today, yesterday = self.get_dates()

        total_users, new_users_today, new_users_yesterday = await asyncio.gather(
            User.count(session),
            User.count(session, {"created_at": today}),
            User.count(session, {"created_at": yesterday}),
        )

        return UsersKpi(
            total_users=total_users,
            new_users_today=new_users_today,
            new_users_yesterday=new_users_yesterday,
        )

    async def get_new_marks_kpi(self, session: "AsyncSession") -> NewMarksKpi:
        """
        Получение KPI по новым меткам.

        Сравнивает количество новых меток созданных сегодня, вчера
        и общее количество всех меток.

        Args:
            session: Асинхронная сессия SQLAlchemy для выполнения запросов

        Returns:
            NewMarksKpi: Объект с метриками новых меток
        """
        _, today, yesterday = self.get_dates()

        new_marks_today, new_marks_yesterday, total_marks = await asyncio.gather(
            Mark.count(session, {"created_at": today}),
            Mark.count(session, {"created_at": yesterday}),
            Mark.count(session),
        )

        return NewMarksKpi(
            new_marks_today=new_marks_today,
            new_marks_yesterday=new_marks_yesterday,
            total_marks=total_marks,
        )

    async def get_active_users_with_change(
        self, session: "AsyncSession"
    ) -> ActivityKpi:
        """
        Получение KPI активности пользователей.

        Сравнивает количество активных пользователей сегодня
        с количеством активных пользователей вчера.

        Args:
            session: Асинхронная сессия SQLAlchemy для выполнения запросов

        Returns:
            ActivityKpi: Объект с метриками активности пользователей
        """
        _, today, yesterday = self.get_dates()

        active_24h, active_prev_24h = await asyncio.gather(
            UserExpHistory.count(session, {"created_at": today, "is_revoked": False}),
            UserExpHistory.count(
                session, {"created_at": yesterday, "is_revoked": False}
            ),
        )

        return ActivityKpi(
            active_24h=active_24h,
            active_prev_24h=active_prev_24h,
        )

    async def get_marks_with_change(self, session: "AsyncSession") -> MarksKpi:
        """
        Получение KPI по меткам.

        Возвращает метрики: активные метки сегодня, все активные метки,
        завершенные метки и общее количество меток.

        Args:
            session: Асинхронная сессия SQLAlchemy для выполнения запросов

        Returns:
            MarksKpi: Объект с метриками меток
        """
        _, today, yesterday = self.get_dates()

        active_marks_today, active_marks, ended_marks, total_marks = (
            await asyncio.gather(
                Mark.count(session, {"created_at": today, "is_ended": False}),
                Mark.count(session, {"is_ended": False}),
                Mark.count(session, {"is_ended": True}),
                Mark.count(session),
            )
        )

        return MarksKpi(
            active_marks_24h=active_marks_today,
            active_marks=active_marks,
            ended_marks=ended_marks,
            total_marks=total_marks,
        )

    async def get_content_maker_kpi(self, session: "AsyncSession") -> ContentMakerKpi:
        """
        Получение KPI создателей контента.

        Сравнивает количество уникальных создателей меток сегодня
        с количеством уникальных создателей вчера.

        Args:
            session: Асинхронная сессия SQLAlchemy для выполнения запросов

        Returns:
            ContentMakerKpi: Объект с метриками создателей контента
        """
        _, today, yesterday = self.get_dates()

        today_content_maker, yesterday_content_maker = await asyncio.gather(
            Mark.count(
                session,
                column=Mark.owner_id,
                filters={"created_at": today},
                distinct=True,
            ),
            Mark.count(
                session,
                column=Mark.owner_id,
                filters={"created_at": yesterday},
                distinct=True,
            ),
        )

        return ContentMakerKpi(
            create_maker_today=today_content_maker,
            create_maker_yesterday=yesterday_content_maker,
        )

    async def get_users_group(self, session: "AsyncSession"):
        now, today, yesterday = self.get_dates()
        users_stmt = (
            select(
                func.date(User.created_at).label("date"),
                func.count(User.id).label("count"),
            )
            .where(User.created_at >= now - timedelta(days=30))
            .group_by(func.date(User.created_at))
            .order_by("date")
        )
        result = await session.execute(users_stmt)
        return [
            MonthUserStat(timestamp=row.date, count=row.count) for row in result.all()
        ]
