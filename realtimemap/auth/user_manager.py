import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users import (
    BaseUserManager,
    IntegerIDMixin,
    models,
    exceptions,
)
from fastapi_users.models import ID, UP
from starlette.responses import Response

from auth.base import MyBaseUserDatabase
from core.config import conf
from integrations.kafka import kafka_producer
from modules import User
from modules.user.schemas import UserCreate

log = logging.getLogger(__name__)


class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
    reset_password_token_secret = conf.api.v1.auth.reset_password_token_secret
    verification_token_secret = conf.api.v1.auth.verification_token_secret
    # noinspection PyTypeHints
    user_db = MyBaseUserDatabase[UP, ID]

    async def on_after_register(
        self,
        user: User,
        request: Optional["Request"] = None,
    ):
        from tasks import welcome_email

        log.warning(
            "User %r has registered.",
            user.id,
        )
        welcome_email.delay(user.email, user.username)

        event = {
            "event_type": "user.registered",
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "is_verified": user.is_verified,
            "oauth": bool(getattr(user, "oauth_accounts", None)),
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }
        await kafka_producer.send(
            topic=conf.kafka.user_registered_topic,
            value=event,
            key=str(user.id),
        )

    async def authenticate(
        self, credentials: OAuth2PasswordRequestForm
    ) -> Optional[models.UP]:
        """
        Authenticate and return a user following an email and a password.

        Will automatically upgrade password hash if necessary.

        :param credentials: The user credentials.
        """
        try:
            user = await self.get_by_username(credentials.username)
        except exceptions.UserNotExists:
            self.password_helper.hash(credentials.password)
            return None

        verified, updated_password_hash = self.password_helper.verify_and_update(
            credentials.password, user.hashed_password
        )
        if not verified:
            return None
        # Update password hash to a more robust one if needed
        if updated_password_hash is not None:
            await self.user_db.update(user, {"hashed_password": updated_password_hash})

        return user

    async def get_by_username(self, username: str) -> models.UP:
        user = await self.user_db.get_by_username(username)
        if user is None:
            raise exceptions.UserNotExists()
        return user

    async def on_after_request_verify(
        self,
        user: User,
        token: str,
        request: Optional["Request"] = None,
    ):
        from tasks import verify_email

        log.warning(
            "Verification requested for user %r.",
            user.id,
        )
        verify_url = conf.frontend.get_verify_url(token)
        verify_email.delay(user.email, user.username, verify_url)

    async def on_after_forgot_password(
        self,
        user: User,
        token: str,
        request: Optional["Request"] = None,
    ):
        from tasks import forgot_password_email

        log.warning(
            "User %r has forgot their password.",
            user.id,
        )
        forgot_password_url = conf.frontend.get_password_reset_url(token)
        forgot_password_email.delay(user.email, user.username, forgot_password_url)

    async def on_after_reset_password(
        self, user: User, request: Optional[Request] = None
    ) -> None:
        from tasks import change_password_email

        ip_address = request.client.host if request else "Unknown"
        change_password_email.delay(user.email, user.username, ip_address)

    async def on_after_login(
        self,
        user: User,
        request: Optional[Request] = None,
        response: Optional[Response] = None,
    ) -> None:
        from tasks import login_email

        log.info("User %r logged in", user.id)
        user_agent = request.headers.get("User-Agent") if request else "Unknown"
        ip_address = request.client.host if request else "Unknown"

        login_email.delay(
            user.email,
            user.username,
            ip_address,
            user_agent,
        )

    async def create(
        self,
        user_create: UserCreate,
        safe: bool = False,
        request: Optional[Request] = None,
    ) -> models.UP:
        """
        Create a user in database.

        Triggers the on_after_register handler on success.

        :param user_create: The UserCreate model to create.
        :param safe: If True, sensitive values like is_superuser or is_verified
        will be ignored during the creation, defaults to False.
        :param request: Optional FastAPI request that
        triggered the operation, defaults to None.
        :raises UserAlreadyExists: A user already exists with the same e-mail.
        :return: A new user.
        """
        await self.validate_password(user_create.password, user_create)

        existing_user = await self.user_db.validate_user_credentials(
            email=user_create.email.lower(), username=user_create.username.lower()
        )

        if existing_user is not None:
            raise exceptions.UserAlreadyExists()

        user_dict = (
            user_create.create_update_dict()
            if safe
            else user_create.create_update_dict_superuser()
        )
        password = user_dict.pop("password")
        user_dict["hashed_password"] = self.password_helper.hash(password)

        created_user = await self.user_db.create(user_dict)

        await self.on_after_register(created_user, request)

        return created_user

    async def oauth_callback(
        self: "BaseUserManager[models.UOAP, models.ID]",
        oauth_name: str,
        access_token: str,
        account_id: str,
        account_email: str,
        expires_at: Optional[int] = None,
        refresh_token: Optional[str] = None,
        request: Optional[Request] = None,
        *,
        associate_by_email: bool = False,
        is_verified_by_default: bool = False,
    ) -> models.UOAP:
        oauth_account_dict = {
            "oauth_name": oauth_name,
            "access_token": access_token,
            "account_id": account_id,
            "account_email": account_email,
            "expires_at": expires_at,
            "refresh_token": refresh_token,
        }

        try:
            user = await self.get_by_oauth_account(oauth_name, account_id)
        except exceptions.UserNotExists:
            try:
                # Associate account
                user = await self.get_by_email(account_email)
                if not associate_by_email:
                    raise exceptions.UserAlreadyExists()
                user = await self.user_db.add_oauth_account(user, oauth_account_dict)
            except exceptions.UserNotExists:
                # Create account
                password = self.password_helper.generate()
                user_dict = {
                    "username": account_email.split("@")[0],
                    "email": account_email,
                    "hashed_password": self.password_helper.hash(password),
                    "is_verified": is_verified_by_default,
                }
                user = await self.user_db.create(user_dict)
                user = await self.user_db.add_oauth_account(user, oauth_account_dict)
                await self.on_after_register(user, request)
        else:
            # Update oauth
            for existing_oauth_account in user.oauth_accounts:
                if (
                    existing_oauth_account.account_id == account_id
                    and existing_oauth_account.oauth_name == oauth_name
                ):
                    user = await self.user_db.update_oauth_account(
                        user, existing_oauth_account, oauth_account_dict
                    )

        return user
