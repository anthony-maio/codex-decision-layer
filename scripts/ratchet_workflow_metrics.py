"""Conservative usage bounds and complete-coverage matched workflow gates."""
from __future__ import annotations
import math
import statistics

METHODS = ("plain", "deterministic", "jev")
TASKS = ("invoice", "queue", "events")


def worker_cost(usage):
    if usage is None:
        return {"lower_usd": None, "upper_usd": None, "status": "MISSING_USAGE"}
    names = ("input_tokens", "cached_input_tokens", "output_tokens")
    if any(type(usage.get(k)) is not int or usage[k] < 0 for k in names):
        raise ValueError("invalid usage counters")
    total, cached, output = (usage[k] for k in names)
    written = usage.get("cache_write_input_tokens")
    if cached > total or (written is not None and
            (type(written) is not int or written < 0 or cached + written > total)):
        raise ValueError("invalid cache partition")
    low_written, high_written = (0, total - cached) if written is None else (written, written)
    low_input = (total - cached - low_written) * 4 + cached * .4 + low_written * 5
    high_input = (total - cached - high_written) * 4 + cached * .4 + high_written * 5
    low = (low_input + output * 20) / 1e6
    surcharge_possible = total > 272000
    high = (high_input * (2 if surcharge_possible else 1)
            + output * (30 if surcharge_possible else 20)) / 1e6
    return {"lower_usd": low, "upper_usd": high,
            "status": "BOUNDED" if surcharge_possible or written is None else "EXACT_AT_DECLARED_RATES",
            "cache_writes_reported": written is not None,
            "per_request_surcharge_unresolved": surcharge_possible,
            "kind": "API-equivalent estimate, not subscription billing"}


def schedule():
    # Across 15 consecutive triplets each method occupies each position five
    # times; all six permutations occur two or three times. Each task sees five
    # different permutations, reducing order confounding within a task.
    permutations = [
        ("plain", "deterministic", "jev"),
        ("deterministic", "jev", "plain"),
        ("jev", "plain", "deterministic"),
        ("plain", "jev", "deterministic"),
        ("jev", "deterministic", "plain"),
        ("deterministic", "plain", "jev"),
    ]
    # Latin rotations three times, reversed rotations twice.
    indexes = [0, 1, 2, 3, 4, 5, 1, 2, 0, 4, 5, 3, 2, 0, 1]
    return [{"index": i * 3 + j, "task": TASKS[i % 3], "replicate": i // 3,
             "method": method, "position": j, "triplet": i}
            for i, order in enumerate(indexes) for j, method in enumerate(permutations[order])]


def assess(rows):
    expected = {(s["task"], s["replicate"], s["method"]) for s in schedule()}
    actual = [(r["task"], r["replicate"], r["method"]) for r in rows]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("require exactly one result for all 45 assigned runs")
    for row in rows:
        latency = row["elapsed_seconds"]
        if type(latency) not in (int, float) or not math.isfinite(latency) or latency <= 0:
            raise ValueError("invalid latency")
        if type(row["quality_pass"]) is not bool:
            raise ValueError("invalid quality flag")
        passed = row["grading"]["passed"]
        if type(passed) is not int or passed < 0:
            raise ValueError("invalid grading count")
        lower, upper = (row["total_cost"][k] for k in ("lower_usd", "upper_usd"))
        for bound in (lower, upper):
            if bound is not None and (type(bound) not in (int, float)
                                       or not math.isfinite(bound) or bound < 0):
                raise ValueError("invalid cost bound")
        if lower is not None and upper is not None and lower > upper:
            raise ValueError("inverted cost bounds")
    groups = {}
    for task in TASKS:
        for method in METHODS:
            group = [r for r in rows if r["task"] == task and r["method"] == method]
            known = all(r["total_cost"]["lower_usd"] is not None and r["total_cost"]["upper_usd"] is not None for r in group)
            groups[(task, method)] = {
                "successes": sum(r["quality_pass"] is True for r in group),
                "passed_tests": sum(r["grading"]["passed"] for r in group),
                "latency": statistics.median(r["elapsed_seconds"] for r in group),
                "cost_lower": statistics.median(r["total_cost"]["lower_usd"] for r in group) if known else None,
                "cost_upper": statistics.median(r["total_cost"]["upper_usd"] for r in group) if known else None}
    comparisons = []
    for candidate, comparator in (("deterministic", "plain"), ("jev", "plain"), ("jev", "deterministic")):
        per_task = []
        for task in TASKS:
            a, b = groups[(task, candidate)], groups[(task, comparator)]
            quality = a["successes"] > 0 and a["successes"] >= b["successes"] and a["passed_tests"] >= b["passed_tests"]
            cost_ratio = (a["cost_upper"] / b["cost_lower"]
                          if a["cost_upper"] is not None and b["cost_lower"] is not None and b["cost_lower"] > 0 else None)
            per_task.append({"task": task, "quality_no_regression": quality,
                             "latency_ratio": a["latency"] / b["latency"],
                             "conservative_cost_ratio": cost_ratio})
        latency = math.exp(statistics.mean(math.log(r["latency_ratio"]) for r in per_task))
        cost = (math.prod(r["conservative_cost_ratio"] for r in per_task) ** (1 / 3)
                if all(r["conservative_cost_ratio"] is not None for r in per_task) else None)
        quality = all(r["quality_no_regression"] for r in per_task)
        tail = all(r["latency_ratio"] <= 1.2 for r in per_task)
        perf = cost is not None and ((latency <= .9 and cost <= 1) or (cost <= .9 and latency <= 1.1))
        comparisons.append({"candidate": candidate, "comparator": comparator, "tasks": per_task,
                            "latency_ratio": latency, "conservative_cost_ratio": cost,
                            "quality_gate": quality, "per_task_latency_gate": tail,
                            "performance_gate": perf, "usefulness_gate": quality and tail and perf})
    return {"status": "COMPLETE", "comparisons": comparisons,
            "jev_incremental_usefulness": all(r["usefulness_gate"] for r in comparisons if r["candidate"] == "jev"),
            "advisory_enabled": False}
