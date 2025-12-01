import logging
from typing import Any

from fastapi import Request
from starlette.datastructures import FormData
from starlette_admin import RequestAction
from starlette_admin.fields import StringField

from utils.geom.geom_serializator import serialization_geom

logger = logging.getLogger(__name__)


class GeomField(StringField):
    def __init__(self, *args, srid=4326, **kwargs):
        super().__init__(*args, **kwargs)
        self.srid = srid

    async def parse_obj(self, request: Request, obj: Any) -> str:
        """
        Parses the WKTElement from the database object to be used in the template.
        Returns coordinates in Yandex Maps format: "longitude, latitude"
        """
        value = getattr(obj, self.name, None)
        if value is None:
            return "Coords not found"
        result = serialization_geom(value)
        coords = result.coordinates._asdict()

        # Yandex Maps использует формат [longitude, latitude]
        return f"{coords.get('latitude')}, {coords.get('longitude')}"

    @staticmethod
    def _validate_coords(data: str) -> str:
        """
        Validates and converts coordinates from "longitude, latitude" format to WKT.
        Yandex Maps format: "longitude, latitude"
        """
        try:
            # Ожидаем формат: "longitude, latitude"
            lat, lon = data.split(", ")

            lat = float(lat)
            lon = float(lon)

            # Валидация диапазонов
            if lat < -90 or lat > 90:
                raise ValueError(f"Latitude {lat} out of range [-90, 90]")

            if lon < -180 or lon > 180:
                raise ValueError(f"Longitude {lon} out of range [-180, 180]")

            # PostGIS POINT использует формат: POINT(longitude latitude)
            return f"SRID=4326;POINT({lon} {lat})"

        except ValueError as e:
            raise ValueError(f"Invalid coordinates format: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse coordinates: {e}")

    async def parse_form_data(
        self, request: Request, form_data: FormData, action: RequestAction
    ) -> Any:
        """
        Extracts the value of this field from submitted form data.
        """
        try:
            geom = form_data.get(self.id)
            wkb_coords = self._validate_coords(geom)
            return wkb_coords
        except Exception as e:
            logger.warning(f"Failed to parse value in {self.id}. {str(e)}")
            return None
