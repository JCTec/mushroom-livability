import math
import unittest

from src.domain import RawLocationData
from src.processing import climate, geo, seasonality
from src.processing.gridding import grid_counts
from src.processing.metrics import build_metrics
from src.settings import Settings

S = Settings()


class GeoTests(unittest.TestCase):
    def test_haversine_paris_amsterdam(self):
        distance = geo.haversine_km(48.8566, 2.3522, 52.3676, 4.9041)
        self.assertAlmostEqual(distance, 430, delta=5)

    def test_circle_polygon_is_closed_and_on_radius(self):
        ring = geo.circle_polygon(48.0, 2.0, 25.0, 32)
        self.assertEqual(len(ring), 33)
        self.assertEqual(ring[0], ring[-1])
        for lon, lat in ring[:-1]:
            self.assertAlmostEqual(geo.haversine_km(48.0, 2.0, lat, lon), 25.0, delta=0.3)

    def test_lattice_points_inside_circle(self):
        points = geo.lattice_in_circle(52.0, 5.0, 25.0, 7)
        self.assertEqual(len(points), 37)
        for lat, lon in points:
            self.assertLessEqual(geo.haversine_km(52.0, 5.0, lat, lon), 25.3)


class GriddingTests(unittest.TestCase):
    def test_centre_and_corner_cells(self):
        box = geo.bounding_box(50.0, 10.0, 25.0)
        points = [
            [50.0001, 10.0001],                      # just NE of centre
            [box["north"] - 0.001, box["west"] + 0.001],  # NW corner
            [80.0, 10.0],                            # far outside: ignored
        ]
        grid = grid_counts(points, 50.0, 10.0, 25.0, 4)
        self.assertEqual(grid[0][0], 1)
        self.assertEqual(grid[1][2], 1)
        self.assertEqual(sum(map(sum, grid)), 2)


class SeasonalityTests(unittest.TestCase):
    def test_reliable_months_needs_share_and_count(self):
        monthly = [0, 0, 5, 20, 30, 10, 10, 40, 200, 400, 250, 35]
        # total 1000 -> 4 % = 40. Qualifying: Aug(40), Sep, Oct, Nov.
        self.assertEqual(seasonality.reliable_months(monthly, 0.04, 10), 4)

    def test_absolute_floor(self):
        self.assertEqual(seasonality.reliable_months([1] * 12, 0.04, 10), 0)

    def test_invalid_input(self):
        self.assertIsNone(seasonality.reliable_months(None, 0.04, 10))
        self.assertIsNone(seasonality.reliable_months([1, 2], 0.04, 10))

    def test_evenness_bounds(self):
        self.assertAlmostEqual(seasonality.evenness([10] * 12), 1.0)
        self.assertAlmostEqual(seasonality.evenness([120] + [0] * 11), 0.0)


class ClimateTests(unittest.TestCase):
    def test_monthly_normals(self):
        dates = ["2020-01-01", "2020-01-02", "2021-01-01", "2021-01-02"]
        normals_input = (dates, [0.0, 2.0, 4.0, 6.0], [1.0, 2.0, 3.0, 4.0])
        with self.assertRaises(ValueError):  # only January present
            climate.monthly_normals(*normals_input)
        dates, temps, precs = [], [], []
        for year in (2020, 2021):
            for month in range(1, 13):
                dates += [f"{year}-{month:02d}-01", f"{year}-{month:02d}-02"]
                temps += [float(month), float(month) + 2]
                precs += [10.0, None]
        normals = climate.monthly_normals(dates, temps, precs)
        self.assertEqual(len(normals), 12)
        self.assertAlmostEqual(normals[0]["temp_c"], 2.0)
        self.assertAlmostEqual(normals[0]["precip_mm"], 10.0)  # 20 mm over 2 years

    def test_temperature_trapezoid(self):
        self.assertEqual(climate.temperature_factor(-3, S), 0.0)
        self.assertAlmostEqual(climate.temperature_factor(4, S), 0.5)
        self.assertEqual(climate.temperature_factor(12, S), 1.0)
        self.assertAlmostEqual(climate.temperature_factor(22, S), 0.5)
        self.assertEqual(climate.temperature_factor(30, S), 0.0)

    def test_suitability_index(self):
        ideal = [{"temp_c": 12.0, "precip_mm": 100.0}] * 12
        dry = [{"temp_c": 12.0, "precip_mm": 40.0}] * 12
        self.assertAlmostEqual(climate.climate_suitability(ideal, S), 1.0)
        self.assertAlmostEqual(climate.climate_suitability(dry, S), 0.5)
        self.assertEqual(climate.suitable_months(ideal, S), 12)
        self.assertIsNone(climate.climate_suitability(None, S))


class MetricsTests(unittest.TestCase):
    def test_build_metrics(self):
        raw = RawLocationData(
            fungi_observations=1000, all_observations=50000, species_count=300, gbif_records=4000,
            population=2_000_000.0, forest_share=0.2,
            monthly_observations=[10, 10, 20, 40, 50, 40, 40, 60, 200, 300, 200, 30],
            climate_monthly=[{"temp_c": 12.0, "precip_mm": 80.0}] * 12,
        )
        m = build_metrics(raw, S)
        self.assertAlmostEqual(m.obs_per_km2, 1000 / (math.pi * 625))
        self.assertAlmostEqual(m.obs_per_100k, 50.0)
        self.assertAlmostEqual(m.fungal_share, 0.02)
        self.assertEqual(m.species_richness, 300.0)
        self.assertEqual(m.reliable_months, 8.0)
        self.assertAlmostEqual(m.climate_suitability, 1.0)

    def test_missing_inputs_give_none(self):
        m = build_metrics(RawLocationData(fungi_observations=10), S)
        self.assertIsNone(m.obs_per_100k)
        self.assertIsNone(m.fungal_share)
        self.assertIsNone(m.reliable_months)
        self.assertIsNotNone(m.obs_per_km2)


if __name__ == "__main__":
    unittest.main()
