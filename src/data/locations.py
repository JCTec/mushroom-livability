"""Load the list of candidate locations from config/locations.csv."""

from __future__ import annotations

import csv
from pathlib import Path

from src.domain import Location


def load_locations(path: Path) -> list:
    """Parse and validate the CSV. Raises ValueError on any bad row.

    Columns: id, name, country, group (region), lat, lon. Extra columns are ignored.
    """
    locations = []
    seen = set()
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        for line_no, row in enumerate(csv.DictReader(handle), start=2):
            try:
                location = Location(
                    id=row["id"].strip(),
                    name=row["name"].strip(),
                    country=row["country"].strip(),
                    group=row["group"].strip(),
                    lat=float(row["lat"]),
                    lon=float(row["lon"]),
                )
            except (KeyError, ValueError, AttributeError) as exc:
                raise ValueError(f"{path}:{line_no}: invalid row ({exc})") from exc
            if not (-90 <= location.lat <= 90 and -180 <= location.lon <= 180):
                raise ValueError(f"{path}:{line_no}: coordinates out of range")
            if not location.id or location.id in seen:
                raise ValueError(f"{path}:{line_no}: missing or duplicate id '{location.id}'")
            seen.add(location.id)
            locations.append(location)
    if not locations:
        raise ValueError(f"{path}: no locations found")
    return locations
