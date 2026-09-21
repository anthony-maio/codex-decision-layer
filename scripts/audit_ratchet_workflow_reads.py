"""Audit batched history reads without changing frozen workflow rows or gates."""
import argparse
import hashlib
import json
from pathlib import Path

from ratchet_atomic import atomic

ROOT = Path(__file__).resolve().parents[1]


def audit(receipt, private):
    freeze_raw = (ROOT / "fixtures/ratchet/workflow-v1/freeze.json").read_bytes()
    if hashlib.sha256(freeze_raw).hexdigest() != receipt["freeze_sha256"]:
        raise ValueError("workflow freeze identity mismatch")
    freeze = json.loads(freeze_raw)
    history_raw = (ROOT / "results/ratchet/workflow-history.json").read_bytes()
    if hashlib.sha256(history_raw).hexdigest() != freeze["sha256"]["results/ratchet/workflow-history.json"]:
        raise ValueError("frozen history receipt mismatch")
    history = json.loads(history_raw)
    if history != receipt["history"]:
        raise ValueError("workflow history differs from frozen history")
    observations = []
    for row in receipt["trials"]:
        if row["method"] != "plain" or row["method_compliance"]:
            continue
        slot = private / f"slot-{row['index']:02d}"
        raw = (slot / "worker/events.jsonl").read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != row["worker_events_sha256"]:
            raise ValueError("worker evidence hash differs from the frozen row")
        expected = {f"attempt-{i}.jsonl": (slot / "workspace/history" / f"attempt-{i}.jsonl").read_bytes()
                    for i in (0, 1)}
        expected_hashes = {r["record"]: r["record_sha256"] for r in history["records"] if r["task"] == row["task"]}
        if set(expected_hashes) != set(expected) or any(hashlib.sha256(raw).hexdigest() != expected_hashes[name]
                                                       for name, raw in expected.items()):
            raise ValueError("workspace history differs from frozen original hashes")
        verified = False
        for line in raw.decode("utf-8").splitlines():
            event = json.loads(line)
            item = event.get("item", {})
            if (event.get("type") != "item.completed" or item.get("type") != "command_execution"
                    or item.get("status") != "completed" or item.get("exit_code") != 0
                    or "read_ratchet_history.py" not in item.get("command", "")):
                continue
            # The supplied reader prints one JSON line, possibly after other output.
            # Do not infer observation from a command string or worker final answer.
            for output_line in item.get("aggregated_output", "").splitlines():
                try:
                    payload = json.loads(output_line)
                    if not isinstance(payload, dict) or payload.get("kind") != "complete_local_history":
                        continue
                    records = payload["records"]
                    verified |= (len(records) == 2 and {r["file"] for r in records} == set(expected)
                                 and all(r["text"].encode("utf-8") == expected[r["file"]]
                                         and r["sha256"] == hashlib.sha256(expected[r["file"]]).hexdigest()
                                         for r in records))
                except (ValueError, KeyError, TypeError, AttributeError):
                    continue
        observations.append({"slot": row["index"], "frozen_method_compliance": False,
            "audit_complete_originals_present": verified, "worker_events_sha256": digest,
            "original_sha256": expected_hashes,
            "finding": ("complete original payload present inside a completed command output; frozen method remains false"
                        if verified else "complete original reads not established by this audit"),
            "frozen_row_modified": False, "gate_adjustment": False})
    return {"scope": "post-run measurement limitation; does not change frozen assessments",
            "observations": observations}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.receipt.resolve():
        parser.error("audit output must not replace the frozen receipt")
    result = audit(json.loads(args.receipt.read_text(encoding="utf-8")), args.private_dir)
    atomic(args.output, result)
    print(json.dumps({"audited": len(result["observations"]),
                      "complete_originals_present": sum(r["audit_complete_originals_present"] for r in result["observations"])}))
