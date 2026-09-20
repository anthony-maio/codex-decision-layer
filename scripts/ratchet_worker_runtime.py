"""Bounded Codex worker with owned child cleanup and private event logging."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evidence_selector.owned_process import ChildJob


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
        worker = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=out, stderr=err,
            text=True, encoding="utf-8", start_new_session=os.name != "nt", env=env)
        try:
            job.attach(worker)
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
    elapsed = time.monotonic() - started
    events, invalid = [], 0
    for line in (private / "events.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            invalid += 1
    items = [e["item"] for e in events if e.get("type") == "item.completed"]
    usage = [e["usage"] for e in events if e.get("type") == "turn.completed"]
    return {"exit_code": worker.returncode, "timed_out": timed_out,
            "elapsed_seconds": elapsed, "invalid_event_lines": invalid,
            "completed_turns": len(usage),
            "usage_status": "REPORTED" if len(usage) == 1 else "MISSING" if not usage else "AMBIGUOUS_DUPLICATES",
            "usage": usage[0] if len(usage) == 1 else None, "items": items}
