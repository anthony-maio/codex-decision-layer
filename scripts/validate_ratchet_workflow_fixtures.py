"""Validate authored repair contracts without running a model or scoring methods."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/ratchet/workflow-v1"
TASKS = ("invoice", "queue", "events")
EXPECTED_TESTS = {"invoice": 39, "queue": 25, "events": 29}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_task(task, workspace, implementation="product.py"):
    workspace.mkdir(parents=True, exist_ok=False)
    source = FIXTURES / task
    for name in ("TASK.md", "test_visible.py"):
        shutil.copyfile(source / name, workspace / name)
    shutil.copyfile(source / implementation, workspace / "product.py")
    # Avoid unrelated global pytest plugins and bytecode from previous versions.
    (workspace / "pytest.ini").write_text("[pytest]\ntestpaths = test_visible.py\n", encoding="utf-8")


def pytest_run(workspace, report, extra=()):
    env = os.environ.copy()
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "--tb=long",
                             "-p", "no:cacheprovider", f"--junitxml={report}", *extra],
                            cwd=workspace, env=env, capture_output=True, text=True,
                            encoding="utf-8", timeout=30)
    (report.with_suffix(".stdout.txt")).write_text(result.stdout, encoding="utf-8")
    (report.with_suffix(".stderr.txt")).write_text(result.stderr, encoding="utf-8")
    cases = ET.parse(report).findall(".//testcase") if report.exists() else []
    return {"exit_code": result.returncode, "tests": len(cases),
            "passed": sum(not any(c.find(k) is not None for k in ("failure", "error", "skipped")) for c in cases),
            "failed": sum(c.find("failure") is not None or c.find("error") is not None for c in cases),
            "skipped": sum(c.find("skipped") is not None for c in cases),
            "test_ids": [c.get("classname", "") + "::" + c.get("name", "") for c in cases]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-dir", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    private = args.private_dir.resolve()
    if private.is_relative_to(ROOT):
        parser.error("private-dir must be outside the repository")
    if args.output and args.output.exists():
        parser.error("preserve existing receipt")
    private.mkdir(parents=True, exist_ok=False)
    rows = []
    for task in TASKS:
        for implementation in ("previous.py", "product.py", "reference.py"):
            folder = private / task / implementation.removesuffix(".py")
            prepare_task(task, folder, implementation)
            extra = []
            if implementation == "reference.py":
                shutil.copyfile(FIXTURES / task / "test_grading.py", folder / "test_grading.py")
                extra = ["test_visible.py", "test_grading.py"]
            result = pytest_run(folder, folder / "result.xml", extra)
            expected = (result["exit_code"] == 0 and result["tests"] == EXPECTED_TESTS[task]
                        and result["passed"] == EXPECTED_TESTS[task]
                        and len(set(result["test_ids"])) == EXPECTED_TESTS[task]
                        if implementation == "reference.py" else
                        result["exit_code"] == 1 and result["failed"] == 1 and result["tests"] == 1)
            rows.append({"task": task, "implementation": implementation, **result,
                         "expected_outcome_verified": expected})
    result = {"status": "PASS" if all(r["expected_outcome_verified"] for r in rows) else "FAIL",
              "scope": "authored fixtures and reference graders only; no model runs",
              "platform": sys.platform, "python": sys.version.split()[0],
              "fixtures_sha256": {p.relative_to(ROOT).as_posix(): digest(p)
                                  for p in sorted(FIXTURES.rglob("*")) if p.is_file()}, "rows": rows}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
