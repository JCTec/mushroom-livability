"""Read and write the results file (the contract between pipeline and app)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


def save_results(results: dict, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=1)
    tmp.replace(path)


def load_results(path: Path) -> Optional[dict]:
    path = Path(path)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
