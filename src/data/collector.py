"""Run every source for every location and collect the raw data.

A failing source never aborts the run: its error is recorded on the
location and the scoring layer decides what to do about the gap.
"""

from __future__ import annotations

from typing import Callable, Iterable

from src.domain import Location, RawLocationData
from src.data.sources import LocationSource

Progress = Callable[[str], None]


class DataCollector:
    def __init__(self, sources: Iterable[LocationSource], progress: Progress = lambda message: None):
        self._sources = list(sources)
        self._progress = progress

    @property
    def sources(self) -> list:
        return list(self._sources)

    def collect(self, locations: Iterable[Location]) -> dict:
        """Return {location_id: RawLocationData}."""
        locations = list(locations)
        collected = {}
        for index, location in enumerate(locations, start=1):
            raw = RawLocationData()
            for source in self._sources:
                key = source.info.key
                try:
                    raw.merge(source.fetch(location))
                    status = "ok"
                except Exception as exc:  # isolate failures per source
                    raw.errors[key] = f"{type(exc).__name__}: {exc}"[:300]
                    status = f"FAILED ({raw.errors[key]})"
                self._progress(f"[{index}/{len(locations)}] {location.name}: {key} {status}")
            collected[location.id] = raw
        return collected
