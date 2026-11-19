# Architecture

## Data flow

```
config/locations.csv
        │  load_locations()
        ▼
  [ Location ] ──► DataCollector ──► { id: RawLocationData }      src/data/
                     │  one LocationSource per dataset
                     │  (HTTP through PoliteHttpClient + CachedJsonHttp → data/cache/)
                     ▼
               build_metrics()  ──► { id: Metrics }                src/processing/
                     ▼
               ScoringEngine    ──► scores, exclusions, model      src/scoring/
                     ▼
               assemble_results() ─► results document (dict)       src/pipeline.py
                     │      + heatmap payloads (src/visualization/)
                     │      + verdict (src/reporting/verdict.py)
          ┌──────────┴───────────┐
          ▼                      ▼
  data/processed/results.json   paper/generated/*.tex              src/reporting/
          ▼                      ▼
   Flask app (src/app/)      paper/paper.tex → paper.pdf
```

The **results document** is the single contract between the analysis and its two
presentations. The web app and the paper read only that document; neither computes
anything that affects a score.

## Layers and their responsibilities

| Package | Responsibility | May import |
|---|---|---|
| `src/domain.py` | Data structures (`Location`, `RawLocationData`, `Metrics`, score types) | nothing |
| `src/settings.py` | All tunable parameters and file paths | nothing |
| `src/data/` | Talking to the outside world: HTTP, cache, one adapter per source, the collector | `domain`, `settings`, `processing.geo`, `processing.climate` (pure helpers) |
| `src/processing/` | Pure transformations: geodesy, gridding, seasonality, climate, metrics | `domain`, `settings` |
| `src/scoring/` | Scalers, the declarative model, the engine | `domain` |
| `src/visualization/` | Colours and chart/heatmap payloads (data only) | `domain`, `settings`, `processing` |
| `src/reporting/` | Results file I/O, verdict, LaTeX fragments | `visualization` |
| `src/app/` | Serving one page and one JSON document; `static_site.py` writes the same page + document as static files (GitHub Pages) | `reporting.store` |
| `src/pipeline.py` | Composition root: the only module that knows every concrete class | everything |
| `main.py` | Command-line interface | `pipeline`, `app`, `diagnostics`, `reporting` |

## SOLID, concretely

- **Single responsibility.** One reason to change per module: the iNaturalist API changes →
  `data/inaturalist.py`; the definition of a reliable month changes → `processing/seasonality.py`;
  the weights change → `scoring/components.py`; the look changes → `app/static/`.
- **Open/closed.** New dataset = new class implementing `LocationSource`, registered in
  `build_sources()`. New ingredient = new entry in `DEFAULT_COMPONENTS`. New scaling rule =
  new `Scaler`. The collector and engine are not edited.
- **Liskov.** Any `LocationSource` can replace another; `SyntheticSource` stands in for all
  real sources in demo mode and tests. `CachedJsonHttp` is a drop-in for `PoliteHttpClient`.
- **Interface segregation.** Sources need only `JsonHttp` (two methods). The engine needs
  only `Metrics.get(key)`. The app needs only `load_results`.
- **Dependency inversion.** Sources receive their HTTP client and settings through the
  constructor; the engine receives its model; the app receives a results path. Nothing
  reaches for a global.

## Key design decisions

| Decision | Why |
|---|---|
| Flask + hand-written page instead of Streamlit | Two small dependencies, full control over a clean design, testable with Flask's test client, no hidden runtime. |
| No pandas / NumPy | The dataset is 40 rows × 10 numbers. Dictionaries and lists are clearer than a dataframe here. |
| API queries instead of bulk dumps or rasters | iNaturalist/GBIF dumps are tens of GB; WorldPop and land-cover rasters need geospatial libraries. Aggregate API queries give the same numbers with ~400 small requests. |
| Point-sampling for woodland share | Avoids downloading polygons or rasters; statistically valid estimate; one request per city. |
| Cache stores provenance | `data/cache/<host>/<hash>.json` holds URL, parameters, timestamp and payload. Re-runs are instant and every number is traceable. |
| Failures are isolated per source and location | One flaky API cannot abort a 15-minute run. |
| Coverage rules in the engine | Scores must be built from the same ingredients for every location, otherwise ranks are meaningless. |
| Paper numbers are generated | `paper/generated/` is written by the pipeline; the prose contains macros, not numbers. |
| Demo mode is synthetic and segregated | Lets the UI and paper build be tested offline; separate file, banner and LaTeX warning box prevent it being mistaken for results. |

## The results document (schema v1)

```
schema_version, generated_at, synthetic, partial
settings      { radius_km, area_km2, climate_period, worldpop_year, reliable_month_*, sample_size_cap }
groups        [ region names in display order ]
palette       { components: {key: hex}, sequential_low, sequential_high }
model         [ { key, label, question, nominal_weight, weight,
                  submetrics: [ { key, label, unit, nominal_weight, weight, scaling, why } ] } ]
exclusions    [ { level: submetric|component, key, label, reason } ]
unscored      [ { id, name, missing: [labels] } ]
sources       [ { key, title, provider, url, license, used_for, retrieval } ]
verdict       { leader_id, best_by_role: {role: id},
                headline: { winner_id, loser_id, margin, is_tie, gaps[], main_driver, sentence } | null }
locations     [ { id, name, country, group, role, lat, lon,
                  scored, score, rank,
                  components: [ { key, label, weight, value, contribution,
                                  submetrics: [ { key, label, unit, raw, normalized, weight } ] } ],
                  metrics: {...}, raw: {...},
                  monthly_share[12], climate_month_suitability[12],
                  heatmap: { cells, counts[cells][cells], max, points, span_km } | null,
                  errors: { source_key: message } } ]        # sorted by rank
```

## Testing strategy

- `tests/test_processing.py` — geodesy, gridding, seasonality, climate, metrics (pure maths).
- `tests/test_scoring.py` — scalers, weights, coverage rules, decomposition identity.
- `tests/test_sources.py` — request parameters and response parsing for every adapter via
  `FakeHttp`; cache behaviour; failure isolation; the locations file.
- `tests/test_end_to_end.py` — full results document on synthetic data, verdict wording,
  LaTeX fragments, Flask routes.

Tests never use the network. Live behaviour is covered by `python main.py check`.
