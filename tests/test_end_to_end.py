"""Whole-pipeline tests on synthetic data: results document, paper, web app."""

import json
import tempfile
import unittest
from pathlib import Path

from src.app.server import APP_DIR, create_app
from src.app.static_site import export_site
from src.data.collector import DataCollector
from src.data.locations import load_locations
from src.data.synthetic import SyntheticSource
from src.pipeline import assemble_results, select_locations
from src.reporting import latex
from src.reporting.store import load_results, save_results
from src.reporting.verdict import build_verdict
from src.settings import Paths, Settings

S = Settings()


def synthetic_results(drop=None):
    locations = load_locations(Paths().locations_csv)
    source = SyntheticSource(S)
    raw = DataCollector([source]).collect(locations)
    if drop:
        drop(raw)
    return assemble_results(locations, raw, S, [source], synthetic=True)


class ResultsDocumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = synthetic_results()

    def test_shape(self):
        r = self.results
        self.assertTrue(r["synthetic"])
        self.assertEqual(len(r["locations"]), 40)
        self.assertEqual([l["rank"] for l in r["locations"]], list(range(1, 41)))
        self.assertEqual(r["groups"], sorted(r["groups"]))  # alphabetical, no region first by design
        self.assertEqual(set(r["groups"]), {l["group"] for l in r["locations"]})
        self.assertNotIn("role", r["locations"][0])
        for loc in r["locations"]:
            self.assertAlmostEqual(loc["score"], sum(c["contribution"] for c in loc["components"]))
            self.assertEqual(len(loc["monthly_share"]), 12)
            self.assertEqual(len(loc["heatmap"]["counts"]), S.heatmap_cells)

    def test_verdict_is_rank_one_vs_rank_two(self):
        v, locs = self.results["verdict"], self.results["locations"]
        self.assertEqual(v["leader_id"], locs[0]["id"])
        self.assertEqual(v["runner_up_id"], locs[1]["id"])
        self.assertEqual((v["top"]["winner_id"], v["top"]["loser_id"]), (locs[0]["id"], locs[1]["id"]))
        self.assertGreaterEqual(v["top"]["margin"], 0)
        self.assertEqual(v["sentence"], v["top"]["sentence"])
        self.assertIn(locs[0]["name"], v["sentence"])
        self.assertIn(locs[1]["name"], v["sentence"])

    def test_best_by_group_covers_every_region(self):
        v, locs = self.results["verdict"], self.results["locations"]
        self.assertEqual(set(v["best_by_group"]), set(self.results["groups"]))
        for group, loc_id in v["best_by_group"].items():
            best_rank = min(l["rank"] for l in locs if l["group"] == group)
            self.assertEqual(next(l for l in locs if l["id"] == loc_id)["rank"], best_rank)

    def test_no_location_is_privileged(self):
        """The verdict depends on scores only: renaming or reordering the input changes nothing."""
        base = {"components": [], "scored": True, "country": "X"}
        entries = [
            {**base, "id": "a", "name": "A", "group": "G1", "score": 40.0, "rank": 2},
            {**base, "id": "b", "name": "B", "group": "G2", "score": 70.0, "rank": 1},
            {**base, "id": "c", "name": "C", "group": "G1", "score": 10.0, "rank": 3},
        ]
        verdict = build_verdict(entries)
        self.assertEqual(verdict, build_verdict(list(reversed(entries))))
        self.assertEqual((verdict["leader_id"], verdict["runner_up_id"]), ("b", "a"))
        self.assertEqual(verdict["best_by_group"], {"G1": "a", "G2": "b"})

    def test_tie_wording(self):
        base = {"components": [], "scored": True, "group": "G", "country": "X"}
        verdict = build_verdict([
            {**base, "id": "a", "name": "A", "score": 50.2, "rank": 1},
            {**base, "id": "b", "name": "B", "score": 50.0, "rank": 2},
        ])
        self.assertTrue(verdict["top"]["is_tie"])
        self.assertIn("too close to call", verdict["sentence"])

    def test_single_scored_location_has_no_comparison(self):
        verdict = build_verdict([{"id": "a", "name": "A", "country": "X", "group": "G", "scored": True,
                                  "score": 50.0, "rank": 1, "components": []}])
        self.assertIsNone(verdict["top"])
        self.assertIsNone(verdict["runner_up_id"])
        self.assertIn("only location", verdict["sentence"])
        self.assertIn("unavailable", latex.headtohead_table({"verdict": verdict, "locations": []}))

    def test_unscored_location_is_left_out_of_verdict(self):
        def drop(raw):
            raw["vancouver"].species_count = None

        r = synthetic_results(drop)
        self.assertEqual(r["unscored"][0]["id"], "vancouver")
        v = r["verdict"]
        self.assertNotIn("vancouver", (v["leader_id"], v["runner_up_id"]))
        self.assertNotIn("vancouver", v["best_by_group"].values())

    def test_retrieval_dates(self):
        self.assertIsNone(self.results["data_retrieved"])  # synthetic: nothing was fetched
        built = {"generated_at": "2026-11-21T10:00:00+00:00"}
        self.assertEqual(latex.retrieval_dates({**built, "data_retrieved": None}), "2026-11-21")
        same = {"first": "2026-11-19T16:00:00+00:00", "last": "2026-11-19T18:00:00+00:00"}
        self.assertEqual(latex.retrieval_dates({**built, "data_retrieved": same}), "2026-11-19")
        span = {"first": "2026-11-18T23:00:00+00:00", "last": "2026-11-19T01:00:00+00:00"}
        self.assertEqual(latex.retrieval_dates({**built, "data_retrieved": span}), "2026-11-18 – 2026-11-19")
        locations = load_locations(Paths().locations_csv)
        raw = DataCollector([SyntheticSource(S)]).collect(locations)
        r = assemble_results(locations, raw, S, [SyntheticSource(S)], synthetic=False, data_retrieved=same)
        self.assertEqual(r["data_retrieved"], same)

    def test_optional_gap_is_reported(self):
        def drop(raw):
            raw["oslo"].forest_share = None

        r = synthetic_results(drop)
        self.assertNotIn("habitat", [c["key"] for c in r["model"]])
        self.assertTrue(any(e["key"] == "habitat" for e in r["exclusions"]))

    def test_select_locations(self):
        locations = load_locations(Paths().locations_csv)
        self.assertEqual([l.id for l in select_locations(locations, ["Paris", " amsterdam "])], ["paris", "amsterdam"])
        with self.assertRaises(ValueError):
            select_locations(locations, ["atlantis"])


class LatexTests(unittest.TestCase):
    def test_escape(self):
        self.assertEqual(latex.tex_escape("50% & km² _x"), r"50\% \& km\textsuperscript{2} \_x")

    def test_fragments_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            written = latex.write_fragments(synthetic_results(), Path(tmp))
            names = {p.name for p in written}
            self.assertEqual(names, {"macros.tex", "ranking_table.tex", "headtohead_table.tex", "regions_table.tex",
                                     "model_table.tex", "contributions_figure.tex", "findings.tex", "coverage.tex"})
            macros = (Path(tmp) / "macros.tex").read_text()
            self.assertIn("\\MLSsynthetictrue", macros)
            self.assertIn("\\newcommand{\\MLSRunnerUpName}", macros)
            self.assertNotIn("Headline", macros)
            self.assertNotIn("Benchmark", macros)
            for name in ("ranking_table.tex", "contributions_figure.tex"):  # nobody is set in bold/italics
                text = (Path(tmp) / name).read_text()
                self.assertNotIn("\\textit", text)
                self.assertNotIn("\\textbf{Paris}", text)
            regions = (Path(tmp) / "regions_table.tex").read_text()
            self.assertEqual(regions.count("\\\\"), 1 + 6)  # header + one row per region
            self.assertEqual((Path(tmp) / "ranking_table.tex").read_text().count("\\\\"), 41)


class WebAppTests(unittest.TestCase):
    def test_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.json"
            client = create_app(path).test_client()
            self.assertEqual(client.get("/api/results").status_code, 404)
            self.assertFalse(client.get("/healthz").get_json()["results_available"])

            save_results(synthetic_results(), path)
            self.assertEqual(load_results(path)["schema_version"], 2)
            response = client.get("/api/results")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.get_json()["locations"]), 40)
            with client.get("/") as page:
                self.assertEqual(page.status_code, 200)
                self.assertIn(b"Mushroom Livability", page.data)
            for asset in ("/static/app.js", "/static/app.css"):
                with client.get(asset) as response:
                    self.assertEqual(response.status_code, 200)

    def test_page_uses_relative_urls_and_download_link(self):
        # Relative URLs let the same page work at "/" (Flask) and under
        # "/<repo>/" on GitHub Pages; the download target comes from settings.
        html = (APP_DIR / "templates" / "index.html").read_text()
        js = (APP_DIR / "static" / "app.js").read_text()
        self.assertIn('href="static/app.css"', html)
        self.assertIn('src="static/app.js"', html)
        self.assertIn('id="download"', html)
        self.assertNotIn('"/static/', html)
        self.assertIn('fetch("api/results")', js)
        self.assertEqual(synthetic_results()["settings"]["download_url"], Settings().download_url)
        self.assertTrue(Settings().download_url.startswith("https://"))

    def test_static_site_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.json"
            with self.assertRaises(FileNotFoundError):
                export_site(path, Path(tmp) / "site")
            results = synthetic_results()
            save_results(results, path)
            out = Path(tmp) / "site"
            (out / "stale.txt").parent.mkdir(parents=True)
            (out / "stale.txt").write_text("old")
            files = {p.relative_to(out).as_posix() for p in export_site(path, out)}
            self.assertEqual(files, {"index.html", "static/app.js", "static/app.css", "api/results", ".nojekyll"})
            self.assertEqual(json.loads((out / "api" / "results").read_text()), load_results(path))

if __name__ == "__main__":
    unittest.main()
