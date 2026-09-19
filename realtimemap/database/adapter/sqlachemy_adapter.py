import logging
from typing import Generic, Type, Optional, Union, List, Dict, Any, TypeVar

from sqlalchemy import delete, select, Select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.expression import exists as sql_exists

from database.adapter import BaseAdapter
from errors.http2 import IntegrityError as RealTimeMapIntegrityError, ServerError
from my_type import Model, CreateSchema, UpdateSchema

logger = logging.getLogger(__name__)

T = TypeVar("T")


class SQLAlchemyAdapter(
    BaseAdapter[Model, CreateSchema, UpdateSchema],
    Generic[Model, CreateSchema, UpdateSchema],
):
    def __init__(
        self,
        session: AsyncSession,
        model: Type[Model],
        id_field: Optional[str] = "id",
    ):
        self.session = session
        self.model = model
        self.id_field = id_field

    async def get_by_id(
        self,
        item_id: Any,
        join_related: Optional[Union[List[str], Dict[str, Any]]] = None,
        load_strategy: Any = joinedload,
    ) -> Optional[Model]:
        """
        Retrieve a record by its ID from PostgreSQL.

        Args:
            item_id: ID of the record to retrieve
            join_related: Optional list of relationships to load, or dict mapping
                         relationships to load strategies
            load_strategy: Strategy to use for loading relationships (default: joinedload)

        Returns:
            The model instance if found, None otherwise
        """
        stmt: Select[Any] = select(self.model).where(
            getattr(self.model, self.id_field) == item_id
        )

        if join_related:
            if isinstance(join_related, list):
                for relation in join_related:
                    relation_attr = getattr(self.model, relation)
                    stmt = stmt.options(load_strategy(relation_attr))
            elif isinstance(join_related, dict):
                for relation, strategy in join_related.items():
                    relation_attr = getattr(self.model, relation)
                    stmt = stmt.options(strategy(relation_attr))

        result = await self.session.execute(stmt)
        instance = result.scalars().first()
        return instance

    async def create(self, data: CreateSchema, **kwargs: Any) -> Model:
        """
        Create a new record in PostgreSQL.

        Args:
            data: Schema containing the data to create
            **kwargs: Additional fields to include in the record

        Returns:
            The created model instance

        Raises:
            IntegrityError: If the record violates database constraints
            ServerError: If any other error occurs during creation
        """
        try:
            logger.info(f"Create record {data} in Repository: {self.model.__name__}")
            dict_data: Dict[str, Any] = data.model_dump()
            join_related: Optional[List[str]] = kwargs.get("join_related", None)

            db_item = self.model(**dict_data)
            self.session.add(db_item)
            await self.session.flush()
            await self.session.refresh(db_item, join_related)

            return db_item
        except IntegrityError:
            logger.info(
                f"Record {data} already exists in Repository: {self.model.__name__}"
            )
            await self.session.rollback()
            raise RealTimeMapIntegrityError()
        except Exception as e:
            logger.error(
                f"Create record {data} in Repository: {self.model.__name__}", exc_info=e
            )
            await self.session.rollback()
            raise ServerError()

    async def update(self, item_id: Any, data: UpdateSchema) -> Optional[Model]:
        """
        Update an existing record in PostgreSQL.

        Args:
            item_id: ID of the record to update
            data: Schema containing the fields to update

        Returns:
            The updated model instance, or None if record not found

        Raises:
            ServerError: If an error occurs during update
        """
        try:
            instance = await self.get_by_id(item_id)

            if instance is None:
                return None

            update_data = data.model_dump(exclude_unset=True, exclude_none=True)

            for k, v in update_data.items():
                setattr(instance, k, v)

            self.session.add(instance)
            await self.session.flush()
            await self.session.refresh(instance)

            return instance
        except Exception:
            logger.error(f"Update record in {self.model.__name__}, data: {data}")
            await self.session.rollback()
            raise ServerError()

    async def delete(self, record_id: Any) -> Optional[Model]:
        """
        Delete a record from PostgreSQL.

        Args:
            record_id: ID of the record to delete

        Returns:
            The deleted model instance if found and deleted, None otherwise
        """
        try:
            record = await self.get_by_id(record_id)

            if record is None:
                return None

            stmt = delete(self.model).where(
                getattr(self.model, self.id_field) == record_id
            )

            logger.info(
                f"Delete record {record_id} in Repository: {self.model.__name__}. Query: {stmt}"
            )

            await self.session.execute(stmt)
            await self.session.flush()

            return record
        except Exception as e:
            logger.error(
                f"Delete record {record_id} by id in Repository: {self.model.__name__}. ",
                e,
            )
            await self.session.rollback()
            return None

    async def exist(self, record_id: Any, id_field: Optional[str] = None) -> bool:
        """
        Check if a record exists in PostgreSQL.

        Args:
            record_id: ID of the record to check

        Returns:
            True if the record exists, False otherwise
        """
        field_name = id_field or self.id_field
        stmt = select(sql_exists().where(getattr(self.model, field_name) == record_id))
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def execute_query(
        self, query: Select[tuple[T]], unique: Optional[bool] = False
    ) -> List[T]:
        """
        Выполнить произвольный SELECT запрос.
        """
        result = await self.session.execute(query)
        scalars = result.scalars()

        if unique:
            scalars = scalars.unique()

        return list(scalars.all())

    async def execute_query_one(self, query: Select[tuple[T]]) -> Optional[T]:
        """
        Выполнить SELECT запрос и вернуть один результат.
        """
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def execute_scalar(self, query: Select[tuple[Any]]) -> Any:
        """
        Выполнить запрос и вернуть скалярное значение.
        """
        result = await self.session.execute(query)
        return result.scalar()

    async def get_by_field(self, field_name: str, value: Any) -> Optional[Model]:
        """
        Универсальный поиск по полю.
        ДОЛЖЕН БЫТЬ В SQLAlchemyAdapter - переиспользуется во всех моделях.
        """
        if not hasattr(self.model, field_name):
            raise AttributeError(
                f"Model {self.model.__name__} has no field {field_name}"
            )

        query = select(self.model).where(getattr(self.model, field_name) == value)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_fields(self, **fields) -> Optional[Model]:
        """
        Универсальный поиск по нескольким полям.
        ДОЛЖЕН БЫТЬ В SQLAlchemyAdapter - переиспользуется во всех моделях.
        """
        query = select(self.model)
        for field_name, value in fields.items():
            if not hasattr(self.model, field_name):
                raise AttributeError(
                    f"Model {self.model.__name__} has no field {field_name}"
                )
            query = query.where(getattr(self.model, field_name) == value)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()
