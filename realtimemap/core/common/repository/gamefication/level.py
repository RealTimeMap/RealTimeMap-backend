from abc import ABC, abstractmethod
from typing import Optional, List

from core.common.repository import BaseRepository
from modules.gamefication.model import Level
from modules.gamefication.schemas import LevelCreate


class LevelRepository(BaseRepository[Level, LevelCreate, None], ABC):

    @abstractmethod
    async def get_next_level(self, current_level: int) -> Optional[Level]:
        """
        Метод на получение следуйщего уровня относительно переданного
        :param current_level:
        :return:
        """
        raise NotImplementedError

    @abstractmethod
    async def get_max_level(self) -> Optional[Level]:
        """
        Метод получает максимальный уровень среди всех уровней
        :return:
        """
        raise NotImplementedError

    @abstractmethod
    async def get_levels(self) -> List[Level]:
        """
        Возможно на будущее! Список всех уровней
        :return:
        """
        raise NotImplementedError

    @abstractmethod
    async def get_level(self, level: int) -> Optional[Level]:
        """
        Получение уровня по его числовому значению
        :param level:
        :return:
        """
        raise NotImplementedError
