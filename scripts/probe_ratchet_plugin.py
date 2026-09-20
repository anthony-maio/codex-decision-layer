"""Invoke an installed Ratchet plugin in a real Codex task without approval overrides."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evidence_selector.owned_process import ChildJob


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-dir", type=Path, required=True)
    args = parser.parse_args()
    private = args.private_dir.resolve()
    if private.is_relative_to(ROOT):
        parser.error("private-dir must be outside Git repository")
    private.mkdir(parents=True, exist_ok=False)
    workspace = private / "workspace"
    workspace.mkdir()
    prompt = (
        "Validate the installed Ratchet plugin using its read-only MCP tools only. "
        "Call ratchet_status. Then call ratchet_compare with previous='attempt-0.jsonl' "
        "and current='attempt-1.jsonl'. Retrieve the first original with ratchet_evidence "
        "using the exact SHA-256 returned by comparison. Do not execute shell commands, "
        "edit files, configure services, or call unrelated tools. Report the comparison "
        "and whether the original evidence supports it. If a tool is unavailable or "
        "declined, state that plainly. This is a read-only integration check, not a request "
        "to investigate or repair the authored failure."
    )
    command = [shutil.which("codex") or "codex", "exec", "--ephemeral", "--skip-git-repo-check",
               "--sandbox", "read-only", "--model", "gpt-5.6-sol", "-c", 'model_reasoning_effort="low"',
               "--json", "-C", str(workspace), "-"]
    codex_version = subprocess.check_output([command[0], "--version"], text=True, encoding="utf-8", timeout=10).strip()
    started = time.monotonic()
    implementation = {str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in sorted((ROOT / "evidence_selector/ratchet").glob("*.py"))}
    timed_out = False
    job = ChildJob()
    with (private / "worker.jsonl").open("w", encoding="utf-8") as out, \
         (private / "worker.stderr.log").open("w", encoding="utf-8") as err:
        worker = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=out, stderr=err,
            text=True, encoding="utf-8", start_new_session=os.name != "nt")
        try:
            job.attach(worker)
            try:
                worker.communicate(prompt, timeout=180)
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
    events = []
    for line in (private / "worker.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    items = [event["item"] for event in events if event.get("type") == "item.completed"]
    calls = [item for item in items if item.get("type") == "mcp_tool_call"]
    usage = [event["usage"] for event in events if event.get("type") == "turn.completed"]
    summary = {"worker_exit_code": worker.returncode, "timed_out": timed_out,
               "codex_cli": codex_version,
               "elapsed_seconds": time.monotonic() - started,
               "tool_calls": [{"server": item.get("server"), "tool": item.get("tool"),
                               "status": item.get("status"), "error": item.get("error")} for item in calls],
               "usage": usage[-1] if usage else None,
               "implementation_sha256": implementation,
               "integration_status": "UNVERIFIED_PENDING_EVIDENCE_REVIEW"}
    (private / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
