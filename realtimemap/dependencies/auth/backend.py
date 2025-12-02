from fastapi_users.authentication import (
    AuthenticationBackend,
)

from auth.transport import bearer_transport, oauth_transport
from .strategy import get_database_strategy

authentication_backend = AuthenticationBackend(
    name="access-tokens-db",
    transport=bearer_transport,
    get_strategy=get_database_strategy,
)


oauth_backend = AuthenticationBackend(
    name="access-tokens-db",
    transport=oauth_transport,
    get_strategy=get_database_strategy,
)