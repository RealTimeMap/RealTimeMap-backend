from typing import TYPE_CHECKING

from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView


if TYPE_CHECKING:
    pass


class HomeView(CustomView):

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        # session: "AsyncSession" = request.state.session
        #
        # stmt = select(User).where(User.is_superuser).limit(10)
        # result = await session.execute(stmt)
        # users = result.scalars().all()
        return templates.TemplateResponse(
            "home.html", {"request": request}
        )
