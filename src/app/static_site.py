"""Static copy of the web app, for hosts that cannot run Flask (GitHub Pages).

The page only ever needs three things: index.html, the static assets and the
results document at the relative URL `api/results`. Writing exactly those
files gives a site that behaves like `python main.py serve`, with the same
front end and the same data (no logic is duplicated).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from src.app.server import APP_DIR
from src.reporting.store import load_results


def export_site(results_path: Path, out_dir: Path) -> list:
    """Write the static site to `out_dir` (replacing it) and return the files written."""
    results = load_results(Path(results_path))
    if results is None:
        raise FileNotFoundError(f"No results at {results_path}; run the pipeline first.")
    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(APP_DIR / "static", out / "static")
    shutil.copy2(APP_DIR / "templates" / "index.html", out / "index.html")
    (out / "api").mkdir(parents=True)
    (out / "api" / "results").write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")  # serve files as-is, no Jekyll processing
    return sorted(p for p in out.rglob("*") if p.is_file())
