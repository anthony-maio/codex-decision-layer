"""Continue the original schedule under a committed, disclosed startup amendment."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
from unittest.mock import patch

import run_ratchet_workflow as runner
import ratchet_workflow_trial as trial
from freeze_ratchet_workflow import ROOT, validate, sha

PACKET = ROOT / "results/ratchet/workflow-amendment-1.json"
MARKER = "execution_amendment_sha256"
FLAG = "mcp_servers.ratchet_trial.required=true"
REVIEW = "results/ratchet/workflow-amendment-review.json"
INPUTS = {"scripts/run_ratchet_workflow_amended.py", "tests/test_ratchet_workflow_amendment.py",
          "docs/ratchet-workflow-amendment-1.md", "results/ratchet/workflow-v1-first-three.json",
          "results/ratchet/workflow-startup-diagnostics.json", REVIEW}


def canonical_sha(value):
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def validate_amendment():
    validate()
    raw = PACKET.read_bytes()
    packet = json.loads(raw)
    if packet["status"] != "FROZEN_BEFORE_SLOT_3" or packet["first_amended_slot"] != 3:
        raise ValueError("unknown amendment")
    validate_review(packet)
    name = PACKET.relative_to(ROOT).as_posix()
    history = subprocess.check_output(["git", "-C", str(ROOT), "log", "--reverse", "--format=%H", "--", name], text=True).splitlines()
    if not history:
        raise ValueError("commit the amendment before continuing")
    commit = history[0]
    if subprocess.check_output(["git", "-C", str(ROOT), "show", commit + ":" + name]) != raw:
        raise ValueError("amendment differs from its first commit")
    for path, expected in packet["sha256"].items():
        if sha((ROOT / path).read_bytes()) != expected or sha(subprocess.check_output(
                ["git", "-C", str(ROOT), "show", commit + ":" + path])) != expected:
            raise ValueError("amendment input changed: " + path)
    snapshot = json.loads((ROOT / "results/ratchet/workflow-v1-first-three.json").read_text())
    if len(snapshot["trials"]) != 3 or canonical_sha(snapshot["trials"]) != packet["original_first_three_sha256"]:
        raise ValueError("original attempts changed")
    return packet, sha(raw)


def validate_review(packet):
    if set(packet.get("sha256", {})) != INPUTS:
        raise ValueError("incomplete amendment input coverage")
    review = json.loads((ROOT / REVIEW).read_text())
    if (review.get("status") != "PASS" or review.get("independent_review") is not True
        or review.get("new_scored_trials_started") != 0 or set(review.get("sha256", {})) != INPUTS - {REVIEW}):
        raise ValueError("require complete independent amendment review")
    for name, expected in review["sha256"].items():
        if sha((ROOT / name).read_bytes()) != expected or packet["sha256"][name] != expected:
            raise ValueError("reviewed amendment input changed")


def amended_command(command, method, index):
    if index < 3 or method == "plain":
        return command
    if method not in ("deterministic", "jev") or command[-1] != "-":
        raise ValueError("unexpected command shape")
    return command[:-1] + ["-c", FLAG, "-"]


def guarded_write(path, result, packet, marker, write):
    """Called by the original runner only while its exclusive output lock is held."""
    path = Path(path)
    previous = json.loads(path.read_text()) if path.exists() else None
    rows = result["trials"]
    if result["kind"] == "ORIGINAL" and canonical_sha(rows[:3]) != packet["original_first_three_sha256"]:
        raise ValueError("original first three rows must remain unchanged")
    metadata = {"id": "required-mcp-from-slot-3", "sha256": marker,
                "first_amended_slot": 3, "interpretation": "amended_exploratory",
                "confirmatory_usefulness": "NOT_ESTABLISHED",
                "mcp_startup_failure": "required server may abort worker; retain failed attempt"}
    old_rows = previous["trials"] if previous else []
    if rows[:len(old_rows)] != old_rows:
        raise ValueError("existing completed attempts changed")
    if any(r.get(MARKER) != marker for r in old_rows if r["index"] >= 3):
        raise ValueError("unamended entry point used after amendment; invalidate and inspect, never rerun")
    if previous and (previous.get("execution_amendment") not in (None, metadata)
                     or (len(old_rows) > 3 and previous.get("execution_amendment") != metadata)):
        raise ValueError("amendment metadata mismatch")
    old_pending = previous.get("pending") if previous else None
    if old_pending and old_pending["slot"]["index"] >= 3 and old_pending.get(MARKER) != marker:
        raise ValueError("pending attempt lacks amendment provenance; inspect before recovery")
    for row in rows[len(old_rows):]:
        if row["index"] < 3:
            continue
        if not old_pending or old_pending["slot"]["index"] != row["index"] or old_pending.get(MARKER) != marker:
            raise ValueError("completed row has no matching amended claim")
        if row.get(MARKER, marker) != marker:
            raise ValueError("completed row amendment mismatch")
        row[MARKER] = marker
    if result.get("pending") and result["pending"]["slot"]["index"] >= 3:
        if result["pending"].get(MARKER, marker) != marker:
            raise ValueError("new claim amendment mismatch")
        result["pending"][MARKER] = marker
    result["execution_amendment"] = metadata
    write(path, result)


def audit_output(path, packet, marker):
    """Audit even ALREADY_COMPLETE without relying on a write occurring."""
    path = Path(path)
    lock = path.with_suffix(path.suffix + ".lock")
    with lock.open("x", encoding="utf-8") as stream:
        json.dump({"pid": os.getpid()}, stream)
    try:
        result = json.loads(path.read_text())
        guarded_write(path, result, packet, marker, lambda *args: None)
    finally:
        lock.unlink()


def main():
    packet, marker = validate_amendment()
    original_command, original_trial, original_write = trial.make_command, runner.run_trial, runner.atomic
    active = {"index": None}

    def command(*args, **kwargs):
        if active["index"] is None:
            raise ValueError("command outside assigned trial")
        return amended_command(original_command(*args, **kwargs), args[2], active["index"])

    def run(slot, *args, **kwargs):
        active["index"] = slot["index"]
        try:
            return original_trial(slot, *args, **kwargs)
        finally:
            active["index"] = None

    with patch.object(trial, "make_command", command), patch.object(runner, "run_trial", run), \
         patch.object(runner, "atomic", lambda path, value: guarded_write(path, value, packet, marker, original_write)):
        runner.main()
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--reproduce-to", type=Path)
    args, _ = parser.parse_known_args()
    audit_output(args.reproduce_to.resolve() if args.reproduce_to else ROOT / "results/ratchet/workflow-v1.json", packet, marker)


if __name__ == "__main__":
    main()
