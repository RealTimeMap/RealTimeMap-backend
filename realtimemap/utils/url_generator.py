from typing import Any, Optional, Union, List

from pydantic import ValidationInfo
from starlette.requests import Request

from core.config import conf


def generate_full_image_url(
    value: Any,
    info: ValidationInfo,
) -> Optional[Union[str, List[str]]]:
    """
    Generate full image URLs from File objects or pass through if already URLs.

    This validator handles two cases:
    1. First validation (from DB): value is File object(s) → generate URLs
    2. Re-validation (from cache): value is already URL string(s) → pass through
    """
    if not value:
        return None

    request: Optional[Request] = info.context.get("request") if info.context else None

    def _generate_url(photo_obj: Any) -> Optional[str]:
        if not photo_obj:
            return ""

        # ✅ If already a string URL (from cache), return as-is
        if isinstance(photo_obj, str):
            return photo_obj

        # ✅ If File object (from DB), generate URL
        if request:
            return str(
                request.url_for(
                    "get_file",
                    storage=photo_obj.upload_storage,
                    file_id=photo_obj.file_id,
                )
            )

        base_url = conf.server.base_url
        file_url = photo_obj.path
        return f"{base_url}/media/{file_url}"

    if isinstance(value, list):
        return [_generate_url(photo) for photo in value if photo]

    # ✅ Single value: check if string (from cache)
    if isinstance(value, str):
        return value

    return _generate_url(value)
