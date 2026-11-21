# Known risks and unverified assumptions

The code was written without network access to most providers. This is the honest list of
what was **verified**, what is **assumed**, how a wrong assumption will show up, and where
to fix it. The execution agent updates the Status column.

Legend: ✅ verified live · ⚠️ assumed from documentation/memory, not verified · 🧪 verified offline only

## External APIs

| # | Assumption | Status | Symptom if wrong | Fix location |
|---|---|---|---|---|
| A1 | iNaturalist `/observations` accepts `per_page=0` and returns `total_results` | ✅ 2026-11-19 (Paris: 8,025 fungi / 240,086 all) | `SourceError: no total_results` or HTTP 422 | `INaturalistStatsSource.fetch` — use `per_page=1` |
| A2 | iNaturalist `/observations/species_counts` `total_results` = number of taxa | ✅ 2026-11-19 (plausible: 171–1,541 taxa across 40 locations; Paris 688) | implausibly small/large species counts | same module; check `total_results` vs `results` length |
| A3 | iNaturalist histogram with `interval=month_of_year` returns `results.month_of_year` keyed `"1"`…`"12"` | ✅ 2026-11-19 (12 non-zero months, autumn peak) | `SourceError: results.month_of_year missing`, or all zeros | `parse_month_histogram` |
| A4 | iNaturalist observation records expose `location` as `"lat,lon"` | ✅ 2026-11-19 (200 points parsed for Paris) | empty density maps (`sample_points: []`) | `parse_points` — fall back to `geojson.coordinates` (`[lon, lat]`) |
| A5 | Taxon id 47170 is Fungi | ✅ indirectly 2026-11-19 (fungi counts in the thousands with autumn peaks; `/v1/taxa/47170` not queried) | counts near zero | `Settings.fungi_taxon_id`; verify at `/v1/taxa/47170` |
| A6 | 1.1 s spacing satisfies iNaturalist rate limits | ✅ 2026-11-19 (240 requests, no 429) | HTTP 429 | raise `host_min_interval_s` |
| A7 | GBIF `geoDistance=<lat>,<lon>,25km` + `kingdomKey=5` + `limit=0` returns `count` | ✅ 2026-11-19 (returned a count for Paris) | — | `src/data/gbif.py` |
| A8 | GBIF accepts `hasGeospatialIssue=false` together with `geoDistance` | ✅ 2026-11-19 (40 counts returned) | HTTP 400 | drop the parameter and document it |
| A9 | Open-Meteo archive endpoint and variable names `temperature_2m_mean`, `precipitation_sum` | ✅ 2026-11-19 | `SourceError: unexpected response shape` or HTTP 400 with a `reason` | `src/data/climate.py` |
| A10 | Open-Meteo allows 40 ten-year daily requests without hitting the free-tier limit | ✅ 2026-11-19 (40 requests, no 429) | HTTP 429 mid-run | raise interval; re-run (cache keeps successes) |
| A11 | WorldPop `services/stats` exists with dataset `wpgppop` | ❌ 2026-11-19 execution: `/v1/services` and `/v1/services/stats` now 302 → `/services…` → 404; no replacement documented (see DATA_SOURCES §4) | — | — |
| A12 | WorldPop stats call: parameters `dataset`, `year`, `geojson` (FeatureCollection), `runasync`; response `status`, `taskid`, `data.total_population`; task polling at `/v1/tasks/<id>` | matches provider docs; untestable live (service 404) — optional source dropped, per-capita sub-metric excluded | `SourceError` from WorldPop for every city | `src/data/population.py`; read the API docs page |
| A13 | WorldPop accepts a 33-vertex polygon in a GET query string and a ~2,000 km² area | untestable (service 404) | HTTP 414/400 or error message | reduce `circle_vertices`; or POST if supported |
| A14 | Overpass: `is_in(lat,lon)->.a; (area.a[…]; area.a[…];); out count;` is valid and yields one `count` element per block, in order | ✅ 2026-11-19 (Paris 0.2162) | HTTP 400 with a parse error, or `expected 37 count blocks` | `build_query` / `parse_forest_share` in `src/data/habitat.py` |
| A15 | Overpass answers 37 `is_in` lookups within 170 s | ✅ 2026-11-19 (all 40 queries answered in the full run; later diagnostics met 502 "at capacity", a server-load issue) | HTTP 504/429, timeouts | lower `forest_sample_grid` to 5 (21 points) **before** any real results are seen; document |
| A16 | Overpass has woodland as areas (closed ways/multipolygons) in all regions incl. Canada | ❌ 2026-11-19, **open**: Overpass builds areas mainly from *named* multipolygons; unnamed woodland relations and closed ways are not counted → 0.0 for Trento, Victoria, Dublin, Milan, Rome, Calgary. A `way.a[...]` fix was tried, showed no live effect on Trento/Paris, could not be re-fetched (Overpass 502 at capacity) and was reverted with the user's agreement. Documented as a limitation (DATA_SOURCES §5); forest share is a lower bound |

If WorldPop (A12–A13) or Overpass (A14–A16) cannot be made to work in three attempts, they
are optional: the engine drops the per-capita sub-metric / habitat component for all
locations and reports it. That is an acceptable, documented outcome.

## Methodology

| # | Risk | Status | Handling |
|---|---|---|---|
| M1 | Observer-effort bias in citizen-science counts | inherent | fungal-share + per-capita sub-metrics; stated in app footer, paper, methodology |
| M2 | Min–max scaling depends on the set of locations | inherent | documented; fixed location list; partial runs flagged |
| M3 | Histogram total may differ from the observation total (records without a full date) | ✅ 2026-11-19 (histogram total = observation total for all 40 locations) | shares are computed from the histogram's own total; note the difference in the log |
| M4 | Reliable-month thresholds (4 %, 10 records) and climate windows are heuristics | by design | parameters in `settings.py`; must not be tuned after seeing results |
| M5 | Coastal discs include sea, lowering per-km² values | inherent | documented limitation |
| M6 | The "why" text of the seasonality sub-metric in `components.py` repeats the 4 % / 10 thresholds as text | 🧪 | if the thresholds in `settings.py` ever change, update that sentence |

## Software and environment

| # | Risk | Status | Handling |
|---|---|---|---|
| S1 | Tested on Python 3.13, Flask 3.1, requests 2.34 only | ✅ 2026-11-19 (Python 3.15.0, Flask 3.1.3, requests 2.34.2: all tests pass) | code avoids 3.10+ syntax; run the tests first on the target machine |
| S2 | Port 8000 already in use | not encountered | `--port` |
| S3 | `python main.py pipeline --only …` overwrites `results.json` with a partial result | by design | flagged `partial: true` and bannered; re-run the full pipeline afterwards (cache makes it fast) |
| S4 | LaTeX distribution missing on the target machine | pdflatex present (TeX Live 2026 basic); latexmk missing → pdflatex run 3× | report; do not install without asking |
| S5 | Paper tested with pdfTeX/TeX Live on Linux only | ✅ 2026-11-19 (macOS, TeX Live 2026: 7 pages, 0 errors, 0 overfull) | standard packages only (`booktabs`, `tikz`, `hyperref`, `lmodern`, `amsmath`, `xcolor`, `geometry`) |
| S6 | Web page tested in headless Chrome only (1200 px and 390 px) | 🧪 **still open**: real-browser checklist not run (Chrome extension never connected); headless render of the real results only | checklist in the runbook covers a real browser |
| S7 | Non-ASCII characters in LaTeX output | 🧪 | `tex_escape` handles common symbols; location names in the CSV are ASCII on purpose |

## Paper

| # | Risk | Status | Handling |
|---|---|---|---|
| P1 | Bibliographic details of the eight references were written from memory | ✅ 2026-11-19: ERA5, Boddy, Isaac & Pocock match Crossref; Open-Meteo matches the provider's recommended citation; the four data-provider entries are web resources — no change needed | verify each (runbook step 9); correct or remove |
| P2 | `interpretation.tex` contains only a neutral placeholder | ✅ 2026-11-19 written from the real results | written in runbook step 9 from real results |
| P3 | The introduction of `paper.tex` names the six regions by hand (the title's city count is the `\MLSNumLocations` macro) | ✅ 2026-11-21 matches the `group` column of `config/locations.csv`; update if regions change | — |
