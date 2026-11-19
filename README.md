# Mushroom Livability

*To my queen, at the end non of us know what to do yet we try.*

**Where is the most strategic place to live as a mushroom lover?**

This project answers that question with open public data. It computes a transparent
**Mushroom Livability Score (0–100)** for Paris, Amsterdam, 30 other European cities and
8 Canadian benchmark cities, and presents the result in a small interactive web app and a
LaTeX paper.

> **Executed on 2026-11-19:** Amsterdam is the better base for a mushroom lover: 60.7 vs 57.4
> out of 100 for Paris (overall leader Berlin, 78.5; best Canadian city Vancouver, 72.3). WorldPop
> was unavailable, so the per-capita sub-metric was dropped for all locations, and the woodland
> share is a lower bound. See [`docs/EXECUTION_LOG.md`](docs/EXECUTION_LOG.md) and
> [`docs/KNOWN_RISKS.md`](docs/KNOWN_RISKS.md).

---

## Quick start

You need Python 3.9 or newer and an internet connection.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

`python main.py` downloads the data on first run (about 10–15 minutes, because the project
deliberately queries the public APIs slowly and politely), computes the scores and opens
the app at <http://127.0.0.1:8000>. Later runs start instantly from the local cache.

Want to see the app immediately, without downloading anything?

```bash
python main.py --demo
```

Demo mode uses **synthetic placeholder numbers** (clearly labelled with a banner). It shows
what the app looks like; it says nothing about real cities.

## Commands

| Command | What it does |
|---|---|
| `python main.py` | Run the pipeline if there are no results yet, then start the web app. |
| `python main.py pipeline` | Fetch data, score, write `data/processed/results.json` and the paper fragments. |
| `python main.py pipeline --only paris,amsterdam` | Quick partial run (scores are then relative to those cities only). |
| `python main.py pipeline --clear-cache` | Throw away cached downloads and fetch everything again. |
| `python main.py serve` | Start the web app on existing results. Options: `--port 8080`, `--no-browser`. |
| `python main.py check` | Live smoke test: one request set per data source for Paris, cache bypassed. |
| `python main.py paper` | Regenerate the LaTeX fragments from saved results. |
| `python main.py site --out site` | Write a static copy of the web app (page + assets + `api/results`) for GitHub Pages. |
| `python -m unittest discover -s tests -t .` | Run the test suite (no network needed). |

Add `--demo` to `run`, `pipeline`, `serve` or `paper` to use synthetic data. Real and demo
results live in different files and are never mixed.

## The hypothesis and the score

The most strategic place maximises a composite of five ingredients, all measured within
25 km of the city centre:

| Ingredient | Weight | Question it answers | Measured by |
|---|---:|---|---|
| Observation density | 25 % | How much fungal life is actually being found here? | iNaturalist research-grade fungi records per km², per 100k residents, as a share of all records; GBIF records per km² |
| Species richness | 25 % | How many different fungi can you expect to meet? | Distinct fungal taxa on iNaturalist |
| Seasonal reliability | 20 % | For how much of the year is there something to find? | Months holding ≥ 4 % of yearly records and ≥ 10 records |
| Climate suitability | 20 % | Does the weather favour fruiting? | Monthly temperature window × moisture factor from ERA5 normals |
| Forest habitat | 10 % | Is there woodland within reach? | Share of the surrounding area mapped as woodland in OpenStreetMap |

Each ingredient is scaled to 0–1, multiplied by its weight and summed. **Every score is
shown with the exact contribution of each ingredient**, in the app and in the paper. If a
data source is unavailable, the affected ingredient is dropped for *all* locations and the
app says so — scores are always built from the same ingredients for everyone.

Full details: [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

## Data sources (open and public only)

| Source | Used for | Licence |
|---|---|---|
| [iNaturalist](https://www.inaturalist.org) API v1 | observations, species, seasonality, density maps | per-observation CC licences; aggregates used |
| [GBIF](https://www.gbif.org) occurrence API | record depth | CC0 / CC BY / CC BY-NC per dataset |
| [Open-Meteo](https://open-meteo.com) historical API (ERA5) | climate normals | CC BY 4.0 |
| [WorldPop](https://www.worldpop.org) stats service | population within the radius | CC BY 4.0 |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) via Overpass | woodland share | ODbL 1.0 |

Exact endpoints, parameters and caveats: [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md).
Every API response is cached in `data/cache/` together with its URL, parameters and
retrieval time, so the cache is a complete provenance record.

## The web app

One page, no build step, no external assets:

- the verdict in one sentence, Paris and Amsterdam side by side with density heatmaps;
- the full ranking with a stacked bar showing what each ingredient contributes;
- filter by region, search by city or country;
- a score breakdown for any location (raw values, normalised values, points);
- a seasonal calendar heatmap;
- how the score works, coverage notes and data source attribution.

### Hosted copy (GitHub Pages)

The page is also published as a static site from the `gh-pages` branch:
<https://jctec.github.io/mushroom-livability/>. The workflow `.github/workflows/gh-pages.yml` rebuilds
that branch on **every push to `main`**: it runs the tests, then `python main.py site` on the committed
`data/processed/results.json` (the real results are versioned for this; CI never calls the data
providers), then force-replaces `gh-pages`. To publish new results, run the pipeline locally and
commit `results.json`. The site is produced from the
same `results.json`, and the page's asset and data URLs are relative, so the same page works at `/` (Flask) and
under `/<repo>/` (Pages). The **Download the data** button links to the latest GitHub release
(`Settings.download_url`), which carries `results.json`, the paper and the execution log as a zip.

## The paper

`paper/paper.tex` is a LaTeX article. All numbers, tables and the figure are generated by
the pipeline into `paper/generated/`, so the PDF cannot drift from the data.

```bash
python main.py pipeline          # or: python main.py paper
cd paper && latexmk -pdf paper.tex     # or run pdflatex twice
```

Requires a TeX distribution (MacTeX, TeX Live or MiKTeX). Only standard packages are used.

## Project layout

```
main.py                    entry point (CLI)
requirements.txt           two runtime dependencies
config/locations.csv       the 40 locations (edit to add a city)
src/
  settings.py              every tunable number, in one place
  domain.py                shared data structures
  pipeline.py              composition root: wires the layers together
  diagnostics.py           `python main.py check`
  data/                    HTTP client + cache, one module per data source
  processing/              geodesy, gridding, seasonality, climate, metrics
  scoring/                 scalers, the declarative score model, the engine
  visualization/           palette, heatmap and chart payloads
  reporting/               results file, verdict, LaTeX fragments
  app/                     Flask server, one HTML page, CSS, JS
tests/                     offline test suite
paper/                     LaTeX paper (+ generated/ fragments)
docs/                      architecture, methodology, sources, runbook, risks
data/                      cache/ and processed/ (git-ignored)
AGENTS.md                  rules for an AI agent executing the project
```

Design notes: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Dependencies

| Package | Why |
|---|---|
| `requests` | Reliable HTTP with sessions and timeouts. |
| `flask` | Smallest sensible way to serve one page and one JSON document. |

Everything else is the Python standard library. pandas, NumPy, mapping libraries and
plotting libraries were considered and left out: the data is 40 rows, and hand-written
SVG/CSS gives full control over the design with nothing to install.

## Extending

- **Add a city:** add a row to `config/locations.csv`, run `python main.py pipeline`.
- **Change weights or thresholds:** `src/scoring/components.py` and `src/settings.py`.
- **Add a data source:** write a class with `info` and `fetch(location)` (see
  `src/data/sources.py`), register it in `build_sources()` in `src/pipeline.py`.

## Troubleshooting

| Symptom | What to do |
|---|---|
| A source prints `FAILED` during the pipeline | Run `python main.py check`. See `docs/KNOWN_RISKS.md`. |
| "Address already in use" | `python main.py serve --port 8080` |
| App shows "No results yet" | Run `python main.py pipeline` first. |
| A coverage note says an ingredient was left out | A source failed for at least one city; re-run the pipeline (cached parts are reused). |
| Want a contact address in API requests | `export MUSHROOM_CONTACT=you@example.org` before running. |

## A word of caution

The score describes *recorded observations* and climate. It reflects where people look as
well as where fungi grow, and it says nothing about edibility. Never eat a wild mushroom on
the strength of an app.
