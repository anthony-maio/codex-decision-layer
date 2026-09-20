"""Real start/infer/stop/offline-restart receipts. Run from an installed environment."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, build_opener, ProxyHandler

OPENER = build_opener(ProxyHandler({}))


def request(url, payload=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request(url, None if payload is None else json.dumps(payload).encode(), headers)
    with OPENER.open(req, timeout=30) as response:
        return json.load(response)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def child_main(module, offline, args):
    if offline:
        # Fail loudly on an attempted external Python connection, including DNS.
        original = socket.getaddrinfo
        def local_only(host, *a, **kw):
            if host not in ("127.0.0.1", "localhost", "::1", None):
                raise OSError("offline validation forbids external DNS")
            return original(host, *a, **kw)
        socket.getaddrinfo = local_only
        connect = socket.socket.connect
        def local_connect(self, address):
            if isinstance(address, tuple) and address[0] not in ("127.0.0.1", "::1"):
                raise OSError("offline validation forbids external connections")
            return connect(self, address)
        socket.socket.connect = local_connect
        os.environ["HF_HUB_OFFLINE"] = "1"
    import importlib
    raise SystemExit(importlib.import_module(module).main(args))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=["fp32", "q8"], required=True)
    parser.add_argument("--llama-server")
    parser.add_argument("--gguf")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = []
    token = secrets.token_hex(24)
    port, llama_port = free_port(), free_port()
    while llama_port == port:
        llama_port = free_port()
    module = "evidence_selector.eve_server" if args.engine == "fp32" else "evidence_selector.gguf_server"
    model = "eve-local" if args.engine == "fp32" else "eve-q8_0"
    options = ["--port", str(port)]
    if args.engine == "q8":
        if not args.llama_server or not args.gguf:
            parser.error("Q8 requires --llama-server and --gguf")
        options += ["--llama-server", str(Path(args.llama_server).resolve()), "--gguf", str(Path(args.gguf).resolve()),
                    "--llama-endpoint", f"http://127.0.0.1:{llama_port}"]
    payload = {"model": model, "state": "The service retains evidence after a provider failure.",
               "questions": {"relevant": {"type": "noul", "instructions": "Does the service retain evidence?"}}}
    with tempfile.TemporaryDirectory() as tmp:
        for offline in (False, True):
            command = [sys.executable, str(Path(__file__).resolve()), "--child", module, str(int(offline)), *options]
            if offline and args.engine == "fp32":
                command.append("--offline")
            log_path = Path(args.output).with_suffix(f".{int(offline)}.log").resolve()
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("wb") as log:
                proc = subprocess.Popen(command, cwd=tmp, env={**os.environ, "DECISION_LAYER_SHUTDOWN_TOKEN": token},
                                        stdout=log, stderr=log, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), start_new_session=os.name != "nt")
                started = time.perf_counter()
                try:
                    while True:
                        if proc.poll() is not None:
                            raise RuntimeError(f"{args.engine} startup exited {proc.returncode}; inspect {log_path}")
                        try:
                            health = request(f"http://127.0.0.1:{port}/health")
                            break
                        except OSError:
                            if time.perf_counter() - started > 180:
                                raise TimeoutError("startup deadline")
                            time.sleep(0.2)
                    startup = time.perf_counter() - started
                    result = request(f"http://127.0.0.1:{port}/v1/systemone", payload)
                    assert result["model"] == model and 0 <= result["answers"]["relevant"]["noul"] <= 1
                    assert result["diagnostics"]["truncated"] is False
                    request(f"http://127.0.0.1:{port}/shutdown", {}, token)
                    proc.wait(timeout=15)
                    assert proc.returncode == 0, proc.returncode
                    from evidence_selector.server_runtime import bind_server
                    with bind_server(port):
                        pass
                    if args.engine == "q8":
                        from evidence_selector.server_runtime import require_no_listener
                        require_no_listener(llama_port)
                    rows.append({"offline": offline, "startup_seconds": round(startup, 3), "health": health,
                                 "inference": result, "clean_stop": True, "ports_released": True})
                finally:
                    if proc.poll() is None:
                        try:
                            request(f"http://127.0.0.1:{port}/shutdown", {}, token)
                            proc.wait(timeout=15)
                        except Exception:
                            proc.terminate()
                            try:
                                proc.wait(timeout=15)
                            except subprocess.TimeoutExpired:
                                if os.name != "nt":
                                    import signal
                                    os.killpg(proc.pid, signal.SIGKILL)
                                else:
                                    proc.kill()
                                proc.wait()
    from evidence_selector.core import Candidate, select
    from evidence_selector.providers import HttpProvider
    failure = select("preservation", [Candidate("original", "public", "Original evidence")],
                     HttpProvider("eve", f"http://127.0.0.1:{port}/v1/systemone", model=model, timeout=1))
    assert failure["returned_ids"] == ["original"] and failure["decisions"][0]["error"] == "connection_failed"
    versions = {}
    for name in ("codex-evidence-selector", "torch", "transformers", "mcp"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    result = {"platform": platform.system(), "python": platform.python_version(), "versions": versions,
              "engine": args.engine, "device": "cpu", "runs": rows, "stopped_provider_fail_open": True,
              "offline_scope": "Python external DNS/connect forbidden; local artifact only for owned llama child; host network not disabled"}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        child_main(sys.argv[2], bool(int(sys.argv[3])), sys.argv[4:])
    else:
        main()
