from fastapi_users.authentication import BearerTransport
from fastapi_users.authentication.transport.bearer import BearerResponse
from starlette.responses import RedirectResponse

from core.config import conf

bearer_transport = BearerTransport(
    tokenUrl=conf.api.v1.auth.login_url,
)


class OAuthTransport(BearerTransport):
    async def get_login_response(self, token: str) -> RedirectResponse:
        bearer_response = BearerResponse(access_token=token, token_type="bearer")
        return RedirectResponse(
            url=conf.frontend.get_oauth_url(*bearer_response.model_dump())
        )


oauth_transport = OAuthTransport(
    tokenUrl=conf.api.v1.auth.login_url,
)
