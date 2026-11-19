"""Prepare heatmap payloads (pure data; rendering happens in the browser)."""

from __future__ import annotations

from typing import Optional

from src.domain import Location
from src.processing.gridding import grid_counts
from src.processing.seasonality import monthly_shares
from src.settings import Settings


def density_heatmap(location: Location, points: Optional[list], settings: Settings) -> Optional[dict]:
    """Grid of observation counts around a location, or None without points."""
    if not points:
        return None
    counts = grid_counts(points, location.lat, location.lon, settings.radius_km, settings.heatmap_cells)
    return {
        "cells": settings.heatmap_cells,
        "counts": counts,
        "max": max(max(row) for row in counts),
        "points": sum(sum(row) for row in counts),
        "span_km": round(settings.radius_km * 2, 1),
    }


def seasonal_row(monthly: Optional[list]) -> Optional[list]:
    """Share of the year's observations per month (12 values, 0..1)."""
    if not monthly or len(monthly) != 12:
        return None
    return [round(share, 4) for share in monthly_shares(monthly)]
