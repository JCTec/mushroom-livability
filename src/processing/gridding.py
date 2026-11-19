"""Bin observation points into a square grid around a location."""

from __future__ import annotations

from src.processing.geo import bounding_box


def grid_counts(points: list, lat: float, lon: float, radius_km: float, cells: int) -> list:
    """Return a `cells` x `cells` matrix of point counts.

    Row 0 is the northernmost row (so the matrix reads like a map), column 0
    the westernmost. Points outside the bounding box are ignored.
    """
    box = bounding_box(lat, lon, radius_km)
    height = box["north"] - box["south"]
    width = box["east"] - box["west"]
    grid = [[0] * cells for _ in range(cells)]
    for point in points:
        p_lat, p_lon = point[0], point[1]
        fy = (box["north"] - p_lat) / height
        fx = (p_lon - box["west"]) / width
        if not (0.0 <= fx < 1.0 and 0.0 <= fy < 1.0):
            continue
        grid[int(fy * cells)][int(fx * cells)] += 1
    return grid
