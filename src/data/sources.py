"""The contract every data source fulfils.

Adding a new open dataset means writing one class that satisfies
`LocationSource` and registering it in `src/pipeline.py`; nothing else
changes (open/closed principle).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

from src.domain import Location


@dataclass(frozen=True)
class SourceInfo:
    """Attribution and retrieval documentation, shown in the app and paper."""

    key: str
    title: str
    provider: str
    url: str
    license: str
    used_for: str
    retrieval: str

    def to_dict(self) -> dict:
        return asdict(self)


class SourceError(RuntimeError):
    """A source returned something it should not have (shape or content)."""


class LocationSource(Protocol):
    """Fetches some fields of `RawLocationData` for one location."""

    info: SourceInfo

    def fetch(self, location: Location) -> dict:
        """Return a dict of RawLocationData fields. Raise on failure."""
        ...
