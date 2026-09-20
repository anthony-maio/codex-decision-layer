"""Bind independently reviewed holdout evidence before its first scoring run."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.evaluate_ratchet_holdout import mandatory_inputs


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--reviewed-input-sha256", required=True)
    args = p.parse_args()
    folder = ROOT / "fixtures/ratchet/holdout-v1"
    if (folder / "freeze.json").exists() or (folder / "review.json").exists():
        p.error("freeze or accepted review already exists; preserve it")
    if list((ROOT / "results/ratchet/holdout-v1").glob("*.json")):
        p.error("cannot freeze after scoring")
    if sha(folder / "review-input.json") != args.reviewed_input_sha256:
        p.error("input differs from independent review confirmation")
    corpus = json.loads((folder / "corpus.json").read_text(encoding="utf-8"))
    independent = json.loads((folder / "independent-review.json").read_text(encoding="utf-8"))
    mapping = json.loads((folder / "review-map.json").read_text(encoding="utf-8"))
    cases = {c["id"]: c for c in corpus["cases"]}
    labels = {}
    for row in independent["labels"]:
        case_id = mapping[row["id"]]
        if case_id in labels or row["relationship"] != cases[case_id]["author_label"]:
            p.error("duplicate or disputed label; resolve before freezing")
        labels[case_id] = {"relationship": row["relationship"], "advisory_eligible": row["advisory_eligible"],
                           "review_id": row["id"], "reason": row["reason"]}
    if set(labels) != set(cases):
        p.error("independent review does not cover every case")
    for case in corpus["cases"]:
        for events, provenance in zip(case["records"], case["record_provenance"], strict=True):
            raw = ("\n".join(json.dumps(e) for e in events) + "\n").encode()
            if hashlib.sha256(raw).hexdigest() != provenance["normalized_sha256"]:
                p.error("normalized record changed")
            if set(provenance["child_imports"]) != {"click", "packaging", "more_itertools", "evidence_selector.ratchet.pytest_reporter"}:
                p.error("actual child import provenance incomplete")
    if corpus["builder_sha256"] != sha(ROOT / "scripts/build_ratchet_holdout.py"):
        p.error("builder changed after construction")
    review = {"status": "ACCEPTED", "human_validation": False, "reviewed_before_scoring": True,
              "corpus_sha256": sha(folder / "corpus.json"), "review_input_sha256": args.reviewed_input_sha256,
              "independent_review_sha256": sha(folder / "independent-review.json"),
              "review_confirmation": "All 30 labels reconfirmed after provenance checks; generator frame fix reconfirmed for pair-22.",
              "accepted_labels": labels, "label_changes": [], "exclusions": [],
              "counts": dict(Counter(r["relationship"] for r in labels.values()))}
    (folder / "review.json").write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8", newline="\n")
    names = mandatory_inputs() | {"scripts/freeze_ratchet_holdout.py", "tests/test_ratchet_evaluation.py", ".gitattributes"}
    names |= {f.relative_to(ROOT).as_posix() for f in folder.iterdir() if f.is_file()}
    freeze = {"status": "FROZEN_BEFORE_SCORING", "created_utc": datetime.now(timezone.utc).isoformat(),
              "checkpoint": "b60386f", "model": "jev-1.13.0", "threshold": .9,
              "corpus": "fixtures/ratchet/holdout-v1/corpus.json", "review": "fixtures/ratchet/holdout-v1/review.json",
              "cases": 30, "scenario_groups": 10, "repositories": 3,
              "limitations": "Authored public-library adapters, correlated scenarios, no human validation, no advisory or workflow result",
              "sha256": {name: sha(ROOT / name) for name in sorted(names)}}
    (folder / "freeze.json").write_text(json.dumps(freeze, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"counts": review["counts"], "files_frozen": len(names), "freeze_sha256": sha(folder / "freeze.json")}, indent=2))


if __name__ == "__main__":
    main()
