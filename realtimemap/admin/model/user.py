from datetime import datetime
from typing import Dict, Any

from fastapi_users.password import PasswordHelper
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from starlette.datastructures import FormData
from starlette.requests import Request
from starlette_admin import (
    PasswordField,
    row_action,
    RowActionsDisplayType,
)
from starlette_admin.exceptions import FormValidationError, ActionFailed

from admin.model.base import BaseModelAdmin
from core.config import conf
from modules import User
from modules.user_ban.dependencies import get_user_ban_repository
from modules.user_ban.model import BanReason
from modules.user_ban.schemas import UsersBanCreate, ReasonTextException, UpdateUsersBan

env = Environment(loader=FileSystemLoader(conf.template_dir))


def generate_ban_form():
    template = env.get_template("admin/forms/ban_form.html")
    ban_reasons = list(BanReason)
    return template.render(ban_reasons=ban_reasons)


class AdminUser(BaseModelAdmin):
    fields = [
        User.id,
        User.username,
        User.email,
        User.phone,
        PasswordField(
            "hashed_password",
            label="Password",
            exclude_from_detail=True,
            exclude_from_edit=True,
            exclude_from_list=True,
            required=True,
        ),
        User.avatar,
        User.is_active,
        User.is_superuser,
        User.is_verified,
        User.bans,
        User.subscriptions,
        User.level,
        User.current_exp,
        User.total_exp,
    ]

    exclude_fields_from_detail = [User.hashed_password]
    exclude_fields_from_edit = [User.hashed_password]
    exclude_fields_from_list = [User.hashed_password]

    row_actions_display_type = RowActionsDisplayType.DROPDOWN

    async def before_create(
        self, request: Request, data: Dict[str, Any], obj: Any
    ) -> None:
        helper = PasswordHelper()
        user_password = data["hashed_password"]
        hashed_password = helper.hash(password=user_password)
        data["hashed_password"] = hashed_password

    async def validate(self, request: Request, data: Dict[str, Any]) -> None:
        errors: Dict[str, str] = dict()
        if len(errors) > 0:
            raise FormValidationError(errors)
        return await super().validate(request, data)

    def get_list_query(self, request: Request) -> Select:
        stmt = super().get_list_query(request)
        stmt = stmt.options(joinedload(User.subscriptions), joinedload(User.bans))
        return stmt

    @row_action(
        name="ban_user",
        text="Ban user",
        confirmation="Are you sure you want to ban this user?",
        submit_btn_text="Yes, ban",
        submit_btn_class="btn-success",
        icon_class="fas fa-check-circle",
        form=generate_ban_form(),
    )
    async def ban_user_action(self, request: Request, pk: Any) -> str:
        # Preparate data
        pk = int(pk)
        current_user = self.get_current_user(request)
        self.disable_self_ban(current_user.id, pk)

        # Ban Checking
        session: AsyncSession = request.state.session
        user_ban_repo = get_user_ban_repository(session)
        is_banned = await user_ban_repo.check_active_user_ban(pk)
        if is_banned:
            raise ActionFailed("User already banned")

        # Validate form data
        data: FormData = await request.form()
        valid_data = self._validate_action_form_data(data, pk, current_user.id)

        await user_ban_repo.ban_user(valid_data)

        return f"User was banned: {valid_data.reason.value}"

    @staticmethod
    def _validate_action_form_data(data: FormData, user_id: int, moderator_id: int):
        try:
            full_data = {
                "user_id": user_id,
                "moderator_id": moderator_id,
                "banned_until": data.get("banned_until", None),
                "reason": data.get("reason"),
                "reason_text": data.get("reason_text"),
                "is_permanent": data.get("is_permanent", False),
            }
            valid_data = UsersBanCreate(**full_data)
            return valid_data
        except ValueError as e:
            raise ActionFailed(str(e))
        except ReasonTextException as e:
            raise ActionFailed(str(e))

    @staticmethod
    def disable_self_ban(current_user_id: int, ban_user_id: int) -> None:
        if current_user_id == ban_user_id:
            raise ActionFailed("Can be ban yourself!")

    @row_action(
        name="unban_user",
        text="Unban user",
        confirmation="Are you sure you want to unban this user?",
        icon_class="fas fa-check-circle",
        submit_btn_text="Yes, approved!",
        submit_btn_class="btn-success",
        action_btn_class="btn-info",
    )
    async def unban_user_row_action(self, request: Request, pk: Any) -> str:
        user_id = int(pk)
        moderator = self.get_current_user(request)
        session: AsyncSession = request.state.session
        current_time = datetime.now()
        user_ban_repo = get_user_ban_repository(session)

        is_banned = await user_ban_repo.check_active_user_ban(user_id)

        if not is_banned:
            raise ActionFailed("User already unbanned")

        unban_data = UpdateUsersBan(unbanned_at=current_time, unbanned_by=moderator.id)
        _ = await user_ban_repo.unban_user(user_id, unban_data)
        return "User was approved!"
