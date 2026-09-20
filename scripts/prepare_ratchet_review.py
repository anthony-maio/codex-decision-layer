"""Prepare shuffled label-free inputs for an independent corpus review."""
import argparse
import hashlib
import json
from pathlib import Path
import random


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    raw = args.corpus.read_bytes()
    corpus = json.loads(raw)
    cases = list(corpus["cases"])
    random.Random(73183).shuffle(cases)
    review = []
    for i, case in enumerate(cases):
        identity = f"pair-{i+1:02}"
        records = json.loads(json.dumps(case["records"]))
        for side, events in enumerate(records):
            for event in events:
                event["run_id"] = f"{identity}-{side}"
                if "task" in event:
                    event["task"] = identity
                if "root" in event:
                    event["root"] = "authored-repository"
        review.append({"id": identity, "records": records,
                       "retry_intent": case["retry_intent"], "available_attempts": 2})
    args.output.write_text(json.dumps({"corpus_sha256": hashlib.sha256(raw).hexdigest(),
        "provenance": corpus["provenance"], "cases": review}, indent=2) + "\n", encoding="utf-8", newline="\n")
    # Mapping is distinct from the review input; reviewers receive only output.
    mapping = {f"pair-{i+1:02}": case["id"] for i, case in enumerate(cases)}
    args.output.with_suffix(".mapping.json").write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
