"""Compare saved probabilities without making new model requests."""
import argparse
import json
from pathlib import Path
import statistics


def compare(reference, candidate):
    if reference["dataset_sha256"] != candidate["dataset_sha256"] or reference["prompt_version"] != candidate["prompt_version"] or reference["thresholds"] != candidate["thresholds"]:
        raise ValueError("Receipts must use identical inputs, prompts, and thresholds")
    a = {(c["case_id"], d["id"]): d for c in reference["cases"] for d in c["decisions"]}
    b = {(c["case_id"], d["id"]): d for c in candidate["cases"] for d in c["decisions"]}
    if set(a) != set(b) or any(d["probability"] is None or "error" in d for d in list(a.values()) + list(b.values())):
        raise ValueError("Comparison requires complete, error-free probabilities")
    differences = [abs(a[key]["probability"] - b[key]["probability"]) for key in a]
    return {"passages": len(a), "max_absolute_probability_delta": max(differences),
            "mean_absolute_probability_delta": statistics.mean(differences),
            "classification_flips_at_0_5": sum((a[k]["probability"] >= 0.5) != (b[k]["probability"] >= 0.5) for k in a),
            "retention_proposal_flips": sum(a[k]["proposal"] != b[k]["proposal"] for k in a)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("reference")
    parser.add_argument("candidate")
    parser.add_argument("--output")
    args = parser.parse_args()
    value = compare(json.loads(Path(args.reference).read_text()), json.loads(Path(args.candidate).read_text()))
    text = json.dumps(value, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(text)
    print(text)
