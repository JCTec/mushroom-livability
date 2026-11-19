# Data sources and retrieval

Only open, public data; no API keys; no proprietary datasets. Every response is cached at
`data/cache/<host>/<hash>.json` as `{method, url, params, fetched_at, payload}`.

Common to all requests: `User-Agent: mushroom-livability/1.0 (…)` (set
`MUSHROOM_CONTACT=you@example.org` to include a contact), sequential requests, per-host
minimum interval, retries with exponential backoff on 429/5xx.

Placeholders: `<lat>`, `<lon>` = location centre; radius = 25 km.

---

## 1. iNaturalist (primary)

- **Provider:** iNaturalist — California Academy of Sciences & National Geographic Society.
- **Docs:** <https://api.inaturalist.org/v1/docs/> · **Base:** `https://api.inaturalist.org/v1`
- **Licence:** observations carry per-observer licences (CC0, CC BY, CC BY-NC); only aggregate counts and binned coordinates are used.
- **Etiquette:** about 1 request/second, under 10,000/day. Throttle: 1.1 s. A full run makes ≈ 240 requests.
- **Code:** `src/data/inaturalist.py`

Shared filter: `taxon_id=47170` (Fungi incl. lichens), `quality_grade=research`, `lat`, `lng`, `radius=25`.

| # | Request | Field used | Becomes |
|---|---|---|---|
| 1 | `GET /observations?<filter>&per_page=0` | `total_results` | `fungi_observations` |
| 2 | `GET /observations?quality_grade=research&lat&lng&radius&per_page=0` (no taxon) | `total_results` | `all_observations` |
| 3 | `GET /observations/species_counts?<filter>&per_page=1` | `total_results` | `species_count` |
| 4 | `GET /observations/histogram?<filter>&date_field=observed&interval=month_of_year` | `results.month_of_year["1".."12"]` | `monthly_observations` |
| 5 | `GET /observations?<filter>&per_page=200&page=1..2&order_by=created_at&order=desc` | each `results[].location` (`"lat,lon"`) | `sample_points` (density map) |

Notes: coordinates of obscured records are randomised by iNaturalist before they reach us.
Request 5 is a sample (≤ 400 points), not a census.

## 2. GBIF (secondary)

- **Provider:** Global Biodiversity Information Facility.
- **Docs:** <https://techdocs.gbif.org/en/openapi/v1/occurrence> · **Code:** `src/data/gbif.py`
- **Licence:** CC0 / CC BY / CC BY-NC per dataset; only a count is used.

| Request | Field used | Becomes |
|---|---|---|
| `GET https://api.gbif.org/v1/occurrence/search?kingdomKey=5&geoDistance=<lat>,<lon>,25km&hasGeospatialIssue=false&limit=0` | `count` | `gbif_records` |

`kingdomKey=5` is Fungi in the GBIF backbone. GBIF includes the iNaturalist research-grade
dataset, so sources 1 and 2 overlap.

## 3. Open-Meteo historical weather (ERA5)

- **Provider:** Open-Meteo.com; underlying data ERA5 (Copernicus Climate Change Service / ECMWF).
- **Docs:** <https://open-meteo.com/en/docs/historical-weather-api> · **Code:** `src/data/climate.py`
- **Licence:** CC BY 4.0 (attribution shown in app and paper). Free for non-commercial use, no key.

| Request | Fields used | Becomes |
|---|---|---|
| `GET https://archive-api.open-meteo.com/v1/archive?latitude=<lat>&longitude=<lon>&start_date=2014-01-01&end_date=2023-12-31&daily=temperature_2m_mean,precipitation_sum&timezone=UTC` | `daily.time[]`, `daily.temperature_2m_mean[]`, `daily.precipitation_sum[]` | `climate_monthly` (12 × `{temp_c, precip_mm}`) |

Reduction (`src/processing/climate.py`): temperature = mean of all daily means in that
calendar month; precipitation = total over all days of that month ÷ number of years.

## 4. WorldPop (population)

- **Provider:** WorldPop, University of Southampton. Dataset `wpgppop`: global 100 m population counts, year 2020.
- **Docs:** <https://www.worldpop.org/sdi/advancedapi/> · **Code:** `src/data/population.py`
- **Licence:** CC BY 4.0.

| Request | Field used | Becomes |
|---|---|---|
| `GET https://api.worldpop.org/v1/services/stats?dataset=wpgppop&year=2020&geojson=<FeatureCollection with one 32-vertex circle polygon>&runasync=false` | `data.total_population` when `status == "finished"` | `population` |
| if not finished: `GET https://api.worldpop.org/v1/tasks/<taskid>` every 4 s (max 30 polls) | same | same |

Only finished responses are cached.

> **Status 2026-11-19 (execution run): unavailable.** The documented endpoint
> `api.worldpop.org/v1/services/stats` (and the `/v1/services` listing) now answers
> `302 → /services/stats`, which answers `404`. worldpop.org documents no replacement; the API root
> points to `/v3/`, which serves an HTML single-page app, not a stats service. Because WorldPop is
> optional, the engine dropped the "Observations per 100k residents" sub-metric for all locations
> (coverage rule 2); no population figure was substituted. The adapter is unchanged and matches the
> provider's documentation, so it will work again if the service returns.

## 5. OpenStreetMap via Overpass (habitat)

- **Provider:** OpenStreetMap contributors; public Overpass API instance.
- **Docs:** <https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL> · **Code:** `src/data/habitat.py`
- **Licence:** ODbL 1.0 — "© OpenStreetMap contributors".
- **Etiquette:** one query per location, 6 s apart.

`POST https://overpass-api.de/api/interpreter` with form field `data=`:

```
[out:json][timeout:170];
is_in(<lat1>,<lon1>)->.a;(area.a["landuse"="forest"];area.a["natural"="wood"];);out count;
is_in(<lat2>,<lon2>)->.a;(area.a["landuse"="forest"];area.a["natural"="wood"];);out count;
… one line per lattice point (7 × 7 lattice clipped to the disc = 37 points)
```

Response: one `{"type":"count","tags":{"total":"N",…}}` element per point, in order.
`forest_share` = points with `total > 0` ÷ 37.

> **Limitation found in the execution run (2026-11-19): the share is a lower bound.**
> The query keeps only Overpass *areas*. Overpass creates areas from objects matching its
> area-creation rules (essentially *named* multipolygons and boundaries), so woodland mapped
> as an unnamed multipolygon relation, or as a plain closed way, is never counted. Live check
> at five Trento lattice points: the nearby woodland is unnamed relations (e.g. 16666226,
> 1281770) or unnamed closed ways, and none of it has an area → Trento 0.0. Forest share is
> also 0.0 for Victoria, Dublin, Milan, Rome and Calgary, and coarse (0–8 of 37 points)
> everywhere else. How much it is under-counted depends on local mapping practice, so
> cross-region comparisons of this ingredient are unreliable.
> *Not fixed.* `is_in` also returns covering closed ways, so adding `way.a[...]` to the union
> would recover closed-way woodland (unnamed relations would still be missed). That change was
> written and tested offline, but it changed neither Trento (0.0) nor Paris (0.2162) live, and
> Overpass was at capacity (HTTP 502) for most of an hour, so its effect could not be shown and
> the 40 queries could not be re-fetched. With the user's agreement it was reverted, so the code
> matches the cached data. Proposed follow-up: add `way.a[...]`, or test woodland
> membership locally against `out geom` polygons, then re-fetch only `overpass-api.de`.

---

## Synthetic source (demo only)

`src/data/synthetic.py` generates pseudo-random values seeded by the location id. It is
used only with `--demo`, writes to `data/processed/demo_results.json`, and is flagged in
the app banner and the paper. It is **not** a data source for any result.

## Considered and not used

| Dataset | Why not |
|---|---|
| iNaturalist / GBIF bulk exports | Tens of GB; the aggregate API answers the same questions. |
| WorldClim rasters | Require raster tooling; Open-Meteo gives ERA5 normals per point with one request. |
| Copernicus / ESA WorldCover land cover | Raster download and reprojection; OSM point sampling is dependency-free. A good upgrade if raster tooling is ever added. |
| WorldPop GeoTIFFs | Same reason; the stats service sums the same grid server-side. |
