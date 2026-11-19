import unittest

from src.domain import Metrics
from src.scoring.components import DEFAULT_COMPONENTS, Component, SubMetric, validate
from src.scoring.engine import ScoringEngine
from src.scoring.normalization import FixedRangeScaler, LogMinMaxScaler


def metrics(**overrides):
    base = dict(obs_per_km2=1.0, obs_per_100k=50.0, fungal_share=0.02, gbif_per_km2=3.0, species_richness=300.0,
                reliable_months=6.0, climate_suitability=0.5, forest_share=0.3)
    base.update(overrides)
    return Metrics(**base)


class ScalerTests(unittest.TestCase):
    def test_log_minmax(self):
        scaled = LogMinMaxScaler().scale([0.0, 9.0, 99.0])
        self.assertEqual(scaled[0], 0.0)
        self.assertEqual(scaled[2], 1.0)
        self.assertAlmostEqual(scaled[1], 0.5)

    def test_log_minmax_all_equal(self):
        self.assertEqual(LogMinMaxScaler().scale([5.0, 5.0]), [0.5, 0.5])

    def test_fixed_range_clamps(self):
        self.assertEqual(FixedRangeScaler(12.0).scale([6.0, 24.0, -1.0]), [0.5, 1.0, 0.0])


class EngineTests(unittest.TestCase):
    def test_default_model_is_valid(self):
        validate(DEFAULT_COMPONENTS)

    def test_invalid_weights_rejected(self):
        bad = (Component("x", "X", 0.9, "?", (SubMetric("species_richness", "S", "", 1.0, LogMinMaxScaler(), True, ""),)),)
        with self.assertRaises(ValueError):
            ScoringEngine(bad)

    def test_contributions_sum_to_score_and_bounds(self):
        result = ScoringEngine().score({
            "a": metrics(),
            "b": metrics(obs_per_km2=5.0, species_richness=900.0, reliable_months=9.0),
            "c": metrics(obs_per_km2=0.2, species_richness=50.0, reliable_months=2.0, forest_share=0.9),
        })
        self.assertEqual([s.rank for s in result.scores], [1, 2, 3])
        self.assertEqual(result.scores[0].location_id, "b")
        for score in result.scores:
            self.assertAlmostEqual(score.score, sum(c.contribution for c in score.components))
            self.assertTrue(0.0 <= score.score <= 100.0)
            for component in score.components:
                self.assertAlmostEqual(sum(s.weight for s in component.submetrics), 1.0)
        self.assertAlmostEqual(sum(c["weight"] for c in result.model), 1.0)
        self.assertEqual(result.exclusions, [])

    def test_best_everywhere_scores_100_on_relative_metrics(self):
        result = ScoringEngine().score({
            "best": metrics(obs_per_km2=9, obs_per_100k=90, fungal_share=0.09, gbif_per_km2=9, species_richness=999,
                            reliable_months=12, climate_suitability=1.0, forest_share=0.7),
            "worst": metrics(obs_per_km2=0.1, obs_per_100k=1, fungal_share=0.001, gbif_per_km2=0.1,
                             species_richness=5, reliable_months=0, climate_suitability=0.0, forest_share=0.0),
        })
        self.assertAlmostEqual(result.scores[0].score, 100.0)
        self.assertAlmostEqual(result.scores[1].score, 0.0)

    def test_missing_required_metric_means_unscored(self):
        result = ScoringEngine().score({"a": metrics(), "b": metrics(species_richness=None)})
        self.assertEqual([s.location_id for s in result.scores], ["a"])
        self.assertEqual(result.unscored[0]["location_id"], "b")
        self.assertIn("Species observed", result.unscored[0]["missing"])

    def test_optional_submetric_dropped_for_everyone(self):
        result = ScoringEngine().score({"a": metrics(), "b": metrics(obs_per_100k=None)})
        self.assertEqual(len(result.scores), 2)
        self.assertEqual([e["key"] for e in result.exclusions], ["obs_per_100k"])
        density = result.scores[0].components[0]
        self.assertNotIn("obs_per_100k", [s.key for s in density.submetrics])
        self.assertAlmostEqual(sum(s.weight for s in density.submetrics), 1.0)
        self.assertAlmostEqual(density.submetrics[0].weight, 0.5)  # 0.40 / 0.80

    def test_component_dropped_and_weights_renormalised(self):
        result = ScoringEngine().score({"a": metrics(forest_share=None), "b": metrics(species_richness=500.0)})
        keys = [c["key"] for c in result.model]
        self.assertNotIn("habitat", keys)
        self.assertAlmostEqual(sum(c["weight"] for c in result.model), 1.0)
        self.assertAlmostEqual(result.model[0]["weight"], 0.25 / 0.90)
        self.assertEqual({e["level"] for e in result.exclusions}, {"submetric", "component"})

    def test_no_scorable_location(self):
        result = ScoringEngine().score({"a": metrics(climate_suitability=None)})
        self.assertEqual(result.scores, [])
        self.assertEqual(len(result.unscored), 1)


if __name__ == "__main__":
    unittest.main()
