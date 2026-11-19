"""Declarative definition of the Mushroom Livability Score.

This file *is* the scoring model. To change weights, add a sub-metric or
add a component, edit `DEFAULT_COMPONENTS`; the engine needs no changes.

Weights of components sum to 1. Weights of sub-metrics inside a component
sum to 1. `required=True` sub-metrics must exist for a location to be
scored at all; optional ones are dropped for everyone when any scored
location lacks them (weights are then renormalised - see engine.py).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.scoring.normalization import FixedRangeScaler, LogMinMaxScaler, Scaler


@dataclass(frozen=True)
class SubMetric:
    key: str  # attribute name on src.domain.Metrics
    label: str
    unit: str
    weight: float
    scaler: Scaler
    required: bool
    why: str


@dataclass(frozen=True)
class Component:
    key: str
    label: str
    weight: float
    question: str  # the plain-language question this component answers
    submetrics: tuple


DEFAULT_COMPONENTS = (
    Component(
        key="density",
        label="Observation density",
        weight=0.25,
        question="How much fungal life is actually being found here?",
        submetrics=(
            SubMetric("obs_per_km2", "Observations per km²", "obs/km²", 0.40, LogMinMaxScaler(), True,
                      "Research-grade iNaturalist fungi records per unit area."),
            SubMetric("obs_per_100k", "Observations per 100k residents", "obs/100k", 0.20, LogMinMaxScaler(), False,
                      "Per-capita rate; stops big cities winning on headcount alone."),
            SubMetric("fungal_share", "Fungal share of all observations", "share", 0.20, LogMinMaxScaler(), False,
                      "Fungi as a share of all research-grade records; corrects for how popular "
                      "iNaturalist is locally."),
            SubMetric("gbif_per_km2", "GBIF records per km²", "rec/km²", 0.20, LogMinMaxScaler(), False,
                      "Adds museum and national recording-scheme data."),
        ),
    ),
    Component(
        key="richness",
        label="Species richness",
        weight=0.25,
        question="How many different fungi can you expect to meet?",
        submetrics=(
            SubMetric("species_richness", "Species observed", "species", 1.0, LogMinMaxScaler(), True,
                      "Distinct research-grade fungal taxa recorded within the radius."),
        ),
    ),
    Component(
        key="seasonality",
        label="Seasonal reliability",
        weight=0.20,
        question="For how much of the year is there something to find?",
        submetrics=(
            SubMetric("reliable_months", "Reliable months", "months", 1.0, FixedRangeScaler(12.0), True,
                      "Months holding at least 4 % of yearly records and at least 10 records."),
        ),
    ),
    Component(
        key="climate",
        label="Climate suitability",
        weight=0.20,
        question="Does the weather favour fruiting?",
        submetrics=(
            SubMetric("climate_suitability", "Climate suitability index", "index (0–1)", 1.0, FixedRangeScaler(1.0), True,
                      "Mean monthly product of a temperature window and a moisture factor (ERA5 normals)."),
        ),
    ),
    Component(
        key="habitat",
        label="Forest habitat",
        weight=0.10,
        question="Is there woodland within reach?",
        submetrics=(
            SubMetric("forest_share", "Woodland share of surrounding area", "share", 1.0, FixedRangeScaler(0.6),
                      False, "Share of the circle mapped as forest/wood in OpenStreetMap; 60 % or more gives "
                             "full marks."),
        ),
    ),
)


def validate(components) -> None:
    """Fail fast on a mis-specified model."""
    total = sum(c.weight for c in components)
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"Component weights must sum to 1 (got {total})")
    for component in components:
        sub_total = sum(s.weight for s in component.submetrics)
        if abs(sub_total - 1.0) > 1e-9:
            raise ValueError(f"Sub-metric weights of '{component.key}' must sum to 1 (got {sub_total})")
