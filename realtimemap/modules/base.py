from datetime import date
from typing import Any, Dict, TYPE_CHECKING, Optional, Union
from dataclasses import dataclass

from sqlalchemy import MetaData, select, func, and_, cast, Date, Column
from sqlalchemy.orm import DeclarativeBase, declared_attr

from core.config import conf
from modules.mixins import IntIdMixin
from utils import camel_case_to_snake_case

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from starlette.requests import Request


@dataclass
class FilterCondition:
    """Базовый класс для условий фильтрации"""
    value: Any


@dataclass
class Eq(FilterCondition):
    """Равенство: field == value"""
    pass


@dataclass
class Ne(FilterCondition):
    """Неравенство: field != value"""
    pass


@dataclass
class Gt(FilterCondition):
    """Больше: field > value"""
    pass


@dataclass
class Gte(FilterCondition):
    """Больше или равно: field >= value"""
    pass


@dataclass
class Lt(FilterCondition):
    """Меньше: field < value"""
    pass


@dataclass
class Lte(FilterCondition):
    """Меньше или равно: field <= value"""
    pass


@dataclass
class Between(FilterCondition):
    """Между: field BETWEEN value[0] AND value[1]"""
    value: tuple[Any, Any]


@dataclass
class In(FilterCondition):
    """В списке: field IN (value)"""
    value: list[Any]


class BaseSqlModel(DeclarativeBase):
    __abstract__ = True

    metadata = MetaData(naming_convention=conf.db.naming_convention)

    @classmethod
    def _validate_filter_fields(cls, filters: Dict[str, Any]):
        for key, value in filters.items():
            if not hasattr(cls, key):
                raise AttributeError(f"Class {cls.__name__} has no attribute {key}")

    @declared_attr.directive
    def __tablename__(cls) -> str:  # noqa
        return camel_case_to_snake_case(cls.__name__) + "s"

    @classmethod
    def _build_filter_condition(cls, column_attr: Column, filter_value: Union[Any, FilterCondition]):
        """
        Построение условия фильтрации на основе типа значения.

        Args:
            column_attr: Атрибут колонки модели
            filter_value: Значение или объект FilterCondition

        Returns:
            SQL условие для WHERE
        """
        # Если это объект FilterCondition, применяем соответствующий оператор
        if isinstance(filter_value, Eq):
            value = filter_value.value
            if isinstance(value, date):
                return cast(column_attr, Date) == value
            return column_attr == value

        elif isinstance(filter_value, Ne):
            value = filter_value.value
            if isinstance(value, date):
                return cast(column_attr, Date) != value
            return column_attr != value

        elif isinstance(filter_value, Gt):
            value = filter_value.value
            if isinstance(value, date):
                return cast(column_attr, Date) > value
            return column_attr > value

        elif isinstance(filter_value, Gte):
            value = filter_value.value
            if isinstance(value, date):
                return cast(column_attr, Date) >= value
            return column_attr >= value

        elif isinstance(filter_value, Lt):
            value = filter_value.value
            if isinstance(value, date):
                return cast(column_attr, Date) < value
            return column_attr < value

        elif isinstance(filter_value, Lte):
            value = filter_value.value
            if isinstance(value, date):
                return cast(column_attr, Date) <= value
            return column_attr <= value

        elif isinstance(filter_value, Between):
            start, end = filter_value.value
            if isinstance(start, date):
                return cast(column_attr, Date).between(start, end)
            return column_attr.between(start, end)

        elif isinstance(filter_value, In):
            return column_attr.in_(filter_value.value)

        # Если это обычное значение, применяем равенство по умолчанию
        else:
            if isinstance(filter_value, date):
                return cast(column_attr, Date) == filter_value
            return column_attr == filter_value

    @classmethod
    async def count(
        cls,
        session: "AsyncSession",
        filters: Optional[Dict[str, Union[Any, FilterCondition]]] = None,
        column: Optional[Column] = None,
        distinct: bool = False,
    ) -> int:
        """
        Подсчет записей в таблице с поддержкой гибких фильтров и distinct.

        Args:
            session: Асинхронная сессия SQLAlchemy
            filters: Словарь фильтров {field_name: value} или {field_name: FilterCondition}
            column: Колонка для подсчета (по умолчанию id модели)
            distinct: Подсчитывать только уникальные значения

        Returns:
            Количество записей (всегда int, не None)

        Examples:
            # Простой подсчет всех пользователей
            total = await User.count(session)

            # Подсчет с простым фильтром (равенство по умолчанию)
            active = await User.count(session, {"is_active": True})

            # Подсчет с фильтром по дате (равенство)
            today_users = await User.count(session, {"created_at": date.today()})

            # Подсчет с условием "меньше чем"
            from modules.base import Lt
            old_users = await User.count(session, {"created_at": Lt(date(2020, 1, 1))})

            # Подсчет с условием "больше или равно"
            from modules.base import Gte
            recent_users = await User.count(session, {"created_at": Gte(date(2024, 1, 1))})

            # Подсчет с условием "между"
            from modules.base import Between
            period_users = await User.count(
                session,
                {"created_at": Between((date(2024, 1, 1), date(2024, 12, 31)))}
            )

            # Подсчет уникальных владельцев меток
            unique_owners = await Mark.count(session, column=Mark.owner_id, distinct=True)

            # Комбинация нескольких условий
            from modules.base import Gte, Lt
            filtered = await User.count(
                session,
                {
                    "created_at": Gte(yesterday),
                    "is_active": True,
                }
            )
        """
        if filters:
            cls._validate_filter_fields(filters)

        # Определяем колонку для подсчета
        count_column = column if column is not None else cls.id

        # Создаем выражение count с учетом distinct
        if distinct:
            count_expr = func.count(func.distinct(count_column))
        else:
            count_expr = func.count(count_column)

        stmt = select(count_expr).select_from(cls)

        if filters:
            filter_conditions = []
            for field_name, filter_value in filters.items():
                column_attr = getattr(cls, field_name)
                condition = cls._build_filter_condition(column_attr, filter_value)
                filter_conditions.append(condition)

            if filter_conditions:
                stmt = stmt.where(and_(*filter_conditions))

        result = await session.scalar(stmt)
        return result or 0

    async def __admin_repr__(self, _: "Request") -> str:
        return self.__class__.__name__

    async def __admin_select2_repr__(self, _: "Request") -> str:
        return self.__class__.__name__


class Base(BaseSqlModel, IntIdMixin):
    pass
