from typing import Optional, TYPE_CHECKING

import grpc

from database.helper import db_helper
from modules.user.service_depenencies import create_user_service
from transport.grpc.generated import user_service_pb2
from transport.grpc.generated.user_service_pb2_grpc import UserServiceServicer

if TYPE_CHECKING:
    from modules import User


class UserService(UserServiceServicer):
    async def GetUserById(self, request, context):
        async with db_helper.session_factory() as session:
            try:
                # Создаем user_service с сессией
                user_service = await create_user_service(session)

                # Получаем пользователя
                user: Optional["User"] = await user_service.user_repo.get_by_id(
                    request.id
                )

                if user is None:
                    await context.abort(
                        grpc.StatusCode.NOT_FOUND,
                        f"User with id {request.id} not found",
                    )

                # Коммит происходит автоматически при выходе из контекста
                return user_service_pb2.UserResponse(
                    id=user.id,
                    username=user.username,
                    email=user.email,
                    is_superuser=user.is_superuser,
                )
            except Exception as e:
                print(str(e))
                # Rollback происходит автоматически
                await context.abort(grpc.StatusCode.INTERNAL, str(e))
