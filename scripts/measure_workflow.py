"""Bounded public-source worker comparison. Raw logs require a private output directory."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import time

from evidence_selector.core import Candidate, select
from evidence_selector.cli import load_env
from evidence_selector.providers import HttpProvider

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {"can_refresh_unmodified": "boolean", "requires_permanent_for_unmodified_refresh": "boolean",
          "refresh_setting": "string", "modified_alone_satisfies_should_set_cookie": "boolean",
          "empty_session_has_separate_save_path": "boolean", "comment_conflicts_with_implementation": "boolean",
          "decisive_sources": "array", "explanation": "string"}
SCHEMA = {"type": "object", "additionalProperties": False, "required": list(FIELDS),
          "properties": {k: {"type": v, **({"items": {"type": "string"}} if v == "array" else {})} for k,v in FIELDS.items()}}


def cost(usage):
    total, cached, written, output = (usage[k] for k in ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens"))
    if min(total, cached, written, output) < 0 or cached + written > total:
        raise ValueError("invalid worker token accounting")
    return ((total - cached - written) * 4 + cached * .4 + written * 5 + output * 20) / 1_000_000


def quality(answer, case):
    expected = {"can_refresh_unmodified": True, "requires_permanent_for_unmodified_refresh": True,
                "refresh_setting": "SESSION_REFRESH_EACH_REQUEST", "modified_alone_satisfies_should_set_cookie": True,
                "empty_session_has_separate_save_path": True, "comment_conflicts_with_implementation": True}
    return all(answer.get(k) == v for k,v in expected.items()) and set(case["critical_ids"]) <= set(answer.get("decisive_sources", []))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--private-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("Preserve existing trials; choose an unused output")
    private = Path(args.private_dir).resolve()
    if private.is_relative_to(ROOT):
        raise ValueError("Raw worker logs must stay outside the repository")
    private.mkdir(parents=True, exist_ok=True)
    worker = private / "empty-worker"
    worker.mkdir(exist_ok=True)
    schema = private / "schema.json"
    schema.write_text(json.dumps(SCHEMA), encoding="utf-8")
    load_env(args.env_file)
    provider = HttpProvider("typesafe")
    case = next(c for c in json.loads((ROOT / "fixtures/public/holdout.json").read_text())["cases"] if c["id"] == "holdout-flask-3")
    candidates = [Candidate.parse(c) for c in case["candidates"]]
    rows = []
    for trial in range(5):
        for method in (["retain-all", "jev"] if trial % 2 == 0 else ["jev", "retain-all"]):
            started = time.perf_counter()
            selection = select(case["query"], candidates, provider) if method == "jev" else None
            chosen = [c for c in case["candidates"] if selection is None or c["id"] in selection["proposed_keep_ids"]]
            # Whole-workflow fail open if any selector failure occurred.
            failures = sum("error" in d for d in selection["decisions"]) if selection else 0
            if failures:
                chosen = case["candidates"]
            prompt = ("Use only the public source excerpts below. Do not call tools. Answer the task as JSON matching the supplied schema. "
                      "Keep explanation under 100 words. Cite exact candidate IDs in decisive_sources. "
                      "Distinguish the implementation from any conflicting comment, and account for the separate empty-session save path.\n"
                      + json.dumps({"task": case["query"], "excerpts": chosen}))
            command = [shutil.which("codex") or "codex", "exec", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check",
                       "--sandbox", "read-only", "--model", "gpt-5.6-sol", "-c", 'model_reasoning_effort="low"',
                       "--json", "--output-schema", str(schema), "-C", str(worker), "-"]
            tick = time.perf_counter()
            proc = subprocess.run(command, input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=180)
            worker_ms = (time.perf_counter() - tick) * 1000
            stem = private / f"trial-{trial}-{method}"
            stem.with_suffix(".jsonl").write_text(proc.stdout, encoding="utf-8")
            stem.with_suffix(".stderr.log").write_text(proc.stderr, encoding="utf-8")
            events = []
            for line in proc.stdout.splitlines():
                try:
                    events.append(json.loads(line))
                except ValueError:
                    pass
            completions = [e for e in events if e.get("type") == "turn.completed"]
            messages = [e["item"]["text"] for e in events if e.get("type") == "item.completed" and e.get("item",{}).get("type") == "agent_message"]
            unexpected = [e for e in events if e.get("type") == "item.completed" and e.get("item",{}).get("type") not in ("agent_message", "reasoning", "error")]
            usage = completions[-1]["usage"] if completions else None
            try:
                answer = json.loads(messages[-1])
            except (ValueError, IndexError):
                answer = {}
            selector_usage = {}
            for d in selection["decisions"] if selection else []:
                for key, value in d["usage"].items():
                    selector_usage[key] = selector_usage.get(key, 0) + value
            selector_cost = selector_usage.get("input_tokens", 0) * .042 / 1_000_000
            row = {"trial": trial, "method": method, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                   "worker_model": "gpt-5.6-sol", "worker_usage": usage, "selector_usage": selector_usage,
                   "worker_latency_ms": worker_ms, "selector_latency_ms": selection["latency_ms"] if selection else 0,
                   "end_to_end_latency_ms": (time.perf_counter()-started)*1000, "answer": answer,
                   "structured_quality_pass": quality(answer, case), "unexpected_tool_items": len(unexpected),
                   "selector_errors": failures, "worker_exit_code": proc.returncode,
                   "worker_succeeded": bool(completions), "retries": 0, "expansion_calls": 0,
                   "estimated_cost_usd": cost(usage) + selector_cost if usage else None,
                   "selector_estimated_cost_usd": selector_cost}
            rows.append(row)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps({"status": "IN_PROGRESS", "trials": rows}, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({k: row[k] for k in ("trial", "method", "structured_quality_pass", "worker_succeeded", "end_to_end_latency_ms", "estimated_cost_usd")}), flush=True)
            if not completions:
                raise RuntimeError("Worker failed; trials preserved, no automatic retry")
    summary = {}
    for method in ("retain-all", "jev"):
        group = [r for r in rows if r["method"] == method]
        summary[method] = {"quality_passes": sum(r["structured_quality_pass"] for r in group),
                           "estimated_cost_usd": sum(r["estimated_cost_usd"] for r in group),
                           "median_latency_ms": statistics.median(r["end_to_end_latency_ms"] for r in group),
                           "empirical_p95_latency_ms": max(r["end_to_end_latency_ms"] for r in group)}
    a,b = summary["retain-all"],summary["jev"]
    cost_ratio, latency_ratio = b["estimated_cost_usd"] / a["estimated_cost_usd"], b["median_latency_ms"] / a["median_latency_ms"]
    result = {"status": "COMPLETE", "protocol": "docs/workflow-protocol.md", "summary": summary, "trials": rows,
              "cost_ratio": cost_ratio, "latency_ratio": latency_ratio,
              "numeric_U2_pass": all(r["structured_quality_pass"] and not r["unexpected_tool_items"] and not r["selector_errors"] for r in rows) and ((cost_ratio <= .9 and latency_ratio <= 1.1) or (latency_ratio <= .9 and cost_ratio <= 1)),
              "independent_answer_review": "PENDING", "cost_kind": "API-equivalent estimate, not a subscription bill",
              "cache_regime": "Service-managed, fresh task each trial, no forced reset; observed cache counts may differ"}
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
