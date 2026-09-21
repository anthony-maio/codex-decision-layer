import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ratchet_workflow_metrics import assess, schedule
from run_ratchet_workflow import interrupted_row
from summarize_ratchet_workflow import summarize


def receipt():
    rows = [{**slot, "quality_pass": True, "method_compliance": True, "elapsed_seconds": 1,
             "grading": {"passed": 1, "elapsed_seconds": 0.1},
             "worker_usage": {"input_tokens": 10, "cached_input_tokens": 5, "cache_write_input_tokens": 0, "output_tokens": 1},
             "selector": {"status": "COMPLETE", "tool_elapsed_ms": 2, "provider_errors": 0},
             "observed_test_commands": 1, "repeated_completed_commands": 0,
             "total_cost": {"lower_usd": 1, "upper_usd": 1}} for slot in schedule()]
    return {"status": "COMPLETE", "trials": rows, "assessment": assess(rows),
            "freeze_commit": "test", "freeze_sha256": "test", "execution_amendment": {},
            "history": {"setup_seconds": 0}}


class WorkflowSummaryTests(unittest.TestCase):
    def test_finalized_interruption_remains_unknown_and_penalized(self):
        data = receipt()
        with tempfile.TemporaryDirectory() as temp:
            data["trials"][0] = interrupted_row(schedule()[0], Path(temp), "PREPARING")
        data["assessment"] = assess(data["trials"])
        before = copy.deepcopy(data)
        result = summarize(json.dumps(data).encode())
        self.assertEqual(data, before)
        self.assertEqual(result["assigned_runs"], 45)
        self.assertEqual(result["excluded_runs"], 0)
        self.assertEqual(result["unknown_full_cost_slots"], [0])
        total = result["all_runs"]
        self.assertEqual(total["latency_penalty_slots"], [0])
        self.assertEqual(total["latency_total_seconds_including_penalties"], 644)
        self.assertEqual(total["observed_elapsed_seconds"]["observed_sum"], 44)
        self.assertIsNone(total["observed_elapsed_seconds"]["complete_sum"])
        for key in ("observed_test_commands", "repeated_completed_commands", "grading_seconds_outside_worker_timer"):
            self.assertEqual(total[key]["unknown_runs"], 1)
            self.assertIsNone(total[key]["complete_sum"])
        self.assertIsNone(total["selector"]["tool_elapsed_ms"]["complete_sum"])
        self.assertEqual(result["frozen_assessment"], data["assessment"])

    def test_partial_meter_keeps_observations_without_complete_total(self):
        data = receipt()
        data["trials"][1]["selector"] = {"status": "INCOMPLETE_ACCOUNTING", "tool_elapsed_ms": 9, "provider_errors": 1}
        result = summarize(json.dumps(data).encode())["all_runs"]
        for key, expected in (("tool_elapsed_ms", 97), ("provider_errors", 1)):
            self.assertEqual(result["selector"][key]["observed_sum"], expected)
            self.assertEqual(result["selector"][key]["unknown_runs"], 1)
            self.assertIsNone(result["selector"][key]["complete_sum"])
        self.assertEqual(result["selector_status_counts"]["INCOMPLETE_ACCOUNTING"], 1)

    def test_pending_or_missing_assigned_run_refuses_summary(self):
        data = receipt()
        data["pending"] = {"slot": 44}
        with self.assertRaises(ValueError):
            summarize(json.dumps(data).encode())
        del data["pending"]
        data["trials"].pop()
        with self.assertRaises(ValueError):
            summarize(json.dumps(data).encode())


if __name__ == "__main__":
    unittest.main()
