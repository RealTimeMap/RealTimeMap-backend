import logging
from typing import List, TYPE_CHECKING

from fastapi import (
    APIRouter,
    Depends,
    Form,
    BackgroundTasks,
    Request,
    Response,
)

from dependencies.notification import (
    get_mark_notification_service,
)
from modules.events.bus import event_bus, DomainEvent, EventType
from modules.mark.dependencies import get_mark_service
from modules.mark.schemas import (
    CreateMarkRequest,
    ReadMark,
    MarkRequestParams,
    DetailMark,
    UpdateMarkRequest,
    ActionType,
    MarkCreateDataResponse,
)
from modules.mark.service import MarkService
from modules.notification import MarkNotificationService
from transport.http.api.v1.auth.fastapi_users import (
    Annotated,
    get_current_user_without_ban,
)
from utils.cache.decorator import custom_cache

if TYPE_CHECKING:
    from modules import User

router = APIRouter(prefix="/marks", tags=["Marks"])

logger = logging.getLogger(__name__)

mark_service = Annotated[MarkService, Depends(get_mark_service)]

mark_notification_service = Annotated[
    MarkNotificationService, Depends(get_mark_notification_service)
]


@router.get("/", response_model=List[ReadMark], status_code=200)
async def get_marks(
    request: Request,
    service: mark_service,
    params: MarkRequestParams = Depends(),
):
    """
    Endpoint for getting all marks in radius, filtered by params.
    """
    result = await service.get_marks(params)
    return [
        ReadMark.model_validate(mark, context={"request": request}) for mark in result
    ]


@router.get("/create-data", response_model=MarkCreateDataResponse)
@custom_cache(expire=1800, namespace="marks")
async def get_dynamic_data_for_mark(
    _: Request,
    service: mark_service,
):
    result = await service.get_data_for_create_mark()
    return result


@router.post(
    "/",
    response_model=ReadMark,
    status_code=201,
    responses={
        404: {
            "description": "Category not found",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"detail": {"type": "string"}},
                    }
                }
            },
        },
        403: {
            "description": "Forbidden",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"detail": {"type": "string"}},
                    }
                }
            },
        },
        429: {
            "description": "Forbidden",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"detail": {"type": "string"}},
                    }
                }
            },
        },
        401: {
            "description": "Unauthorized",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"detail": {"type": "string"}},
                    }
                }
            },
        },
    },
)
async def create_mark_point(
    background: BackgroundTasks,
    mark: Annotated[CreateMarkRequest, Form(media_type="multipart/form-data")],
    user: Annotated["User", Depends(get_current_user_without_ban)],
    service: mark_service,
    request: Request,
    notification: mark_notification_service,
):
    """
    Protected endpoint for create mark.
    """
    instance = await service.create_mark(mark, user)
    background.add_task(
        notification.notify_mark_action,
        mark=instance,
        event=ActionType.CREATE.value,
        request=request,
    )
    background.add_task(
        event_bus.publish,
        DomainEvent(
            event_type=EventType.MARK_CREATE,
            user=user,
            source_id=instance.id,
            source_type="marks",
        ),
    )
    return ReadMark.model_validate(instance, context={"request": request})


@router.get(
    "/{mark_id}",
    response_model=DetailMark,
    status_code=200,
    responses={
        404: {
            "description": "Mark not found",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"detail": {"type": "string"}},
                    }
                }
            },
        }
    },
)
@custom_cache(expire=1800, namespace="marks")
async def get_mark(mark_id: int, service: mark_service, request: Request):
    result = await service.get_mark_by_id(mark_id)
    return DetailMark.model_validate(result, context={"request": request})


@router.delete(
    "/{mark_id}",
    status_code=204,
    responses={
        404: {
            "description": "Mark not found",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"detail": {"type": "string"}},
                    }
                }
            },
        },
        403: {
            "description": "Forbiden",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"detail": {"type": "string"}},
                    }
                }
            },
        },
        401: {
            "description": "Unauthorized",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"detail": {"type": "string"}},
                    }
                }
            },
        },
    },
)
async def delete_mark(
    mark_id: int,
    background: BackgroundTasks,
    user: Annotated["User", Depends(get_current_user_without_ban)],
    service: mark_service,
    request: Request,
    notification: mark_notification_service,
):
    instance = await service.delete_mark(mark_id, user)
    background.add_task(
        notification.notify_mark_action,
        mark=instance,
        event=ActionType.DELETE.value,
        request=request,
    )
    return Response(status_code=204)


@router.patch(
    "/{mark_id}",
    response_model=ReadMark,
    status_code=200,
    responses={
        404: {
            "description": "Mark not found",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"detail": {"type": "string"}},
                    }
                }
            },
        },
        403: {
            "description": "Forbiden",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"detail": {"type": "string"}},
                    }
                }
            },
        },
        400: {
            "description": "Bad Request. Example: TimeOut for updating",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"detail": {"type": "string"}},
                    }
                }
            },
        },
    },
)
async def update_mark(
    mark_id: int,
    mark: Annotated[UpdateMarkRequest, Form(media_type="multipart/form-data")],
    service: mark_service,
    user: Annotated["User", Depends(get_current_user_without_ban)],
    request: Request,
    background: BackgroundTasks,
    notification: mark_notification_service,
):
    result = await service.update_mark(mark_id, mark, user)
    background.add_task(
        notification.notify_mark_action,
        mark=result,
        event=ActionType.UPDATE.value,
        request=request,
    )
    return ReadMark.model_validate(result, context={"request": request})
