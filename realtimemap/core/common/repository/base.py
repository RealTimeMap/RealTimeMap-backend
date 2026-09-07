from abc import ABC
from typing import Generic, Any, Optional, Union, List, Dict

from database.adapter import BaseAdapter
from my_type import CreateSchema, UpdateSchema, Model


class IBaseRepository(
    BaseAdapter[Model, CreateSchema, UpdateSchema],
    ABC,
    Generic[Model, CreateSchema, UpdateSchema],
):
    pass


class BaseRepository(IBaseRepository[Model, CreateSchema, UpdateSchema]):
    """
    Base Repository class for incapsulated adapter
    """

    def __init__(self, adapter: BaseAdapter[Model, CreateSchema, UpdateSchema]):
        self.adapter = adapter

    async def create(self, data: CreateSchema, **kwargs: Any) -> Model:
        return await self.adapter.create(data, **kwargs)

    async def update(self, record_id: int, data: UpdateSchema, **kwargs: Any) -> Model:
        return await self.adapter.update(record_id, data)

    async def delete(self, record_id: int, **kwargs: Any) -> Model:
        return await self.adapter.delete(record_id)

    async def get_by_id(
        self,
        item_id: Any,
        join_related: Optional[Union[List[str], Dict[str, Any]]] = None,
        load_strategy: Any = None,
    ) -> Optional[Model]:
        return await self.adapter.get_by_id(item_id, join_related, load_strategy)

    async def exist(self, record_id: Any, id_field: Optional[str] = None) -> bool:
        return await self.adapter.exist(record_id, id_field)
