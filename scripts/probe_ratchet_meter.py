"""Unscored real Codex MCP-plus-edit preflight, separate from scored repairs."""
import argparse
import hashlib
from importlib.resources import files
import json
from pathlib import Path
import shutil
import sys

from ratchet_worker_runtime import run_worker
from ratchet_workflow_trial import ROOT, make_command, mcp_compliance, read_meter


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--private-dir", type=Path, required=True)
    args = p.parse_args()
    private = args.private_dir.resolve()
    if private.is_relative_to(ROOT):
        p.error("preflight must stay outside Git")
    private.mkdir(parents=True, exist_ok=False)
    workspace = private / "workspace"
    workspace.mkdir()
    history = workspace / "history"
    history.mkdir()
    replay = json.loads(files("evidence_selector.ratchet").joinpath("data/replay.json").read_text())
    for side, events in enumerate(replay["examples"][0]["records"]):
        (history / f"attempt-{side}.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8", newline="\n")
    (workspace / "product.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    test = "from product import add\ndef test_add():\n    assert add(2, 3) == 5\n"
    (workspace / "test_visible.py").write_text(test, encoding="utf-8")
    (workspace / "pytest.ini").write_text("[pytest]\ntestpaths = test_visible.py\n", encoding="utf-8")
    meter = private / "metrics.jsonl"
    codex = shutil.which("codex")
    if not codex:
        p.error("Codex not found")
    command = make_command(codex, workspace, "deterministic", meter)
    prompt = ("Unscored integration preflight. First use only MCP server ratchet_trial to call ratchet_status, "
              "ratchet_compare(previous='attempt-0.jsonl', current='attempt-1.jsonl'), and ratchet_evidence "
              "to retrieve both complete originals using the returned hashes. Those are a recorded replay "
              "unrelated to the addition repair; do not diagnose the replay beyond reporting the relationship. "
              "Then inspect product.py and test_visible.py, repair add(a,b) to add its arguments by editing "
              "only product.py, and run the existing pytest test once. Keep all supplied files intact except "
              "product.py. Do not escalate, disable rules, or route around a declined action. Stop and report "
              "any decline. Use this Python interpreter: " + sys.executable + ". Report observed outcomes briefly.")
    result = run_worker(command, prompt, private / "worker", timeout=240)
    compliant, unexpected = mcp_compliance(result["items"], workspace, "deterministic")
    numeric = read_meter(meter, "deterministic")
    commands = [i for i in result["items"] if i.get("type") == "command_execution" and i.get("status") == "completed"]
    tests = [i for i in commands if "-m pytest" in i.get("command", "") and i.get("exit_code") == 0
             and "1 passed" in i.get("aggregated_output", "")]
    checks = {"worker_completed": result["exit_code"] == 0 and not result["timed_out"] and result["completed_turns"] == 1,
              "mcp_status_comparison_and_exact_originals": compliant,
              "implementation_changed_to_addition": (workspace / "product.py").read_text() == "def add(a, b):\n    return a + b\n",
              "test_unchanged": (workspace / "test_visible.py").read_text() == test,
              "one_observed_passing_test_command": len(tests) == 1,
              "complete_meter": numeric["status"] == "COMPLETE"}
    safe = {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
            "scope": "unscored addition repair plus recorded replay; no usefulness comparison",
            "platform": sys.platform, "elapsed_seconds": result["elapsed_seconds"],
            "usage": result["usage"], "meter": numeric, "unexpected_mcp_calls": unexpected,
            "worker_events_sha256": hashlib.sha256((private / "worker/events.jsonl").read_bytes()).hexdigest()}
    (private / "summary.json").write_text(json.dumps(safe, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(safe, indent=2))
    return 0 if safe["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
