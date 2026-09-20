"""Real stdio metering roundtrip; only recorded development evidence is used."""
import asyncio
from importlib.resources import files
import json
from pathlib import Path
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


async def main():
    with tempfile.TemporaryDirectory(prefix="ratchet-meter-") as temp:
        folder = Path(temp)
        replay = json.loads(files("evidence_selector.ratchet").joinpath("data/replay.json").read_text())
        for side, events in enumerate(replay["examples"][0]["records"]):
            (folder / f"attempt-{side}.jsonl").write_text(
                "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8", newline="\n")
        log = folder / "metrics.jsonl"
        params = StdioServerParameters(command=sys.executable,
            args=[str(ROOT / "scripts/ratchet_mcp_meter.py"), "--root", str(folder), "--metrics", str(log)])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                assert {t.name for t in listed.tools} == {"ratchet_status", "ratchet_compare", "ratchet_evidence"}
                status = await session.call_tool("ratchet_status", {})
                assert not status.isError
                compared = await session.call_tool("ratchet_compare", {"previous": "attempt-0.jsonl", "current": "attempt-1.jsonl"})
                assert not compared.isError
                result = compared.structuredContent or json.loads(compared.content[0].text)
                assert result["mode"] == "shadow" and result["relationship"] == "same_blocker"
                for source in result["sources"]:
                    expanded = await session.call_tool("ratchet_evidence", {"file": source["file"], "expected_sha256": source["sha256"]})
                    assert not expanded.isError
                    evidence = expanded.structuredContent or json.loads(expanded.content[0].text)
                    assert evidence["text"] == (folder / source["file"]).read_bytes().decode()
        rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        starts = [r for r in rows if r["event"] == "tool_started"]
        ends = [r for r in rows if r["event"] == "tool_finished"]
        assert len(starts) == len(ends) == 4
        assert {r["call"] for r in starts} == {r["call"] for r in ends}
        assert not any(r["event"] == "instrumentation_error" for r in rows)
        assert all(r["elapsed_ms"] > 0 and not r["tool_error"] for r in ends)
        comparison = next(r for r in ends if r["tool"] == "ratchet_compare")
        assert comparison["provider_calls"] == 0 and comparison["provider_input_tokens"] == 0
        assert comparison["accounting"] == "REPORTED"
        assert "API_ENDPOINT" not in log.read_text() and str(folder) not in log.read_text()
        print(json.dumps({"meter_stdio": "PASS", "platform": sys.platform, "completed_tools": 4,
                          "comparison_and_originals_preserved": True, "evidence_in_metrics": False,
                          "scope": "recorded development replay; no hosted calls or worker task"}))


if __name__ == "__main__":
    asyncio.run(main())
