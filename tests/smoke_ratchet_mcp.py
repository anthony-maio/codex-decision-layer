"""Real stdio protocol roundtrip against Ratchet's read-only tools."""
import asyncio
import argparse
import hashlib
import json
import os
from importlib.resources import files
from pathlib import Path
import sys
import subprocess
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main(entrypoint=None, manifest=None):
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        replay = json.loads(files("evidence_selector.ratchet").joinpath("data/replay.json").read_text())
        for side, events in enumerate(replay["examples"][0]["records"]):
            (root / f"attempt-{side}.jsonl").write_text(
                "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8", newline="\n")
        params = StdioServerParameters(command=sys.executable,
            args=[str(Path(__file__).with_name("offline_ratchet_server.py")), str(root)])
        manifest_sha = None
        if entrypoint or manifest:
            child_env = {**os.environ, "RATCHET_CONFIG": str(root / "settings.json")}
            command, server_args = str(entrypoint), ["mcp"]
            if manifest:
                raw = manifest.read_bytes()
                manifest_sha = hashlib.sha256(raw).hexdigest()
                server = json.loads(raw)["mcpServers"]["ratchet"]
                command, server_args = server["command"], server["args"]
                if command != "uvx" or server_args[-2:] != ["ratchet", "mcp"]:
                    raise ValueError("expected the release Ratchet uvx launcher")
            subprocess.run([command, *server_args[:-1], "configure", "--root", str(root)], env=child_env,
                           check=True, capture_output=True, timeout=180)
            params = StdioServerParameters(command=command, args=server_args, env=child_env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                assert {t.name for t in listed.tools} == {"ratchet_compare", "ratchet_evidence", "ratchet_status"}
                assert all(t.annotations.readOnlyHint and not t.annotations.destructiveHint for t in listed.tools)
                comparison = await session.call_tool("ratchet_compare", {"previous": "attempt-0.jsonl", "current": "attempt-1.jsonl"})
                assert not comparison.isError
                result = comparison.structuredContent or json.loads(comparison.content[0].text)
                assert result["relationship"] == "same_blocker" and result["mode"] == "shadow"
                assert len(result["sources"]) == 2
                assert {source["file"] for source in result["sources"]} == {"attempt-0.jsonl", "attempt-1.jsonl"}
                for source in result["sources"]:
                    expanded = await session.call_tool("ratchet_evidence", {"file": source["file"], "expected_sha256": source["sha256"]})
                    assert not expanded.isError
                    evidence = expanded.structuredContent or json.loads(expanded.content[0].text)
                    assert evidence["text"] == (root / source["file"]).read_bytes().decode()
                denied = await session.call_tool("ratchet_evidence", {"file": "../outside.jsonl", "expected_sha256": source["sha256"]})
                assert denied.isError
                print(json.dumps({"ratchet_stdio": "PASS", "read_only_annotations": True,
                    "shadow_comparison": "PASS", "exact_evidence_recovery": "PASS", "outside_root": "REFUSED",
                    "launch": "plugin_manifest_saved_root" if manifest else "installed_entrypoint_saved_root" if entrypoint else "offline_python_bootstrap",
                    "manifest_sha256": manifest_sha,
                    "package_manager_offline": os.environ.get("UV_OFFLINE") == "1",
                    "server_dns_and_connect": "NOT_BLOCKED" if entrypoint or manifest else "DENIED_AFTER_EVENT_LOOP_CREATION"}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    launch = parser.add_mutually_exclusive_group()
    launch.add_argument("--entrypoint", type=Path)
    launch.add_argument("--manifest", type=Path, help="Exercise the actual release uvx launcher with a temporary saved record root")
    args = parser.parse_args()
    asyncio.run(main(args.entrypoint, args.manifest))
