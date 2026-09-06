import contextlib
from typing import Optional, TYPE_CHECKING

from fastapi import Request, Response
from starlette_admin.auth import AuthProvider, AdminConfig, AdminUser
from starlette_admin.exceptions import LoginFailed

from database.helper import db_helper
from dependencies.auth.manager import get_user_manager
from dependencies.auth.users import get_users_db
from modules import User
from modules.user.schemas import UserLogin

if TYPE_CHECKING:
    pass


get_users_db_context = contextlib.asynccontextmanager(get_users_db)
get_user_manager_context = contextlib.asynccontextmanager(get_user_manager)


class AdminAuthProvider(AuthProvider):
    """
    This is only for demo purpose, it's not a better
    way to save and validate user credentials
    """

    @staticmethod
    async def authenticate_user(user_credentials: UserLogin) -> Optional[User]:
        async with db_helper.session_factory() as session:
            async with get_users_db_context(session=session) as users_db:
                async with get_user_manager_context(users_db=users_db) as user_manager:
                    user = await user_manager.authenticate(credentials=user_credentials)
                    return user if user else None

    async def login(
        self,
        username: str,
        password: str,
        remember_me: bool,
        request: Request,
        response: Response,
    ) -> Response:
        user = await self.authenticate_user(
            UserLogin(username=username, password=password)
        )
        if user and user.is_superuser:
            request.session.update({"username": user.username})
            return response

        raise LoginFailed("login failed")

    async def is_authenticated(self, request) -> bool:
        username = request.session.get("username")
        if not username:
            return False

        async with db_helper.session_factory() as session:
            async with get_users_db_context(session=session) as users_db:
                user = await users_db.get_by_username(username)
                if user and user.is_superuser:
                    request.state.user = user
                    return True
        return False

    def get_admin_config(self, request: Request) -> AdminConfig:
        user = request.state.user  # Retrieve current user
        # Update app title according to current_user
        custom_app_title = "Hello, " + user.username + "!"
        # Update logo url according to current_user
        return AdminConfig(
            app_title=custom_app_title,
        )

    def get_admin_user(self, request: Request) -> AdminUser:
        user = request.state.user  # Retrieve current user
        photo_url = None
        if user.avatar:
            photo_url = str(
                request.url_for(
                    "get_file",
                    storage=user.avatar.upload_storage,
                    file_id=user.avatar.file_id,
                )
            )
        return AdminUser(username=user.username, photo_url=photo_url)

    async def logout(self, request: Request, response: Response) -> Response:
        request.session.clear()
        return response
