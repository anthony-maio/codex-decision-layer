"""Measure a real Ratchet stdio server without changing its tool responses.

This experiment-only proxy records numeric lifecycle and usage fields privately.
It does not execute worker commands, cache decisions, or alter comparison logic.
"""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_TOOLS = {"ratchet_status", "ratchet_compare", "ratchet_evidence"}


def comparison_metrics(response):
    """Return only numeric/enum fields, never reports, arguments, or error text."""
    result = response.get("result", {})
    payload = result.get("structuredContent")
    if not isinstance(payload, dict):
        texts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
        if len(texts) != 1:
            return {"accounting": "UNAVAILABLE"}
        try:
            payload = json.loads(texts[0])
        except (ValueError, TypeError):
            return {"accounting": "UNAVAILABLE"}
    if not isinstance(payload, dict) or payload.get("mode") != "shadow":
        return {"accounting": "UNAVAILABLE"}
    # A completed deterministic decision has no provider counters.
    calls = payload.get("provider_calls", 0)
    retries = payload.get("retries", 0)
    latency = payload.get("provider_latency_ms", 0)
    if (type(calls) is not int or calls not in (0, 1) or type(retries) is not int or retries != 0
        or type(latency) not in (int, float) or not math.isfinite(latency) or latency < 0):
        return {"accounting": "UNAVAILABLE"}
    usage = payload.get("decision", {}).get("usage")
    known = calls == 0 or (isinstance(usage, dict) and all(
        type(usage.get(k)) is int and usage[k] >= 0 for k in ("input_tokens", "output_tokens")))
    return {"accounting": "REPORTED" if known else "MISSING_PROVIDER_USAGE",
            "provider_calls": calls, "provider_retries": retries,
            "provider_latency_ms": latency,
            "provider_input_tokens": usage["input_tokens"] if calls and known else 0 if not calls else None,
            "provider_output_tokens": usage["output_tokens"] if calls and known else 0 if not calls else None,
            "provider_failed": payload.get("reason") == "provider_failure"}


class Meter:
    def __init__(self, stream):
        self.stream = stream
        self.lock = threading.Lock()
        self.pending = {}
        self.sequence = 0

    def write(self, entry):
        self.stream.write(json.dumps(entry) + "\n")
        self.stream.flush()
        os.fsync(self.stream.fileno())

    def request(self, message):
        if message.get("method") != "tools/call" or "id" not in message:
            return
        tool = message.get("params", {}).get("name")
        if tool not in ALLOWED_TOOLS:
            tool = "unknown_tool"
        key = json.dumps(message["id"])
        with self.lock:
            if key in self.pending:
                self.write({"event": "instrumentation_error", "reason": "duplicate_request_id"})
                return
            index = self.sequence
            self.sequence += 1
            self.pending[key] = (index, tool, time.perf_counter())
            self.write({"event": "tool_started", "call": index, "tool": tool})

    def response(self, message):
        if "id" not in message or ("result" not in message and "error" not in message):
            return
        key = json.dumps(message["id"])
        with self.lock:
            pending = self.pending.pop(key, None)
            if pending is None:
                return
            index, tool, started = pending
            row = {"event": "tool_finished", "call": index, "tool": tool,
                   "elapsed_ms": (time.perf_counter() - started) * 1000,
                   "tool_error": "error" in message or message.get("result", {}).get("isError", False)}
            if tool == "ratchet_compare":
                row.update(comparison_metrics(message))
            self.write(row)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--metrics", type=Path, required=True)
    p.add_argument("--jev", action="store_true")
    p.add_argument("--allow-hosted", action="store_true")
    p.add_argument("--env-file", type=Path)
    p.add_argument("--require-freeze", action="store_true")
    args = p.parse_args()
    output = args.metrics.resolve()
    if output.is_relative_to(ROOT):
        p.error("numeric instrumentation logs must be private until verified")
    if args.jev and not args.allow_hosted:
        p.error("--jev requires --allow-hosted")
    command = [sys.executable, str(ROOT / "scripts/ratchet_verified_child.py"), "mcp",
               "--provenance", str(output.with_suffix(".provenance.json"))]
    if args.require_freeze:
        command += ["--require-freeze"]
    command += ["--", "--root", str(args.root)]
    if args.jev:
        command += ["--jev", "--allow-hosted"]
        if args.env_file:
            command += ["--env-file", str(args.env_file)]
    # The Codex worker owns this process tree. Do not detach the server from it.
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        meter = Meter(stream)
        server = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=sys.stderr, bufsize=0)

        def replies():
            try:
                for line in server.stdout:
                    try:
                        meter.response(json.loads(line))
                    except (ValueError, TypeError, AttributeError):
                        with meter.lock:
                            meter.write({"event": "instrumentation_error", "reason": "response_unreadable"})
                    sys.stdout.buffer.write(line)
                    sys.stdout.buffer.flush()
            except BrokenPipeError:
                pass

        reader = threading.Thread(target=replies, daemon=True)
        reader.start()
        try:
            for line in sys.stdin.buffer:
                try:
                    meter.request(json.loads(line))
                except (ValueError, TypeError, AttributeError):
                    with meter.lock:
                        meter.write({"event": "instrumentation_error", "reason": "request_unreadable"})
                server.stdin.write(line)
                server.stdin.flush()
        except BrokenPipeError:
            pass
        finally:
            server.stdin.close()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
            reader.join(timeout=5)
            with meter.lock:
                meter.write({"event": "server_stopped", "exit_code": server.returncode,
                             "unfinished_tools": len(meter.pending), "reader_finished": not reader.is_alive()})


if __name__ == "__main__":
    main()
