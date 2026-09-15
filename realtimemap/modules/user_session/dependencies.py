from typing import Annotated, TYPE_CHECKING

from fastapi import Depends

from core.config import conf
from dependencies.auth.access_token import get_access_token_db
from .service import SessionService

if TYPE_CHECKING:
    from auth.access_token_database import SessionAccessTokenDatabase


def get_session_service(
    access_tokens_db: Annotated[
        "SessionAccessTokenDatabase",
        Depends(get_access_token_db),
    ],
) -> SessionService:
    return SessionService(
        access_tokens_db=access_tokens_db,
        lifetime_seconds=conf.api.v1.auth.token_lifetime_seconds,
    )
