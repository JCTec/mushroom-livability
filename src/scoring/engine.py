"""The scoring engine: metrics in, explainable scores out.

Score(location) = 100 * sum_c  w_c * sum_m  w_cm * normalised(metric_m)

Coverage rules (applied before any arithmetic, and reported in the output):

1. A location missing any *required* sub-metric is not scored ("unscored").
2. An *optional* sub-metric missing for any scored location is dropped for
   ALL locations, so every score is built from the same ingredients.
3. A component left without sub-metrics is dropped; remaining weights are
   renormalised proportionally so they still sum to 1.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Sequence

from src.domain import ComponentScore, LocationScore, Metrics, SubScore
from src.scoring.components import DEFAULT_COMPONENTS, Component, validate


@dataclass
class ScoringResult:
    scores: list  # LocationScore, best first
    unscored: list = field(default_factory=list)  # {"location_id", "missing": [labels]}
    exclusions: list = field(default_factory=list)  # {"level", "key", "label", "reason"}
    model: list = field(default_factory=list)  # effective weights actually used

    def to_dict(self) -> dict:
        return {
            "scores": [s.to_dict() for s in self.scores],
            "unscored": self.unscored,
            "exclusions": self.exclusions,
            "model": self.model,
        }


class ScoringEngine:
    def __init__(self, components: Sequence[Component] = DEFAULT_COMPONENTS):
        validate(components)
        self._components = tuple(components)

    def score(self, metrics_by_id: dict) -> ScoringResult:
        result = ScoringResult(scores=[])
        scored_ids = self._split_scorable(metrics_by_id, result)
        if not scored_ids:
            return result

        active = self._active_model(metrics_by_id, scored_ids, result)
        normalised = self._normalise(metrics_by_id, scored_ids, active)

        scores = []
        for location_id in scored_ids:
            components = []
            for component, comp_weight, subs in active:
                sub_scores = [
                    SubScore(
                        key=sub.key,
                        label=sub.label,
                        unit=sub.unit,
                        raw=metrics_by_id[location_id].get(sub.key),
                        normalized=normalised[sub.key][location_id],
                        weight=sub_weight,
                    )
                    for sub, sub_weight in subs
                ]
                value = sum(s.normalized * s.weight for s in sub_scores)
                components.append(
                    ComponentScore(
                        key=component.key,
                        label=component.label,
                        weight=comp_weight,
                        value=value,
                        contribution=comp_weight * value * 100.0,
                        submetrics=sub_scores,
                    )
                )
            total = sum(c.contribution for c in components)
            scores.append(LocationScore(location_id=location_id, score=total, rank=0, components=components))

        scores.sort(key=lambda s: (-s.score, s.location_id))
        for rank, score in enumerate(scores, start=1):
            score.rank = rank
        result.scores = scores
        return result

    # -- coverage ---------------------------------------------------------

    def _split_scorable(self, metrics_by_id: dict, result: ScoringResult) -> list:
        scored = []
        for location_id, metrics in metrics_by_id.items():
            missing = [
                sub.label
                for component in self._components
                for sub in component.submetrics
                if sub.required and metrics.get(sub.key) is None
            ]
            if missing:
                result.unscored.append({"location_id": location_id, "missing": missing})
            else:
                scored.append(location_id)
        return scored

    def _active_model(self, metrics_by_id: dict, scored_ids: list, result: ScoringResult) -> list:
        """Return [(component, effective_weight, [(submetric, effective_weight)])]."""
        kept = []
        for component in self._components:
            subs = []
            for sub in component.submetrics:
                lacking = [i for i in scored_ids if metrics_by_id[i].get(sub.key) is None]
                if lacking:
                    result.exclusions.append(
                        {
                            "level": "submetric",
                            "key": sub.key,
                            "label": sub.label,
                            "reason": f"not available for {len(lacking)} of {len(scored_ids)} locations "
                                      f"(e.g. {lacking[0]}); dropped for all so scores stay comparable",
                        }
                    )
                else:
                    subs.append(sub)
            if subs:
                kept.append((component, subs))
            else:
                result.exclusions.append(
                    {
                        "level": "component",
                        "key": component.key,
                        "label": component.label,
                        "reason": "no sub-metric available; weight redistributed proportionally",
                    }
                )

        comp_total = sum(component.weight for component, _ in kept)
        active = []
        for component, subs in kept:
            sub_total = sum(sub.weight for sub in subs)
            sub_weights = [(sub, sub.weight / sub_total) for sub in subs]
            active.append((component, component.weight / comp_total, sub_weights))
            result.model.append(
                {
                    "key": component.key,
                    "label": component.label,
                    "question": component.question,
                    "nominal_weight": component.weight,
                    "weight": component.weight / comp_total,
                    "submetrics": [
                        {
                            "key": sub.key,
                            "label": sub.label,
                            "unit": sub.unit,
                            "nominal_weight": sub.weight,
                            "weight": weight,
                            "scaling": sub.scaler.description,
                            "why": sub.why,
                        }
                        for sub, weight in sub_weights
                    ],
                }
            )
        return active

    @staticmethod
    def _normalise(metrics_by_id: dict, scored_ids: list, active: list) -> dict:
        normalised = {}
        for _, _, subs in active:
            for sub, _ in subs:
                values = [float(metrics_by_id[i].get(sub.key)) for i in scored_ids]
                normalised[sub.key] = dict(zip(scored_ids, sub.scaler.scale(values)))
        return normalised


__all__ = ["ScoringEngine", "ScoringResult", "asdict", "Metrics"]
