"""`python main.py check` - a live smoke test of every open data source.

Sends the real requests for ONE location, bypassing the cache, and prints
what came back. Run this first when anything looks wrong: it pinpoints
which API changed or is unreachable without running the whole pipeline.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable

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


def run_checks(settings: Settings, paths: Paths, location_id: str = "paris",
               progress: Callable[[str], None] = print) -> bool:
    """Return True when every source answered with a valid shape."""
    location = next((l for l in load_locations(paths.locations_csv) if l.id == location_id), None)
    if location is None:
        raise ValueError(f"Unknown location id: {location_id}")
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
