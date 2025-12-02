from typing import Annotated, TYPE_CHECKING, List

from fastapi import APIRouter, Request, Form, Depends, Query
from fastapi_limiter.depends import RateLimiter
from starlette.responses import Response

from api.v1.auth.fastapi_users import get_current_user_without_ban, get_current_user
from modules.user.schemas import UserRead, UserUpdate, UserRequestParams, DetailUserRead
from modules.user.service import UserService
from modules.user.service_depenencies import get_user_service

if TYPE_CHECKING:
    from modules import User

router = APIRouter(tags=["user"])


@router.get(
    "/me",
    response_model=DetailUserRead,
)
# @cache(expire=3600, namespace="user")
async def me(
    request: Request,
    user: Annotated["User", Depends(get_current_user)],
    params: Annotated[UserRequestParams, Query()],
    service: Annotated["UserService", Depends(get_user_service)],
):
    result = await service.get_included_user_info(request, user, params)
    return result


@router.patch(
    "/me",
    response_model=UserRead,
    dependencies=[Depends(RateLimiter(times=2, minutes=5))],
)
async def update_me(
    user: Annotated["User", Depends(get_current_user_without_ban)],
    update_data: Annotated[UserUpdate, Form(media_type="multipart/form-data")],
    service: Annotated["UserService", Depends(get_user_service)],
    request: Request,
):
    result = await service.update_user(user.id, update_data)
    return UserRead.model_validate(result, context={"request": request})


@router.delete("/me", status_code=204, response_class=Response)
async def delete_me(
    user: Annotated["User", Depends(get_current_user_without_ban)],
    service: Annotated["UserService", Depends(get_user_service)],
):
    await service.delete_user(user.id)
    return Response(status_code=204)


@router.get("/leaderboard", response_model=List[UserRead])
async def get_leaderboard(
    request: Request, service: Annotated["UserService", Depends(get_user_service)]
):
    leaders = await service.get_leaderboard(request)
    return leaders
