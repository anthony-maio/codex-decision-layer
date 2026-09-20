"""Terminal entry point for selecting evidence, replaying labels, and serving MCP."""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys

from .core import Candidate, evaluate_case, retrieve, select
from .providers import HttpProvider


def load_env(path):
    """Read an explicitly selected dotenv file, without executing or expanding values."""
    import re
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", line)
        if not match:
            raise ValueError("Invalid dotenv assignment")
        key, value = match.groups()
        if value.startswith(('"', "'")):
            quote = value[0]
            end = value.find(quote, 1)
            if end < 0 or value[end + 1:].strip() and not value[end + 1:].strip().startswith("#"):
                raise ValueError("Invalid quoted dotenv value")
            value = value[1:end]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
        os.environ.setdefault(key, value)


def provider_from(args):
    if args.env_file:
        load_env(args.env_file)
    if args.provider == "baseline":
        return None
    return HttpProvider(args.provider, args.endpoint, args.key_env, args.model, args.timeout)


def evaluate(dataset, provider, drop_below=0.1, keep_above=0.9):
    raw = Path(dataset).read_bytes()
    data = json.loads(raw)
    if not isinstance(data.get("cases"), list) or not data["cases"] or len(data["cases"]) > 100:
        raise ValueError("Dataset must have 1-100 cases")
    if len({c["id"] for c in data["cases"]}) != len(data["cases"]):
        raise ValueError("Case IDs must be unique")
    # Validate all labels before spending on any model requests.
    prepared = []
    for case in data["cases"]:
        candidates = [Candidate.parse(c) for c in case["candidates"]]
        baseline = select(case["query"], candidates, drop_below=drop_below, keep_above=keep_above)
        evaluate_case(case, baseline)
        prepared.append((case, candidates))
    rows = []
    for case, candidates in prepared:
        result = select(case["query"], candidates, provider, drop_below, keep_above)
        rows.append(evaluate_case(case, result))
    relevant = sum(r["relevant"] for r in rows)
    retained_relevant = sum(r["retained_relevant"] for r in rows)
    retained = sum(r["retained"] for r in rows)
    scored = sum(r["scored"] for r in rows)
    usage = {}
    for row in rows:
        for decision in row["decisions"]:
            for key, value in decision["usage"].items():
                usage[key] = usage.get(key, 0) + value
    total_bytes = sum(r["evidence_bytes"] for r in rows)
    proposed_bytes = sum(r["proposed_evidence_bytes"] for r in rows)
    return {"mode": "shadow", "provider": provider.name if provider else "baseline",
            "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "dataset_sha256": hashlib.sha256(raw).hexdigest(),
            "label_provenance": data.get("label_provenance", "unspecified"),
            "prompt_version": "relevance-v1", "thresholds": {"drop_below": drop_below, "keep_above": keep_above},
            "summary": {"cases": len(rows), "candidates": sum(r["candidates"] for r in rows),
                        "scored": scored, "errors": sum(r["errors"] for r in rows),
                        "proposed_recall": retained_relevant / relevant if relevant else None,
                        "proposed_precision": retained_relevant / retained if retained else None,
                        "missed_relevant": relevant - retained_relevant,
                        "missed_critical": sum(len(r["missed_critical_ids"]) for r in rows),
                        "brier_on_scored": sum(r["brier_sum"] for r in rows) / scored if scored else None,
                        "proposed_byte_reduction": 1 - proposed_bytes / total_bytes if total_bytes else 0,
                        "actual_evidence_bytes_removed": 0,
                        "total_selector_latency_ms": sum(r["latency_ms"] for r in rows),
                        "median_case_latency_ms": statistics.median(r["latency_ms"] for r in rows),
                        "provider_reported_usage": usage}, "cases": rows,
            "limitations": ["Fixture replay, not end-to-end task performance",
                            "Byte reduction is hypothetical and is not token or dollar savings",
                            "Sequential per-passage requests; no latency optimization",
                            "Provisional thresholds; no production filtering enabled"]}


def parser():
    p = argparse.ArgumentParser(description="Evidence selector experiment: all output remains in shadow mode")
    p.add_argument("--provider", choices=["baseline", "typesafe", "openrouter", "eve"], default="baseline")
    p.add_argument("--env-file", help="Explicit dotenv path; secrets are never printed")
    p.add_argument("--key-env")
    p.add_argument("--endpoint", help="Full loopback Eve endpoint URL")
    p.add_argument("--model")
    p.add_argument("--timeout", type=float, default=15)
    p.add_argument("--drop-below", type=float, default=0.1)
    p.add_argument("--keep-above", type=float, default=0.9)
    sub = p.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("evaluate", help="Replay a fully labeled JSON fixture set")
    demo.add_argument("dataset")
    demo.add_argument("--output")
    choose = sub.add_parser("select", help="Evaluate a JSON query/candidates document; retain all text")
    choose.add_argument("input")
    search = sub.add_parser("retrieve", help="Read and chunk explicit files under one root")
    search.add_argument("--root", required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--file", action="append", required=True)
    search.add_argument("--chunk-lines", type=int, default=12)
    mcp = sub.add_parser("mcp", help="Expose shadow_evidence and read_evidence through stdio MCP")
    mcp.add_argument("--root", required=True)
    configure = sub.add_parser("configure", help="Write user-local plugin settings; never stores key values")
    configure.add_argument("--root", required=True)
    sub.add_parser("plugin-mcp", help="Start MCP with ~/.codex/decision-layer.json settings")
    sub.add_parser("doctor", help="Check provider inference using a public diagnostic passage")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "configure":
            from .plugin import configure
            print(f"Plugin configuration saved: {configure(args)}")
            return 0
        if args.command == "plugin-mcp":
            from .plugin import serve
            serve()
            return 0
        provider = provider_from(args)
        if args.command == "doctor":
            import importlib.metadata
            result = select("Does this service preserve evidence?", [Candidate("diagnostic", "diagnostic", "The service preserves every original evidence passage.")], provider, args.drop_below, args.keep_above)
            print(json.dumps({"package_version": importlib.metadata.version("codex-evidence-selector"),
                              "provider": result["provider"], "decisions": result["decisions"],
                              "ready": not any("error" in d for d in result["decisions"]),
                              "hint": "Start eve-decision-server or gguf-decision-server for local inference; check credentials for hosted providers."}, indent=2))
            return 2 if any("error" in d for d in result["decisions"]) else 0
        if args.command == "mcp":
            from .mcp_server import run
            run(args.root, provider, args.drop_below, args.keep_above)
            return 0
        if args.command == "evaluate":
            result = evaluate(args.dataset, provider, args.drop_below, args.keep_above)
            if args.output:
                output = Path(args.output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
                print(json.dumps(result["summary"], indent=2))
            else:
                print(json.dumps(result, indent=2, allow_nan=False))
            return 2 if result["summary"]["errors"] else 0
        if args.command == "select":
            data = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
            query = data["query"]
            candidates = [Candidate.parse(c) for c in data["candidates"]]
        else:
            query = args.query
            candidates = retrieve(args.root, args.file, args.chunk_lines)
        result = select(query, candidates, provider, args.drop_below, args.keep_above)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 2 if any("error" in d for d in result["decisions"]) else 0
    except ImportError:
        print("Missing optional dependency. Install with uv sync --extra mcp --locked for MCP, or --extra local for FP32. Use uv run --no-sync after setup.", file=sys.stderr)
        return 1
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # Only controlled validation messages or exception class names reach stderr.
        message = str(exc) if type(exc) is ValueError else type(exc).__name__
        print(f"Configuration/input error: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
