"""Publish bounded decision fields from hash-verified private workflow events."""
import argparse
import hashlib
import json
from pathlib import Path

from ratchet_workflow_metrics import schedule

ROOT = Path(__file__).resolve().parents[1]


def audit(raw, private):
    receipt = json.loads(raw)
    freeze_raw = (ROOT / "fixtures/ratchet/workflow-v1/freeze.json").read_bytes()
    if hashlib.sha256(freeze_raw).hexdigest() != receipt["freeze_sha256"]:
        raise ValueError("workflow freeze identity mismatch")
    history_raw = (ROOT / "results/ratchet/workflow-history.json").read_bytes()
    if hashlib.sha256(history_raw).hexdigest() != json.loads(freeze_raw)["sha256"]["results/ratchet/workflow-history.json"]:
        raise ValueError("frozen history receipt mismatch")
    if json.loads(history_raw) != receipt["history"]:
        raise ValueError("workflow history differs from frozen history")
    rows = receipt["trials"]
    if receipt["status"] != "COMPLETE" or receipt.get("pending") or len(rows) != 45:
        raise ValueError("require the completed workflow")
    if any(any(row[k] != slot[k] for k in slot) for row, slot in zip(rows, schedule())):
        raise ValueError("unexpected workflow schedule")
    observed = []
    for row in rows:
        expected = {r["record"]: r["record_sha256"] for r in receipt["history"]["records"] if r["task"] == row["task"]}
        calls = []
        if row["worker_events_sha256"] is not None:
            events = (private / f"slot-{row['index']:02d}/worker/events.jsonl").read_bytes()
            if hashlib.sha256(events).hexdigest() != row["worker_events_sha256"]:
                raise ValueError("worker events changed")
            for line in events.decode("utf-8").splitlines():
                event = json.loads(line)
                item = event.get("item", {})
                if (event.get("type") != "item.completed" or item.get("type") != "mcp_tool_call"
                        or item.get("server") != "ratchet_trial" or item.get("tool") != "ratchet_compare"):
                    continue
                result = item.get("result") or {}
                if item.get("status") != "completed" or item.get("error") or result.get("isError"):
                    calls.append({"status": "UNAVAILABLE"})
                    continue
                value = result.get("structured_content") or json.loads(result["content"][0]["text"])
                sources = {s["file"]: s["sha256"] for s in value["sources"]}
                if len(value["sources"]) != 2 or sources != expected:
                    raise ValueError("decision does not identify the expected original records")
                selected = {key: value.get(key) for key in ("mode", "relationship", "method", "reason", "advisory",
                            "provider_calls", "provider_latency_ms", "retries")}
                decision = value.get("decision")
                if decision is not None:
                    selected["decision"] = {key: decision[key] for key in
                        ("choice", "probabilities", "provider_confidence", "model", "usage")}
                calls.append({"status": "OBSERVED", "sources_sha256": sources, **selected})
        observed.append({"index": row["index"], "task": row["task"], "method": row["method"],
                         "worker_events_sha256": row["worker_events_sha256"], "comparisons": calls})
    return {"scope": "observed shadow decisions from all assigned workers; no new classifier calls or changed gates",
            "source_receipt_sha256": hashlib.sha256(raw).hexdigest(), "rows": observed}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.receipt.read_bytes(), args.private_dir)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"assigned_workers": len(result["rows"]),
                      "observed_comparisons": sum(len(row["comparisons"]) for row in result["rows"])}))
