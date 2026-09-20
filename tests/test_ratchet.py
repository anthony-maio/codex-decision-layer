"""Exercise real pytest stage transitions and evidence integrity."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from evidence_selector.ratchet.records import compare, read_run


@unittest.skipUnless(importlib.util.find_spec("pytest"), "requires ratchet extra")
class ReporterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.counter = 0

    def run_pytest(self, source, extra=()):
        self.counter += 1
        (self.root / "test_case.py").write_text(source, encoding="utf-8")
        output = self.root / f"attempt-{self.counter}.jsonl"
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]),
                   PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", "--tb=short",
            "-p", "no:cacheprovider", "-p", "evidence_selector.ratchet.pytest_reporter",
            "--ratchet-output", str(output), "--ratchet-task", "test-task", *extra], cwd=self.root, env=env,
            capture_output=True, text=True, timeout=30)
        self.assertIn(result.returncode, (0, 1, 2), result.stderr)
        return read_run(output), output

    def test_same_failure_preserves_exact_exception_and_distinct_runs(self):
        source = "def test_case():\n    raise ValueError('literal 123 decisive evidence')\n"
        first, first_path = self.run_pytest(source)
        second, _ = self.run_pytest(source)
        self.assertEqual(compare(first, second)["relationship"], "same_blocker")
        self.assertIsNone(compare(first, second)["advisory"])
        self.assertNotEqual(first.run_id, second.run_id)
        self.assertIn("literal 123 decisive evidence", first.failures[0]["longrepr"])
        self.assertEqual(compare(first, read_run(first_path))["reason"], "duplicate_run")

    def test_progress_from_setup_to_assertion_is_not_repetition(self):
        first, _ = self.run_pytest("import pytest\n@pytest.fixture\ndef db():\n"
            "    raise ConnectionRefusedError('database unavailable')\n"
            "def test_case(db):\n    assert db == 2\n")
        second, _ = self.run_pytest("import pytest\n@pytest.fixture\ndef db():\n"
            "    return 1\ndef test_case(db):\n    assert db == 2\n")
        self.assertEqual(first.failures[0]["stage"], "setup")
        self.assertEqual(second.failures[0]["stage"], "call")
        self.assertEqual(compare(first, second)["reason"], "execution_advanced")

    def test_changed_error_value_needs_comparison(self):
        first, _ = self.run_pytest("def test_case():\n    raise ValueError('port 1234')\n")
        second, _ = self.run_pytest("def test_case():\n    raise ValueError('port 5678')\n")
        self.assertEqual(compare(first, second)["reason"], "semantic_comparison_needed")

    def test_same_error_message_different_origin_is_not_exact_match(self):
        first, _ = self.run_pytest("def auth():\n    raise ValueError('unavailable')\n"
                                 "def test_case():\n    auth()\n")
        second, _ = self.run_pytest("def storage():\n    raise ValueError('unavailable')\n"
                                  "def test_case():\n    storage()\n")
        self.assertEqual(compare(first, second)["reason"], "semantic_comparison_needed")

    def test_maxfail_finish_is_incomplete_and_duplicate_reports_rejected(self):
        _, path = self.run_pytest("def test_case():\n    assert False\n"
                                 "def test_other():\n    assert True\n", extra=("-x",))
        self.assertFalse(read_run(path).complete)
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        report = next(e for e in events if e["kind"] == "report")
        events.insert(len(events) - 1, report)
        path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
        with self.assertRaises(ValueError):
            read_run(path)

    def test_partial_and_mixed_runs_cannot_be_compared(self):
        first, path = self.run_pytest("def test_case():\n    assert False\n")
        lines = path.read_text(encoding="utf-8").splitlines()
        partial = self.root / "partial.jsonl"
        partial.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
        self.assertFalse(read_run(partial).complete)
        altered = [json.loads(line) for line in lines]
        altered[-1]["run_id"] = "different-run"
        partial.write_text("\n".join(json.dumps(e) for e in altered), encoding="utf-8")
        with self.assertRaises(ValueError):
            read_run(partial)

    def test_mixed_failures_abstain_and_success_is_progress(self):
        source = "def test_case():\n    assert False\ndef test_other():\n    assert False\n"
        first, _ = self.run_pytest(source)
        second, _ = self.run_pytest(source)
        self.assertEqual(compare(first, second)["reason"], "multiple_or_missing_failures")
        passed, _ = self.run_pytest("def test_case():\n    assert True\ndef test_other():\n    assert True\n")
        self.assertEqual(compare(second, passed)["reason"], "current_run_passed")

    def test_omitted_failing_test_is_not_progress(self):
        first, _ = self.run_pytest("def test_case():\n    assert False\n")
        passed, _ = self.run_pytest("def test_other():\n    assert True\n")
        self.assertEqual(compare(first, passed)["reason"], "different_task_or_selection")

    def test_invalid_phase_order_is_rejected(self):
        _, path = self.run_pytest("def test_case():\n    assert False\n")
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        report = next(e for e in events if e["kind"] == "report")
        report["stage"] = "call"
        path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
        with self.assertRaises(ValueError):
            read_run(path)


if __name__ == "__main__":
    unittest.main()
