"""Turn raw source data into the interpretable metrics that get scored."""

from __future__ import annotations

from typing import Optional

from src.domain import Metrics, RawLocationData
from src.processing import climate, seasonality
from src.settings import Settings


def _ratio(numerator: Optional[float], denominator: Optional[float], scale: float = 1.0) -> Optional[float]:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator * scale


def build_metrics(raw: RawLocationData, settings: Settings) -> Metrics:
    """Pure function: RawLocationData -> Metrics. Missing inputs give None."""
    area = settings.area_km2
    return Metrics(
        obs_per_km2=_ratio(raw.fungi_observations, area),
        obs_per_100k=_ratio(raw.fungi_observations, raw.population, 100_000.0),
        fungal_share=_ratio(raw.fungi_observations, raw.all_observations),
        gbif_per_km2=_ratio(raw.gbif_records, area),
        species_richness=None if raw.species_count is None else float(raw.species_count),
        reliable_months=_as_float(
            seasonality.reliable_months(
                raw.monthly_observations, settings.reliable_month_min_share, settings.reliable_month_min_count
            )
        ),
        seasonal_evenness=seasonality.evenness(raw.monthly_observations),
        climate_suitability=climate.climate_suitability(raw.climate_monthly, settings),
        suitable_climate_months=_as_float(climate.suitable_months(raw.climate_monthly, settings)),
        forest_share=raw.forest_share,
    )


def _as_float(value) -> Optional[float]:
    return None if value is None else float(value)
