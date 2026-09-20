"""Bounded Codex worker with owned child cleanup and private event logging."""
import json
import os
import re
from pathlib import Path
import signal
import subprocess
import sys
import time
from ratchet_atomic import atomic

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evidence_selector.owned_process import ChildJob


def transport_observations(events, stderr):
    """Count exposed retry notices; the CLI does not expose a complete retry ledger."""
    pattern = re.compile(r"reconnecting|retrying|retry attempt|stream disconnected", re.I)
    notices = [e for e in events if e.get("type") == "error"
               and pattern.search(str(e.get("message", "")))]
    return {"retry_count": None, "retry_count_status": "NOT_EXPOSED_BY_CLI",
            "retry_notice_events": len(notices),
            "retry_notice_stderr_lines": sum(bool(pattern.search(line)) for line in stderr.splitlines()),
            "error_events": sum(e.get("type") in ("error", "turn.failed") for e in events)}


def run_worker(command, prompt, private, timeout=240, env=None):
    private = Path(private).resolve()
    if private.is_relative_to(ROOT):
        raise ValueError("worker logs must remain outside Git")
    private.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    job = ChildJob()
    timed_out = False
    with (private / "events.jsonl").open("w", encoding="utf-8") as out, \
         (private / "stderr.log").open("w", encoding="utf-8") as err:
        lifecycle = private / "lifecycle.json"
        try:
            worker = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=out, stderr=err,
                text=True, encoding="utf-8", start_new_session=os.name != "nt", env=env)
        except OSError:
            atomic(lifecycle, {"state": "LAUNCH_FAILED", "pid": None})
            raise
        try:
            job.attach(worker)
            atomic(lifecycle, {"state": "RUNNING", "pid": worker.pid})
            try:
                worker.communicate(prompt, timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
        finally:
            if os.name != "nt":
                try:
                    os.killpg(worker.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            job.close()
            if worker.poll() is None:
                worker.kill()
            worker.wait(timeout=10)
            atomic(lifecycle, {"state": "STOPPED", "pid": worker.pid,
                "exit_code": worker.returncode, "elapsed_seconds": time.monotonic() - started})
    elapsed = time.monotonic() - started
    events, invalid = [], 0
    for line in (private / "events.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            invalid += 1
    items = [e["item"] for e in events if e.get("type") == "item.completed"]
    usage = [e["usage"] for e in events if e.get("type") == "turn.completed"]
    result = {"exit_code": worker.returncode, "timed_out": timed_out,
            "elapsed_seconds": elapsed, "invalid_event_lines": invalid,
            "completed_turns": len(usage),
            "usage_status": "REPORTED" if len(usage) == 1 else "MISSING" if not usage else "AMBIGUOUS_DUPLICATES",
            "usage": usage[0] if len(usage) == 1 else None, "items": items,
            "transport": transport_observations(events, (private / "stderr.log").read_text(encoding="utf-8"))}
    atomic(private / "result.json", result)
    return result
