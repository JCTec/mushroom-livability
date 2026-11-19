"""Climate processing: daily series -> monthly normals -> suitability.

The suitability model is intentionally simple and fully explainable:

    month_suitability = temperature_factor * moisture_factor

- temperature_factor is a trapezoid: 0 at/below `temp_zero_below_c`, rising
  linearly to 1 at `temp_ideal_low_c`, flat to `temp_ideal_high_c`, falling
  linearly to 0 at `temp_zero_above_c`.
- moisture_factor = min(1, monthly_precipitation / `precip_full_mm`).

The yearly score is the mean of the twelve monthly values (0..1).
"""

from __future__ import annotations

from typing import Optional

from src.settings import Settings


def monthly_normals(dates: list, temps: list, precips: list) -> list:
    """Reduce daily values to 12 monthly normals.

    `dates` are ISO strings (YYYY-MM-DD). Temperature is averaged over all
    days of a calendar month; precipitation is the mean *monthly total*
    (sum over all days of that month divided by the number of distinct
    years in which the month occurs). Missing values (None) are skipped.
    """
    if not (len(dates) == len(temps) == len(precips)):
        raise ValueError("dates, temps and precips must have the same length")
    temp_sum = [0.0] * 12
    temp_n = [0] * 12
    precip_sum = [0.0] * 12
    years = [set() for _ in range(12)]
    for date, temp, precip in zip(dates, temps, precips):
        month = int(date[5:7]) - 1
        if temp is not None:
            temp_sum[month] += float(temp)
            temp_n[month] += 1
        if precip is not None:
            precip_sum[month] += float(precip)
            years[month].add(date[:4])
    normals = []
    for m in range(12):
        if temp_n[m] == 0 or not years[m]:
            raise ValueError(f"No climate data for month {m + 1}")
        normals.append(
            {"temp_c": round(temp_sum[m] / temp_n[m], 2), "precip_mm": round(precip_sum[m] / len(years[m]), 1)}
        )
    return normals


def temperature_factor(temp_c: float, s: Settings) -> float:
    if temp_c <= s.temp_zero_below_c or temp_c >= s.temp_zero_above_c:
        return 0.0
    if temp_c < s.temp_ideal_low_c:
        return (temp_c - s.temp_zero_below_c) / (s.temp_ideal_low_c - s.temp_zero_below_c)
    if temp_c <= s.temp_ideal_high_c:
        return 1.0
    return (s.temp_zero_above_c - temp_c) / (s.temp_zero_above_c - s.temp_ideal_high_c)


def moisture_factor(precip_mm: float, s: Settings) -> float:
    return max(0.0, min(1.0, precip_mm / s.precip_full_mm))


def month_suitability(temp_c: float, precip_mm: float, s: Settings) -> float:
    return temperature_factor(temp_c, s) * moisture_factor(precip_mm, s)


def monthly_suitability(normals: list, s: Settings) -> list:
    return [round(month_suitability(m["temp_c"], m["precip_mm"], s), 4) for m in normals]


def climate_suitability(normals: Optional[list], s: Settings) -> Optional[float]:
    """Mean monthly suitability (0..1), or None without data."""
    if not normals or len(normals) != 12:
        return None
    values = monthly_suitability(normals, s)
    return sum(values) / 12.0


def suitable_months(normals: Optional[list], s: Settings) -> Optional[int]:
    """Number of months whose suitability reaches the threshold."""
    if not normals or len(normals) != 12:
        return None
    return sum(1 for v in monthly_suitability(normals, s) if v >= s.suitable_month_threshold)
