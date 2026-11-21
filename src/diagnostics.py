"""`python main.py check` - a live smoke test of every open data source.

Sends the real requests for ONE location, bypassing the cache, and prints
what came back. Run this first when anything looks wrong: it pinpoints
which API changed or is unreachable without running the whole pipeline.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable, Optional

from src.data.climate import OpenMeteoClimateSource
from src.data.gbif import GbifSource
from src.data.habitat import OverpassForestSource
from src.data.http import PoliteHttpClient
from src.data.inaturalist import INaturalistSampleSource, INaturalistStatsSource
from src.data.locations import load_locations
from src.data.population import WorldPopSource
from src.settings import Paths, Settings


def _describe(values: dict) -> str:
    parts = []
    for key, value in values.items():
        if isinstance(value, list):
            preview = value[:3] if key != "monthly_observations" else value
            parts.append(f"{key}: {len(value)} items, e.g. {preview}")
        else:
            parts.append(f"{key}: {value}")
    return "; ".join(parts)


def pick_location(locations: list, location_id: Optional[str] = None):
    """The requested location, or the first row of the list when none is given."""
    if location_id is None:
        return locations[0]
    location = next((l for l in locations if l.id == location_id), None)
    if location is None:
        raise ValueError(f"Unknown location id: {location_id}")
    return location


def run_checks(settings: Settings, paths: Paths, location_id: Optional[str] = None,
               progress: Callable[[str], None] = print) -> bool:
    """Return True when every source answered with a valid shape.

    Without `location_id` the first row of config/locations.csv is used, so no
    city is hard-coded as the reference.
    """
    location = pick_location(load_locations(paths.locations_csv), location_id)
    quick = replace(settings, sample_pages=1)
    http = PoliteHttpClient(quick.user_agent, quick.host_min_interval_s, quick.request_timeout_s, max_retries=1)
    sources = [
        INaturalistStatsSource(http, quick),
        INaturalistSampleSource(http, quick),
        GbifSource(http, quick),
        OpenMeteoClimateSource(http, quick),
        WorldPopSource(http, quick),
        OverpassForestSource(http, quick),
    ]
    progress(f"Live source check for {location.name} (radius {quick.radius_km:g} km), cache bypassed.\n")
    all_ok = True
    for source in sources:
        try:
            values = source.fetch(location)
            progress(f"  OK    {source.info.key:<18} {_describe(values)}")
        except Exception as exc:
            all_ok = False
            progress(f"  FAIL  {source.info.key:<18} {type(exc).__name__}: {exc}")
    progress("\nAll sources OK." if all_ok else "\nAt least one source failed - see docs/KNOWN_RISKS.md.")
    return all_ok
