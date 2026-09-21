"""Describe all assigned repair trials; never rescore or repair frozen gates."""
import argparse
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path

from ratchet_workflow_metrics import METHODS, TASKS, assess, schedule


def measured(values, coverage=None):
    """Retain missing measurements instead of silently treating them as zero."""
    known = [v for v in values if v is not None]
    coverage = [True] * len(values) if coverage is None else coverage
    complete_runs = sum(v is not None and covered for v, covered in zip(values, coverage))
    return {"observed_sum": sum(known), "reported_runs": len(known), "known_runs": complete_runs,
            "unknown_runs": len(values) - complete_runs,
            "complete_sum": sum(known) if complete_runs == len(values) else None}


def group_summary(rows):
    costs = [r["total_cost"] for r in rows]
    cost_known = all(c["lower_usd"] is not None and c["upper_usd"] is not None for c in costs)
    usage = {key: measured([(r.get("worker_usage") or {}).get(key) for r in rows])
             for key in ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens",
                         "reasoning_output_tokens")}
    total, cached = usage["input_tokens"]["complete_sum"], usage["cached_input_tokens"]["complete_sum"]
    selectors = [r.get("selector") or {} for r in rows]
    selector_coverage = [s.get("status") in ("COMPLETE", "NOT_USED") for s in selectors]
    selector = {key: measured([s.get(key) for s in selectors], selector_coverage)
                for key in ("tool_calls", "tool_elapsed_ms", "provider_calls", "provider_input_tokens",
                            "provider_output_tokens", "provider_latency_ms", "provider_errors", "provider_retries",
                            "estimated_cost_usd")}
    penalties = [r.get("latency_kind") == "600_second_penalty_unknown_duration" for r in rows]
    return {"assigned_runs": len(rows), "quality_passes": sum(r["quality_pass"] for r in rows),
            "method_passes": sum(r["method_compliance"] for r in rows),
            "latency_median_seconds_including_penalties": statistics.median(r["elapsed_seconds"] for r in rows),
            "latency_total_seconds_including_penalties": sum(r["elapsed_seconds"] for r in rows),
            "latency_penalty_slots": [r["index"] for r, penalty in zip(rows, penalties) if penalty],
            "observed_elapsed_seconds": measured([None if penalty else r["elapsed_seconds"] for r, penalty in zip(rows, penalties)]),
            "full_cost_known_runs": sum(c["lower_usd"] is not None and c["upper_usd"] is not None for c in costs),
            "full_cost_median_lower_usd": statistics.median(c["lower_usd"] for c in costs) if cost_known else None,
            "full_cost_median_upper_usd": statistics.median(c["upper_usd"] for c in costs) if cost_known else None,
            "full_cost_lower": measured([c["lower_usd"] for c in costs]),
            "full_cost_upper": measured([c["upper_usd"] for c in costs]),
            "worker_tokens": usage, "cache_read_fraction": cached / total if cached is not None and total else None,
            "selector": selector, "selector_status_counts": dict(Counter(s.get("status", "MISSING") for s in selectors)),
            "observed_test_commands": measured([r.get("observed_test_commands") for r in rows]),
            "repeated_completed_commands": measured([r.get("repeated_completed_commands") for r in rows]),
            "grading_seconds_outside_worker_timer": measured([r["grading"].get("elapsed_seconds") for r in rows]),
            "worker_retry_count": None,
            "worker_retry_count_status": "NOT_EXPOSED_BY_CLI",
            "worker_retry_notice_events": measured([(r.get("worker_transport") or {}).get("retry_notice_events") for r in rows]),
            "worker_retry_notice_stderr_lines": measured([(r.get("worker_transport") or {}).get("retry_notice_stderr_lines") for r in rows])}


def summarize(raw):
    receipt = json.loads(raw)
    if receipt["status"] != "COMPLETE" or receipt.get("pending"):
        raise ValueError("wait for every assigned run and final accounting")
    rows = receipt["trials"]
    expected = schedule()
    if len(rows) != len(expected) or any(any(r[k] != s[k] for k in s) for r, s in zip(rows, expected)):
        raise ValueError("receipt is not the exact complete frozen schedule")
    assessment = assess(rows)
    if assessment != receipt["assessment"]:
        raise ValueError("stored assessment differs from the frozen assessor")
    groups = [{"task": task, "method": method, **group_summary(
        [r for r in rows if r["task"] == task and r["method"] == method])} for task in TASKS for method in METHODS]
    return {"scope": "descriptive summary of all 45 original assigned positions; amended exploratory run",
            "source_receipt_sha256": hashlib.sha256(raw).hexdigest(),
            "freeze_commit": receipt["freeze_commit"], "freeze_sha256": receipt["freeze_sha256"],
            "execution_amendment": receipt["execution_amendment"],
            "assigned_runs": len(rows), "excluded_runs": 0,
            "quality_failed_slots": [r["index"] for r in rows if not r["quality_pass"]],
            "method_failed_slots": [r["index"] for r in rows if not r["method_compliance"]],
            "unknown_full_cost_slots": [r["index"] for r in rows if any(v is None for v in r["total_cost"].values())],
            "per_task_method": groups,
            "per_method": [{"method": method, **group_summary([r for r in rows if r["method"] == method])} for method in METHODS],
            "all_runs": group_summary(rows), "frozen_assessment": assessment,
            "history_recording_seconds_outside_worker_timer": receipt["history"]["setup_seconds"],
            "cost_kind": "API-equivalent estimate at frozen declared rates, not subscription billing",
            "interpretation": "No filtering or advisory promotion. Unknown costs remain unknown; observed subtotals are not complete totals.",
            "source_rows_modified": False, "gate_adjustment": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.receipt.read_bytes())
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"assigned_runs": result["assigned_runs"], "excluded_runs": 0,
                      "quality_failed_slots": result["quality_failed_slots"],
                      "method_failed_slots": result["method_failed_slots"],
                      "unknown_full_cost_slots": result["unknown_full_cost_slots"]}))
