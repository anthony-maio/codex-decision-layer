"""Run the next unstarted slot in a committed 45-worker workflow schedule."""
from __future__ import annotations
import argparse
from importlib.metadata import version
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
from ratchet_atomic import atomic

from freeze_ratchet_workflow import FREEZE, validate, sha
from ratchet_workflow_metrics import assess
from ratchet_workflow_trial import run_trial
from validate_ratchet_workflow_fixtures import ROOT, FIXTURES, TASKS


def validate_history(folder, reproduce):
    local = json.loads((folder / "history-receipt.json").read_text(encoding="utf-8"))
    frozen = json.loads((ROOT / "results/ratchet/workflow-history.json").read_text(encoding="utf-8"))
    if local["status"] != "RECORDED_NOT_CLASSIFIED" or (not reproduce and local != frozen):
        raise ValueError("original trials require the frozen recorded history")
    rows = local["records"]
    if len(rows) != 6 or {(r["task"], r["attempt"]) for r in rows} != {(t, i) for t in TASKS for i in (0, 1)}:
        raise ValueError("history requires all six unique attempts")
    for row in rows:
        task, side = row["task"], row["attempt"]
        name = f"attempt-{side}.jsonl"
        if row["record"] != name or sha((folder / task / "history" / name).read_bytes()) != row["record_sha256"]:
            raise ValueError("historical record changed")
        source = FIXTURES / task / ("previous.py" if side == 0 else "product.py")
        if sha(source.read_bytes()) != row["source_sha256"]:
            raise ValueError("history source changed")
        proof = row.get("child_provenance", {})
        required = {"evidence_selector/__init__.py", "evidence_selector/ratchet/records.py",
                    "evidence_selector/ratchet/pytest_reporter.py"}
        if proof.get("status") != "VERIFIED" or proof.get("mode") != "pytest" or set(proof.get("module_sha256", {})) != required:
            raise ValueError("historical child provenance is missing")
        if any(sha((ROOT / name).read_bytes()) != expected for name, expected in proof["module_sha256"].items()):
            raise ValueError("historical child used different project code")
    return local


def interrupted_row(slot, trial_dir, phase):
    """Conservative failure receipt after an authoritative process-group check."""
    if phase == "PREPARING":
        lifecycle = {"state": "LAUNCH_FAILED", "pid": None}
    elif phase == "LAUNCHING":
        try:
            lifecycle = json.loads((trial_dir / "worker/lifecycle.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ValueError("launch may have occurred but its identity is unavailable; inspect processes before any finalization") from None
    else:
        raise ValueError("unknown launch phase")
    pid = lifecycle.get("pid")
    if pid is not None:
        if sys.platform != "linux":
            raise ValueError("interrupted-worker recovery currently requires a Linux process-group audit")
        for probe in (os.kill, os.killpg):
            try:
                probe(pid, 0)
            except ProcessLookupError:
                continue
            raise ValueError("owned worker or process group still exists; do not finalize or restart it")
    elif lifecycle.get("state") != "LAUNCH_FAILED":
        raise ValueError("worker launch status is not verifiable")
    elapsed = lifecycle.get("elapsed_seconds", 600)
    return {**slot, "status": "INTERRUPTED", "elapsed_seconds": max(.001, elapsed),
            "latency_kind": "observed_until_owned_cleanup" if "elapsed_seconds" in lifecycle else "600_second_penalty_unknown_duration",
            "quality_pass": False, "method_compliance": False, "grading": {"status": "UNVERIFIED", "passed": 0},
            "worker_usage": None, "total_cost": {"lower_usd": None, "upper_usd": None},
            "worker_restarted": False, "failure_reason": "interrupted_or_unrecorded_measurement",
            "worker_events_sha256": sha((trial_dir / "worker/events.jsonl").read_bytes()) if (trial_dir / "worker/events.jsonl").exists() else None}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--private-dir", required=True, type=Path)
    p.add_argument("--history-dir", required=True, type=Path)
    p.add_argument("--env-file", required=True, type=Path, help="explicit Jev upload opt-in for the authored trial records")
    p.add_argument("--reproduce-to", type=Path, help="new separately labeled output outside the repository")
    p.add_argument("--recover-completed", action="store_true", help="finalize a saved completed slot without launching another worker")
    p.add_argument("--finalize-interrupted", action="store_true", help="retain a failed attempted slot after verifying its Linux process group is absent")
    args = p.parse_args()
    if args.recover_completed and args.finalize_interrupted:
        p.error("choose one recovery action")
    freeze, commit = validate()
    private = args.private_dir.resolve()
    if private.is_relative_to(ROOT):
        p.error("private-dir must remain outside Git")
    output = (args.reproduce_to.resolve() if args.reproduce_to else ROOT / "results/ratchet/workflow-v1.json")
    if args.reproduce_to and output.is_relative_to(ROOT):
        p.error("reproductions must be kept outside the canonical repository results")
    if not args.reproduce_to and sys.platform != freeze["original_platform"]:
        p.error("original worker schedule uses the frozen Linux platform")
    if version("pytest") != "8.4.2" or version("mcp") != "1.30.0":
        p.error("use the frozen pytest 8.4.2 and mcp 1.30.0 environment")
    codex = shutil.which("codex")
    if not codex:
        p.error("Codex is not on PATH")
    cli_version = subprocess.check_output([codex, "--version"], text=True, encoding="utf-8", timeout=10).strip()
    if cli_version != freeze["codex_cli"]:
        p.error("Codex CLI version differs from the freeze")
    history = validate_history(args.history_dir.resolve(), bool(args.reproduce_to))
    if not args.env_file.is_file():
        p.error("explicit provider env-file does not exist")
    private.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = output.with_suffix(output.suffix + ".lock")
    # Exclusive claim, never automatically deleted by another invocation. A stale
    # lock requires inspecting the recorded PID, not assuming a worker has stopped.
    with lock.open("x", encoding="utf-8") as stream:
        json.dump({"pid": os.getpid()}, stream)
    try:
        identity_path = private / "experiment-identity.json"
        if not identity_path.exists():
            with identity_path.open("x", encoding="utf-8") as stream:
                json.dump({"id": uuid.uuid4().hex}, stream)
        private_id = json.loads(identity_path.read_text(encoding="utf-8"))["id"]
        result = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {
            "status": "IN_PROGRESS", "kind": "REPRODUCTION" if args.reproduce_to else "ORIGINAL",
            "freeze_commit": commit, "freeze_sha256": sha(FREEZE.read_bytes()),
            "codex_cli": cli_version, "python": sys.version.split()[0], "platform": sys.platform,
            "history": history, "trials": []}
        if (result["freeze_commit"] != commit or result["freeze_sha256"] != sha(FREEZE.read_bytes())
            or result["history"] != history or result["kind"] != ("REPRODUCTION" if args.reproduce_to else "ORIGINAL")):
            raise ValueError("existing result belongs to different inputs")
        rows = result["trials"]
        expected = freeze["schedule"]
        if len(rows) > len(expected) or any(any(row[k] != slot[k] for k in slot) for row, slot in zip(rows, expected)):
            raise ValueError("results are not the exact schedule prefix")
        if len(rows) == len(expected):
            print(json.dumps({"status": "ALREADY_COMPLETE", "workers": len(rows)}))
            return
        slot = expected[len(rows)]
        trial_dir = private / f"slot-{slot['index']:02d}"
        pending = result.get("pending")
        if pending:
            if not args.recover_completed and not args.finalize_interrupted:
                raise ValueError("the canonical experiment has an attempted slot; inspect its process and recover it, never rerun")
            if pending.get("slot") != slot or pending.get("private_id") != private_id:
                raise ValueError("recovery requires the original attempt's private directory")
            if args.finalize_interrupted and (trial_dir / "result.json").exists():
                try:
                    candidate = json.loads((trial_dir / "result.json").read_text(encoding="utf-8"))
                except (ValueError, UnicodeError):
                    candidate = None
                if isinstance(candidate, dict) and candidate.get("status") == "COMPLETE":
                    raise ValueError("a completed receipt exists; recover it without replacing its result")
            saved = (interrupted_row(slot, trial_dir, pending.get("phase")) if args.finalize_interrupted else
                     json.loads((trial_dir / "result.json").read_text(encoding="utf-8")))
            event_path = trial_dir / "worker/events.jsonl"
            actual_event_hash = sha(event_path.read_bytes()) if event_path.exists() else None
            if (saved.get("status") not in ("COMPLETE", "INTERRUPTED") or any(saved[k] != slot[k] for k in slot)
                or saved["worker_events_sha256"] != actual_event_hash):
                raise ValueError("saved completed result does not match the attempted slot")
            rows.append(saved)
            result.pop("pending")
            if len(rows) == len(expected):
                result["status"] = "COMPLETE"
                result["assessment"] = assess(rows)
            atomic(output, result)
            print(json.dumps({"status": "FINALIZED_INTERRUPTION" if args.finalize_interrupted else "RECOVERED_SAVED_RESULT",
                              "slot": slot["index"], "worker_restarted": False}))
            return
        if args.recover_completed or args.finalize_interrupted:
            raise ValueError("no attempted slot requires recovery")
        if trial_dir.exists():
            raise ValueError("slot has already started; inspect its owned process and logs before recovery, never rerun it")
        result["pending"] = {"slot": slot, "private_id": private_id, "phase": "PREPARING"}
        atomic(output, result)
        def before_launch():
            result["pending"]["phase"] = "LAUNCHING"
            atomic(output, result)
        try:
            row = run_trial(slot, trial_dir, args.history_dir.resolve(), codex, args.env_file.resolve(), before_launch=before_launch)
        except Exception as exc:
            result["measurement_error"] = type(exc).__name__
            atomic(output, result)
            raise
        rows.append(row)
        result.pop("pending")
        if len(rows) == len(expected):
            result["status"] = "COMPLETE"
            result["assessment"] = assess(rows)
        atomic(output, result)
        print(json.dumps({"slot": row["index"], "task": row["task"], "method": row["method"],
                          "quality_pass": row["quality_pass"], "method_compliance": row["method_compliance"],
                          "seconds": row["elapsed_seconds"], "total_cost": row["total_cost"],
                          "workers_remaining": len(expected) - len(rows)}))
    finally:
        lock.unlink()


if __name__ == "__main__":
    main()
