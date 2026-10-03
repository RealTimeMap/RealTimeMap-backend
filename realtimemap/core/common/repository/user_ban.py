from abc import ABC, abstractmethod
from typing import List, Optional, Sequence

from modules.user_ban.model import UsersBan
from modules.user_ban.schemas import UpdateUsersBan, UsersBanCreate
from .base import BaseRepository


class UsersBanRepository(BaseRepository[UsersBan, UsersBanCreate, UpdateUsersBan], ABC):
    @abstractmethod
    async def check_active_user_ban(self, user_id: int) -> bool:
        """

        :param user_id:
        :return:
        """
        raise NotImplementedError

    @abstractmethod
    async def ban_user(self, data: UsersBanCreate) -> UsersBan:
        """

        :param data:
        :return:
        """
        raise NotImplementedError

    @abstractmethod
    async def unban_user(self, user_id: int, data: UpdateUsersBan) -> UsersBan:
        """

        :param user_id:
        :param data:
        :return:
        """
        raise NotImplementedError

    @abstractmethod
    async def get_user_bans(self, user_id: int) -> List[UsersBan]:
        """

        :param user_id:
        :return:
        """
        raise NotImplementedError

    @abstractmethod
    async def get_active_user_ban(self, user_id: int) -> Optional[UsersBan]:
        """
        Метод возвращает активный бан пользователя
        :param user_id:
        :return:
        """
        raise NotImplementedError

    @abstractmethod
    async def get_active_bans(self, user_ids: Sequence[int]) -> List[UsersBan]:
        """Активные баны пачки пользователей, по одному свежему на пользователя."""
        raise NotImplementedError
