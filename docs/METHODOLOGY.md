# Methodology

## Question

*Where is the most strategic place to live as a mushroom lover?*

"Strategic" is read as: a place where, over a normal year, you can reliably find a lot of
fungi of many kinds close to home.

## Unit of analysis

A **location** is the disc of radius **25 km** around a city centre (≈ 1,963 km²): what is
reachable on a half-day outing. All quantities refer to that disc. Coordinates are in
`config/locations.csv`.

40 locations: Paris and Amsterdam (headline), 30 further European cities across France &
Benelux, Germany & Central Europe, the Nordics, UK & Ireland and Southern Europe, and 8
Canadian cities (benchmark).

## From raw data to metrics

| Raw quantity | Symbol | Source |
|---|---|---|
| Research-grade fungal observations | N_f | iNaturalist |
| Research-grade observations, all taxa | N_a | iNaturalist |
| Distinct fungal taxa observed | S | iNaturalist |
| Observations per calendar month | n_1 … n_12 | iNaturalist |
| Fungal occurrence records | G | GBIF |
| Monthly mean temperature / precipitation total | T_m, P_m | Open-Meteo (ERA5), 2014–2023 |
| Residents in the disc | P | WorldPop 2020 |
| Woodland share of the disc | F | OpenStreetMap |

| Metric | Formula | Why |
|---|---|---|
| Observations per km² | N_f / A | How much is found per unit of land. |
| Observations per 100k residents | 10⁵ · N_f / P | Stops big cities winning on headcount. |
| Fungal share | N_f / N_a | Corrects for local popularity of iNaturalist: where everyone uses the app, everything has more records. |
| GBIF records per km² | G / A | Adds museum and national recording-scheme depth. |
| Species richness | S | Variety. |
| Reliable months | #{ m : n_m / Σn ≥ 0.04 and n_m ≥ 10 } | Length of the season. 4 % is about half of an even month (8.3 %). The floor of 10 records stops thinly recorded places looking reliable. |
| Climate suitability | mean over months of τ(T_m) · min(1, P_m / 80) | Fruiting needs mild temperatures and moisture. |
| Woodland share | F | Habitat within reach. |

Temperature factor τ: 0 at or below 0 °C; rises linearly to 1 at 8 °C; stays 1 to 18 °C;
falls linearly to 0 at 26 °C. Moisture factor: monthly precipitation divided by 80 mm,
capped at 1.

Seasonal evenness (Pielou) and the number of months with suitability ≥ 0.5 are computed and
stored for context but are **not** part of the score.

## Normalisation

| Metric type | Scaling | Consequence |
|---|---|---|
| Counts and rates (observations, species, GBIF, per-capita, share) | log(1 + x), then min–max across scored locations | Best location = 1, weakest = 0. Relative to the comparison set. |
| Reliable months | x / 12 | Absolute. |
| Climate suitability | x / 1 | Absolute. |
| Woodland share | min(1, x / 0.6) | Absolute; 60 % woodland or more is full marks. |

For the fungal share (values well below 1) log(1 + x) is practically linear; the same scaler
is used for uniformity.

## Aggregation

```
score = 100 × Σ_components  w_c × Σ_submetrics  w_cm × normalised_metric
```

| Component | w_c | Sub-metric | w_cm |
|---|---:|---|---:|
| Observation density | 0.25 | observations per km² (required) | 0.40 |
| | | observations per 100k residents | 0.20 |
| | | fungal share of all observations | 0.20 |
| | | GBIF records per km² | 0.20 |
| Species richness | 0.25 | species observed (required) | 1.00 |
| Seasonal reliability | 0.20 | reliable months (required) | 1.00 |
| Climate suitability | 0.20 | climate suitability index (required) | 1.00 |
| Forest habitat | 0.10 | woodland share | 1.00 |

Rationale for the weights: what is actually found (density, richness) carries half the
score because it is the most direct evidence; the two "can I rely on it" ingredients
(season, climate) carry 40 %; habitat carries 10 % because its data source is the least
uniform. The weights are a judgement, stated openly; contributions are always shown
separately so anyone can re-weight.

The model is declared in `src/scoring/components.py`; parameters in `src/settings.py`.

## Explainability

For every location the output contains, per component: effective weight, normalised value,
points contributed; and per sub-metric: raw value, unit, normalised value, weight. The
identity `score = Σ contributions` is enforced by tests. The verdict sentence names the
component with the largest advantage for the winner and, if there is one of at least one
point, the largest advantage for the loser. A margin below one point is reported as "too
close to call".

## Missing data (coverage rules)

1. A location lacking a **required** sub-metric is **not scored** and is listed as such.
2. An **optional** sub-metric missing for any scored location is **dropped for all**.
3. A component with no sub-metric left is dropped; remaining component weights are
   rescaled proportionally to sum to 1.

Everything dropped is reported in the app ("Coverage notes"), in the paper and in
`results.json` (`exclusions`, `unscored`). The effective weights actually used are in
`results.json` → `model`.

## Density maps

The maps show the coordinates of the most recently added research-grade records (at most
400 per location) binned into a 24 × 24 grid over the disc's bounding box. They show
**where finds cluster**, not totals — both headline cities are capped at the same sample
size, and each map is scaled to its own maximum. They do not enter the score.

## Limitations (read before quoting a result)

1. **Observer effort.** Records measure where people look as well as where fungi grow.
   Fungal share and per-capita rates reduce this but cannot remove it.
2. **Relative scaling.** Adding or removing locations changes min–max-scaled values.
3. **Overlap.** GBIF contains iNaturalist's research-grade export; hence its small weight.
4. **Heuristic climate model** on monthly normals; ignores humidity, soil, altitude,
   inter-annual variability.
5. **OSM completeness** differs between countries; the lattice estimate (37 points) has a
   standard error of up to about 8 percentage points.
   Point membership is tested against Overpass *areas* only, which exist mainly for named
   woodland multipolygons; unnamed woodland is not seen, so the share is a lower bound
   whose bias varies by region (0.0 for six locations, incl. forested Trento and Victoria).
   See DATA_SOURCES.md §5.
6. **Taxon scope.** iNaturalist's Fungi taxon includes lichens. Species counts are leaf
   taxa as returned by the API and may include a few non-species ranks.
7. **City definition.** A 25 km disc around a centre point treats a coastal city (half sea)
   and an inland city alike; per-km² values of coastal cities are therefore conservative.
8. **Weights are judgement**, not estimated from data.
9. No statement is made about edibility, access rights or foraging law.
