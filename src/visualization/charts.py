"""Chart-ready summaries derived from scores (pure data)."""

from __future__ import annotations


def contribution_gap(score_a: dict, score_b: dict) -> list:
    """Per-component point difference (a minus b), largest absolute first.

    Explains *why* one location beats another.
    """
    by_key_b = {c["key"]: c for c in score_b["components"]}
    gaps = []
    for component in score_a["components"]:
        other = by_key_b.get(component["key"])
        if other is None:
            continue
        gaps.append(
            {
                "key": component["key"],
                "label": component["label"],
                "a": component["contribution"],
                "b": other["contribution"],
                "gap": component["contribution"] - other["contribution"],
            }
        )
    gaps.sort(key=lambda g: -abs(g["gap"]))
    return gaps
