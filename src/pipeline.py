"""Composition root: wires the layers together and runs the analysis.

    locations.csv -> DataCollector -> build_metrics -> ScoringEngine
                  -> results.json (+ LaTeX fragments for the paper)

This is the only module that knows about concrete classes of every layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Iterable, Optional

from src.data.climate import OpenMeteoClimateSource
from src.data.collector import DataCollector
from src.data.gbif import GbifSource
from src.data.habitat import OverpassForestSource
from src.data.http import CachedJsonHttp, PoliteHttpClient
from src.data.inaturalist import INaturalistSampleSource, INaturalistStatsSource
from src.data.locations import load_locations
from src.data.population import WorldPopSource
from src.data.synthetic import SyntheticSource
from src.domain import Location
from src.processing.climate import monthly_suitability
from src.processing.metrics import build_metrics
from src.reporting import latex
from src.reporting.store import save_results
from src.reporting.verdict import build_verdict
from src.scoring.engine import ScoringEngine
from src.settings import Paths, Settings
from src.visualization import palette
from src.visualization.heatmap import density_heatmap, seasonal_row

SCHEMA_VERSION = 2  # 2: no location roles; verdict = rank 1 vs rank 2 + best per group; data_retrieved
Progress = Callable[[str], None]


def build_http(settings: Settings, paths: Paths) -> CachedJsonHttp:
    client = PoliteHttpClient(
        user_agent=settings.user_agent,
        host_min_interval_s=settings.host_min_interval_s,
        timeout_s=settings.request_timeout_s,
        max_retries=settings.max_retries,
    )
    return CachedJsonHttp(client, paths.cache_dir)


def build_sources(settings: Settings, paths: Paths, synthetic: bool,
                  http: Optional[CachedJsonHttp] = None) -> list:
    """The ordered list of sources. Register new datasets here."""
    if synthetic:
        return [SyntheticSource(settings)]
    http = http or build_http(settings, paths)
    return [
        INaturalistStatsSource(http, settings),
        INaturalistSampleSource(http, settings),
        GbifSource(http, settings),
        OpenMeteoClimateSource(http, settings),
        WorldPopSource(http, settings),
        OverpassForestSource(http, settings),
    ]


def select_locations(locations: list, only: Optional[Iterable[str]]) -> list:
    if not only:
        return locations
    wanted = {item.strip().lower() for item in only if item.strip()}
    chosen = [loc for loc in locations if loc.id in wanted]
    unknown = wanted - {loc.id for loc in chosen}
    if unknown:
        raise ValueError(f"Unknown location ids: {sorted(unknown)}")
    return chosen


def assemble_results(locations: list, raw_by_id: dict, settings: Settings, sources: list, synthetic: bool,
                     engine: Optional[ScoringEngine] = None, data_retrieved: Optional[dict] = None) -> dict:
    """Pure function: raw data -> the full results document.

    `data_retrieved` is {"first", "last"} retrieval timestamps of the provider
    responses used (None for synthetic data); `generated_at` is only the build time.
    """
    engine = engine or ScoringEngine()
    metrics_by_id = {loc.id: build_metrics(raw_by_id[loc.id], settings) for loc in locations}
    scoring = engine.score(metrics_by_id)
    score_by_id = {score.location_id: score.to_dict() for score in scoring.scores}

    entries = []
    for loc in locations:
        raw = raw_by_id[loc.id]
        score = score_by_id.get(loc.id)
        entries.append(_location_entry(loc, raw, metrics_by_id[loc.id], score, settings))
    entries.sort(key=lambda e: (e["rank"] is None, e["rank"] or 0, e["name"]))

    names = {loc.id: loc.name for loc in locations}
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "synthetic": synthetic,
        "data_retrieved": data_retrieved,
        "settings": {
            "radius_km": settings.radius_km,
            "area_km2": round(settings.area_km2, 1),
            "climate_period": f"{settings.climate_start[:4]}–{settings.climate_end[:4]}",
            "worldpop_year": settings.worldpop_year,
            "reliable_month_min_share": settings.reliable_month_min_share,
            "reliable_month_min_count": settings.reliable_month_min_count,
            "sample_size_cap": settings.sample_pages * settings.sample_page_size,
            "download_url": settings.download_url,
        },
        "groups": sorted({loc.group for loc in locations}),  # alphabetical: no region listed first by design
        "palette": palette.as_dict(),
        "model": scoring.model,
        "exclusions": scoring.exclusions,
        "unscored": [
            {"id": u["location_id"], "name": names[u["location_id"]], "missing": u["missing"]}
            for u in scoring.unscored
        ],
        "sources": [source.info.to_dict() for source in sources],
        "verdict": build_verdict(entries),
        "locations": entries,
    }


def _location_entry(loc: Location, raw, metrics, score: Optional[dict], settings: Settings) -> dict:
    return {
        **loc.to_dict(),
        "scored": score is not None,
        "score": score["score"] if score else None,
        "rank": score["rank"] if score else None,
        "components": score["components"] if score else [],
        "metrics": metrics.to_dict(),
        "raw": {
            "fungi_observations": raw.fungi_observations,
            "all_observations": raw.all_observations,
            "species_count": raw.species_count,
            "gbif_records": raw.gbif_records,
            "population": raw.population,
            "forest_share": raw.forest_share,
            "monthly_observations": raw.monthly_observations,
            "climate_monthly": raw.climate_monthly,
        },
        "monthly_share": seasonal_row(raw.monthly_observations),
        "climate_month_suitability": (
            monthly_suitability(raw.climate_monthly, settings) if raw.climate_monthly else None
        ),
        "heatmap": density_heatmap(loc, raw.sample_points, settings),
        "errors": raw.errors,
    }


def run_pipeline(settings: Settings, paths: Paths, synthetic: bool = False, only: Optional[Iterable[str]] = None,
                 progress: Progress = print) -> dict:
    """Fetch (or reuse cached) data, score, save results and paper fragments."""
    locations = select_locations(load_locations(paths.locations_csv), only)
    http = None if synthetic else build_http(settings, paths)
    sources = build_sources(settings, paths, synthetic, http)
    progress(f"Collecting data for {len(locations)} locations from {len(sources)} source(s)"
             f"{' [SYNTHETIC DEMO DATA]' if synthetic else ''} ...")
    raw_by_id = DataCollector(sources, progress).collect(locations)

    results = assemble_results(locations, raw_by_id, settings, sources, synthetic,
                               data_retrieved=http.retrieval_window() if http else None)
    results["partial"] = bool(only)
    out = paths.results_file(synthetic)
    save_results(results, out)
    progress(f"Results written to {out}")

    if results["partial"]:
        progress("Partial run (--only): paper fragments not regenerated.")
    else:
        written = latex.write_fragments(results, paths.paper_generated_dir)
        progress(f"Paper fragments written: {', '.join(p.name for p in written)}")
    summarise(results, progress)
    return results


def summarise(results: dict, progress: Progress) -> None:
    scored = [loc for loc in results["locations"] if loc["scored"]]
    progress(f"Scored {len(scored)} locations; {len(results['unscored'])} unscored; "
             f"{len(results['exclusions'])} exclusion(s).")
    for exclusion in results["exclusions"]:
        progress(f"  excluded {exclusion['level']} '{exclusion['label']}': {exclusion['reason']}")
    for unscored in results["unscored"]:
        progress(f"  unscored {unscored['name']}: missing {', '.join(unscored['missing'])}")
    verdict = results["verdict"]
    progress("Verdict: " + verdict["sentence"])
    names = {loc["id"]: loc["name"] for loc in results["locations"]}
    for group, loc_id in sorted(verdict["best_by_group"].items()):
        progress(f"  best in {group}: {names[loc_id]}")
