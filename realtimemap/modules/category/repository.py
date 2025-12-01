from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import select

from core.common.repository.category import CategoryRepository
from database.adapter import PgAdapter
from .model import Category
from .schemas import CreateCategory, UpdateCategory

if TYPE_CHECKING:
    pass


class PgCategoryRepository(CategoryRepository):
    def __init__(self, adapter: PgAdapter[Category, CreateCategory, UpdateCategory]):
        super().__init__(adapter)
        self.adapter = adapter

    def get_select_all(self):
        return select(Category).order_by(Category.id.desc())

    async def get_active_categories(self) -> Optional[List[Category]]:
        stmt = self.get_select_all()
        categories = await self.adapter.execute_query(stmt)
        return categories
