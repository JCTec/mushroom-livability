"""Forest cover near a location, estimated from OpenStreetMap.

Method: point sampling. A regular lattice of points is laid over the
location circle; for each point the Overpass API is asked whether it lies
inside an area tagged landuse=forest or natural=wood. The share of points
inside woodland estimates the mapped forest share. Only woodland that has an
Overpass *area* counts (Overpass builds areas mainly from named multipolygons),
so this is a lower bound - see docs/DATA_SOURCES.md section 5.

Documentation: https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL
"""

from __future__ import annotations

from src.data.http import JsonHttp
from src.data.sources import SourceError, SourceInfo
from src.domain import Location
from src.processing.geo import lattice_in_circle
from src.settings import Settings

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def build_query(points: list, timeout_s: int = 170) -> str:
    """One `is_in` + `out count` block per sample point, in order."""
    lines = [f"[out:json][timeout:{timeout_s}];"]
    for lat, lon in points:
        lines.append(
            f"is_in({lat},{lon})->.a;"
            '(area.a["landuse"="forest"];area.a["natural"="wood"];);'
            "out count;"
        )
    return "\n".join(lines)


def parse_forest_share(payload: dict, expected_points: int) -> float:
    """Share of `count` elements reporting at least one enclosing woodland."""
    try:
        counts = [e for e in payload["elements"] if e.get("type") == "count"]
    except (KeyError, TypeError) as exc:
        raise SourceError("Overpass: elements missing in response") from exc
    if len(counts) != expected_points:
        raise SourceError(f"Overpass: expected {expected_points} count blocks, got {len(counts)}")
    inside = sum(1 for e in counts if int(e.get("tags", {}).get("total", 0)) > 0)
    return inside / expected_points


class OverpassForestSource:
    info = SourceInfo(
        key="osm_forest",
        title="OpenStreetMap woodland polygons (landuse=forest, natural=wood)",
        provider="OpenStreetMap contributors, queried through the Overpass API",
        url="https://www.openstreetmap.org/copyright",
        license="ODbL 1.0",
        used_for="Habitat proximity (share of the surrounding area mapped as woodland)",
        retrieval=(
            "overpass-api.de/api/interpreter, one query per location: for each point of a 7x7 "
            "lattice clipped to the circle, is_in(lat,lon) filtered to landuse=forest or "
            "natural=wood areas, `out count`. Forest share = points inside woodland / points "
            "(lower bound: woodland without an Overpass area is not seen)."
        ),
    )

    def __init__(self, http: JsonHttp, settings: Settings):
        self._http = http
        self._settings = settings

    def fetch(self, location: Location) -> dict:
        s = self._settings
        points = lattice_in_circle(location.lat, location.lon, s.radius_km, s.forest_sample_grid)
        payload = self._http.post_json(OVERPASS_URL, {"data": build_query(points)})
        return {"forest_share": round(parse_forest_share(payload, len(points)), 4)}
