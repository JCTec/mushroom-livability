"""Plain data structures shared by every layer.

No behaviour beyond (de)serialisation lives here; layers depend on these
types instead of on each other.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class Location:
    """A place someone could live. `role` is headline, europe or benchmark."""

    id: str
    name: str
    country: str
    group: str
    role: str
    lat: float
    lon: float

    @property
    def is_headline(self) -> bool:
        return self.role == "headline"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RawLocationData:
    """Everything the data layer learned about one location.

    Every field is optional: a source that fails leaves its fields at None
    and records a message in `errors` (keyed by source name).
    """

    fungi_observations: Optional[int] = None
    all_observations: Optional[int] = None
    species_count: Optional[int] = None
    monthly_observations: Optional[list] = None  # 12 ints, January first
    sample_points: Optional[list] = None  # [[lat, lon], ...]
    gbif_records: Optional[int] = None
    climate_monthly: Optional[list] = None  # 12 x {"temp_c", "precip_mm"}
    population: Optional[float] = None
    forest_share: Optional[float] = None  # 0..1
    errors: dict = field(default_factory=dict)

    FIELDS = (
        "fungi_observations",
        "all_observations",
        "species_count",
        "monthly_observations",
        "sample_points",
        "gbif_records",
        "climate_monthly",
        "population",
        "forest_share",
    )

    def merge(self, values: dict) -> None:
        """Copy known fields from a source's result; reject unknown ones."""
        for key, value in values.items():
            if key not in self.FIELDS:
                raise KeyError(f"Unknown raw data field: {key}")
            setattr(self, key, value)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "RawLocationData":
        raw = cls()
        raw.merge({k: payload.get(k) for k in cls.FIELDS})
        raw.errors = dict(payload.get("errors", {}))
        return raw


@dataclass
class Metrics:
    """Interpretable numbers derived from raw data (None = not available)."""

    obs_per_km2: Optional[float] = None
    obs_per_100k: Optional[float] = None
    fungal_share: Optional[float] = None
    gbif_per_km2: Optional[float] = None
    species_richness: Optional[float] = None
    reliable_months: Optional[float] = None
    seasonal_evenness: Optional[float] = None
    climate_suitability: Optional[float] = None
    suitable_climate_months: Optional[float] = None
    forest_share: Optional[float] = None

    def get(self, key: str) -> Optional[float]:
        return getattr(self, key)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SubScore:
    key: str
    label: str
    unit: str
    raw: Optional[float]
    normalized: float  # 0..1
    weight: float  # effective weight inside its component (sums to 1)


@dataclass
class ComponentScore:
    key: str
    label: str
    weight: float  # effective weight in the total (all components sum to 1)
    value: float  # 0..1
    contribution: float  # points out of 100 = weight * value * 100
    submetrics: list


@dataclass
class LocationScore:
    location_id: str
    score: float  # 0..100
    rank: int
    components: list

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
