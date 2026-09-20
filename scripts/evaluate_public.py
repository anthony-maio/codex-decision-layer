"""Replay frozen public cases, or diagnose Eve on development only."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from evidence_selector.benchmark import PROMPTS, replay, summarize
from evidence_selector.cli import load_env
from evidence_selector.providers import HttpProvider

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "holdout"], default="dev")
    parser.add_argument("--method", choices=["retain-all", "lexical", "bm25", "jev", "fp32", "q8"], required=True)
    parser.add_argument("--env-file")
    parser.add_argument("--endpoint")
    parser.add_argument("--diagnose", action="store_true")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("Output already exists; preserve previous receipts")
    if args.diagnose and (args.split != "dev" or args.method not in ("fp32", "q8")):
        parser.error("Diagnosis is restricted to local Eve development runs")
    manifest = json.loads((ROOT / "fixtures/public/frozen.json").read_text())
    for file, expected in manifest["sha256"].items():
        if hashlib.sha256((ROOT / file).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Frozen evaluation input changed: {file}")
    if args.env_file:
        load_env(args.env_file)
    provider = None
    if args.method == "jev":
        provider = HttpProvider("typesafe")
    if args.method in ("fp32", "q8"):
        provider = HttpProvider("eve", args.endpoint or ("http://127.0.0.1:8765/v1/systemone" if args.method == "fp32" else "http://127.0.0.1:8767/v1/systemone"), model="eve-local" if args.method == "fp32" else "eve-q8_0")
    data = json.loads((ROOT / f"fixtures/public/{args.split}.json").read_text())
    result = replay(data, args.method, provider)
    if args.diagnose:
        variants = [result] + [replay(data, args.method, provider, p) for p in (1, 2)]
        grid = []
        for variant in variants:
            for threshold in (.1, .2, .3, .4, .5):
                rows = copy.deepcopy(variant["cases"])
                for case, row in zip(data["cases"], rows):
                    kept = {d["id"] for d in row["decisions"] if d["probability"] is None or d["probability"] >= threshold}
                    relevant = {k for k,v in case["labels"].items() if v}
                    row.update(retained_relevant=len(relevant & kept), retained=len(kept),
                               missed_relevant_ids=sorted(relevant-kept), missed_critical_ids=sorted(set(case["critical_ids"])-kept),
                               missed_contradiction_ids=sorted(set(case["contradiction_ids"])-kept),
                               proposed_evidence_bytes=sum(len(c["text"].encode()) for c in case["candidates"] if c["id"] in kept))
                summary = summarize(rows)
                eligible = summary["missed_relevant"] == 0 and all(summary["gates"].values())
                grid.append({"prompt_index": variant["prompt_index"], "threshold": threshold, "eligible": eligible, "summary": summary})
        eligible = sorted([v for v in grid if v["eligible"]], key=lambda v: (-v["summary"]["byte_reduction"], v["threshold"], v["prompt_index"]))
        result = {"variants": variants, "grid": grid, "selected": eligible[0] if eligible else {"prompt_index": 0, "threshold": .1, "reason": "No development variant passed all improvement criteria"}}
    result.update(split=args.split, frozen_manifest_sha256=hashlib.sha256((ROOT / "fixtures/public/frozen.json").read_bytes()).hexdigest())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.get("summary", result.get("selected")), indent=2))


if __name__ == "__main__":
    main()
