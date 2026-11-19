"""Open-Meteo historical weather (ERA5 reanalysis) -> monthly normals.

Documentation: https://open-meteo.com/en/docs/historical-weather-api
"""

from __future__ import annotations

from src.data.http import JsonHttp
from src.data.sources import SourceError, SourceInfo
from src.domain import Location
from src.processing.climate import monthly_normals
from src.settings import Settings

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


class OpenMeteoClimateSource:
    info = SourceInfo(
        key="open_meteo",
        title="Open-Meteo Historical Weather API (ERA5 reanalysis)",
        provider="Open-Meteo.com; ERA5 by Copernicus Climate Change Service / ECMWF",
        url="https://open-meteo.com",
        license="CC BY 4.0",
        used_for="Climate suitability (monthly temperature and precipitation normals)",
        retrieval=(
            "archive-api.open-meteo.com/v1/archive with daily=temperature_2m_mean,precipitation_sum, "
            "timezone=UTC over the configured period (default 2014-2023); reduced to 12 monthly normals."
        ),
    )

    def __init__(self, http: JsonHttp, settings: Settings):
        self._http = http
        self._settings = settings

    def fetch(self, location: Location) -> dict:
        s = self._settings
        payload = self._http.get_json(
            ARCHIVE_URL,
            {
                "latitude": location.lat,
                "longitude": location.lon,
                "start_date": s.climate_start,
                "end_date": s.climate_end,
                "daily": "temperature_2m_mean,precipitation_sum",
                "timezone": "UTC",
            },
        )
        try:
            daily = payload["daily"]
            normals = monthly_normals(daily["time"], daily["temperature_2m_mean"], daily["precipitation_sum"])
        except (KeyError, TypeError) as exc:
            raise SourceError("Open-Meteo: unexpected response shape") from exc
        return {"climate_monthly": normals}
