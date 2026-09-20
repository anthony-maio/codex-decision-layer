"""Evaluate independently reviewed development pairs; never scores a holdout."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evidence_selector.cli import load_env
from evidence_selector.ratchet.records import compare, read_run
from evidence_selector.ratchet.semantic import JevChoice, compare_with_jev


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(rows, threshold=None):
    predicted = []
    for row in rows:
        label = row["relationship"]
        if threshold is not None and "decision" in row:
            decision = row["decision"]
            label = decision["choice"] if decision["probabilities"][decision["choice"]] >= threshold else "insufficient_evidence"
        predicted.append(label)
    positives = sum(label == "same_blocker" for label in predicted)
    actual = sum(row["expected"] == "same_blocker" for row in rows)
    correct = sum(label == "same_blocker" and row["expected"] == "same_blocker" for label, row in zip(predicted, rows))
    precision = correct / positives if positives else None
    recall = correct / actual if actual else None
    return {"cases": len(rows), "same_predictions": positives, "true_same": correct,
            "false_same": positives - correct, "actual_same": actual,
            "same_precision": precision, "same_recall": recall,
            "all_label_accuracy": sum(label == row["expected"] for label, row in zip(predicted, rows)) / len(rows) if rows else None,
            "classification_gate": precision is not None and precision >= .95 and recall is not None and recall >= .7}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--method", choices=("exact", "deterministic", "jev"), required=True)
    parser.add_argument("--env-file")
    parser.add_argument("--allow-hosted", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; preserve prior experiments")
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    review = json.loads(args.review.read_text(encoding="utf-8"))
    if corpus["split"] != "development" or review["status"] != "ACCEPTED":
        parser.error("only independently reviewed development data may be scored here")
    if review["corpus_sha256"] != digest(args.corpus):
        parser.error("corpus changed since independent review")
    if args.method == "jev" and not args.allow_hosted:
        parser.error("--allow-hosted is required to upload authored failure evidence")
    if args.env_file and args.method == "jev":
        load_env(args.env_file)
    provider = JevChoice(allow_hosted=args.allow_hosted) if args.method == "jev" else None
    result = {"status": "IN_PROGRESS", "split": "development", "method": args.method,
              "corpus_sha256": digest(args.corpus), "review_sha256": digest(args.review),
              "implementation_sha256": {name: digest(ROOT / name) for name in (
                  "evidence_selector/ratchet/records.py", "evidence_selector/ratchet/semantic.py",
                  "docs/ratchet-development-evaluation.md", "scripts/evaluate_ratchet_dev.py")},
              "provenance": corpus["provenance"], "rows": [], "advisory_gate": "NOT_EVALUATED",
              "workflow_gate": "NOT_EVALUATED", "retries": 0}
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")

    with tempfile.TemporaryDirectory() as temp:
        for case in corpus["cases"]:
            runs = []
            for side, events in enumerate(case["records"]):
                path = Path(temp) / f"{side}.jsonl"
                path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8", newline="\n")
                runs.append(read_run(path))
            answer = compare_with_jev(*runs, provider) if provider else compare(*runs, explicit_chains=args.method != "exact")
            row = {"id": case["id"], "expected": review["accepted_labels"][case["id"]]["relationship"], **answer}
            result["rows"].append(row)
            save()
            print(json.dumps({"id": row["id"], "relationship": row["relationship"], "reason": row["reason"]}), flush=True)
            if row.get("error") in ("http_401", "http_403", "http_429", "http_529"):
                result["status"] = "STOPPED_PROVIDER_ERROR"
                save()
                return 2
    result.update(status="COMPLETE", metrics=metrics(result["rows"]),
                  provider_calls=sum(r.get("provider_calls", 0) for r in result["rows"]),
                  provider_latency_ms=sum(r.get("provider_latency_ms", 0) for r in result["rows"]),
                  provider_errors=sum("error" in r for r in result["rows"]))
    if provider:
        grid = {str(t): metrics(result["rows"], t) for t in (.6, .7, .8, .9)}
        eligible = [float(t) for t, m in grid.items() if m["classification_gate"]]
        result.update(threshold_grid=grid, selected_development_threshold=max(eligible) if eligible else None,
                      provider_usage={key: sum(r.get("decision", {}).get("usage", {}).get(key, 0) for r in result["rows"])
                                      for key in ("input_tokens", "output_tokens")})
    save()
    print(json.dumps({key: result[key] for key in ("metrics", "provider_calls", "provider_errors")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
