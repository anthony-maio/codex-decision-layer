"""Compare deterministic reproduction receipts without scoring again."""
import argparse
import hashlib
import json
from pathlib import Path
import platform

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--reproduction", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    checks = {}
    for method in ("exact", "deterministic"):
        original_path = ROOT / "results/ratchet/holdout-v1" / (method + ".json")
        reproduced_path = args.reproduction / (method + ".json")
        original = json.loads(original_path.read_text(encoding="utf-8"))
        reproduced = json.loads(reproduced_path.read_text(encoding="utf-8"))
        if (not all(d["status"] == "COMPLETE" and d["complete_corpus_evaluated"] for d in (original, reproduced))
            or original["freeze_sha256"] != reproduced["freeze_sha256"] or reproduced["provider_calls"] != 0):
            raise ValueError("incomplete or mismatched experiment")
        fields = ("id", "expected", "relationship", "reason", "evidence", "advisory")
        project = lambda result: [{key: row[key] for key in fields} for row in result["rows"]]
        if project(original) != project(reproduced) or original["metrics"] != reproduced["metrics"]:
            raise ValueError("reproduction differs")
        checks[method] = {"matched_cases": len(original["rows"]), "labels_reasons_evidence_and_metrics": "EXACT_MATCH",
                          "original_sha256": hashlib.sha256(original_path.read_bytes()).hexdigest(),
                          "reproduction_sha256": hashlib.sha256(reproduced_path.read_bytes()).hexdigest()}
    receipt = {"platform": platform.system(), "freeze_sha256": original["freeze_sha256"],
               "provider_calls": 0, "checks": checks, "scope": "Frozen corpus scoring on a second platform; no new pytest execution or Jev inference"}
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
