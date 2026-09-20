"""Capture real Codex hook payloads in a private, disposable pytest workspace.

No global configuration changes or hook-trust bypass. This is a developer probe,
not the plugin installation path. Hook trust and command approval are separate
requirements; denied calls or untrusted hooks leave integration unverified.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evidence_selector.owned_process import ChildJob


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.private_dir.resolve()
    repo = Path(__file__).resolve().parents[1]
    if root.is_relative_to(repo):
        parser.error("private-dir must be outside the repository")
    if importlib.util.find_spec("pytest") is None:
        parser.error("install pytest in the probe Python environment first")
    # Codex can load hooks.json independently of --ignore-user-config.
    config_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    if (config_home / "hooks.json").exists():
        parser.error("user hooks.json exists; isolate/review hook sources before running")
    root.mkdir(parents=True, exist_ok=False)
    workspace = root / "workspace"
    workspace.mkdir()
    capture = root / "capture.py"
    capture.write_text(
        "import json, pathlib, sys, uuid\n"
        "event = json.load(sys.stdin)\n"
        "folder = pathlib.Path(__file__).parent\n"
        "(folder / ('event-' + uuid.uuid4().hex + '.json')).write_text(\n"
        "    json.dumps(event), encoding='utf-8')\n",
        encoding="utf-8",
    )
    (workspace / "test_probe.py").write_text(
        "import pytest\n"
        "@pytest.fixture\n"
        "def database():\n"
        "    raise ConnectionRefusedError('ratchet-public-probe: database unavailable')\n"
        "def test_query(database):\n"
        "    assert database == 'ready'\n",
        encoding="utf-8",
    )
    executable = shutil.which("codex.cmd" if os.name == "nt" else "codex")
    if not executable:
        parser.error("codex executable not found")
    hook_command = f'"{sys.executable}" "{capture}"'
    # Single-quoted TOML literal strings preserve Windows backslashes.
    if "'" in hook_command:
        parser.error("probe paths cannot contain a single quote")
    hooks = ('hooks.PostToolUse=[{matcher="Bash", hooks=[{type="command", '
             f"command='{hook_command}', timeout=5" + '}]}]')
    prompt = (
        "Integration probe. Run this exact test command twice as two separate shell "
        "tool calls even though it fails. Do not edit files, install packages, use "
        "network tools, or investigate the failure. Then report both exit codes. "
        f'Command: & "{sys.executable}" -m pytest -q --tb=short -p no:cacheprovider'
        if os.name == "nt" else
        "Integration probe. Run this exact command twice as separate shell tool calls. "
        "Do not edit files or investigate. Report both exit codes. "
        f'Command: "{sys.executable}" -m pytest -q --tb=short -p no:cacheprovider'
    )
    command = [executable, "exec", "--ignore-user-config", "--ephemeral",
               "--skip-git-repo-check", "--disable", "plugins", "--enable", "hooks",
               "--sandbox", "read-only",
               "--model", "gpt-5.6-sol", "-c", 'model_reasoning_effort="low"',
               "-c", hooks, "--json", "-C", str(workspace), "-"]
    started = time.monotonic()
    timed_out = False
    job = ChildJob()
    with (root / "worker.jsonl").open("w", encoding="utf-8") as out, \
         (root / "worker.stderr.log").open("w", encoding="utf-8") as err:
        worker = subprocess.Popen(command, stdin=subprocess.PIPE, text=True,
                                  stdout=out, stderr=err, start_new_session=os.name != "nt")
        try:
            job.attach(worker)
            try:
                worker.communicate(prompt, timeout=180)
            except subprocess.TimeoutExpired:
                timed_out = True
        finally:
            # Only this invocation's owned process group/job is terminated.
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
    for path in sorted(root.glob("event-*.json")):
        raw = path.read_bytes()
        event = json.loads(raw)
        events.append({"sha256": hashlib.sha256(raw).hexdigest(),
                       "event": event.get("hook_event_name"),
                       "tool": event.get("tool_name"),
                       "response_type": type(event.get("tool_response")).__name__,
                       "response_keys": sorted(event["tool_response"])
                       if isinstance(event.get("tool_response"), dict) else []})
    summary = {"worker_exit_code": worker.returncode, "timed_out": timed_out,
               "elapsed_seconds": time.monotonic() - started,
               "captured_events": events,
               "scope": "real Codex CLI, invocation-only hook, not installed plugin"}
    # Capture is diagnostic only until payload identities and completeness have
    # been verified. A successful worker exit is not a successful integration.
    summary["integration_status"] = "UNVERIFIED" if events else "NO_EVENTS"
    (root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
