from typing import Annotated, List

from fastapi import APIRouter, Depends, BackgroundTasks

from dependencies.checker import check_message_exist, check_chat_exist
from dependencies.notification import get_chat_notification_service
from modules import User
from modules.chat.dependencies import get_chat_service
from modules.chat.schemas import ReadChat
from modules.chat.service import ChatService
from modules.message import ReadMessage
from modules.message.schemas import (
    CreateMessageRequest,
    UpdateMessageRequest,
    ChatEventName,
    MessageParamsRequest,
)
from modules.notification import ChatNotificationService
from transport.http.api.v1.auth.fastapi_users import get_current_user_without_ban

router = APIRouter(
    prefix="/chats",
    tags=["chats"],
)

current_user = Annotated[User, Depends(get_current_user_without_ban)]
chat_service = Annotated[ChatService, Depends(get_chat_service)]
chat_notification_service = Annotated[
    ChatNotificationService, Depends(get_chat_notification_service)
]


@router.get("/", response_model=List[ReadChat])
async def get_chats(
    user: current_user,
    service: chat_service,
):
    result = await service.get_chats_for_user(user)
    return result


@router.post(
    "/message/",
)
async def send_message(
    user: current_user,
    service: chat_service,
    message: CreateMessageRequest,
    background: BackgroundTasks,
    chat_notificator: chat_notification_service,
):
    message = await service.send_message(user=user, message=message)
    background.add_task(
        chat_notificator.notify_action_in_chat,
        event=ChatEventName.new_message.value,
        message=message,
    )
    return message


@router.patch("/message/{message_id}", dependencies=[Depends(check_message_exist)])
async def update_message(
    message_id: int,
    user: current_user,
    service: chat_service,
    message: UpdateMessageRequest,
    background: BackgroundTasks,
    chat_notificator: chat_notification_service,
):
    message = await service.update_message(message_id, message, user)
    background.add_task(
        chat_notificator.notify_action_in_chat,
        event=ChatEventName.update_message.value,
        message=message,
    )
    return message


@router.delete("/message/{message_id}", dependencies=[Depends(check_message_exist)])
async def delete_message(
    message_id: int,
    user: current_user,
    service: chat_service,
    background: BackgroundTasks,
    chat_notificator: chat_notification_service,
):
    message = await service.delete_message(message_id, user)
    background.add_task(
        chat_notificator.notify_action_in_chat,
        event=ChatEventName.delete_message.value,
        message=message,
    )
    return message


@router.get(
    "/message/history/{chat_id}/",
    dependencies=[Depends(check_chat_exist)],
    response_model=List[ReadMessage],
)
async def get_chat_history(
    chat_id: int,
    user: current_user,
    service: chat_service,
    params: MessageParamsRequest = Depends(),
):
    messages = await service.get_chat_message_history(chat_id, user, params)
    return messages
