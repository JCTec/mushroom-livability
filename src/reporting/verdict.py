"""Turn scores into the plain-language answer to the project's question.

No location is singled out in advance: the answer is whoever ranks first,
explained against whoever ranks second, plus the best location of every
region so that no region is privileged in the summary.
"""

from __future__ import annotations

from typing import Optional

from src.visualization.charts import contribution_gap

TIE_MARGIN = 1.0  # points; a smaller gap is reported as "too close to call"


def build_verdict(locations: list) -> dict:
    """`locations` are result entries (dicts with id, name, country, group, scored, score, rank...)."""
    scored = sorted((loc for loc in locations if loc.get("scored")), key=lambda loc: loc["rank"])
    verdict = {"leader_id": None, "runner_up_id": None, "best_by_group": {}, "top": None,
               "tie_margin": TIE_MARGIN, "sentence": "No location could be scored yet."}
    if not scored:
        return verdict

    leader = scored[0]
    verdict["leader_id"] = leader["id"]
    for loc in scored:  # ranked order, so the first seen per group is that group's best
        verdict["best_by_group"].setdefault(loc["group"], loc["id"])

    if len(scored) >= 2:
        runner_up = scored[1]
        verdict["runner_up_id"] = runner_up["id"]
        verdict["top"] = _head_to_head(leader, runner_up)
        verdict["sentence"] = verdict["top"]["sentence"]
    else:
        verdict["sentence"] = f"{_place(leader)} is the only location scored ({leader['score']:.1f} out of 100)."
    return verdict


def _place(loc: dict) -> str:
    return f"{loc['name']} ({loc['country']})" if loc.get("country") else loc["name"]


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
            f"{_place(winner)} and {_place(loser)} are too close to call at the top of the ranking "
            f"({winner['score']:.1f} vs {loser['score']:.1f} out of 100)."
        )
    text = (
        f"{_place(winner)} ranks first for a mushroom lover with {winner['score']:.1f} out of 100, "
        f"ahead of {_place(loser)} with {loser['score']:.1f}."
    )
    driver: Optional[dict] = next((g for g in gaps if g["gap"] >= TIE_MARGIN), None)
    if driver:
        text += f" Its biggest advantage is {driver['label'].lower()} (+{driver['gap']:.1f} points)."
    counter = next((g for g in gaps if g["gap"] <= -TIE_MARGIN), None)
    if counter:
        text += f" {loser['name']} does better on {counter['label'].lower()} (+{-counter['gap']:.1f} points)."
    return text
