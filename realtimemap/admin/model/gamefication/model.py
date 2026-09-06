from typing import Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette_admin import TextAreaField, IntegerField, ColorField
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError

from admin.fields import ActionTypeField
from modules import Level, ExpAction, UserExpHistory
from modules.gamefication.dependencies import get_pg_level_repository


class AdminLevel(ModelView):
    fields = [
        IntegerField("level", help_text="Level number"),
        ColorField("color", required=False),
        Level.required_exp,
        TextAreaField("description", label="description"),
        Level.is_active,
    ]

    async def validate(self, request: Request, data: Dict[str, Any]) -> None:
        errors: Dict[str, str] = dict()
        session: "AsyncSession" = request.state.session
        level_repository = get_pg_level_repository(session)
        max_level = await level_repository.get_max_level()
        if max_level is not None and max_level.level + 1 != data["level"]:
            errors["level"] = "Уровень не может превышать предыдущий больше чем +1"

        if len(errors) > 0:
            raise FormValidationError(errors)
        return await super().validate(request, data)


# TODO Валидация на проверку является ли action_type словосочетанием
class AdminExpAction(ModelView):
    fields = [
        ActionTypeField(
            name="action_type",
            label="Action type",
            help_text="Action type",
            required=True,
        ),
        ExpAction.base_exp,
        ExpAction.name,
        TextAreaField("description", label="description"),
        ExpAction.is_active,
        ExpAction.is_repeatable,
        ExpAction.max_per_day,
    ]


class AdmiUserExpHistory(ModelView):
    fields = [
        UserExpHistory.user,
        UserExpHistory.action,
        UserExpHistory.source_id,
        UserExpHistory.base_exp,
        UserExpHistory.exp_before,
        UserExpHistory.total_exp,
        UserExpHistory.level_before,
        UserExpHistory.level_after,
    ]
