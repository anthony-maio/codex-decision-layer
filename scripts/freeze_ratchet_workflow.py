"""Create and verify the first committed prospective workflow freeze."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from ratchet_workflow_metrics import schedule
from validate_ratchet_workflow_fixtures import ROOT, FIXTURES, TASKS

FREEZE = FIXTURES / "freeze.json"
REVIEW = ROOT / "results/ratchet/workflow-runner-review.json"


def inputs():
    names = {p.relative_to(ROOT).as_posix() for p in (ROOT / "evidence_selector").rglob("*.py")}
    names |= {p.relative_to(ROOT).as_posix() for task in TASKS for p in (FIXTURES / task).iterdir() if p.is_file()}
    names |= {"docs/ratchet-plan.md", "docs/ratchet-workflow-protocol.md", "pyproject.toml", "uv.lock",
              "results/ratchet/workflow-fixtures-linux.json", "results/ratchet/workflow-history.json",
              "results/ratchet/workflow-runner-review.json"}
    names |= {"scripts/" + s for s in ("freeze_ratchet_workflow.py", "run_ratchet_workflow.py",
              "ratchet_workflow_trial.py", "ratchet_workflow_metrics.py", "ratchet_worker_runtime.py",
              "ratchet_mcp_meter.py", "ratchet_verified_child.py", "ratchet_atomic.py", "read_ratchet_history.py",
              "prepare_ratchet_workflow_history.py", "validate_ratchet_workflow_fixtures.py")}
    return names


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def validate():
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    if (freeze.get("status") != "FROZEN_BEFORE_SCORING" or set(freeze["sha256"]) != inputs()
        or freeze["schedule"] != schedule() or freeze["model"] != "gpt-5.6-sol"
        or freeze["codex_cli"] != "codex-cli 0.146.0"):
        raise ValueError("incomplete or altered workflow freeze")
    for name, expected in freeze["sha256"].items():
        if sha((ROOT / name).read_bytes()) != expected:
            raise ValueError("frozen workflow input changed: " + name)
    path = FREEZE.relative_to(ROOT).as_posix()
    history = subprocess.check_output(["git", "-C", str(ROOT), "log", "--reverse", "--format=%H", "--", path], text=True).splitlines()
    if not history:
        raise ValueError("commit the complete freeze before running any scored worker")
    commit = history[0]
    if subprocess.check_output(["git", "-C", str(ROOT), "show", commit + ":" + path]) != FREEZE.read_bytes():
        raise ValueError("freeze differs from its first committed version")
    for name, expected in freeze["sha256"].items():
        if sha(subprocess.check_output(["git", "-C", str(ROOT), "show", commit + ":" + name])) != expected:
            raise ValueError("input was not committed with first freeze: " + name)
    return freeze, commit


def create():
    if FREEZE.exists():
        raise ValueError("preserve the existing workflow freeze")
    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    if review.get("status") != "PASS" or review.get("model_repair_trials_started") != 0:
        raise ValueError("require independent pre-trial runner review")
    names = inputs()
    for name, expected in review["sha256"].items():
        if sha((ROOT / name).read_bytes()) != expected:
            raise ValueError("reviewed input changed: " + name)
    required_review = {name for name in names if name.startswith("scripts/") or name.startswith("fixtures/") or name == "docs/ratchet-workflow-protocol.md"}
    if not required_review <= set(review["sha256"]):
        raise ValueError("runner review does not cover required inputs")
    result = {"status": "FROZEN_BEFORE_SCORING", "model": "gpt-5.6-sol", "reasoning": "low",
              "codex_cli": "codex-cli 0.146.0", "original_platform": "linux", "schedule": schedule(),
              "sha256": {name: sha((ROOT / name).read_bytes()) for name in sorted(names)}}
    with FREEZE.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=("create", "verify"))
    args = p.parse_args()
    if args.action == "create":
        result = create()
        print(json.dumps({"status": result["status"], "inputs": len(result["sha256"]), "commit_required": True}))
    else:
        freeze, commit = validate()
        print(json.dumps({"status": "VERIFIED", "commit": commit, "workers": len(freeze["schedule"])}))
