from abc import ABC, abstractmethod

from core.common.repository import BaseRepository
from core.common.schemas import PaginationParams, PaginationResults
from modules.mark_comment.model import Comment
from modules.mark_comment.schemas import CreateComment, UpdateComment


class MarkCommentRepository(BaseRepository[Comment, CreateComment, UpdateComment], ABC):

    @abstractmethod
    async def get_comments(
        self, mark_id: int, params: PaginationParams
    ) -> PaginationResults[Comment]:
        raise NotImplementedError

    @abstractmethod
    async def update_reaction(self):
        raise NotImplementedError

    @abstractmethod
    async def update_comment(self):
        raise NotImplementedError

    @abstractmethod
    async def get_replies(
        self, comment_id: int, params: PaginationParams
    ) -> PaginationResults[Comment]:
        """
        Получение ответов на комментарии
        Args:
            comment_id: ID родительского комментария
            params: Параметры для управления постраничной пагинации

        Returns:

        """
        raise NotImplementedError
