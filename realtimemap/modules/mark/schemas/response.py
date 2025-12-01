from typing import Optional, List

from pydantic import BaseModel

from modules.category.schemas import ReadCategory


class MarkCreateDataResponse(BaseModel):
    allowed_category: Optional[List[ReadCategory]] = []
    allowed_duration: Optional[List[int]] = []
