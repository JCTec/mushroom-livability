"""Seasonal reliability from a 12-month observation histogram."""

from __future__ import annotations

import math
from typing import Optional


def monthly_shares(monthly: list) -> list:
    """Share of the yearly total falling in each month (sums to 1, or 0s)."""
    total = sum(monthly)
    if total <= 0:
        return [0.0] * 12
    return [count / total for count in monthly]


def reliable_months(monthly: Optional[list], min_share: float, min_count: int) -> Optional[int]:
    """Months with meaningful fruiting activity.

    A month qualifies when it holds at least `min_share` of the year's
    observations AND at least `min_count` observations. The absolute floor
    stops a place with a handful of records from looking "reliable".
    """
    if not monthly or len(monthly) != 12:
        return None
    shares = monthly_shares(monthly)
    return sum(1 for count, share in zip(monthly, shares) if share >= min_share and count >= min_count)


def evenness(monthly: Optional[list]) -> Optional[float]:
    """Pielou evenness of the monthly distribution (0 = one month, 1 = flat).

    Reported for context only; it is not part of the score.
    """
    if not monthly or len(monthly) != 12:
        return None
    shares = [s for s in monthly_shares(monthly) if s > 0]
    if not shares:
        return 0.0
    entropy = -sum(s * math.log(s) for s in shares)
    return entropy / math.log(12)
