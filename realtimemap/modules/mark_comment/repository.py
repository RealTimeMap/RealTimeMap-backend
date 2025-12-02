from typing import TYPE_CHECKING, Optional

from sqlalchemy import select, Select
from sqlalchemy.orm import selectinload

from core.common.repository import (
    MarkCommentRepository,
    CommentStatRepository,
    CommentReactionRepository,
)
from core.common.schemas import PaginationParams, PaginationResults
from database.adapter import PgAdapter
from .model import Comment, CommentStat, CommentReaction
from .schemas import (
    CreateComment,
    CreateCommentStat,
    UpdateComment,
    UpdateCommentStat,
    CreateCommentReaction,
    UpdateCommentReaction,
)

if TYPE_CHECKING:
    pass


class PgMarkCommentRepository(MarkCommentRepository):

    def __init__(self, adapter: PgAdapter[Comment, CreateComment, UpdateComment]):
        super().__init__(adapter)
        self.adapter = adapter

    async def create_comment(self, data: CreateComment) -> Comment:
        result = await self.create(data=data)
        return result

    @staticmethod
    def _get_load_strategy():
        loads = [
            # load replies with joined data
            selectinload(Comment.replies).options(
                selectinload(Comment.stats),
                selectinload(Comment.owner),
            ),
            # load for main comment
            selectinload(Comment.owner),
            selectinload(Comment.stats),
        ]
        return loads

    def _get_comment_for_mark(self, mark_id: int) -> Select:
        stmt = (
            select(Comment)
            .where(Comment.mark_id == mark_id, Comment.parent_id.is_(None))
            .options(*self._get_load_strategy())
        ).order_by(Comment.created_at.desc())
        return stmt

    async def get_replies(
        self, comment_id: int, params: PaginationParams
    ) -> PaginationResults[Comment]:
        stmt = (
            select(Comment)
            .where(Comment.parent_id == comment_id, Comment.is_deleted == False)
            .options(selectinload(Comment.owner), selectinload(Comment.stats))
            .order_by(Comment.created_at.desc())
            .limit(params.limit)
            .offset(params.offset)
        )

        replies = await self.adapter.execute_query(stmt)
        replies_count = await self.adapter.count(
            {
                "parent_id": comment_id,
                "is_deleted": False,
            },
        )

        return PaginationResults(replies, replies_count)

    async def get_comments(
        self, mark_id: int, params: PaginationParams
    ) -> PaginationResults[Comment]:
        """
        Загружает комментарии к метке с первым ответом (если есть).
        Args:
            mark_id: ID Метки
            params: Параметры пагинации

        Returns: Результат с пагинацией

        """
        stmt = (
            select(Comment)
            .where(
                Comment.mark_id == mark_id,
                Comment.is_deleted == False,
                Comment.parent_id.is_(None),
            )
            .options(
                selectinload(Comment.replies.and_(Comment.is_deleted == False)).options(
                    selectinload(Comment.owner),
                    selectinload(Comment.stats),
                ),
                selectinload(Comment.owner),
                selectinload(Comment.stats),
            )
            .order_by(Comment.created_at.desc())
            .limit(params.limit)
            .offset(params.offset)
        )

        comments = await self.adapter.execute_query(stmt, unique=True)

        # Оставляем только первый reply как превью
        for comment in comments:
            if comment.replies:
                first_reply = min(comment.replies, key=lambda r: r.created_at)
                comment.replies = [first_reply]

        total_comments = await Comment.count(
            self.adapter.session,
            {"mark_id": mark_id, "is_deleted": False},
        )

        return PaginationResults(comments, total_comments)

    async def update_reaction(self):
        pass

    async def update_comment(self):
        pass


class PgCommentStatRepository(CommentStatRepository):
    def __init__(
        self, adapter: PgAdapter[CommentStat, CreateCommentStat, UpdateCommentStat]
    ):
        super().__init__(adapter)
        self.adapter = adapter

    async def create_base_stat(self, comment_id: int) -> None:
        data = CreateCommentStat(comment_id=comment_id)
        await self.create(data=data)


class PgCommentReactionRepository(CommentReactionRepository):
    def __init__(
        self,
        adapter: PgAdapter[
            CommentReaction, CreateCommentReaction, UpdateCommentReaction
        ],
    ):
        super().__init__(adapter)
        self.adapter = adapter

    async def get_comment_reaction(
        self, user_id: int, comment_id: int
    ) -> Optional[CommentReaction]:
        stmt = select(CommentReaction).where(
            CommentReaction.user_id == user_id, CommentReaction.comment_id == comment_id
        )
        comment = await self.adapter.execute_query_one(stmt)
        return comment
