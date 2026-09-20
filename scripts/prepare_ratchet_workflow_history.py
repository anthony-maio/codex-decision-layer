"""Record actual authored prior/current attempts without scoring a comparator."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from validate_ratchet_workflow_fixtures import ROOT, FIXTURES, TASKS, digest, prepare_task

sys.path.insert(0, str(ROOT))
from evidence_selector.ratchet.records import parse_run


def prepare(private):
    private = Path(private).resolve()
    if private.is_relative_to(ROOT):
        raise ValueError("raw history must stay outside Git")
    private.mkdir(parents=True, exist_ok=False)
    rows = []
    started = time.perf_counter()
    env = os.environ.copy()
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for task in TASKS:
        workspace = private / task
        prepare_task(task, workspace, "previous.py")
        records = workspace / "history"
        records.mkdir()
        for number, implementation in enumerate(("previous.py", "product.py")):
            shutil.copyfile(FIXTURES / task / implementation, workspace / "product.py")
            name = f"attempt-{number}.jsonl"
            proof = private / f"{task}-{number}.provenance.json"
            command = [sys.executable, "-B", str(ROOT / "scripts/ratchet_verified_child.py"), "pytest",
                       "--provenance", str(proof), "--", "-q", "--tb=long", "-p", "no:cacheprovider",
                       "-p", "evidence_selector.ratchet.pytest_reporter", "--ratchet-task", f"workflow-{task}",
                       "--ratchet-output", str(records / name), "test_visible.py"]
            proc = subprocess.run(command, cwd=workspace, env=env, capture_output=True,
                                  text=True, encoding="utf-8", timeout=30)
            (private / f"{task}-{number}.stdout.txt").write_text(proc.stdout, encoding="utf-8")
            (private / f"{task}-{number}.stderr.txt").write_text(proc.stderr, encoding="utf-8")
            run = parse_run((records / name).read_bytes())
            if proc.returncode != 1 or not run.complete or len(run.failures) != 1:
                raise ValueError("authored historical run did not produce one complete failure: " + task)
            rows.append({"task": task, "attempt": number, "record": name,
                         "record_sha256": run.digest, "source_sha256": digest(FIXTURES / task / implementation),
                         "failure_stage": run.failures[0]["stage"], "exit_code": proc.returncode,
                         "child_provenance": json.loads(proof.read_text(encoding="utf-8"))})
    receipt = {"status": "RECORDED_NOT_CLASSIFIED", "records": rows,
               "setup_seconds": time.perf_counter() - started,
               "python": sys.version.split()[0], "platform": sys.platform}
    (private / "history-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--private-dir", required=True, type=Path)
    args = p.parse_args()
    print(json.dumps(prepare(args.private_dir), indent=2))
