from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

from geoalchemy2.functions import ST_SetSRID

from modules.geo_service.service import GeoService
from modules.mark.schemas.params import MarkRequestParams

DEFAULT_RADIUS_METERS: int = 5000


@dataclass(frozen=True)
class MarkFilter:
    latitude: float
    longitude: float

    geohash_neighbors: List[str]

    duration: int
    min_start: datetime
    max_end: datetime

    current_point: ST_SetSRID

    show_ended: bool

    srid: int

    radius: int = DEFAULT_RADIUS_METERS

    date: datetime = datetime.now()

    @classmethod
    def from_request(
        cls, req: "MarkRequestParams", geo_service: "GeoService" = GeoService()
    ) -> "MarkFilter":
        current_point = geo_service.create_point(req, req.srid)
        geohash = geo_service.get_geohash(req)
        geohash_neighbors = geo_service.get_neighbors(geohash, True)

        min_start = req.date - timedelta(req.duration)
        max_end = req.date + timedelta(req.duration)
        srid = req.srid
        return cls(
            latitude=req.latitude,
            longitude=req.longitude,
            geohash_neighbors=geohash_neighbors,
            duration=req.duration,
            min_start=min_start,
            max_end=max_end,
            current_point=current_point,
            show_ended=req.show_ended,
            radius=req.radius,
            srid=srid,
            date=req.date,
        )
