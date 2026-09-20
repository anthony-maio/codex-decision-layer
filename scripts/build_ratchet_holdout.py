"""Execute pinned public-library adapters without invoking either comparator."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import random
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "click": {"url": "https://github.com/pallets/click", "version": "8.1.8",
              "commit": "934813e4d421071a1b3db3973c02fe2721359a6e", "license": "LICENSE.txt", "spdx": "BSD-3-Clause"},
    "packaging": {"url": "https://github.com/pypa/packaging", "version": "25.0",
                  "commit": "f58537628042c7f29780b9d33f31597e7fc9d664", "license": "LICENSE.BSD", "spdx": "BSD-2-Clause"},
    "more-itertools": {"url": "https://github.com/more-itertools/more-itertools", "version": "10.8.0",
                       "commit": "8c1a6ef241b51ff055e89219f050ccf4f15f37f6", "license": "LICENSE", "spdx": "MIT"},
}
# Imports plus three real calls: original failure, same constraint with changed
# input, and a different constraint/failing operation. No fabricated exceptions.
SCENARIOS = [
    ("click", "cli-choice", "import click", "click.Choice(['red', 'blue']).convert('green', None, None)",
     "click.Choice(['red', 'blue']).convert('purple', None, None)", "click.INT.convert('red', None, None)"),
    ("click", "cli-range", "import click", "click.IntRange(1, 9).convert(10, None, None)",
     "click.IntRange(1, 9).convert(11, None, None)", "click.INT.convert('ten', None, None)"),
    ("click", "cli-tuple-arity", "import click", "click.Tuple([int, int]).convert([], None, None)",
     "click.Tuple([int, int]).convert(['1'], None, None)", "click.Tuple([int, int]).convert(['1', 'word'], None, None)"),
    ("click", "cli-required-option", "import click\n@click.command()\n@click.option('--name', required=True)\n@click.option('--verbose', is_flag=True)\ndef command(name, verbose):\n    return name",
     "command.main(args=[], standalone_mode=False)", "command.main(args=['--verbose'], standalone_mode=False)",
     "command.main(args=['--name', 'valid', '--unknown'], standalone_mode=False)"),
    ("packaging", "release-version-grammar", "from packaging.version import Version", "Version('banana')",
     "Version('not-a-version')", "assert Version('1.0') > Version('2.0')"),
    ("packaging", "release-specifier-operator", "from packaging.specifiers import SpecifierSet", "SpecifierSet('=>1.0')",
     "SpecifierSet('=>2.0')", "assert SpecifierSet('>=1.0').contains('0.9')"),
    ("packaging", "requirement-url-grammar", "from packaging.requirements import Requirement", "Requirement('demo @')",
     "Requirement('other @')", "assert Requirement('demo>=1.0').name == 'other'"),
    ("packaging", "environment-marker-operator", "from packaging.markers import Marker", 'Marker("python_version ??? \'3.12\'")',
     'Marker("python_version ??? \'3.13\'")', 'assert Marker("python_version < \'2.0\'").evaluate({"python_version": "3.12"})'),
    ("more-itertools", "single-result-cardinality", "from more_itertools import one",
     "one([], too_short=ValueError('expected exactly one result'))",
     "one(iter([]), too_short=ValueError('expected exactly one result'))",
     "one([1, 2], too_long=ValueError('expected exactly one result'))"),
    ("more-itertools", "fixed-result-cardinality", "from more_itertools import strictly_n\ndef count_error(count):\n    raise ValueError('expected exactly three results')",
     "list(strictly_n([1], 3, too_short=count_error))",
     "list(strictly_n([1, 2], 3, too_short=count_error))",
     "list(strictly_n([1, 2, 3, 4], 3, too_long=count_error))"),
]


def adapter(imports, expression, *, setup=False, mixed=False):
    source = imports + "\n\n"
    if setup:
        source += "import pytest\n@pytest.fixture\ndef prepared():\n    " + expression + "\n\ndef test_case(prepared):\n    assert prepared == 'expected'\n"
    else:
        source += "def test_case():\n    " + expression + "\n"
    if mixed:
        source += "\ndef test_second():\n    assert 2 + 2 == 5\n"
    return source


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source-dir", type=Path, required=True)
    p.add_argument("--private-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    private, output = args.private_dir.resolve(), args.output_dir.resolve()
    if private.is_relative_to(ROOT) or output.exists():
        p.error("private-dir must be outside Git; output-dir must be new")
    private.mkdir(parents=True, exist_ok=False)
    output.mkdir(parents=True)
    provenance = {}
    replacements = [(str(private), "<RUNS>"), (str(Path(sys.prefix)), "<ENV>")]
    for name, expected in SOURCES.items():
        path = (args.source_dir / name).resolve()
        head = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(["git", "-C", str(path), "diff", "--name-only"], text=True).strip()
        if head != expected["commit"] or dirty or importlib.metadata.version(name) != expected["version"]:
            raise ValueError("source_or_version_mismatch: " + name)
        license_bytes = (path / expected["license"]).read_bytes()
        license_name = name + "-LICENSE.txt"
        (output / license_name).write_bytes(license_bytes)
        provenance[name] = {**expected, "license_file": license_name,
                            "license_sha256": hashlib.sha256(license_bytes).hexdigest()}
        replacements.insert(0, (str(path), "<PUBLIC>/" + name))
    if importlib.metadata.version("pytest") != "8.4.2":
        raise ValueError("pytest_version_mismatch")
    cases = []
    for index, (repo, family, imports, before_call, same_call, different_call) in enumerate(SCENARIOS):
        for kind in ("same", "different", "insufficient"):
            case_id = f"holdout-{family}-{kind}"
            workspace = private / case_id
            workspace.mkdir()
            mixed = kind == "insufficient" and index >= 4
            before = adapter(imports, before_call, setup=kind == "different" and index < 2, mixed=mixed)
            after = adapter(imports, different_call if kind == "different" else same_call, mixed=mixed)
            if kind == "different" and index < 2:
                after = "import pytest\n@pytest.fixture\ndef prepared():\n    return 'initialized'\n\ndef test_case(prepared):\n    assert prepared == 'expected'\n"
            records = []
            for side, source in (("before", before), ("after", after)):
                (workspace / "test_case.py").write_text(source, encoding="utf-8", newline="\n")
                record = workspace / (side + ".jsonl")
                env = dict(os.environ, PYTHONPATH=str(ROOT), PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONDONTWRITEBYTECODE="1")
                command = [sys.executable, "-m", "pytest", "-q", "--tb=short", "-p", "no:cacheprovider", "-p",
                           "evidence_selector.ratchet.pytest_reporter", "--ratchet-task", case_id, "--ratchet-output", str(record)]
                run = subprocess.run(command, cwd=workspace, env=env, capture_output=True, text=True, timeout=30)
                if run.returncode != 1:
                    (workspace / (side + ".stderr")).write_text(run.stdout + run.stderr, encoding="utf-8")
                    raise ValueError(f"fixture_did_not_fail: {case_id}/{side}, exit {run.returncode}")
                events = [json.loads(line) for line in record.read_text(encoding="utf-8").splitlines()]
                for event in events:
                    event["run_id"] = case_id + "-" + side
                    if "root" in event:
                        event["root"] = "public-adapter/" + repo + "/" + family
                    for key in ("duration", "duration_seconds"):
                        if key in event:
                            event[key] = 0
                    if "longrepr" in event:
                        for old, new in replacements:
                            event["longrepr"] = event["longrepr"].replace(old, new).replace(old.replace("\\", "/"), new)
                        event["longrepr"] = event["longrepr"].replace("\\", "/")
                if kind == "insufficient" and not mixed and side == "after":
                    events = events[:-1]
                records.append(events)
            tags = ["public_library_adapter", family]
            if kind == "different":
                tags.append("productive_progress" if index < 8 else "identical_message_different_constraint")
            if kind == "insufficient":
                tags.append("mixed_failures" if mixed else "incomplete_record")
            cases.append({"id": case_id, "repository": repo, "family": family, "tags": tags,
                          "retry_intent": "diagnostic_retry" if kind == "same" and index < 3 else "unknown",
                          "adapter_sources": {"before": before, "after": after}, "records": records,
                          "author_label": {"same": "same_blocker", "different": "different_blocker", "insufficient": "insufficient_evidence"}[kind],
                          "author_advisory_eligible": False})
            print(case_id, flush=True)
    corpus = {"schema": 1, "split": "holdout", "status": "UNREVIEWED_UNSCORED",
              "provenance": "Authored adapters deliberately trigger failures in pinned public library code; not natural agent traces or upstream bugs.",
              "sources": provenance, "pytest": "8.4.2",
              "normalization": "Deterministic run IDs, public root/task labels, zero timing, absolute paths replaced, path separators normalized. Four current records deliberately omit finish; all other report content preserved.",
              "cases": cases}
    def write(name, value):
        (output / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
    write("corpus.json", corpus)
    ordered = list(cases)
    random.Random(20260920).shuffle(ordered)
    blind, mapping = [], {}
    for i, case in enumerate(ordered):
        anonymous = f"pair-{i + 1:02d}"
        mapping[anonymous] = case["id"]
        records = json.loads(json.dumps(case["records"]))
        for side, events in enumerate(records):
            for event in events:
                event["run_id"] = anonymous + "-" + str(side)
                if "task" in event:
                    event["task"] = anonymous
                if "root" in event:
                    event["root"] = "public-adapter/" + case["repository"]
        blind.append({"id": anonymous, "retry_intent": case["retry_intent"],
                      "sources": case["adapter_sources"], "records": records})
    write("review-input.json", {"protocol": "Label same_blocker/different_blocker/insufficient_evidence and advisory eligibility with decisive evidence. Same means same immediate failing operation and constraint, not necessarily identical input. Only two attempts are available. Do not inspect other files or run comparators.", "cases": blind})
    write("review-map.json", mapping)


if __name__ == "__main__":
    main()
