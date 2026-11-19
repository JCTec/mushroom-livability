"""Small geodesy helpers (pure functions, standard library only)."""

from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0088
KM_PER_DEG_LAT = 111.32


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in kilometres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def km_to_deg(lat: float, km: float) -> tuple:
    """Convert a distance to (delta_lat, delta_lon) degrees at a latitude."""
    dlat = km / KM_PER_DEG_LAT
    dlon = km / (KM_PER_DEG_LAT * max(0.01, math.cos(math.radians(lat))))
    return dlat, dlon


def bounding_box(lat: float, lon: float, radius_km: float) -> dict:
    """Axis-aligned box enclosing the circle (south, west, north, east)."""
    dlat, dlon = km_to_deg(lat, radius_km)
    return {"south": lat - dlat, "west": lon - dlon, "north": lat + dlat, "east": lon + dlon}


def circle_polygon(lat: float, lon: float, radius_km: float, vertices: int = 32) -> list:
    """Closed ring of [lon, lat] pairs approximating a circle (GeoJSON order)."""
    dlat, dlon = km_to_deg(lat, radius_km)
    ring = []
    for i in range(vertices):
        angle = 2 * math.pi * i / vertices
        ring.append([round(lon + dlon * math.cos(angle), 6), round(lat + dlat * math.sin(angle), 6)])
    ring.append(ring[0])
    return ring


def lattice_in_circle(lat: float, lon: float, radius_km: float, n: int) -> list:
    """Regular n x n lattice of (lat, lon) points, keeping those in the circle.

    Used for point-sampling estimates (e.g. "what share of the area is
    forest?"). Points sit at cell centres so none lies on the boundary.
    """
    dlat, dlon = km_to_deg(lat, radius_km)
    points = []
    for row in range(n):
        for col in range(n):
            fy = (row + 0.5) / n * 2 - 1
            fx = (col + 0.5) / n * 2 - 1
            if fx * fx + fy * fy <= 1.0:
                points.append((round(lat + fy * dlat, 5), round(lon + fx * dlon, 5)))
    return points
