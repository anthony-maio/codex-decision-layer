"""Install the wheel into an empty environment and exercise it outside the checkout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    wheel = Path(args.wheel).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        env = root / "venv"
        python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        ratchet = env / ("Scripts/ratchet.exe" if os.name == "nt" else "bin/ratchet")
        child_env = os.environ.copy()
        child_env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        for name in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS"):
            child_env.pop(name, None)
        def run(command, expected=0):
            result = subprocess.run(command, cwd=root, env=child_env, capture_output=True, text=True, encoding="utf-8", timeout=180)
            if result.returncode != expected:
                raise RuntimeError(f"Install check failed: {result.stderr[-1000:]}")
            return result.stdout
        run(["uv", "venv", str(env), "--python", "3.12"])
        constraints = root / "constraints.txt"
        exported = subprocess.run(["uv", "export", "--project", str(ROOT), "--locked", "--extra", "mcp", "--extra", "ratchet", "--no-emit-project", "--no-hashes"], capture_output=True, text=True, encoding="utf-8", check=True)
        constraints.write_text(exported.stdout, encoding="utf-8")
        run(["uv", "pip", "install", "--python", str(python), "--constraints", str(constraints), str(wheel) + "[mcp,ratchet]"])
        identity = json.loads(run([str(python), "-c", "import evidence_selector,importlib.metadata,json;print(json.dumps({'module':evidence_selector.__file__,'version':importlib.metadata.version('codex-evidence-selector')}))"]))
        assert Path(identity["module"]).is_relative_to(env)
        cli = json.loads(run([str(python), "-m", "evidence_selector", "doctor"]))
        assert cli["ready"]
        mcp = json.loads(run([str(python), str(ROOT / "tests/smoke_mcp.py")]))
        ratchet_mcp = json.loads(run([str(python), str(ROOT / "tests/smoke_ratchet_mcp.py")]))
        installed_entrypoint = json.loads(run([str(python), str(ROOT / "tests/smoke_ratchet_mcp.py"), "--entrypoint", str(ratchet)]))
        (root / "test_install.py").write_text("def test_failure():\n    assert 2 == 3\n", encoding="utf-8")
        (root / "pytest.ini").write_text("[pytest]\ntestpaths = test_install.py\n", encoding="utf-8")
        records = root / ".ratchet"
        records.mkdir()
        for number in (1, 2):
            run([str(python), "-m", "pytest", "-q", "-p", "no:cacheprovider",
                 "-p", "evidence_selector.ratchet.pytest_reporter", "--ratchet-task", "installed-project",
                 "--ratchet-output", str(records / f"attempt-{number}.jsonl"), "test_install.py"], expected=1)
        originals = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in records.iterdir()}
        comparison = json.loads(run([str(ratchet), "compare", str(records / "attempt-1.jsonl"), str(records / "attempt-2.jsonl")]))
        assert comparison["mode"] == "shadow" and comparison["relationship"] == "same_blocker"
        assert originals == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in records.iterdir()}
        run([str(python), "-m", "evidence_selector.eve_server", "--port", "0"], expected=1)
        # Restart the installed CLI/MCP with package management explicitly offline.
        offline = run(["uv", "run", "--offline", "--no-project", "--python", str(python), "python", "-m", "evidence_selector", "doctor"])
        assert json.loads(offline)["ready"]
        # Exercise packaged replay data with Python networking explicitly denied.
        # This checks the installed wheel, not resources in the source checkout.
        replay = json.loads(run([str(python), "-c",
            "import socket,runpy,sys; "
            "deny=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('offline')); "
            "socket.socket.connect=deny; socket.getaddrinfo=deny; "
            "sys.argv=['ratchet','demo','--json']; "
            "runpy.run_module('evidence_selector.ratchet',run_name='__main__')"]))
        assert replay["provider_calls_this_run"] == 0 and len(replay["examples"]) == 3
    receipt = {"platform": platform.system(), "package_version": identity["version"], "wheel": wheel.name,
               "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
               "isolated_wheel_import": True, "cli": "PASS", "mcp": mcp, "missing_local_extra": "ACTIONABLE_NONZERO",
               "offline_installed_cli_restart": "PASS", "ratchet_offline_wheel_replay": "PASS",
               "ratchet_mcp": ratchet_mcp,
               "ratchet_installed_entrypoint_mcp": installed_entrypoint,
               "ratchet_fresh_project_reporter_and_cli_comparison": "PASS",
               "ratchet_original_records_unchanged": True,
               "dependencies": "constrained by uv.lock"}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
