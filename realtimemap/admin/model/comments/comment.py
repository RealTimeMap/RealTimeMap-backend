from typing import Dict, Any

from sqlalchemy import Select
from sqlalchemy.orm import joinedload
from starlette.requests import Request
from starlette_admin import TextAreaField, HasOne
from starlette_admin.exceptions import FormValidationError

from admin.model.base import BaseModelAdmin
from modules import Comment


class AdminComment(BaseModelAdmin):
    fields = [
        Comment.id,
        HasOne("mark", identity="mark", required=True, label="Mark"),
        HasOne("owner", identity="user", required=True, label="Owner"),
        TextAreaField("content", required=True),
        HasOne("parent", identity="comment", label="Parent comment", required=False),
        Comment.stats,
    ]

    exclude_fields_from_create = [Comment.stats]
    exclude_fields_from_edit = [Comment.stats]

    async def validate(self, request: Request, data: Dict[str, Any]) -> None:
        errors: Dict[str, str] = dict()

        if data.get("parent", None) is not None:
            parent_comment: "Comment" = data.get("parent")

            if parent_comment.parent_id:
                errors["parent"] = "Nesting limit exceeded. Cannot reply to this reply."

        if len(errors) > 0:
            raise FormValidationError(errors)

        return await super().validate(request, data)

    def get_list_query(self, request: Request) -> Select:
        stmt = super().get_list_query(request)
        stmt = stmt.options(
            joinedload(Comment.mark),
            joinedload(Comment.owner),
            joinedload(Comment.stats),
        )
        return stmt
