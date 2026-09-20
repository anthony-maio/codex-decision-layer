"""Validate runner evidence before making a narrowly scoped comparison."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re


@dataclass(frozen=True)
class Run:
    digest: str
    root: str
    run_id: str
    reports: tuple[dict, ...]
    exit_code: int | None
    complete: bool
    task: str
    options: tuple[str, ...]
    selection: tuple[str, ...]

    @property
    def failures(self):
        return tuple(r for r in self.reports if r["outcome"] == "failed")


def read_run(path: Path) -> Run:
    raw = path.read_bytes()
    if len(raw) > 8_000_000:
        raise ValueError("record_too_large")
    try:
        events = [json.loads(line) for line in raw.splitlines()]
        start = events[0]
        if start["kind"] != "start" or start["schema"] != 1 or start["runner"] != "pytest":
            raise ValueError("invalid_start")
        if not isinstance(start["root"], str) or not isinstance(start["run_id"], str):
            raise ValueError("invalid_identity")
        if not isinstance(start["task"], str) or not start["task"]:
            raise ValueError("missing_task")
        if not isinstance(start["options"], list) or not all(isinstance(a, str) for a in start["options"]):
            raise ValueError("invalid_options")
        reports = []
        seen_reports = set()
        stages = {}
        selection = None
        finish = None
        for event in events[1:]:
            if event["run_id"] != start["run_id"] or finish is not None:
                raise ValueError("mixed_or_trailing_records")
            if event["kind"] == "finish":
                if type(event["exit_code"]) is not int or event["exit_code"] not in range(6):
                    raise ValueError("invalid_exit_code")
                if type(event["collected"]) is not int or event["collected"] < 0:
                    raise ValueError("invalid_collected_count")
                finish = event
            elif event["kind"] == "selection":
                if selection is not None or reports and any(r["stage"] != "collection" for r in reports):
                    raise ValueError("invalid_selection_order")
                selection = event["nodeids"]
                if not isinstance(selection, list) or not all(isinstance(n, str) for n in selection):
                    raise ValueError("invalid_selection")
                if len(set(selection)) != len(selection):
                    raise ValueError("duplicate_selection")
            elif event["kind"] == "report":
                if event["stage"] not in ("collection", "setup", "call", "teardown"):
                    raise ValueError("invalid_stage")
                if event["outcome"] not in ("passed", "failed", "skipped"):
                    raise ValueError("invalid_outcome")
                if not isinstance(event["nodeid"], str) or not isinstance(event["longrepr"], str):
                    raise ValueError("invalid_report")
                identity = (event["nodeid"], event["stage"])
                if identity in seen_reports:
                    raise ValueError("duplicate_report")
                seen_reports.add(identity)
                if event["stage"] != "collection":
                    if selection is None or event["nodeid"] not in selection:
                        raise ValueError("unselected_test")
                    prior = stages.setdefault(event["nodeid"], [])
                    stage = event["stage"]
                    if ((stage == "setup" and prior) or
                        (stage == "call" and prior != [("setup", "passed")]) or
                        (stage == "teardown" and (not prior or prior[-1][0] == "teardown"))):
                        raise ValueError("invalid_stage_sequence")
                    if stage == "teardown" and prior == [("setup", "passed")]:
                        raise ValueError("missing_call_report")
                    prior.append((stage, event["outcome"]))
                reports.append(event)
            else:
                raise ValueError("unknown_event")
        setup = {r["nodeid"] for r in reports if r["stage"] == "setup"}
        teardown = {r["nodeid"] for r in reports if r["stage"] == "teardown"}
        # A finish hook also runs after Ctrl-C and --maxfail. Those are not full
        # executions. Collection failures remain unsupported in this baseline.
        complete = bool(finish and finish["exit_code"] in (0, 1)
                        and selection is not None and set(selection) == setup == teardown
                        and len(setup) == finish["collected"]
                        and not any(r["stage"] == "collection" for r in reports))
        return Run(hashlib.sha256(raw).hexdigest(), start["root"], start["run_id"],
                   tuple(reports), finish["exit_code"] if finish else None, complete,
                   start["task"], tuple(start["options"]), tuple(selection or []))
    except (KeyError, TypeError, IndexError, json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("invalid_record") from exc


def failure_signature(report):
    # Terminal messages alone collide across different causes. Require the full
    # observed traceback and source context too; changed origins remain unresolved.
    # This identifies matching observed failures, not proof of an ultimate cause.
    lines = [line.strip() for line in report["longrepr"].splitlines() if line.strip()]
    errors = [re.sub(r"^E\s+", "", line) for line in lines if re.match(r"^E\s+", line)]
    if not errors:
        return None
    return report["stage"], report["nodeid"], tuple(errors), report["longrepr"]


def explicit_cause_signature(report):
    """Recognize short tracebacks with explicit cause chains conservatively.

    Preserve the innermost operation, source statement, and exception evidence.
    Implicit context chains or unknown formatting abstain rather than guessing.
    """
    text = report["longrepr"]
    if "During handling of the above exception" in text:
        return None
    first = text.split("The above exception was the direct cause of the following exception:")[0]
    lines = first.splitlines()
    frames = [i for i, line in enumerate(lines) if re.match(r"^.+:\d+: in \w+\s*$", line)]
    if not frames:
        return None
    terminal = [line.rstrip() for line in lines[frames[-1]:] if line.strip()]
    if not any(re.match(r"^E\s+", line) for line in terminal):
        return None
    return report["stage"], report["nodeid"], tuple(terminal)


def compare(previous: Run, current: Run, *, explicit_chains=True) -> dict:
    result = {"relationship": "insufficient_evidence", "method": "deterministic",
              "reason": "unsupported_or_incomplete", "evidence": [previous.digest, current.digest],
              "advisory": None}
    if previous.digest == current.digest or previous.run_id == current.run_id:
        result["reason"] = "duplicate_run"
        return result
    if previous.root != current.root:
        result["reason"] = "different_repository"
        return result
    if previous.task != current.task or previous.options != current.options or previous.selection != current.selection:
        result["reason"] = "different_task_or_selection"
        return result
    if not previous.complete or not current.complete:
        return result
    if current.exit_code == 0 and not current.failures:
        result.update(relationship="different_blocker", reason="current_run_passed")
        return result
    if previous.exit_code not in (1, 2) or current.exit_code not in (1, 2):
        return result
    old, new = previous.failures, current.failures
    if len(old) != 1 or len(new) != 1:
        result["reason"] = "multiple_or_missing_failures"
        return result
    before, after = old[0], new[0]
    if before["nodeid"] != after["nodeid"]:
        result["reason"] = "different_test_scope"
        return result
    order = {"collection": 0, "setup": 1, "call": 2, "teardown": 3}
    if before["stage"] != after["stage"]:
        result.update(relationship="different_blocker",
                      reason="execution_advanced" if order[after["stage"]] > order[before["stage"]]
                      else "execution_regressed")
        return result
    signature = failure_signature(before)
    if signature and signature == failure_signature(after):
        result.update(relationship="same_blocker", reason="matching_failure_signature")
    elif explicit_chains and (cause := explicit_cause_signature(before)) and cause == explicit_cause_signature(after):
        result.update(relationship="same_blocker", reason="matching_explicit_cause")
    else:
        result["reason"] = "semantic_comparison_needed"
    # No warning yet: repeated evidence alone does not prove an unproductive
    # retry. Intervention policy must account for retry intent and cooldown.
    return result
