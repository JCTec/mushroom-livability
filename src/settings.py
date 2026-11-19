"""Central, immutable configuration.

Every tunable number of the project lives here so that the methodology can be
audited in one place. Nothing in this module performs I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Paths:
    """Filesystem layout. All paths derive from the project root."""

    root: Path = PROJECT_ROOT

    @property
    def locations_csv(self) -> Path:
        return self.root / "config" / "locations.csv"

    @property
    def cache_dir(self) -> Path:
        return self.root / "data" / "cache"

    @property
    def processed_dir(self) -> Path:
        return self.root / "data" / "processed"

    @property
    def paper_generated_dir(self) -> Path:
        return self.root / "paper" / "generated"

    def results_file(self, synthetic: bool) -> Path:
        """Real and synthetic results never share a file."""
        name = "demo_results.json" if synthetic else "results.json"
        return self.processed_dir / name


@dataclass(frozen=True)
class Settings:
    """Analysis parameters. Changing any of these changes the results."""

    # --- Geography -------------------------------------------------------
    radius_km: float = 25.0  # "living there" = everything within a day trip

    # --- iNaturalist -----------------------------------------------------
    fungi_taxon_id: int = 47170  # iNaturalist taxon "Fungi (including lichens)"
    quality_grade: str = "research"
    sample_pages: int = 2  # pages of 200 points used for the density map
    sample_page_size: int = 200

    # --- GBIF ------------------------------------------------------------
    gbif_fungi_kingdom_key: int = 5  # GBIF backbone key for kingdom Fungi

    # --- Climate (Open-Meteo / ERA5) -------------------------------------
    climate_start: str = "2014-01-01"
    climate_end: str = "2023-12-31"
    temp_zero_below_c: float = 0.0   # no fruiting at or below this mean temp
    temp_ideal_low_c: float = 8.0    # full suitability from here ...
    temp_ideal_high_c: float = 18.0  # ... to here
    temp_zero_above_c: float = 26.0  # too hot / dry at or above this
    precip_full_mm: float = 80.0     # monthly rain giving full moisture score
    suitable_month_threshold: float = 0.5

    # --- Seasonality -----------------------------------------------------
    # A month counts as "reliable" when it holds at least this share of the
    # year's observations (a perfectly even year gives 1/12 = 8.3 %) AND at
    # least `reliable_month_min_count` observations in absolute terms.
    reliable_month_min_share: float = 0.04
    reliable_month_min_count: int = 10

    # --- Population (WorldPop) -------------------------------------------
    worldpop_year: int = 2020
    circle_vertices: int = 32

    # --- Habitat (OpenStreetMap via Overpass) ----------------------------
    forest_sample_grid: int = 7  # 7x7 lattice clipped to the circle (~37 pts)

    # --- Density map -----------------------------------------------------
    heatmap_cells: int = 24  # cells per side

    # --- HTTP ------------------------------------------------------------
    user_agent: str = (
        "mushroom-livability/1.0 (open-data research project; "
        "set MUSHROOM_CONTACT env var to add a contact address)"
    )
    request_timeout_s: float = 60.0
    max_retries: int = 4
    # Minimum delay between two requests to the same host, in seconds.
    host_min_interval_s: dict = field(
        default_factory=lambda: {
            "api.inaturalist.org": 1.1,
            "api.gbif.org": 0.4,
            "archive-api.open-meteo.com": 1.0,
            "api.worldpop.org": 1.0,
            "overpass-api.de": 6.0,
        }
    )

    # --- Web app ---------------------------------------------------------
    host: str = "127.0.0.1"
    port: int = 8000
    # Target of the page's "Download the data" button (release with the data zip).
    download_url: str = "https://github.com/JCTec/mushroom-livability/releases/latest"

    @property
    def area_km2(self) -> float:
        import math

        return math.pi * self.radius_km**2
