"""GBIF occurrence counts (secondary dataset).

Documentation: https://techdocs.gbif.org/en/openapi/v1/occurrence
GBIF aggregates museum specimens and national recording schemes in addition
to iNaturalist's research-grade export, so it adds depth that iNaturalist
alone misses (and partially overlaps with it - see docs/METHODOLOGY.md).
"""

from __future__ import annotations

from src.data.http import JsonHttp
from src.data.sources import SourceError, SourceInfo
from src.domain import Location
from src.settings import Settings

SEARCH_URL = "https://api.gbif.org/v1/occurrence/search"


class GbifSource:
    info = SourceInfo(
        key="gbif",
        title="GBIF fungal occurrence records",
        provider="Global Biodiversity Information Facility (GBIF.org)",
        url="https://www.gbif.org",
        license="CC0 / CC BY / CC BY-NC per dataset; aggregate counts used here",
        used_for="Record depth sub-metric of observation density",
        retrieval=(
            "API v1 /occurrence/search with kingdomKey=5 (Fungi), "
            "geoDistance=<lat>,<lon>,<radius>km, hasGeospatialIssue=false, limit=0; "
            "the `count` field is used."
        ),
    )

    def __init__(self, http: JsonHttp, settings: Settings):
        self._http = http
        self._settings = settings

    def fetch(self, location: Location) -> dict:
        s = self._settings
        payload = self._http.get_json(
            SEARCH_URL,
            {
                "kingdomKey": s.gbif_fungi_kingdom_key,
                "geoDistance": f"{location.lat},{location.lon},{s.radius_km:g}km",
                "hasGeospatialIssue": "false",
                "limit": 0,
            },
        )
        try:
            return {"gbif_records": int(payload["count"])}
        except (KeyError, TypeError, ValueError) as exc:
            raise SourceError("GBIF: no count in response") from exc
