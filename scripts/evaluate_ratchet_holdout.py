"""Score each frozen holdout method once, with no prompt or threshold search."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evidence_selector.cli import load_env
from evidence_selector.ratchet.records import compare, parse_run
from evidence_selector.ratchet.semantic import JevChoice, compare_with_jev


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mandatory_inputs():
    return {p.relative_to(ROOT).as_posix() for p in (ROOT / "evidence_selector").rglob("*.py")} | {
        "fixtures/ratchet/holdout-v1/corpus.json", "fixtures/ratchet/holdout-v1/review.json",
        "fixtures/ratchet/holdout-v1/independent-review.json", "fixtures/ratchet/holdout-v1/review-input.json",
        "fixtures/ratchet/holdout-v1/review-map.json", "docs/ratchet-plan.md",
        "docs/ratchet-holdout-protocol.md", "scripts/build_ratchet_holdout.py",
        "scripts/evaluate_ratchet_holdout.py", "pyproject.toml", "uv.lock"}


def validate_freeze(path):
    canonical = ROOT / "fixtures/ratchet/holdout-v1/freeze.json"
    if path.resolve() != canonical.resolve():
        raise ValueError("use the canonical committed freeze")
    freeze = json.loads(path.read_text(encoding="utf-8"))
    if (freeze["status"] != "FROZEN_BEFORE_SCORING" or freeze["threshold"] != .9
        or freeze["model"] != "jev-1.13.0" or freeze["checkpoint"] != "b60386f"
        or freeze["corpus"] != "fixtures/ratchet/holdout-v1/corpus.json"
        or freeze["review"] != "fixtures/ratchet/holdout-v1/review.json"
        or not mandatory_inputs().issubset(freeze["sha256"])):
        raise ValueError("incomplete or altered freeze declaration")
    for name, expected in freeze["sha256"].items():
        source = (ROOT / name).resolve()
        if not source.is_relative_to(ROOT) or sha(source) != expected:
            raise ValueError("frozen input changed: " + name)
    for name in ("records.py", "semantic.py", "pytest_reporter.py"):
        relative = "evidence_selector/ratchet/" + name
        original = subprocess.check_output(["git", "-C", str(ROOT), "show", "b60386f:" + relative])
        if original != (ROOT / relative).read_bytes():
            raise ValueError("comparator or reporter changed after predeclaration")
    relative = canonical.relative_to(ROOT).as_posix()
    history = subprocess.check_output(["git", "-C", str(ROOT), "log", "--reverse", "--format=%H", "--", relative], text=True).splitlines()
    if not history:
        raise ValueError("freeze must be committed before scoring")
    committed = subprocess.check_output(["git", "-C", str(ROOT), "show", history[0] + ":" + relative])
    if committed != path.read_bytes():
        raise ValueError("freeze differs from its first committed version")
    for name, expected in freeze["sha256"].items():
        committed_input = subprocess.check_output(["git", "-C", str(ROOT), "show", history[0] + ":" + name])
        if hashlib.sha256(committed_input).hexdigest() != expected:
            raise ValueError("input not frozen in the first freeze commit: " + name)
    return freeze, history[0]


def atomic_save(path, result):
    staged = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as stream:
            staged = Path(stream.name)
            stream.write(json.dumps(result, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staged, path)
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


def incremental(rows, baseline):
    current = {r["id"]: r for r in rows}
    prior = {r["id"]: r for r in baseline}
    if set(current) != set(prior):
        raise ValueError("incremental comparison requires identical complete coverage")
    recovered, added_false = [], []
    for key, row in current.items():
        if row["expected"] != prior[key]["expected"]:
            raise ValueError("incremental comparison labels differ")
        if row["relationship"] == "same_blocker" and prior[key]["relationship"] != "same_blocker":
            (recovered if row["expected"] == "same_blocker" else added_false).append(key)
    return {"new_correct_same": recovered, "added_false_same": added_false,
            "incremental_semantic_gate": len(recovered) >= 3 and not added_false,
            "note": "Incremental recovery alone does not pass classification, advisory, or workflow gates"}


def complete_coverage(status, rows, expected_ids):
    return (status == "COMPLETE" and len(rows) == len(expected_ids)
            and {r["id"] for r in rows} == set(expected_ids))


def wilson(successes, total):
    if not total:
        return None
    z = 1.959963984540054
    rate = successes / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    half = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total)) / denominator
    return [max(0, center - half), min(1, center + half)]


def metrics(rows):
    actual = sum(r["expected"] == "same_blocker" for r in rows)
    predicted = sum(r["relationship"] == "same_blocker" for r in rows)
    correct = sum(r["expected"] == r["relationship"] == "same_blocker" for r in rows)
    false_critical = sum(r["critical"] and r["expected"] != "same_blocker"
                         and r["relationship"] == "same_blocker" for r in rows)
    precision = correct / predicted if predicted else None
    recall = correct / actual if actual else None
    return {"cases": len(rows), "expected_distribution": dict(Counter(r["expected"] for r in rows)),
            "same_predictions": predicted, "true_same": correct, "false_same": predicted - correct,
            "actual_same": actual, "same_precision": precision, "same_recall": recall,
            "precision_wilson_95": wilson(correct, predicted), "recall_wilson_95": wilson(correct, actual),
            "critical_false_same": false_critical,
            "all_label_accuracy": sum(r["expected"] == r["relationship"] for r in rows) / len(rows) if rows else None,
            "classification_gate": precision is not None and precision >= .95
                                   and recall is not None and recall >= .7 and false_critical == 0}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--freeze", type=Path, required=True)
    p.add_argument("--method", choices=("exact", "deterministic", "jev"), required=True)
    p.add_argument("--env-file")
    p.add_argument("--allow-hosted", action="store_true")
    p.add_argument("--reproduce-to", type=Path, help="Separate receipt directory outside this checkout; never overwrites the original scored experiment")
    args = p.parse_args()
    setup_start = time.perf_counter()
    try:
        freeze, freeze_commit = validate_freeze(args.freeze)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        p.error(str(exc))
    corpus = json.loads((ROOT / freeze["corpus"]).read_text(encoding="utf-8"))
    review = json.loads((ROOT / freeze["review"]).read_text(encoding="utf-8"))
    if (corpus["split"] != "holdout" or review["status"] != "ACCEPTED"
        or review["corpus_sha256"] != sha(ROOT / freeze["corpus"])
        or set(review["accepted_labels"]) != {c["id"] for c in corpus["cases"]}):
        p.error("review does not cover the exact holdout")
    if args.method == "jev" and not args.allow_hosted:
        p.error("--allow-hosted required for public failure-text upload")
    if args.env_file and args.method == "jev":
        load_env(args.env_file)
    receipt_root = ROOT / "results/ratchet/holdout-v1"
    if args.reproduce_to:
        receipt_root = args.reproduce_to.resolve()
        if receipt_root.is_relative_to(ROOT):
            p.error("reproduction receipts must be outside this checkout")
    output = receipt_root / (args.method + ".json")
    output.parent.mkdir(parents=True, exist_ok=True)
    baseline = None
    for other in output.parent.glob("*.json"):
        previous = json.loads(other.read_text(encoding="utf-8"))
        if previous.get("freeze_sha256") != sha(args.freeze):
            p.error("prior receipt belongs to a different freeze")
    if args.method == "jev":
        baseline = json.loads((output.parent / "deterministic.json").read_text(encoding="utf-8"))
        if (baseline["status"] != "COMPLETE" or not baseline["complete_corpus_evaluated"]
            or {r["id"] for r in baseline["rows"]} != {c["id"] for c in corpus["cases"]}):
            p.error("complete frozen deterministic baseline required first")
    result = {"status": "IN_PROGRESS", "method": args.method, "split": "holdout",
              "run_purpose": "REPRODUCTION" if args.reproduce_to else "ORIGINAL_FROZEN_EXPERIMENT",
              "started_utc": datetime.now(timezone.utc).isoformat(), "freeze_sha256": sha(args.freeze),
              "freeze_commit": freeze_commit,
              "threshold": .9 if args.method == "jev" else None, "model": "Jev 1.13.0" if args.method == "jev" else None,
              "provenance": corpus["provenance"], "rows": [], "retries": 0,
              "advisory_gate": "NOT_EVALUATED_TWO_ATTEMPT_PAIRS", "workflow_gate": "NOT_EVALUATED",
              "cost_estimate": None, "cache_usage": "NOT_REPORTED_BY_PROVIDER",
              "uncertainty_scope": "Wilson intervals summarize pair counts; correlated scenarios and purposive sampling prevent population-level reliability claims",
              "setup_validation_ms": (time.perf_counter() - setup_start) * 1000}
    # Claim the fixed method receipt before any inference; a second run cannot
    # silently replace it or use a different filename to hide earlier scores.
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    def save():
        atomic_save(output, result)
    experiment_start = time.perf_counter()
    try:
        provider = JevChoice(allow_hosted=True) if args.method == "jev" else None
        for case in corpus["cases"]:
            started = time.perf_counter()
            runs = [parse_run(("\n".join(json.dumps(e) for e in events) + "\n").encode()) for events in case["records"]]
            answer = compare_with_jev(*runs, provider, threshold=.9) if provider else compare(*runs, explicit_chains=args.method != "exact")
            row = {"id": case["id"], "expected": review["accepted_labels"][case["id"]]["relationship"],
                   "critical": bool(set(case["tags"]) & {"productive_progress", "identical_message_different_constraint", "mixed_failures", "incomplete_record"}),
                   **answer, "selector_elapsed_ms": (time.perf_counter() - started) * 1000}
            result["rows"].append(row)
            save()
            print(json.dumps({"id": row["id"], "relationship": row["relationship"], "reason": row["reason"]}), flush=True)
            if row.get("error") in ("http_401", "http_403", "http_429", "http_529"):
                result["status"] = "STOPPED_PROVIDER_ERROR"
                break
        else:
            result["status"] = "COMPLETE"
    except Exception as exc:
        # Do not emit arbitrary provider/configuration text, which can contain
        # local paths or credentials. Preserve all prior rows and stop.
        result.update(status="STOPPED_EXECUTION_ERROR", error_type=type(exc).__name__)
    result.update(elapsed_ms=(time.perf_counter() - experiment_start) * 1000,
                  metrics=metrics(result["rows"]),
                  provider_calls=sum(r.get("provider_calls", 0) for r in result["rows"]),
                  provider_errors=sum("error" in r for r in result["rows"]),
                  provider_latency_ms=sum(r.get("provider_latency_ms", 0) for r in result["rows"]),
                  provider_usage={key: sum(r.get("decision", {}).get("usage", {}).get(key, 0) for r in result["rows"])
                                  for key in ("input_tokens", "output_tokens")})
    if args.method == "jev":
        unresolved = [r for r in result["rows"] if r.get("provider_calls")]
        result["unresolved_subset_metrics"] = metrics(unresolved)
        del result["unresolved_subset_metrics"]["classification_gate"]
    result["complete_corpus_evaluated"] = complete_coverage(result["status"], result["rows"], [c["id"] for c in corpus["cases"]])
    if not result["complete_corpus_evaluated"]:
        result["metrics"]["classification_gate"] = False
    if baseline is not None and result["complete_corpus_evaluated"]:
        result["incremental_comparison"] = incremental(result["rows"], baseline["rows"])
    save()
    print(json.dumps({k: result[k] for k in ("status", "metrics", "provider_calls", "provider_errors")}, indent=2))
    return 0 if result["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
