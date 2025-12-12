from typing import Annotated, TYPE_CHECKING

from fastapi import APIRouter, Depends

from core.common.schemas import PaginationParams, PaginationResponse
from dependencies.checker import check_mark_exist
from modules.mark_comment.dependencies import get_mark_comment_service
from modules.mark_comment.schemas import (
    CreateCommentRequest,
)
from modules.mark_comment.schemas.comment.crud import (
    BaseReadComment,
    ReadComment,
    ReadCommentReply,
)
from transport.http.api.v1.auth.fastapi_users import get_current_user_without_ban
from utils.cache.decorator import custom_cache

if TYPE_CHECKING:
    from modules.mark_comment.service import MarkCommentService
    from modules import User

router = APIRouter(
    tags=["Mark Comments"],
    responses={
        404: {
            "description": "Mark not found",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "detail": {"type": "string"},
                        },
                    }
                }
            },
        },
    },
)


@router.post(
    "/{mark_id}/comments/",
    response_model=BaseReadComment,
    responses={},
    dependencies=[Depends(check_mark_exist)],
)
async def create_comment_endpoint(
    mark_id: int,
    service: Annotated["MarkCommentService", Depends(get_mark_comment_service)],
    user: Annotated["User", Depends(get_current_user_without_ban)],
    create_data: CreateCommentRequest,
):
    result = await service.create_comment(
        mark_id=mark_id, create_data=create_data, user=user
    )
    return result


@router.get(
    "/comments/{comment_id}/replies/",
    response_model=PaginationResponse[ReadCommentReply],
)
@custom_cache(expire=60, namespace="mark-comments")
async def get_comment_replies(
    comment_id: int,
    service: Annotated["MarkCommentService", Depends(get_mark_comment_service)],
    params: Annotated[PaginationParams, Depends()],
):
    result = await service.get_paginated_comment_replies(
        comment_id=comment_id, params=params
    )
    return result


@router.get(
    "/{mark_id}/comments/",
    response_model=PaginationResponse[ReadComment],
    dependencies=[Depends(check_mark_exist)],
)
@custom_cache(expire=60, namespace="mark-comments")
async def get_comments(
    mark_id: int,
    service: Annotated["MarkCommentService", Depends(get_mark_comment_service)],
    params: Annotated[PaginationParams, Depends()],
):
    result = await service.get_pagination_comments(mark_id=mark_id, params=params)
    return result


# @router.put("/comments/{comment_id}/", dependencies=[Depends(check_mark_comment_exist)])
# async def add_comment_reaction(
#     comment_id: int,
#     user: Annotated["User", Depends(get_current_user_without_ban)],
#     service: Annotated["MarkCommentService", Depends(get_mark_comment_service)],
#     data: CommentReactionRequest,
# ):
#     result = await service.create_or_update_comment_reaction(comment_id, data, user)
#     return result
