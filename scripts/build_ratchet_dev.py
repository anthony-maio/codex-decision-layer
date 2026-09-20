"""Produce authored development failures by executing real pytest fixtures.

This is authored test evidence, not a public-repository benchmark or a real agent
session. Exact raw run records stay in --private-dir; normalized copies are public.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Every family belongs entirely to development. Holdout construction must exclude
# these causal scenarios and templates, not simply rename these exceptions.
FAMILIES = [
    ("database", "ConnectionRefusedError", "database listener refused connection", "PermissionError", "database authentication rejected"),
    ("configuration", "KeyError", "required API_ENDPOINT setting absent", "ValueError", "API_ENDPOINT scheme is invalid"),
    ("payload", "ValueError", "response body is invalid JSON", "KeyError", "decoded object lacks result key"),
    ("artifact", "FileNotFoundError", "compiled artifact is missing", "PermissionError", "artifact file cannot be opened"),
    ("dependency", "ModuleNotFoundError", "optional parser dependency is missing", "AttributeError", "installed parser has no parse method"),
    ("integrity", "ValueError", "download checksum differs from manifest", "FileNotFoundError", "checksum manifest is missing"),
    ("validation", "TypeError", "account identifier must be a string", "ValueError", "account identifier is empty"),
    ("capacity", "OSError", "storage device has no free space", "PermissionError", "storage directory is read only"),
    ("decoding", "ValueError", "byte sequence is not valid UTF-8", "LookupError", "requested codec is unavailable"),
    ("routing", "LookupError", "handler for route is not registered", "TypeError", "registered handler is not callable"),
]


def fixture(error, message, *, wrapped=False, location="perform", setup=False, multi=False):
    text = f"def {location}():\n    raise {error}({message!r})\n\n"
    if wrapped:
        text += (f"def invoke():\n    try:\n        {location}()\n"
                 "    except Exception as cause:\n        raise RuntimeError('request could not finish') from cause\n\n")
    expression = "invoke()" if wrapped else f"{location}()"
    if setup:
        text += f"import pytest\n@pytest.fixture\ndef prepared():\n    {expression}\n\ndef test_case(prepared):\n    assert prepared == 'ready'\n"
    else:
        text += f"def test_case():\n    {expression}\n"
    if multi:
        text += "\ndef test_independent():\n    raise RuntimeError('separate worker has stopped')\n"
    return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    private = args.private_dir.resolve()
    if private.is_relative_to(ROOT) or args.output.exists():
        parser.error("private-dir must be outside repository; output must be new")
    private.mkdir(parents=True, exist_ok=False)
    cases = []
    for index, (family, error, message, other_error, other_message) in enumerate(FAMILIES):
        for kind in ("same", "different", "insufficient"):
            case_id = f"dev-{family}-{kind}"
            workspace = private / case_id
            workspace.mkdir()
            before = fixture(error, message, setup=index < 2 and kind == "different")
            after = fixture(error, message, wrapped=index not in (0, 3, 7))
            tags = ["authored", family]
            intent = "diagnostic_retry" if index < 2 and kind == "same" else "unknown"
            if kind == "same":
                tags.append("wrapper_change" if index not in (0, 3, 7) else "exact_repeat")
            elif kind == "different":
                after = fixture(other_error, other_message)
                if index < 2:
                    after = "import pytest\n@pytest.fixture\ndef prepared():\n    return 'started'\n\ndef test_case(prepared):\n    assert prepared == 'ready'\n"
                    tags.append("productive_progress")
                elif index in (2, 3):
                    # The same generic text at different, explicitly identified
                    # operations. Function names provide the decisive evidence.
                    before = fixture("ValueError", "operation unavailable",
                                     location="decode_payload" if index == 2 else "authenticate")
                    after = fixture("ValueError", "operation unavailable",
                                    location="validate_schema" if index == 2 else "read_storage")
                    tags.append("same_message_different_operation")
            elif kind == "insufficient":
                if index % 2:
                    before = fixture(error, message, multi=True)
                    after = fixture(other_error, other_message, multi=True)
                    tags.append("mixed_failures")
                else:
                    tags.append("incomplete_record")
            records = []
            for side, source in (("before", before), ("after", after)):
                (workspace / "test_case.py").write_text(source, encoding="utf-8")
                output = workspace / (side + ".jsonl")
                env = dict(os.environ, PYTHONPATH=str(ROOT), PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
                           PYTHONDONTWRITEBYTECODE="1")
                command = [sys.executable, "-m", "pytest", "-q", "--tb=short", "-p", "no:cacheprovider",
                           "-p", "evidence_selector.ratchet.pytest_reporter", "--ratchet-task", case_id,
                           "--ratchet-output", str(output)]
                result = subprocess.run(command, cwd=workspace, env=env, capture_output=True,
                                        text=True, timeout=30)
                if result.returncode != 1:
                    raise RuntimeError(f"unexpected fixture exit for {case_id}/{side}: {result.returncode}")
                events = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
                for event in events:
                    event["run_id"] = case_id + "-" + side
                    if "root" in event:
                        event["root"] = "authored/" + family
                    for key in ("duration", "duration_seconds"):
                        if key in event:
                            event[key] = 0
                    if "longrepr" in event:
                        event["longrepr"] = event["longrepr"].replace(str(workspace), "<WORKSPACE>")
                if kind == "insufficient" and index % 2 == 0 and side == "after":
                    events = events[:-1]
                records.append(events)
            label = {"same": "same_blocker", "different": "different_blocker",
                     "insufficient": "insufficient_evidence"}[kind]
            cases.append({"id": case_id, "family": family, "tags": tags, "retry_intent": intent,
                          "authored_sources": {"before": before, "after": after},
                          "records": records, "author_label": label,
                          "author_advisory_eligible": False,
                          "advisory_reason": "Only two attempts; retry intent is justified or unknown."})
            print(case_id, flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema": 1, "split": "development", "status": "UNREVIEWED",
        "provenance": "Authored fixtures executed with pytest 8.4.2; no production agent traces.",
        "normalization": "Run IDs and roots replaced, timing zeroed, workspace path replaced. Even-index incomplete cases omit finish intentionally; raw originals remain private.",
        "cases": cases}, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
