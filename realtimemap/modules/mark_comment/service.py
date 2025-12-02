from typing import TYPE_CHECKING

from core.common.schemas import PaginationParams, PaginationResponse
from errors.http2 import NestingLevelExceededError, NotFoundError, ValidationError
from modules.user.model import User
from .model import Comment
from .schemas import (
    CreateComment,
    CreateCommentRequest,
    CommentReactionRequest,
    CreateCommentReaction,
)
from .schemas.comment.crud import ReadComment, ReadCommentReply

if TYPE_CHECKING:
    from core.common.repository import (
        MarkCommentRepository,
        CommentStatRepository,
        CommentReactionRepository,
    )


class MarkCommentService:
    # Явно указываем слоты для экономии памяти
    __slots__ = (
        "comment_repo",
        "comment_stat_repo",
        "comment_reaction_repo",
    )

    def __init__(
        self,
        comment_repo: "MarkCommentRepository",
        comment_stat_repo: "CommentStatRepository",
        comment_reaction_repo: "CommentReactionRepository",
    ):
        self.comment_repo = comment_repo
        self.comment_stat_repo = comment_stat_repo
        self.comment_reaction_repo = comment_reaction_repo

    async def create_comment(
        self, create_data: CreateCommentRequest, mark_id: int, user: User
    ):
        """
        Метод создает комментарий к метке

        Args:
            create_data: Сырые данные от пользователя
            mark_id: Id метки к которой оставляется комментарий
            user: Авторизованный пользователей

        Returns:

        """
        if create_data.parent_id:
            parent_comment = await self.comment_repo.get_by_id(create_data.parent_id)
            print(parent_comment.id)
            if not parent_comment:
                raise ValidationError(
                    field="parent_id",
                    user_input=create_data.parent_id,
                    input_type="number",
                )
            if parent_comment.parent_id:
                raise NestingLevelExceededError()

        valid_data = CreateComment(
            **create_data.model_dump(), mark_id=mark_id, owner_id=user.id
        )

        await self.before_create_comment()
        result = await self.comment_repo.create(valid_data)
        await self.after_create_comment(result)
        return result

    async def before_create_comment(self) -> None:
        """
        Метод срабатывает перед созданием комментария
        Returns: None

        """
        pass

    async def after_create_comment(self, comment: Comment) -> None:
        """
        Метод срабатывает после созданием комментария

        Args:
            comment: Созданный объект комментария

        Returns: None

        """
        pass

    async def get_comment_by_id(self, comment_id: int) -> Comment:
        result = await self.comment_repo.get_by_id(comment_id)
        if not result:
            raise NotFoundError()
        return result

    async def get_paginated_comment_replies(
        self, comment_id: int, params: PaginationParams
    ) -> PaginationResponse[ReadCommentReply]:
        replies = await self.comment_repo.get_replies(comment_id, params)

        response = PaginationResponse.create(
            [ReadCommentReply.model_validate(reply) for reply in replies.items],
            replies.total,
            params,
        )
        return response

    async def get_pagination_comments(
        self, mark_id: int, params: PaginationParams
    ) -> PaginationResponse[ReadComment]:
        comments = await self.comment_repo.get_comments(mark_id=mark_id, params=params)

        response = PaginationResponse.create(
            [ReadComment.model_validate(comment) for comment in comments.items],
            comments.total,
            params,
        )
        return response

    # TODO Optimization ORM use this on_conflict_do_update
    async def create_or_update_comment_reaction(
        self, comment_id: int, data: CommentReactionRequest, user: User
    ):
        comment_reaction = await self.comment_reaction_repo.get_comment_reaction(
            user.id, comment_id
        )
        if not comment_reaction:
            create_data = CreateCommentReaction(
                comment_id=comment_id, user_id=user.id, **data.model_dump()
            )
            result = await self.comment_reaction_repo.create(create_data)
            return result

        if comment_reaction.reaction_type == data.reaction_type:
            result = await self.comment_reaction_repo.delete(comment_reaction.id)
            return result

        result = await self.comment_reaction_repo.update(comment_reaction.id, data)
        return result
