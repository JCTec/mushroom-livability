# Runbook — execution phase

Do the steps in order. After each step, append an entry to `docs/EXECUTION_LOG.md`.
Rules of conduct are in `AGENTS.md`; this file is the procedure.

All commands run from the project root.

## Step 0 — Orient

Read `README.md`, `AGENTS.md`, `docs/KNOWN_RISKS.md`. Skim `src/pipeline.py` (the wiring) and
`src/data/` (where failures are most likely).

## Step 1 — Environment

```bash
python3 --version                 # need 3.9+
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Expected: `requests` and `flask` install without errors.

## Step 2 — Offline tests

```bash
python -m unittest discover -s tests -t .
```

Expected: `Ran 46 tests … OK`. If anything fails here, it is an environment difference
(Python or Flask version) — fix before going further.

## Step 3 — Demo smoke test (no network)

```bash
python main.py pipeline --demo
python main.py serve --demo --no-browser --port 8000
```

Open <http://127.0.0.1:8000>. Expected: yellow "DEMO MODE" banner, page fully rendered.
This proves the app works on this machine before real data is involved. Stop the server
(Ctrl+C). Do not use demo output for anything else.

## Step 4 — Live source check

```bash
python main.py check
```

Sends one real request set per source for Paris, bypassing the cache. Expected output: six
`OK` lines with plausible values:

| Source | Plausible for Paris (25 km) |
|---|---|
| `inaturalist` | fungi observations in the thousands or more; all-taxa count much larger; species in the hundreds or more; 12 monthly counts peaking in autumn |
| `inaturalist_points` | up to 200 `[lat, lon]` pairs near 48.86, 2.35 |
| `gbif` | a positive record count (11,342 was returned on 2026-11-19) |
| `open_meteo` | 12 months; July mean around 20 °C, January around 5 °C; monthly rain roughly 40–70 mm |
| `worldpop` | population on the order of 9–10 million |
| `osm_forest` | a share between 0 and 1 (Paris region: expect roughly 0.1–0.3) |

For every `FAIL`: apply the decision rules in `AGENTS.md` section 6 and the matching entry
in `docs/KNOWN_RISKS.md`. Re-run `check` until each source is OK or documented as an
unavailable optional source.

## Step 5 — Two-city rehearsal

```bash
python main.py pipeline --only paris,amsterdam
```

Expected: 12 `ok` lines, results written, a verdict printed. This validates caching and
the whole chain cheaply. (Scores from this partial run are relative to two cities only —
ignore their values.)

## Step 6 — Full run

```bash
python main.py pipeline
```

40 locations × about 10 requests; expect 10–15 minutes on first run. Progress is printed per
location and source. When it finishes, read the summary:

- `Scored N locations` — N should be 40.
- `excluded …` lines — optional ingredients dropped (acceptable, must be reported).
- `unscored …` lines — locations missing required data. If any appear, re-run the same
  command (only failed requests are retried). Up to 3 re-runs.

## Step 7 — Sanity checks on the results

```bash
python - <<'EOF'
import json
r = json.load(open("data/processed/results.json"))
assert r["synthetic"] is False and r["partial"] is False
locs = r["locations"]; scored = [l for l in locs if l["scored"]]
print("scored", len(scored), "of", len(locs), "| exclusions", len(r["exclusions"]), "| unscored", len(r["unscored"]))
for l in scored:
    assert abs(l["score"] - sum(c["contribution"] for c in l["components"])) < 1e-6
    assert 0 <= l["score"] <= 100
    assert l["raw"]["fungi_observations"] > 0, l["id"]
    assert l["raw"]["all_observations"] >= l["raw"]["fungi_observations"], l["id"]
    assert sum(l["raw"]["monthly_observations"]) > 0, l["id"]
assert abs(sum(c["weight"] for c in r["model"]) - 1) < 1e-9
ids = {l["id"] for l in scored}; assert {"paris", "amsterdam"} <= ids
print(r["verdict"]["headline"]["sentence"])
print("errors:", {l["id"]: l["errors"] for l in locs if l["errors"]})
EOF
```

All assertions must pass. Also eyeball: Northern-hemisphere seasonality should peak in
late summer–autumn; climate normals should be colder in Helsinki than in Lisbon. If the
histogram total differs from the observation total by more than a few percent, note it
(undated records) — it is not an error.

## Step 8 — Web page test

```bash
python main.py serve --no-browser
```

Open <http://127.0.0.1:8000> in a real browser and work through the checklist. Take a
full-page screenshot at the start and after the checklist.

### Web page test checklist

**Load**
- [ ] Page loads with no errors in the browser console and no failed network requests.
- [ ] **No** "DEMO MODE" or "Partial run" banner.
- [ ] `GET /api/results` returns 200; `GET /healthz` returns `results_available: true`.

**Answer**
- [ ] The headline shows the verdict sentence naming Paris and Amsterdam with both scores.
- [ ] The line under it names the overall leader, the number of scored locations, the 25 km radius and today's retrieval date.

**Head to head**
- [ ] Section title reads "Paris vs Amsterdam"; two cards, Paris left, Amsterdam right.
- [ ] The higher-scoring card is outlined and labelled "Better for mushroom lovers" (unless a tie is declared).
- [ ] Each card shows score, overall rank, observation count, species count, reliable months.
- [ ] Each card shows a density heatmap with visible cells; hovering a cell shows a tooltip with a record count.
- [ ] The comparison bars below list every active ingredient with points for both cities; values match the cards' totals when summed.

**Ranking**
- [ ] Table lists all scored locations in descending score order, ranks 1…N without gaps.
- [ ] Paris and Amsterdam carry a "Headline" tag; Canadian cities a "Benchmark" tag.
- [ ] Each row has a stacked bar; the legend above names every colour with its weight; hovering a segment shows points.
- [ ] Region chips: clicking "Canada" leaves only Canadian cities (8); "All" restores the list.
- [ ] Search: typing `van` leaves Vancouver; typing nonsense shows "No location matches this filter."

**Breakdown**
- [ ] Clicking a ranking row scrolls to the breakdown and shows that location's name and score.
- [ ] The dropdown switches location; the selected row is highlighted in the table.
- [ ] Each ingredient shows points "of max", a bar, and its sub-metrics with raw value, unit and normalised value.
- [ ] Points of all ingredients sum to the location's score (check one location by hand).
- [ ] Density map, "Observations by month" and "Climate suitability by month" charts render; bars have tooltips.

**Seasonal calendar**
- [ ] One row per visible location, 12 month columns, darker cells in the fruiting season; tooltip shows share and record count.
- [ ] The calendar follows the region filter and search.

**Method and sources**
- [ ] Every active ingredient is listed with weight, question and sub-metrics; weights sum to 100 %.
- [ ] If the pipeline reported exclusions/unscored locations, a "Coverage notes" box lists exactly those.
- [ ] Five real data sources are listed with provider, licence, use and retrieval method. No "SYNTHETIC" entry.

**Design and robustness**
- [ ] Clean typography, soft palette, generous whitespace, nothing overlapping or cut off at 1200 px wide.
- [ ] At 390 px wide (mobile) there is no horizontal page scroll; cards stack; the table scrolls inside its own box.
- [ ] Keyboard: Tab reaches chips, search, table rows and the dropdown; Enter on a row selects it.

**Cross-check against the data**
- [ ] Pick three locations (Paris, the leader, one Canadian city): score and rank on the page equal `results.json`.

Any failed item → fix → re-run the *entire* checklist.

## Step 9 — Paper

1. Write `paper/interpretation.tex` following the rules in its header (2–4 paragraphs,
   no typed numbers, claims supported by `results.json`). Remove the placeholder paragraph.
2. Verify the eight references in `paper/paper.tex` (authors, year, journal, volume,
   pages). Correct any that are wrong; remove any that cannot be verified and the sentence
   citing it.
3. Build:

```bash
cd paper && latexmk -pdf -interaction=nonstopmode -halt-on-error paper.tex && cd ..
```

Expected: `paper/paper.pdf`, 7–8 pages, no red "SYNTHETIC" box, no `??` references, no
overfull boxes wider than a few points (`grep Overfull paper/paper.log`). Read the PDF once
end to end: the abstract's numbers must match the app.

If no TeX distribution is installed, do not install one without asking; report it.

## Step 10 — Close out

- Update statuses in `docs/KNOWN_RISKS.md` (verified / fixed / still open).
- Make sure README's status note is replaced by a one-line "Executed on <date>" statement
  with the verdict.
- Complete `docs/EXECUTION_LOG.md`.
- Deliver the final report in the format of `AGENTS.md` section 8.
