"""Real stdio MCP roundtrip. Baseline by default; explicit --env-file enables Jev."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        original = "Pending writes are discarded during shutdown.\nDrain the buffer before closing storage.\n"
        (Path(tmp) / "evidence.txt").write_bytes(original.encode())
        server_args = ["-m", "evidence_selector"]
        if args.env_file:
            server_args += ["--provider", "typesafe", "--env-file", str(Path(args.env_file).resolve())]
        server_args += ["mcp", "--root", tmp]
        params = StdioServerParameters(command=sys.executable, args=server_args)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                assert {tool.name for tool in listed.tools} == {"shadow_evidence", "read_evidence"}
                result = await session.call_tool("shadow_evidence", {
                    "query": "Why are queued writes lost on shutdown?", "files": ["evidence.txt"]})
                assert not result.isError, result
                data = result.structuredContent or json.loads(result.content[0].text)
                assert data["candidates"][0]["text"] == original
                assert data["returned_ids"] == [data["candidates"][0]["id"]]
                assert data["actual_evidence_bytes_removed"] == 0
                assert not any("error" in d for d in data["decisions"])
                expanded = await session.call_tool("read_evidence", {
                    "file": "evidence.txt", "start_line": 2, "line_count": 1})
                assert not expanded.isError
                expansion = expanded.structuredContent or json.loads(expanded.content[0].text)
                assert expansion["text"] == original.splitlines(keepends=True)[1]
                denied = await session.call_tool("read_evidence", {"file": "../outside.txt"})
                assert denied.isError
                print(json.dumps({"mcp_stdio": "PASS", "provider": data["provider"],
                                  "original_text_preserved": True, "expansion": "PASS",
                                  "outside_root": "REFUSED", "decisions": data["decisions"]}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
