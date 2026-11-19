# Execution log

Append one entry per runbook step. Keep entries factual and short.

## Build phase (done)

| Date | What | Result |
|---|---|---|
| 2026-11-19 | Project written offline (code, tests, docs, paper) | complete |
| 2026-11-19 | `python -m unittest discover -s tests -t .` (Python 3.13, Flask 3.1, requests 2.34) | 46 tests OK |
| 2026-11-19 | Demo pipeline + web page in headless Chrome at 1200 px and 390 px; chips, search, row selection, dropdown, tooltips exercised | rendered, no console errors, no horizontal overflow |
| 2026-11-19 | `latexmk -pdf paper.tex` on demo fragments | 7 pages, no errors, no overfull boxes |
| 2026-11-19 | Chart palette validated for colour-vision-deficiency separation (5 component colours, light surface) | pass; low-contrast hues relieved by legend labels and the breakdown table |
| 2026-11-19 | Live API verification | GBIF `geoDistance` count confirmed; WorldPop service list confirmed; iNaturalist, Open-Meteo, Overpass not reachable from the build environment → unverified (see KNOWN_RISKS) |

**Not done in the build phase:** any real data retrieval, any real result.

## Execution phase (to be filled in by the executing agent)

Template:

```
### Step N — <name>            <date time>
Command(s):
Outcome:
Problems:
Changes made (file — what — why — test):
```

### Step 1 — Environment            2026-11-19
Command(s): `python3 -m venv .venv && pip install -r requirements.txt`
Outcome: Python 3.15.0 (macOS, Darwin 27.2); Flask 3.1.3, requests 2.34.2 installed. `pdflatex` present at /Library/TeX/texbin; `latexmk` not installed.
Problems: none.
Changes made: none.

### Step 2 — Offline tests            2026-11-19
Command(s): `python -m unittest discover -s tests -t .`
Outcome: Ran 46 tests — OK (Python 3.15.0).
Problems: none. Changes made: none.

### Step 3 — Demo smoke test            2026-11-19
Command(s): `python main.py pipeline --demo`; `python main.py serve --demo --no-browser --port 8000`
Outcome: demo pipeline scored 40/40 synthetic locations; server answered `/` 200, `/healthz` `results_available: true`, `/api/results` `synthetic: true`. Server stopped.
Problems: the Claude-in-Chrome browser extension was not connected at this point, so the demo page was checked over HTTP only, not visually. The demo run also wrote demo fragments into `paper/generated/` (overwritten by the real full run in step 6).
Changes made: none.

### Step 4 — Live source check            2026-11-19
Command(s): `python main.py check`
Outcome (Paris, 25 km):
- `inaturalist` OK — fungi 8,025; all taxa 240,086; species 688; monthly [580, 497, 455, 780, 371, 268, 318, 306, 775, 1680, 1348, 647] (peak Oct–Nov).
- `inaturalist_points` OK — 200 `[lat, lon]` pairs near 48.8, 2.4.
- `gbif` OK — 11,342 records.
- `open_meteo` OK — 12 monthly normals (Jan 4.8 °C / 64.1 mm …).
- `worldpop` **FAIL** — `HTTP 404` on `GET https://api.worldpop.org/v1/services/stats`.
- `osm_forest` OK — forest share 0.2162.
Problems / WorldPop investigation (3 attempts, AGENTS.md §6):
1. Read the provider docs (worldpop.org/sdi/advancedapi): they still document `api.worldpop.org/v1/services/stats` with exactly the parameters the adapter uses (`dataset`, `year`, `geojson`, `runasync`) and polling at `/v1/tasks/<id>`. The adapter matches the docs.
2. Inspected the live server: `/v1/services` and `/v1/services/stats` now answer `302` → `/services[/stats]`, which answers `404` (HTML). The service listing itself is gone, so this is not a parameter problem. No deprecation/migration notice on worldpop.org/sdi/, /sdi/advancedapi/, /sdi/api_rate_limits.
3. The API root says "Current version: https://api.worldpop.org/v3/". `/v3/services` and `/v3/services/stats` return the same HTML single-page app (catch-all route), not JSON; no v3 stats endpoint is documented.
Decision: WorldPop is an **optional** source and stays broken → proceed; the engine drops the per-capita sub-metric for all locations (documented rule). No data substituted.
Changes made: none to code (nothing in the adapter is wrong against the documentation; the provider's service is unavailable).

### Step 5 — Two-city rehearsal            2026-11-19
Command(s): `python main.py pipeline --only paris,amsterdam` (2 min 51 s)
Outcome: 10 `ok` lines + 2 expected `worldpop FAILED (HTTP 404)`; results written with `partial: true`; 2 scored, 1 exclusion (sub-metric "Observations per 100k residents", dropped for all). Cache populated for iNaturalist, GBIF, Open-Meteo, Overpass. Raw values plausible (Amsterdam: 9,077 fungi obs, 814 species, GBIF 224,303 — large Dutch recording-scheme datasets; Paris as in step 4). Partial-run scores ignored as instructed.
Problems: none beyond WorldPop. Changes made: none.

### Step 6 — Full run            2026-11-19
Command(s): `python main.py pipeline` (39 min 11 s, first fetch)
Outcome: 200 `ok` lines (40 locations × 5 sources); 40 `worldpop FAILED (HTTP 404)`; nothing else failed, so no re-run was needed. `Scored 40 locations; 0 unscored; 1 exclusion(s)` — sub-metric "Observations per 100k residents" dropped for all. Cached responses: api.inaturalist.org 240, api.gbif.org 40, archive-api.open-meteo.com 40, overpass-api.de 40, worldpop 0 (failures are not cached). Paper fragments regenerated (replacing the step-3 demo fragments).
Verdict printed: "Amsterdam is the better base for a mushroom lover: 60.7 vs 57.4 out of 100 for Paris. The biggest advantage is observation density (+7.6 points). Paris does better on seasonal reliability (+6.7 points)."

### Step 7 — Sanity checks            2026-11-19
Command(s): runbook step-7 script.
Outcome: all assertions pass — `synthetic: false`, `partial: false`, scored 40 of 40, 1 exclusion, 0 unscored; scores = sum of contributions; weights sum to 1; Paris and Amsterdam scored. The only per-location errors are the WorldPop 404s.
Eyeball checks: seasonality peaks Sep–Nov for 37 of 40 locations; Berlin, Krakow and Calgary peak in April (real histogram values, kept). Climate: Helsinki Jan −3.1 °C vs Lisbon Jan 11.3 °C — correct ordering. Histogram total equals the observation total for all 40 locations (M3: no undated-record gap).
Implausible value investigated: forest share 0.0 for Trento, Victoria, Dublin, Milan, Rome, Calgary (Trento and Victoria are surrounded by forest). Cached Overpass response for Trento is well-formed (37 count blocks, all zero) — see the Overpass entry below.

### Step 7b — Overpass forest-share investigation            2026-11-19
Trigger: forest share 0.0 for Trento, Victoria, Dublin, Milan, Rome, Calgary (implausible for Trento and Victoria).
Evidence:
- Cached Trento response well-formed: 37 `count` blocks, all `total: 0`, no remark. Not a transport error.
- Overpass docs (wiki Overpass_API/Areas, Overpass_QL, areas.osm3s): areas are created only for objects matching the area rules (named multipolygons, named boundaries, postal codes); "most multipolygons … that don't have a defined name=* will not be part of areas". `is_in` returns areas *and* closed ways.
- Live diagnostic at 5 Trento lattice points (`is_in … out tags` + woodland within 150 m): the nearby woodland is unnamed multipolygon relations (16666226, 1281770), a named forest relation with no area at that point, or unnamed closed ways; no woodland area covers any point.
Actions (asked the user at each methodology decision):
1. User chose "fix query, re-fetch". Added `way.a[...]` to the union in `build_query` + regression test (48 tests OK).
2. Live check with the new query: Trento 0.0, Paris 0.2162, both unchanged. Unnamed relations are invisible to `is_in` whatever the filter. A point-level proof of the change (interior of unnamed closed way 53752230) could not be completed: Overpass answered `502 — server at capacity` to 6 of 9 requests over about an hour. No loop: each retry was spaced 5–10 min apart.
3. Reported back; the user chose "revert, document". Code and test restored exactly to the build-phase query (46 tests OK). The Overpass cache was **not** deleted (no response proven wrong — they are correct answers to the query as specified).
4. Docs: limitation added to DATA_SOURCES §5, METHODOLOGY limitation 5, KNOWN_RISKS A16 (open), habitat module docstring and `SourceInfo.retrieval` ("lower bound").
5. `python main.py pipeline` re-run from cache (40 s; only the 40 WorldPop 404s went to the network) so that `results.json` carries the updated source text. Scores, ranks, raw values, verdict and exclusions are byte-for-byte identical to the first full run.
Net code change: documentation strings in `src/data/habitat.py` only.

### Step 8 — Web page test            2026-11-19 (in progress)
Command(s): `python main.py serve --no-browser`
HTTP-level checks done: `/` 200; `/healthz` → `{"results_available": true, "status": "ok"}`; `/api/results` 200, payload identical to results.json, `synthetic: false`, `partial: false`.
Browser checklist: **not yet run** — the Claude-in-Chrome extension was not connected (checked 6 times between 10:45 and 12:35). Waiting for the user to connect Chrome.

### Step 9 — Paper            2026-11-19
1. `paper/interpretation.tex` written (4 paragraphs: Paris/Amsterdam gap, what the leaders share, Canada, caveats specific to this run). No typed numbers (macros and table/figure references only); each claim checked against results.json (e.g. Amsterdam's density lead comes from fungal share 0.095 vs 0.033 and GBIF 114 vs 5.78 rec/km² while iNaturalist obs/km² are 4.62 vs 4.09; Halifax/Montreal/Quebec City/Toronto climate points all below the European median 13.2). Placeholder removed.
2. References: ERA5 (Hersbach 2020, QJRMS 146(730) 1999–2049, doi 10.1002/qj.3803), Boddy et al. 2014 (Fungal Ecology 10, 20–33, doi 10.1016/j.funeco.2013.10.006) and Isaac & Pocock 2015 (Biol. J. Linn. Soc. 115(3) 522–531, doi 10.1111/bij.12532) match Crossref. Open-Meteo entry matches the citation recommended on open-meteo.com's historical-weather docs ("Zippenfenig, P. (2023) … Zenodo"). iNaturalist, GBIF, WorldPop and OSM entries are web resources with correct URLs. No change needed.
3. Build: `latexmk` is not installed, so `pdflatex -interaction=nonstopmode -halt-on-error paper.tex` was run three times (README alternative). Exit 0 each time; 7 pages; 0 Overfull boxes; no undefined references; no SYNTHETIC box. Read end to end: abstract numbers match the app/results (Amsterdam 60.7, Paris 57.4, Berlin 78.5, Vancouver 72.3).
Problem left open: static prose in `paper/paper.tex` (abstract source list, §2 "Population", §3.1 per-capita rationale, limitation "per-capita metrics reduce … this bias") still presents WorldPop/per-capita as used. AGENTS.md §4 only allows reference fixes in paper.tex, so it was not edited; the generated coverage section (4.4) and the Discussion caveat state the exclusion.

### Post-run — GitHub repository, Pages and release (user request)            2026-11-19
Decisions by the user: private repo `JCTec/mushroom-livability`; public GitHub Pages site (Pages on a private repo needs a paid plan and the site is public); commits under the existing global git identity; release zip = results + paper + log (not the 913 MB API cache).
Changes made (file — what — why — test):
- `src/app/templates/index.html`, `src/app/static/app.js` — asset and data URLs made relative (`static/…`, `api/results`) — the page must work under `/<repo>/` on Pages as well as at `/` — `test_page_uses_relative_urls_and_download_link`.
- `src/settings.py` (`download_url`), `src/pipeline.py` (`settings.download_url` in the payload), `app.js`/`index.html`/`app.css` — "Download the data" button linking to the latest release, rendered from the payload, https-only — same test.
- `src/app/static_site.py`, `main.py site` — static export (index.html, static/, api/results, .nojekyll) — `test_static_site_export`.
- `.gitignore` — `site/`, `paper/*.synctex.gz`.
- README (dedication line, `site` command, Pages section), ARCHITECTURE (static_site).
Verification: 48 tests OK. `python main.py pipeline` re-run from cache to add `download_url`: scores, ranks, raw values, components, verdict and exclusions identical. Paper rebuilt (0 errors, 0 overfull). Static export served under `/mushroom-livability/` locally: all files 200; headless Chrome render shows `data-ready="true"`, the real verdict and the button href. (Headless smoke test only — not the Step 8 checklist.)

### Step 10 — Close out

## Deviations from the documented method

(none yet)

## Final verdict

(to be copied from the app after the real run)
