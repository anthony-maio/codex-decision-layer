import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ratchet_mcp_meter import comparison_metrics
from ratchet_workflow_trial import FIXTURES, ROOT, mcp_compliance, read_meter, trusted_grade, verified_test_records
from read_ratchet_history import read_history


class TrialTests(unittest.TestCase):
    def test_meter_does_not_leak_evidence_or_treat_failed_call_as_free(self):
        response = {"result": {"structuredContent": {"mode": "shadow", "provider_calls": 1,
            "reason": "provider_failure", "error": "PRIVATE SENTINEL", "retries": 0,
            "provider_latency_ms": 10, "sources": [{"text": "PRIVATE SENTINEL"}]}}}
        result = comparison_metrics(response)
        self.assertEqual(result["accounting"], "MISSING_PROVIDER_USAGE")
        self.assertIsNone(result["provider_input_tokens"])
        self.assertNotIn("PRIVATE", json.dumps(result))
        response["result"]["structuredContent"]["provider_latency_ms"] = "PRIVATE SENTINEL"
        self.assertEqual(comparison_metrics(response), {"accounting": "UNAVAILABLE"})

    def test_unfinished_or_invalid_meter_has_unknown_cost(self):
        with tempfile.TemporaryDirectory(prefix="ratchet-trial-") as temp:
            path = Path(temp) / "meter.jsonl"
            path.write_text(json.dumps({"event": "tool_started", "call": 0, "tool": "ratchet_compare"}) + "\n")
            self.assertIsNone(read_meter(path, "jev")["estimated_cost_usd"])
            path.write_text("{broken\n")
            self.assertEqual(read_meter(path, "jev")["status"], "INVALID")

    def test_every_reported_provider_attempt_is_charged(self):
        with tempfile.TemporaryDirectory(prefix="ratchet-trial-") as temp:
            path = Path(temp) / "meter.jsonl"
            events = []
            for i in range(2):
                events += [{"event": "tool_started", "call": i, "tool": "ratchet_compare"},
                           {"event": "tool_finished", "call": i, "tool": "ratchet_compare",
                            "elapsed_ms": 12, "accounting": "REPORTED", "provider_calls": 1,
                            "provider_retries": 0, "provider_input_tokens": 1000,
                            "provider_output_tokens": 3, "provider_latency_ms": 10}]
            path.write_text("\n".join(json.dumps(e) for e in events) + "\n")
            result = read_meter(path, "jev")
            self.assertEqual(result["provider_calls"], 2)
            self.assertEqual(result["provider_input_tokens"], 2000)
            self.assertAlmostEqual(result["estimated_cost_usd"], .000084)

    def test_grader_ignores_worker_test_configuration(self):
        with tempfile.TemporaryDirectory(prefix="ratchet-trial-") as temp:
            root = Path(temp)
            worker = root / "workspace"
            worker.mkdir()
            shutil.copyfile(FIXTURES / "queue/reference.py", worker / "product.py")
            (worker / "conftest.py").write_text("raise RuntimeError('should never enter trusted grader')\n")
            (worker / "pytest.ini").write_text("[pytest]\naddopts = --ignore=test_grading.py\n")
            result = trusted_grade("queue", worker / "product.py", root)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["passed"], 25)
            self.assertFalse((root / "grader/conftest.py").exists())

    def test_wrong_test_collection_cannot_pass_or_inflate_score(self):
        with tempfile.TemporaryDirectory(prefix="ratchet-trial-") as temp:
            root = Path(temp)
            result = dict(exit_code=0, tests=999, passed=999, skipped=0, failed=0, test_ids=["wrong"] * 999)
            with patch("ratchet_workflow_trial.pytest_run", return_value=result):
                grade = trusted_grade("queue", FIXTURES / "queue/reference.py", root)
            self.assertEqual(grade["status"], "FAIL")
            self.assertEqual(grade["passed"], 0)

    def test_plain_method_cannot_silently_use_mcp(self):
        with tempfile.TemporaryDirectory(prefix="ratchet-trial-") as temp:
            root = Path(temp)
            (root / "history").mkdir()
            for i in (0, 1):
                (root / f"history/attempt-{i}.jsonl").write_text("{}\n")
            items = [{"type": "mcp_tool_call", "server": "ratchet_trial", "tool": "ratchet_compare"}]
            self.assertEqual(mcp_compliance(items, root, "plain"), (False, 1))
            self.assertEqual(mcp_compliance([], root, "plain"), (False, 0))
            read = {"type": "command_execution", "command": "python read_ratchet_history.py --root history",
                    "status": "completed", "exit_code": 0,
                    "aggregated_output": json.dumps(read_history(root / "history"))}
            self.assertEqual(mcp_compliance([read], root, "plain"), (True, 0))

    def test_comparison_without_original_retrieval_is_noncompliant(self):
        with tempfile.TemporaryDirectory(prefix="ratchet-trial-") as temp:
            root = Path(temp)
            (root / "history").mkdir()
            for i in (0, 1):
                (root / f"history/attempt-{i}.jsonl").write_text("{}\n")
            self.assertEqual(mcp_compliance([], root, "deterministic"), (False, 0))

    def test_worker_test_is_bound_to_final_source_and_command(self):
        with tempfile.TemporaryDirectory(prefix="ratchet-trial-") as temp:
            root = Path(temp).resolve()
            (root / "product.py").write_text("def add(a,b):\n    return a+b\n", encoding="utf-8")
            (root / "test_visible.py").write_text("from product import add\ndef test_add():\n    assert add(2,3)==5\n", encoding="utf-8")
            (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
            command = [sys.executable, "-B", str(ROOT / "scripts/ratchet_verified_child.py"), "pytest",
                       "--test-proof", "--provenance", "test-run-1.provenance.json", "--", "-q",
                       "-p", "no:cacheprovider", "-p", "evidence_selector.ratchet.pytest_reporter",
                       "--ratchet-task", "trial-addition", "--ratchet-output", "test-run-1.jsonl", "test_visible.py"]
            completed = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=20)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            observed = [{"command": " ".join(command), "exit_code": 0}]
            self.assertEqual(len(verified_test_records(root, observed, "addition", None)), 1)
            self.assertEqual(verified_test_records(root, [], "addition", None), [])
            (root / "product.py").write_text("def add(a,b):\n    return a-b\n", encoding="utf-8")
            self.assertEqual(verified_test_records(root, observed, "addition", None), [])


if __name__ == "__main__":
    unittest.main()
