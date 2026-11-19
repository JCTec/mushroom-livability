"""Scalers: map raw metric values onto 0..1 so they can be combined.

Each scaler is a tiny strategy object with one method, `scale(values)`,
which takes the values of *all scored locations* for one metric and returns
their normalised counterparts in the same order.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol


class Scaler(Protocol):
    description: str

    def scale(self, values: list) -> list: ...


@dataclass(frozen=True)
class LogMinMaxScaler:
    """log(1 + x), then min-max across locations.

    For heavy-tailed counts (observations, species): the logarithm stops one
    record-rich city from flattening everyone else. The best location gets
    1, the weakest 0. If all values are equal every location gets 0.5.
    """

    description: str = "log(1+x), then min-max"

    def scale(self, values: list) -> list:
        logs = [math.log1p(max(0.0, v)) for v in values]
        low, high = min(logs), max(logs)
        if high - low < 1e-12:
            return [0.5] * len(values)
        return [(v - low) / (high - low) for v in logs]


@dataclass(frozen=True)
class FixedRangeScaler:
    """x / maximum, clamped to 0..1.

    For metrics with a natural ceiling (months out of 12, shares). The
    result does not depend on which other locations are in the comparison.
    """

    maximum: float = 1.0

    @property
    def description(self) -> str:
        return f"x / {self.maximum:g}, capped at 1"

    def scale(self, values: list) -> list:
        return [max(0.0, min(1.0, v / self.maximum)) for v in values]
