from typing import TYPE_CHECKING

from fastapi import APIRouter

if TYPE_CHECKING:
    pass

router = APIRouter(prefix="/level", tags=["level"])
