from typing import Annotated, TYPE_CHECKING

from fastapi import Depends, Request

from auth.strategy import SessionDatabaseStrategy
from core.config import conf
from .access_token import get_access_token_db

if TYPE_CHECKING:
    from modules import AccessToken
    from fastapi_users.authentication.strategy.db import AccessTokenDatabase


async def get_database_strategy(
    access_tokens_db: Annotated[
        "AccessTokenDatabase[AccessToken]",
        Depends(get_access_token_db),
    ],
    request: Request = None,
) -> SessionDatabaseStrategy:
    """Стратегия аутентификации.

    request со значением по умолчанию, а не Optional[Request]: FastAPI
    подставляет сюда запрос по типу аннотации, а Optional превратил бы
    параметр в поле схемы и сломал бы построение роутов. Значение по
    умолчанию нужно для кода, который резолвит зависимость вручную вне
    HTTP-запроса (websocket-хендлеры, socket_current_user) — там токен
    только читается, а метаданные нужны лишь при записи.
    """
    yield SessionDatabaseStrategy(
        database=access_tokens_db,
        lifetime_seconds=conf.api.v1.auth.token_lifetime_seconds,
        request=request,
        trust_forwarded_for=conf.api.v1.auth.trust_forwarded_for,
    )
