"""Source tests: request parameters and response parsing, with a fake HTTP."""

import json
import tempfile
import unittest
from pathlib import Path

from src.data.climate import OpenMeteoClimateSource
from src.data.collector import DataCollector
from src.data.gbif import GbifSource
from src.data.habitat import OverpassForestSource, build_query, parse_forest_share
from src.data.http import CachedJsonHttp
from src.data.inaturalist import INaturalistSampleSource, INaturalistStatsSource, parse_month_histogram, parse_points
from src.data.locations import load_locations
from src.data.population import WorldPopSource
from src.data.sources import SourceError, SourceInfo
from src.data.synthetic import SyntheticSource
from src.settings import Paths, Settings
from src.diagnostics import pick_location
from tests.fakes import VANCOUVER, FakeHttp

S = Settings()


class INaturalistTests(unittest.TestCase):
    def test_stats_requests_and_parsing(self):
        def observations(url, params):
            return {"total_results": 1234 if "taxon_id" in params else 99999, "results": []}

        http = FakeHttp([
            ("/observations/species_counts", {"total_results": 321, "results": [{}]}),
            ("/observations/histogram", {"results": {"month_of_year": {str(m): m * 10 for m in range(1, 13)}}}),
            ("/observations", observations),
        ])
        values = INaturalistStatsSource(http, S).fetch(VANCOUVER)
        self.assertEqual(values["fungi_observations"], 1234)
        self.assertEqual(values["all_observations"], 99999)
        self.assertEqual(values["species_count"], 321)
        self.assertEqual(values["monthly_observations"], [m * 10 for m in range(1, 13)])
        first = http.calls[0][2]
        self.assertEqual((first["taxon_id"], first["quality_grade"], first["radius"], first["per_page"]),
                         (47170, "research", 25.0, 0))
        self.assertNotIn("taxon_id", http.calls[1][2])  # all-taxa baseline
        self.assertEqual(http.calls[3][2]["interval"], "month_of_year")

    def test_histogram_missing_months_default_to_zero(self):
        self.assertEqual(parse_month_histogram({"results": {"month_of_year": {"10": 7}}}), [0] * 9 + [7, 0, 0])
        with self.assertRaises(SourceError):
            parse_month_histogram({"results": {}})

    def test_points(self):
        records = [{"location": "48.85,2.35"}, {"location": None}, {"location": "bad"}, {"location": "x,y"}, {}]
        self.assertEqual(parse_points(records), [[48.85, 2.35]])

    def test_sample_stops_on_short_page(self):
        http = FakeHttp([("/observations", {"results": [{"location": "48.9,2.3"}] * 3})])
        values = INaturalistSampleSource(http, S).fetch(VANCOUVER)
        self.assertEqual(len(values["sample_points"]), 3)
        self.assertEqual(len(http.calls), 1)


class OtherSourceTests(unittest.TestCase):
    def test_gbif(self):
        http = FakeHttp([("occurrence/search", {"count": 11342, "results": []})])
        self.assertEqual(GbifSource(http, S).fetch(VANCOUVER), {"gbif_records": 11342})
        params = http.calls[0][2]
        self.assertEqual(params["geoDistance"], "49.2827,-123.1207,25km")
        self.assertEqual(params["kingdomKey"], 5)
        with self.assertRaises(SourceError):
            GbifSource(FakeHttp([("occurrence", {})]), S).fetch(VANCOUVER)

    def test_open_meteo(self):
        dates = [f"2020-{m:02d}-15" for m in range(1, 13)]
        payload = {"daily": {"time": dates, "temperature_2m_mean": [10.0] * 12, "precipitation_sum": [2.0] * 12}}
        http = FakeHttp([("archive", payload)])
        normals = OpenMeteoClimateSource(http, S).fetch(VANCOUVER)["climate_monthly"]
        self.assertEqual(len(normals), 12)
        self.assertEqual(normals[0], {"temp_c": 10.0, "precip_mm": 2.0})
        self.assertEqual(http.calls[0][2]["daily"], "temperature_2m_mean,precipitation_sum")
        with self.assertRaises(SourceError):
            OpenMeteoClimateSource(FakeHttp([("archive", {"error": True})]), S).fetch(VANCOUVER)

    def test_worldpop_immediate_and_polled(self):
        done = {"status": "finished", "error": False, "data": {"total_population": 9_500_000.4}}
        http = FakeHttp([("services/stats", done)])
        self.assertAlmostEqual(WorldPopSource(http, S).fetch(VANCOUVER)["population"], 9_500_000.4)
        geojson = json.loads(http.calls[0][2]["geojson"])
        ring = geojson["features"][0]["geometry"]["coordinates"][0]
        self.assertEqual(ring[0], ring[-1])

        polled = FakeHttp([("services/stats", {"status": "created", "error": False, "taskid": "abc"}),
                           ("tasks/abc", done)])
        source = WorldPopSource(polled, S, sleep=lambda seconds: None)
        self.assertAlmostEqual(source.fetch(VANCOUVER)["population"], 9_500_000.4)

    def test_worldpop_errors(self):
        failing = FakeHttp([("services/stats", {"status": "finished", "error": True, "error_message": "boom"})])
        with self.assertRaises(SourceError):
            WorldPopSource(failing, S, sleep=lambda s: None).fetch(VANCOUVER)
        stuck = FakeHttp([("services/stats", {"status": "started", "taskid": "t"}), ("tasks/t", {"status": "started", "taskid": "t"})])
        with self.assertRaises(SourceError):
            WorldPopSource(stuck, S, sleep=lambda s: None, max_polls=2).fetch(VANCOUVER)

    def test_overpass(self):
        query = build_query([(48.1, 2.1), (48.2, 2.2)])
        self.assertEqual(query.count("is_in("), 2)
        self.assertEqual(query.count("out count;"), 2)
        self.assertIn('area.a["natural"="wood"]', query)

        def answer(url, data):
            n = data["data"].count("is_in(")
            elements = [{"type": "count", "id": 0, "tags": {"total": "1" if i % 4 == 0 else "0"}} for i in range(n)]
            return {"elements": elements}

        share = OverpassForestSource(FakeHttp([("interpreter", answer)]), S).fetch(VANCOUVER)["forest_share"]
        self.assertAlmostEqual(share, 10 / 37, places=3)
        with self.assertRaises(SourceError):
            parse_forest_share({"elements": []}, 37)


class InfrastructureTests(unittest.TestCase):
    def test_cache_hits_and_cache_if(self):
        with tempfile.TemporaryDirectory() as tmp:
            inner = FakeHttp([("example", lambda url, params: {"n": len(inner.calls)})])
            cached = CachedJsonHttp(inner, Path(tmp))
            first = cached.get_json("https://example.org/a", {"q": 1})
            second = cached.get_json("https://example.org/a", {"q": 1})
            self.assertEqual(first, second)
            self.assertEqual(len(inner.calls), 1)
            cached.get_json("https://example.org/a", {"q": 2})
            self.assertEqual(len(inner.calls), 2)
            cached.get_json("https://example.org/b", None, cache_if=lambda payload: False)
            cached.get_json("https://example.org/b", None, cache_if=lambda payload: False)
            self.assertEqual(len(inner.calls), 4)
            record = json.loads(next(Path(tmp).rglob("*.json")).read_text())
            self.assertEqual(set(record), {"method", "url", "params", "fetched_at", "payload"})

    def test_cache_reports_when_data_was_fetched_not_when_it_was_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(CachedJsonHttp(FakeHttp([]), Path(tmp)).retrieval_window())
            folder = Path(tmp) / "example.org"
            folder.mkdir()
            warm = CachedJsonHttp(FakeHttp([("example", {"n": 1})]), Path(tmp))
            warm.get_json("https://example.org/a", {"q": 1})
            path = next(folder.glob("*.json"))
            record = json.loads(path.read_text())
            record["fetched_at"] = "2026-11-19T16:46:25+00:00"  # an old cache entry
            path.write_text(json.dumps(record))

            inner = FakeHttp([("example", {"n": 2})])
            cached = CachedJsonHttp(inner, Path(tmp))
            cached.get_json("https://example.org/a", {"q": 1})  # served from cache
            self.assertEqual(len(inner.calls), 0)
            self.assertEqual(cached.retrieval_window(),
                             {"first": "2026-11-19T16:46:25+00:00", "last": "2026-11-19T16:46:25+00:00"})
            cached.get_json("https://example.org/b", None, cache_if=lambda payload: False)  # fresh, not cached
            window = cached.retrieval_window()
            self.assertEqual(window["first"], "2026-11-19T16:46:25+00:00")
            self.assertGreater(window["last"], window["first"])

    def test_collector_isolates_failures(self):
        class Good:
            info = SourceInfo("good", "", "", "", "", "", "")

            def fetch(self, location):
                return {"gbif_records": 5}

        class Bad:
            info = SourceInfo("bad", "", "", "", "", "", "")

            def fetch(self, location):
                raise RuntimeError("down")

        raw = DataCollector([Bad(), Good()]).collect([VANCOUVER])["vancouver"]
        self.assertEqual(raw.gbif_records, 5)
        self.assertIn("down", raw.errors["bad"])

    def test_check_defaults_to_first_row_not_a_hard_coded_city(self):
        locations = load_locations(Paths().locations_csv)
        self.assertEqual(pick_location(locations), locations[0])
        self.assertEqual(pick_location(locations, "oslo").name, "Oslo")
        with self.assertRaises(ValueError):
            pick_location(locations, "atlantis")

    def test_locations_file(self):
        locations = load_locations(Paths().locations_csv)
        ids = [l.id for l in locations]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertFalse(hasattr(locations[0], "role"), "locations are peers: no role field")
        groups = [l.group for l in locations]
        self.assertEqual(groups, sorted(groups), "rows are ordered by region, so no city is first by design")
        countries = {l.country for l in locations}
        for needed in ("Germany", "Sweden", "United Kingdom", "Ireland", "Italy", "Spain", "Canada"):
            self.assertIn(needed, countries)

    def test_synthetic_is_deterministic_and_complete(self):
        a, b = SyntheticSource(S).fetch(VANCOUVER), SyntheticSource(S).fetch(VANCOUVER)
        self.assertEqual(a, b)
        self.assertEqual(len(a["monthly_observations"]), 12)
        self.assertEqual(len(a["climate_monthly"]), 12)


if __name__ == "__main__":
    unittest.main()
