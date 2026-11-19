"""SYNTHETIC data for demos and offline UI testing. NOT REAL.

The numbers produced here are pseudo-random (seeded by the location id) and
carry no information about the real world. They exist so the web app and
the paper build can be exercised without network access. Results built from
this source are flagged `synthetic: true`, stored in a separate file and
shown with a warning banner everywhere.
"""

from __future__ import annotations

import hashlib
import math
import random

from src.data.sources import SourceInfo
from src.domain import Location
from src.processing.geo import km_to_deg
from src.settings import Settings


class SyntheticSource:
    info = SourceInfo(
        key="synthetic",
        title="SYNTHETIC placeholder data (not real)",
        provider="Generated locally by src/data/synthetic.py",
        url="",
        license="n/a",
        used_for="Demo mode and offline testing only",
        retrieval="Pseudo-random numbers seeded by the location id. No real-world meaning.",
    )

    def __init__(self, settings: Settings):
        self._settings = settings

    def fetch(self, location: Location) -> dict:
        seed = int(hashlib.sha256(location.id.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        s = self._settings

        fungi = int(10 ** rng.uniform(2.6, 4.4))
        peak = rng.uniform(8.5, 10.5)
        width = rng.uniform(1.2, 3.0)
        weights = [math.exp(-((m - peak) ** 2) / (2 * width**2)) + rng.uniform(0.02, 0.12) for m in range(1, 13)]
        total_w = sum(weights)
        monthly = [int(fungi * w / total_w) for w in weights]

        base_temp = rng.uniform(4.0, 16.0)
        climate = [
            {
                "temp_c": round(base_temp - 9.0 * math.cos(2 * math.pi * (m - 0.5) / 12), 2),
                "precip_mm": round(rng.uniform(25, 120), 1),
            }
            for m in range(12)
        ]

        dlat, dlon = km_to_deg(location.lat, s.radius_km)
        hot = [(rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), rng.uniform(0.08, 0.3)) for _ in range(4)]
        points = []
        for _ in range(min(fungi, s.sample_pages * s.sample_page_size)):
            cx, cy, spread = rng.choice(hot)
            points.append(
                [round(location.lat + (cy + rng.gauss(0, spread)) * dlat, 5),
                 round(location.lon + (cx + rng.gauss(0, spread)) * dlon, 5)]
            )

        return {
            "fungi_observations": fungi,
            "all_observations": int(fungi / rng.uniform(0.01, 0.08)),
            "species_count": int(fungi ** rng.uniform(0.62, 0.78)),
            "monthly_observations": monthly,
            "sample_points": points,
            "gbif_records": int(fungi * rng.uniform(1.2, 6.0)),
            "climate_monthly": climate,
            "population": float(int(10 ** rng.uniform(5.3, 7.0))),
            "forest_share": round(rng.uniform(0.03, 0.6), 4),
        }
