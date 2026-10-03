from typing import Optional, TYPE_CHECKING

import grpc

from database.helper import db_helper
from errors.http2 import NotFoundError
from modules.rbac.dependencies import create_rbac_service
from modules.rbac.policy import PERMISSION_CODE_RE, SCOPE_RE
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

    async def GetUserAccess(self, request, context):
        async with db_helper.session_factory() as session:
            service = create_rbac_service(session)
            try:
                user = await service.get_user(request.id)
            except NotFoundError:
                await context.abort(
                    grpc.StatusCode.NOT_FOUND, f"User with id {request.id} not found"
                )
            access = await service.get_access(user)
            return user_service_pb2.UserAccessResponse(
                user_id=user.id,
                is_superuser=user.is_superuser,
                roles=access.roles,
                permissions=access.permissions,
                priority=access.priority,
            )

    async def CheckPermission(self, request, context):
        if request.scope and not SCOPE_RE.match(request.scope):
            await context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, f"Invalid scope {request.scope!r}"
            )
        async with db_helper.session_factory() as session:
            service = create_rbac_service(session)
            try:
                user = await service.get_user(request.user_id)
            except NotFoundError:
                await context.abort(
                    grpc.StatusCode.NOT_FOUND,
                    f"User with id {request.user_id} not found",
                )
            allowed = await service.check(
                user, request.permission, request.scope or None
            )
            return user_service_pb2.CheckPermissionResponse(allowed=allowed)

    async def RegisterPermissions(self, request, context):
        if not request.service:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "service is required")
        invalid = [
            p.code for p in request.permissions if not PERMISSION_CODE_RE.match(p.code)
        ]
        if invalid:
            await context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                f"Invalid permission codes: {', '.join(invalid)}",
            )
        async with db_helper.session_factory() as session:
            service = create_rbac_service(session)
            registered = await service.register_permissions(
                request.service,
                ((p.code, p.description or None) for p in request.permissions),
            )
            return user_service_pb2.RegisterPermissionsResponse(registered=registered)
