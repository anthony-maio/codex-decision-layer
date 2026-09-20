from collections import Counter
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ratchet_workflow_metrics import assess, schedule, worker_cost


def rows():
    return [{**s, "elapsed_seconds": 100 if s["method"] == "plain" else 80,
             "total_cost": {"lower_usd": 1, "upper_usd": 1},
             "quality_pass": True, "grading": {"passed": 10}} for s in schedule()]


class WorkflowMetricTests(unittest.TestCase):
    def test_cached_tokens_are_not_full_price(self):
        result = worker_cost(dict(input_tokens=1000, cached_input_tokens=800,
                                  cache_write_input_tokens=50, output_tokens=100))
        self.assertAlmostEqual(result["lower_usd"], .00317)
        self.assertEqual(result["lower_usd"], result["upper_usd"])

    def test_missing_cache_writes_and_large_aggregate_bound_cost(self):
        result = worker_cost(dict(input_tokens=1000, cached_input_tokens=800, output_tokens=100))
        self.assertAlmostEqual(result["lower_usd"], .00312)
        self.assertAlmostEqual(result["upper_usd"], .00332)
        large = worker_cost(dict(input_tokens=300000, cached_input_tokens=0,
                                 cache_write_input_tokens=0, output_tokens=100))
        self.assertTrue(large["per_request_surcharge_unresolved"])
        self.assertAlmostEqual(large["upper_usd"], 2.403)

    def test_invalid_or_missing_usage_is_not_free(self):
        self.assertIsNone(worker_cost(None)["lower_usd"])
        for usage in [dict(input_tokens=-1, cached_input_tokens=0, output_tokens=0),
                      dict(input_tokens=10, cached_input_tokens=8, cache_write_input_tokens=3, output_tokens=0),
                      dict(input_tokens=True, cached_input_tokens=0, output_tokens=0)]:
            with self.assertRaises(ValueError):
                worker_cost(usage)

    def test_schedule_balanced_within_and_across_tasks(self):
        planned = schedule()
        self.assertEqual(len(planned), 45)
        orders = Counter(tuple(s["method"] for s in planned if s["triplet"] == i) for i in range(15))
        self.assertEqual(len(orders), 6)
        self.assertLessEqual(max(orders.values()) - min(orders.values()), 1)
        for method in ("plain", "deterministic", "jev"):
            self.assertEqual(Counter(s["position"] for s in planned if s["method"] == method), {0: 5, 1: 5, 2: 5})

    def test_full_coverage_required(self):
        for invalid in (rows()[:-1], rows() + [rows()[0]]):
            with self.assertRaises(ValueError):
                assess(invalid)

    def test_malformed_bounds_cannot_pass_usefulness(self):
        for low, high in [(1, 0), (-1, 1), (0, float("nan")),
                          (float("inf"), float("inf")), (True, 1), (0, "1")]:
            sample = rows()
            sample[0]["total_cost"] = {"lower_usd": low, "upper_usd": high}
            with self.subTest(low=low, high=high), self.assertRaises(ValueError):
                assess(sample)

    def test_invalid_latency_quality_or_grading_is_rejected(self):
        for field, value in [("elapsed_seconds", True), ("elapsed_seconds", float("inf")),
                             ("quality_pass", 1), ("grading", {"passed": -1}),
                             ("grading", {"passed": True}), ("grading", {"passed": 2.5})]:
            sample = rows()
            sample[0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                assess(sample)

    def test_jev_must_beat_both_baselines(self):
        result = assess(rows())
        self.assertTrue(result["comparisons"][1]["usefulness_gate"])
        self.assertFalse(result["jev_incremental_usefulness"])

    def test_failed_runs_missing_usage_and_quality_cannot_be_removed(self):
        sample = rows()
        i = next(i for i, r in enumerate(sample) if r["method"] == "jev")
        sample[i]["quality_pass"] = False
        sample[i]["total_cost"] = {"lower_usd": None, "upper_usd": None}
        result = assess(sample)["comparisons"][1]
        self.assertFalse(result["quality_gate"])
        self.assertFalse(result["performance_gate"])
        self.assertIsNone(result["conservative_cost_ratio"])

    def test_single_task_latency_regression_fails_even_if_aggregate_improves(self):
        sample = rows()
        for row in sample:
            if row["method"] == "jev":
                row["elapsed_seconds"] = 121 if row["task"] == "events" else 50
        result = assess(sample)["comparisons"][1]
        self.assertTrue(result["performance_gate"])
        self.assertFalse(result["per_task_latency_gate"])
        self.assertFalse(result["usefulness_gate"])


if __name__ == "__main__":
    unittest.main()
