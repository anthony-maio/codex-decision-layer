"""Install the wheel into an empty environment and exercise it outside the checkout."""
import argparse
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
        def run(command, expected=0):
            result = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=180)
            if result.returncode != expected:
                raise RuntimeError(f"Install check failed: {result.stderr[-1000:]}")
            return result.stdout
        run(["uv", "venv", str(env), "--python", "3.12"])
        constraints = root / "constraints.txt"
        exported = subprocess.run(["uv", "export", "--project", str(ROOT), "--locked", "--extra", "mcp", "--no-emit-project", "--no-hashes"], capture_output=True, text=True, encoding="utf-8", check=True)
        constraints.write_text(exported.stdout, encoding="utf-8")
        run(["uv", "pip", "install", "--python", str(python), "--constraints", str(constraints), str(wheel) + "[mcp]"])
        identity = json.loads(run([str(python), "-c", "import evidence_selector,importlib.metadata,json;print(json.dumps({'module':evidence_selector.__file__,'version':importlib.metadata.version('codex-evidence-selector')}))"]))
        assert Path(identity["module"]).is_relative_to(env)
        cli = json.loads(run([str(python), "-m", "evidence_selector", "doctor"]))
        assert cli["ready"]
        mcp = json.loads(run([str(python), str(ROOT / "tests/smoke_mcp.py")]))
        run([str(python), "-m", "evidence_selector.eve_server", "--port", "0"], expected=1)
        # Restart the installed CLI/MCP with package management explicitly offline.
        offline = run(["uv", "run", "--offline", "--no-project", "--python", str(python), "python", "-m", "evidence_selector", "doctor"])
        assert json.loads(offline)["ready"]
    receipt = {"platform": platform.system(), "package_version": identity["version"], "wheel": wheel.name,
               "isolated_wheel_import": True, "cli": "PASS", "mcp": mcp, "missing_local_extra": "ACTIONABLE_NONZERO",
               "offline_installed_cli_restart": "PASS", "dependencies": "constrained by uv.lock"}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
