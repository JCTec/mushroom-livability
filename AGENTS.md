# AGENTS.md — rules for the execution agent

This file governs any AI agent working in this repository. Read it fully before running
anything. It takes precedence over your defaults; the user's direct instructions take
precedence over it.

## 1. Situation

The project was **written and tested offline** by a previous session that had no network
access. The code is complete; the live data run has never happened. Mistakes are expected,
mostly at the boundary with external APIs (see `docs/KNOWN_RISKS.md`).

**Your phase is execution and verification.** You run the project against the real APIs,
fix what demonstrably blocks it, test the web page in a browser, build the paper, and
report. You do not redesign.

## 2. Mission

Deliver, on this machine:

1. a passing test suite;
2. a completed real (non-demo) pipeline run → `data/processed/results.json`;
3. the web app verified in a browser against `docs/RUNBOOK.md` → "Web page test checklist";
4. `paper/paper.pdf` built from the real results, with `paper/interpretation.tex` written;
5. `docs/EXECUTION_LOG.md` filled in, and a final report to the user.

The step-by-step procedure is `docs/RUNBOOK.md`. Follow it in order.

## 3. Behaviour

- **Evidence before action.** Reproduce a failure, read the error, read the relevant module
  and the provider's API documentation, then change code. Never patch on a guess.
- **Smallest fix that works.** Change only what the failure requires. Keep the layer
  boundaries in `docs/ARCHITECTURE.md`.
- **Every fix gets a test.** Add or update a test in `tests/` that would have caught the
  problem (use `tests/fakes.py`; tests never touch the network). Run the full suite after
  every change.
- **Keep the docs true.** If you change an endpoint, parameter, threshold, dependency or
  behaviour, update `docs/DATA_SOURCES.md`, `docs/METHODOLOGY.md`, `README.md`, the
  `SourceInfo.retrieval` text and `docs/KNOWN_RISKS.md` in the same change.
- **Log as you go.** Append to `docs/EXECUTION_LOG.md` after each runbook step: command,
  outcome, any change made and why.
- **Be polite to the APIs.** They are free public services. Keep the throttles in
  `src/settings.py`; never parallelise requests; never loop on a failing endpoint.
- **Say what you did not do.** If a step is skipped or fails, the report says so plainly.

## 4. Allowed actions

- Create `.venv`, install `requirements.txt`, run any `python main.py …` command and the tests.
- Make HTTPS requests to the five documented providers only (iNaturalist, GBIF, Open-Meteo,
  WorldPop, Overpass) and read their public documentation.
- Edit files under `src/`, `tests/`, `docs/`, `README.md`, `paper/interpretation.tex`
  to fix defects found during execution.
- Fix the reference list in `paper/paper.tex` if a citation turns out to be wrong.
- Open the local web app in a browser and interact with it.
- Build the paper with `latexmk`/`pdflatex` if a TeX distribution is installed.

## 5. Forbidden actions (hard rules)

1. **Never fabricate, hard-code, estimate or hand-edit data or results.** Every number must
   come from a provider response in `data/cache/`. No "typical values", no numbers from
   memory, no manual edits to `results.json` or `paper/generated/*`.
2. **Never present demo data as results.** `--demo` is for testing the UI only. The final
   app, paper and report use the real run. If the real run is impossible, stop and report.
3. **Never tune the method to the outcome.** After seeing any real scores, do not change
   weights, thresholds, scalers, the radius or the location list. The only permitted method
   change is replacing a broken data retrieval with an equivalent one — and that must be
   documented as a deviation.
4. **No proprietary or non-open data sources**, no API keys, no scraping of web pages.
5. **No new runtime dependencies** unless a fix is impossible without one; if so, justify it
   in `README.md` → Dependencies and in the log.
6. **Do not weaken the coverage rules** in `src/scoring/engine.py` (drop-for-all,
   unscored locations) to make a number appear.
7. **Do not remove or loosen throttling, retries or the User-Agent.**
8. **Do not delete** `data/cache/` content unless a cached response is proven wrong; then
   delete only that provider's folder and log it.
9. **No git commits, pushes, or changes outside this folder** unless the user asks.
10. **No causal or biological claims** in `paper/interpretation.tex` beyond what
    `results.json` supports (rules are in the header of that file).

## 6. Decision rules for failures

| Situation | Action |
|---|---|
| A test fails before any change | Fix the code (not the test) unless the test is provably wrong; log it. |
| `python main.py check` fails for one source | Read the error → provider docs → fix the adapter in `src/data/` → add a test → re-run `check`. Max 3 fix attempts per source. |
| An **optional** source stays broken (WorldPop, Overpass, GBIF, iNaturalist points) | Proceed. The engine drops the affected sub-metric/component for all locations and reports it. Record it as a limitation in the log and report. Do not substitute invented data. |
| A **required** source stays broken (iNaturalist stats, Open-Meteo) | Stop. Report what was tried. Do not produce results. |
| A source fails for a few locations only (transient) | Re-run `python main.py pipeline`; successful responses are cached, only the failures are retried. Up to 3 re-runs, waiting a few minutes between them. |
| HTTP 429 / rate limiting | Wait, then re-run. Increase the host interval in `src/settings.py` if it recurs. Never decrease it. |
| A headline city (Paris or Amsterdam) is unscored | The deliverable is incomplete. Treat as a required-source failure for that city: retry, then stop and report. |
| Results look implausible (e.g. a count of 0 for a major city, identical values everywhere) | Inspect the cached response in `data/cache/<host>/`. If the request was wrong, fix the adapter and delete that host's cache folder. If the data is real, keep it — surprising is not wrong. |
| A web checklist item fails | Fix in `src/app/` (or the payload builder it reads), re-test the whole checklist. |
| LaTeX is not installed | Do not install system software without asking the user. Report the paper as "fragments generated, PDF not built". |
| Anything requiring a judgement about the methodology | Stop and ask the user. |

## 7. Definition of done

- [ ] `python -m unittest discover -s tests -t .` → OK
- [ ] `python main.py check` → all sources OK, or failures documented as optional-source limitations
- [ ] `python main.py pipeline` (no `--demo`, no `--only`) completed; Paris and Amsterdam both scored
- [ ] `results.json` has `"synthetic": false` and `"partial": false`
- [ ] Sanity checks in the runbook pass
- [ ] Every item of the web page test checklist passes on the real results, with screenshots
- [ ] No demo banner, no browser console errors
- [ ] `paper/interpretation.tex` written per its rules; `paper/paper.pdf` builds without errors (or LaTeX absence reported)
- [ ] All docs reflect the code as executed; `docs/KNOWN_RISKS.md` statuses updated
- [ ] `docs/EXECUTION_LOG.md` complete
- [ ] Final report delivered (format below)

## 8. Final report format

1. **Answer** — the verdict sentence from the app, plus the overall leader and best Canadian city.
2. **What ran** — commands, duration, number of requests cached per provider.
3. **Coverage** — exclusions, unscored locations, failed requests.
4. **Changes made** — file, what, why, which test covers it. "None" if none.
5. **Deviations from the documented method** — or "None".
6. **Verification** — test count, checklist result, screenshots, paper build status.
7. **Open issues** — anything not done or not certain.

## 9. Code conventions

- Python ≥ 3.9, standard library first; type hints on public functions; module docstrings explain *why*.
- Layers depend inward only: `app → reporting/visualization → scoring/processing → domain`; `data` is reached only through `pipeline.py`.
- Pure functions for all processing and scoring; I/O only in `src/data/`, `src/reporting/store.py`, `src/reporting/latex.py` (writing), and `src/app/`.
- A data source = one class with `info: SourceInfo` and `fetch(location) -> dict`.
- Settings live in `src/settings.py`; the score model in `src/scoring/components.py`. No magic numbers elsewhere.
- Front end: plain HTML/CSS/JS, no CDN, no build step. All data rendered via `textContent`.
