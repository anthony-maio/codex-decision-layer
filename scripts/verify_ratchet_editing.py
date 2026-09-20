"""Publish only numeric and hash evidence from an unscored repair preflight."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TEST = (
    "import unittest\nfrom sum_values import sum_values\n"
    "class SumTests(unittest.TestCase):\n"
    "    def test_positive(self):\n        self.assertEqual(sum_values(3, 4), 7)\n"
    "    def test_negative(self):\n        self.assertEqual(sum_values(-2, 3), 1)\n")


def verify(private):
    private = Path(private).resolve()
    if private.is_relative_to(ROOT):
        raise ValueError("private evidence must be outside Git")
    summary = json.loads((private / "summary.json").read_text(encoding="utf-8"))
    raw = (private / "worker/events.jsonl").read_bytes()
    events = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    completed = [e["item"] for e in events if e.get("type") == "item.completed"]
    source = (private / "workspace/sum_values.py").read_text(encoding="utf-8")
    tests = (private / "workspace/test_sum_values.py").read_text(encoding="utf-8")
    executed = [i for i in completed if i.get("type") == "command_execution"
                and i.get("status") == "completed" and "-m unittest" in i.get("command", "")]
    edits = [i for i in completed if i.get("type") == "file_change" and i.get("status") == "completed"]
    checks = {
        "worker_completed": summary["exit_code"] == 0 and not summary["timed_out"]
                            and any(e.get("type") == "turn.completed" for e in events),
        "actual_addition_edit": source == "def sum_values(a, b):\n    return a + b\n" and bool(edits),
        "tests_unchanged": tests == EXPECTED_TEST,
        "one_observed_passing_test_command": len(executed) == 1 and executed[0].get("exit_code") == 0
                    and "Ran 2 tests" in executed[0].get("aggregated_output", "")
                    and "\nOK" in executed[0].get("aggregated_output", ""),
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
            "scope": "unscored authored addition repair; no Ratchet comparison or usefulness measurement",
            "elapsed_seconds": summary["elapsed_seconds"], "timed_out": summary["timed_out"],
            "worker_exit_code": summary["exit_code"], "usage": summary["usage"],
            "events_sha256": hashlib.sha256(raw).hexdigest(),
            "implementation_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "supplied_tests_sha256": hashlib.sha256(tests.encode()).hexdigest(),
            "verification_platform": sys.platform}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--private-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = verify(args.private_dir)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 2)
