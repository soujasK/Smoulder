"""Geometry helpers. All distance work happens in a local UTM CRS chosen per site."""
from __future__ import annotations

import math
from functools import lru_cache

from pyproj import CRS, Transformer
from shapely.geometry import Polygon, shape
from shapely.ops import transform


def utm_epsg(lon: float, lat: float) -> int:
    zone = int((lon + 180) // 6) + 1
    return (32600 if lat >= 0 else 32700) + zone


@lru_cache(maxsize=None)
def _transformers(epsg: int) -> tuple[Transformer, Transformer]:
    fwd = Transformer.from_crs(CRS.from_epsg(4326), CRS.from_epsg(epsg), always_xy=True)
    inv = Transformer.from_crs(CRS.from_epsg(epsg), CRS.from_epsg(4326), always_xy=True)
    return fwd, inv


def to_metric(geom, epsg: int):
    return transform(_transformers(epsg)[0].transform, geom)


def to_wgs84(geom, epsg: int):
    return transform(_transformers(epsg)[1].transform, geom)


def project_point(lon: float, lat: float, epsg: int) -> tuple[float, float]:
    return _transformers(epsg)[0].transform(lon, lat)


def unproject_point(x: float, y: float, epsg: int) -> tuple[float, float]:
    return _transformers(epsg)[1].transform(x, y)


def footprint(x: float, y: float, scan_km: float, track_km: float) -> Polygon:
    """Axis-aligned approximation of a VIIRS pixel footprint (metres, metric CRS).

    scan is the along-scan (roughly east-west for these polar orbits) size and
    track the along-track (roughly north-south) size. The true footprint is
    rotated by the orbit inclination (~8 deg from north at these latitudes);
    we ignore that rotation and document it in docs/METHOD.md.
    """
    hw, hh = scan_km * 500.0, track_km * 500.0
    return Polygon([(x - hw, y - hh), (x + hw, y - hh), (x + hw, y + hh), (x - hw, y + hh)])


def bearing_deg(x0: float, y0: float, x1: float, y1: float) -> float:
    """Bearing from (x0,y0) to (x1,y1) in a metric CRS, degrees clockwise from grid north."""
    return math.degrees(math.atan2(x1 - x0, y1 - y0)) % 360.0


def ang_diff(a: float, b: float) -> float:
    """Smallest absolute angular difference in degrees, in [0, 180]."""
    d = abs((a - b) % 360.0)
    return 360.0 - d if d > 180.0 else d


def geojson_to_shape(g: dict):
    return shape(g)


COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def compass(deg: float) -> str:
    return COMPASS[int(((deg % 360) + 11.25) // 22.5) % 16]
