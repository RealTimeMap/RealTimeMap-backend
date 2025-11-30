import logging
from typing import Optional, Union, Any

from geoalchemy2 import WKBElement
from geoalchemy2.shape import to_shape
from geojson_pydantic import Point

logger = logging.getLogger(__name__)


def serialization_geom(geom: Union[WKBElement, Point, dict, None, Any]) -> Optional[Point]:
    """
    Serialize geometry to GeoJSON Point.

    Handles multiple input types:
    1. WKBElement (from DB) → convert to Point
    2. Point (from cache) → return as-is
    3. dict (from cache, raw) → parse as Point
    4. None → return None
    """
    if geom is None:
        return None

    # ✅ Already a Point object (from cache or previous validation)
    if isinstance(geom, Point):
        return geom

    # ✅ Dictionary (from cache, deserialized JSON)
    if isinstance(geom, dict):
        try:
            return Point(**geom)
        except Exception as e:
            logger.error(f"Failed to parse Point from dict: {e}")
            return None

    # ✅ WKBElement (from database)
    if isinstance(geom, WKBElement):
        try:
            result = to_shape(geom)
            return Point(**result.__geo_interface__)
        except Exception as e:
            logger.error(f"Failed to serialize WKBElement: {e}")
            return None

    # Unknown type
    logger.warning(f"Unknown geometry type: {type(geom)}")
    return None
