from abc import abstractmethod, ABC
from typing import List, Optional

from sqlalchemy import Select

from core.common.repository.base import BaseRepository
from modules.category.model import Category
from modules.category.schemas import CreateCategory, UpdateCategory


class CategoryRepository(BaseRepository[Category, CreateCategory, UpdateCategory], ABC):
    """
    Абстрактный класс(интерфейс) для репозитория Категорий
    """

    @abstractmethod
    def get_select_all(self) -> Select[Category]:
        raise NotImplementedError

    @abstractmethod
    async def get_active_categories(self) -> Optional[List[Category]]:
        """
        Возвращает все активные категории
        Returns: если категории есть, вернет список категорий: List[Category]

        """
        raise NotImplementedError
