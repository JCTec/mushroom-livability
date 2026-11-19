"""Colours used by the web app and the paper (single source of truth).

Component colours are the first five slots of a categorical palette that
was validated for colour-vision-deficiency separation in this fixed order;
do not reorder or cycle them. Density maps use one hue, light to dark.
"""

from __future__ import annotations

COMPONENT_COLORS = {
    "density": "#2a78d6",
    "richness": "#eb6834",
    "seasonality": "#1baf7a",
    "climate": "#eda100",
    "habitat": "#e87ba4",
}

# Sequential ramp endpoints (low -> high) for heatmaps.
SEQUENTIAL_LOW = "#eef1e8"
SEQUENTIAL_HIGH = "#1f5a3d"


def hex_to_rgb(color: str) -> tuple:
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def sequential(t: float) -> str:
    """Colour at position t (0..1) on the sequential ramp, as #rrggbb."""
    t = max(0.0, min(1.0, t))
    low, high = hex_to_rgb(SEQUENTIAL_LOW), hex_to_rgb(SEQUENTIAL_HIGH)
    return "#" + "".join(f"{round(a + (b - a) * t):02x}" for a, b in zip(low, high))


def as_dict() -> dict:
    return {
        "components": dict(COMPONENT_COLORS),
        "sequential_low": SEQUENTIAL_LOW,
        "sequential_high": SEQUENTIAL_HIGH,
    }
