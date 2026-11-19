"""WorldPop gridded population, summed inside the location circle.

Uses the WorldPop "stats" web service so that no raster has to be
downloaded. Documentation: https://www.worldpop.org/sdi/advancedapi/
"""

from __future__ import annotations

import json
import time
from typing import Callable

from src.data.http import JsonHttp
from src.data.sources import SourceError, SourceInfo
from src.domain import Location
from src.processing.geo import circle_polygon
from src.settings import Settings

STATS_URL = "https://api.worldpop.org/v1/services/stats"
TASK_URL = "https://api.worldpop.org/v1/tasks"


def _finished(payload) -> bool:
    return isinstance(payload, dict) and payload.get("status") == "finished" and not payload.get("error")


class WorldPopSource:
    info = SourceInfo(
        key="worldpop",
        title="WorldPop global gridded population (100 m, unconstrained)",
        provider="WorldPop, University of Southampton",
        url="https://www.worldpop.org",
        license="CC BY 4.0",
        used_for="Per-capita normalisation of observation density",
        retrieval=(
            "api.worldpop.org/v1/services/stats with dataset=wpgppop, year=2020 and a GeoJSON "
            "circle polygon; `data.total_population` is used (asynchronous tasks are polled)."
        ),
    )

    def __init__(self, http: JsonHttp, settings: Settings, sleep: Callable[[float], None] = time.sleep,
                 max_polls: int = 30, poll_interval_s: float = 4.0):
        self._http = http
        self._settings = settings
        self._sleep = sleep
        self._max_polls = max_polls
        self._poll_interval_s = poll_interval_s

    def fetch(self, location: Location) -> dict:
        s = self._settings
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [circle_polygon(location.lat, location.lon, s.radius_km, s.circle_vertices)],
                    },
                }
            ],
        }
        payload = self._http.get_json(
            STATS_URL,
            {
                "dataset": "wpgppop",
                "year": s.worldpop_year,
                "geojson": json.dumps(geojson, separators=(",", ":")),
                "runasync": "false",
            },
            cache_if=_finished,
        )
        payload = self._wait(payload)
        try:
            population = float(payload["data"]["total_population"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SourceError("WorldPop: total_population missing in response") from exc
        if population <= 0:
            raise SourceError("WorldPop: non-positive population")
        return {"population": population}

    def _wait(self, payload: dict) -> dict:
        """Poll the task endpoint until the job is finished."""
        polls = 0
        while not _finished(payload):
            if not isinstance(payload, dict):
                raise SourceError("WorldPop: response is not an object")
            if payload.get("error"):
                raise SourceError(f"WorldPop: {payload.get('error_message', 'service error')}")
            task_id = payload.get("taskid")
            if not task_id or polls >= self._max_polls:
                raise SourceError("WorldPop: task did not finish in time")
            polls += 1
            self._sleep(self._poll_interval_s)
            payload = self._http.get_json(f"{TASK_URL}/{task_id}", None, cache_if=_finished)
        return payload
