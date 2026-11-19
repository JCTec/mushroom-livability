"""iNaturalist API v1 sources (primary dataset).

Documentation: https://api.inaturalist.org/v1/docs/
All queries share the same filter: research-grade observations of the taxon
Fungi within `radius_km` of the location centre.
"""

from __future__ import annotations

from src.data.http import JsonHttp
from src.data.sources import SourceError, SourceInfo
from src.domain import Location
from src.settings import Settings

BASE_URL = "https://api.inaturalist.org/v1"


def _area_filter(location: Location, settings: Settings) -> dict:
    return {
        "lat": location.lat,
        "lng": location.lon,
        "radius": settings.radius_km,
        "quality_grade": settings.quality_grade,
    }


def _fungi_filter(location: Location, settings: Settings) -> dict:
    return {**_area_filter(location, settings), "taxon_id": settings.fungi_taxon_id}


def _total_results(payload: dict, what: str) -> int:
    try:
        return int(payload["total_results"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SourceError(f"iNaturalist {what}: no total_results in response") from exc


class INaturalistStatsSource:
    """Counts, species richness and the month-of-year histogram."""

    info = SourceInfo(
        key="inaturalist",
        title="iNaturalist research-grade observations",
        provider="iNaturalist (California Academy of Sciences & National Geographic Society)",
        url="https://www.inaturalist.org",
        license="Observation records CC0 / CC BY / CC BY-NC per observer; aggregate counts used here",
        used_for="Observation density, fungal share, species richness, seasonal reliability",
        retrieval=(
            "API v1 (api.inaturalist.org/v1): /observations (per_page=0 for totals), "
            "/observations/species_counts, /observations/histogram "
            "(date_field=observed, interval=month_of_year); filters taxon_id=47170 (Fungi), "
            "quality_grade=research, lat/lng/radius."
        ),
    )

    def __init__(self, http: JsonHttp, settings: Settings):
        self._http = http
        self._settings = settings

    def fetch(self, location: Location) -> dict:
        s = self._settings
        fungi = _fungi_filter(location, s)

        fungi_total = _total_results(
            self._http.get_json(f"{BASE_URL}/observations", {**fungi, "per_page": 0}), "fungi count"
        )
        all_total = _total_results(
            self._http.get_json(f"{BASE_URL}/observations", {**_area_filter(location, s), "per_page": 0}),
            "all-taxa count",
        )
        species_total = _total_results(
            self._http.get_json(f"{BASE_URL}/observations/species_counts", {**fungi, "per_page": 1}),
            "species count",
        )
        histogram = self._http.get_json(
            f"{BASE_URL}/observations/histogram",
            {**fungi, "date_field": "observed", "interval": "month_of_year"},
        )
        return {
            "fungi_observations": fungi_total,
            "all_observations": all_total,
            "species_count": species_total,
            "monthly_observations": parse_month_histogram(histogram),
        }


def parse_month_histogram(payload: dict) -> list:
    """Extract 12 monthly counts (January first) from a histogram response."""
    try:
        months = payload["results"]["month_of_year"]
    except (KeyError, TypeError) as exc:
        raise SourceError("iNaturalist histogram: results.month_of_year missing") from exc
    return [int(months.get(str(m), months.get(m, 0)) or 0) for m in range(1, 13)]


class INaturalistSampleSource:
    """Coordinates of the most recently added observations (density map).

    This is a *sample* (at most sample_pages x sample_page_size points), so
    it shows where finds cluster, not how many there are in total.
    """

    info = SourceInfo(
        key="inaturalist_points",
        title="iNaturalist observation coordinates (recent sample)",
        provider="iNaturalist",
        url="https://www.inaturalist.org",
        license="Per-observation licences (CC0 / CC BY / CC BY-NC); only coordinates are binned",
        used_for="Density heatmaps",
        retrieval=(
            "API v1 /observations with per_page=200, order_by=created_at, order=desc; "
            "the `location` field (\"lat,lon\") of each record is binned into a grid. "
            "Coordinates of obscured (sensitive) records are already randomised by iNaturalist."
        ),
    )

    def __init__(self, http: JsonHttp, settings: Settings):
        self._http = http
        self._settings = settings

    def fetch(self, location: Location) -> dict:
        s = self._settings
        points: list = []
        for page in range(1, s.sample_pages + 1):
            payload = self._http.get_json(
                f"{BASE_URL}/observations",
                {
                    **_fungi_filter(location, s),
                    "per_page": s.sample_page_size,
                    "page": page,
                    "order_by": "created_at",
                    "order": "desc",
                },
            )
            results = payload.get("results") if isinstance(payload, dict) else None
            if results is None:
                raise SourceError("iNaturalist observations: results missing")
            points.extend(parse_points(results))
            if len(results) < s.sample_page_size:
                break
        return {"sample_points": points}


def parse_points(results: list) -> list:
    """Pull [lat, lon] pairs out of observation records, skipping blanks."""
    points = []
    for record in results:
        text = record.get("location")
        if not text or "," not in text:
            continue
        lat_text, lon_text = text.split(",", 1)
        try:
            points.append([round(float(lat_text), 5), round(float(lon_text), 5)])
        except ValueError:
            continue
    return points
