"""Verify the private Codex probe against public replay records; emit no raw logs."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify(private):
    summary = json.loads((private / "summary.json").read_text(encoding="utf-8"))
    if summary["worker_exit_code"] != 0 or summary["timed_out"]:
        raise ValueError("worker_did_not_finish")
    events = [json.loads(line) for line in (private / "worker.jsonl").read_text(encoding="utf-8").splitlines()]
    calls = [e["item"] for e in events if e.get("type") == "item.completed"
             and e["item"].get("type") == "mcp_tool_call"]
    expected = ["ratchet_status", "ratchet_compare", "ratchet_evidence"]
    if [c.get("tool") for c in calls] != expected:
        raise ValueError("unexpected_tool_sequence")
    values = []
    for call in calls:
        if call.get("server") != "ratchet" or call.get("status") != "completed" or call.get("error"):
            raise ValueError("tool_failure")
        result = call["result"]
        if result.get("isError"):
            raise ValueError("tool_result_error")
        values.append(result.get("structured_content") or json.loads(result["content"][0]["text"]))
    status, decision, evidence = values
    if status != {"mode": "shadow", "provider": "deterministic", "advisory_enabled": False,
                  "command_execution": False, "hosted_upload": False, "experimental": True}:
        raise ValueError("unexpected_server_mode")
    replay = json.loads((ROOT / "evidence_selector/ratchet/data/replay.json").read_text(encoding="utf-8"))
    records = [("\n".join(json.dumps(event) for event in events) + "\n").encode()
               for events in replay["examples"][0]["records"]]
    hashes = [hashlib.sha256(raw).hexdigest() for raw in records]
    if ([s["sha256"] for s in decision["sources"]] != hashes
        or decision["relationship"] != "same_blocker" or decision["reason"] != "matching_explicit_cause"
        or decision["mode"] != "shadow" or decision["advisory"] is not None
        or decision["originals_modified"] is not False):
        raise ValueError("comparison_not_expected_public_replay")
    if (evidence["sha256"] != hashes[0] or evidence["text"].encode() != records[0]
        or evidence["next_offset"] is not None or evidence["originals_modified"] is not False):
        raise ValueError("original_evidence_not_exact")
    for name, digest in summary["implementation_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("implementation_changed_since_probe")
    return {**summary, "integration_status": "PASS_INSTALLED_CODEX_READ_ONLY_MCP",
            "scope": "Installed local development plugin using public recorded pytest evidence",
            "codex_cli": summary.get("codex_cli"), "worker_model_requested": "gpt-5.6-sol",
            "launch": "Local plugin uses an explicit development interpreter and record root",
            "source_sha256": hashes, "original_evidence_recovery": "EXACT_FIRST_RECORD",
            "live_test_execution": "NOT_ATTEMPTED", "automatic_hook_capture": "NOT_VERIFIED",
            "workflow_usefulness": "NOT_EVALUATED", "cost_estimate": None,
            "usage_scope": "Integration probe including host tool catalog and cached context; not a matched workflow"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = verify(args.private_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(receipt, indent=2) + "\n")
    print(receipt["integration_status"])


if __name__ == "__main__":
    main()
