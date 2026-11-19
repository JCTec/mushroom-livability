"""Turn scores into the plain-language answer to the project's question."""

from __future__ import annotations

from typing import Optional

from src.visualization.charts import contribution_gap

TIE_MARGIN = 1.0  # points; a smaller gap is reported as "too close to call"


def build_verdict(locations: list) -> dict:
    """`locations` are result entries (dicts with role, scored, score...)."""
    scored = [loc for loc in locations if loc.get("scored")]
    verdict = {"leader_id": None, "headline": None, "best_by_role": {}}
    if not scored:
        return verdict

    leader = min(scored, key=lambda loc: loc["rank"])
    verdict["leader_id"] = leader["id"]
    for role in ("headline", "europe", "benchmark"):
        in_role = [loc for loc in scored if loc["role"] == role]
        if in_role:
            verdict["best_by_role"][role] = min(in_role, key=lambda loc: loc["rank"])["id"]

    headline = [loc for loc in scored if loc["role"] == "headline"]
    if len(headline) == 2:
        verdict["headline"] = _head_to_head(*sorted(headline, key=lambda loc: loc["rank"]))
    return verdict


def _head_to_head(winner: dict, loser: dict) -> dict:
    margin = winner["score"] - loser["score"]
    gaps = contribution_gap(winner, loser)
    return {
        "winner_id": winner["id"],
        "loser_id": loser["id"],
        "margin": margin,
        "is_tie": margin < TIE_MARGIN,
        "gaps": gaps,
        "main_driver": gaps[0]["label"] if gaps else None,
        "sentence": _sentence(winner, loser, margin, gaps),
    }


def _sentence(winner: dict, loser: dict, margin: float, gaps: list) -> str:
    if margin < TIE_MARGIN:
        return (
            f"{winner['name']} and {loser['name']} are too close to call "
            f"({winner['score']:.1f} vs {loser['score']:.1f} out of 100)."
        )
    text = (
        f"{winner['name']} is the better base for a mushroom lover: "
        f"{winner['score']:.1f} vs {loser['score']:.1f} out of 100 for {loser['name']}."
    )
    driver: Optional[dict] = next((g for g in gaps if g["gap"] >= TIE_MARGIN), None)
    if driver:
        text += f" The biggest advantage is {driver['label'].lower()} (+{driver['gap']:.1f} points)."
    counter = next((g for g in gaps if g["gap"] <= -TIE_MARGIN), None)
    if counter:
        text += f" {loser['name']} does better on {counter['label'].lower()} (+{-counter['gap']:.1f} points)."
    return text
