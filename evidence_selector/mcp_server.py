"""Optional stdio tools. These do not intercept Codex's built-in tools."""
from pathlib import Path

from .core import read_file, retrieve, select


def run(root, provider, drop_below, keep_above):
    from mcp.server.fastmcp import FastMCP

    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("MCP root must be a directory")
    server = FastMCP("Evidence selector (shadow)")

    @server.tool()
    def shadow_evidence(query: str, files: list[str], chunk_lines: int = 12) -> dict:
        """Read explicit UTF-8 files under the configured root and score passage relevance.

        Returns every original snippet, source location, and a proposed retention decision.
        Proposals are experimental; they do not establish truth or authorize actions.
        Hosted providers receive the query and snippet text. Baseline stays local.
        """
        return select(query, retrieve(root, files, chunk_lines), provider, drop_below, keep_above)

    @server.tool()
    def read_evidence(file: str, start_line: int = 1, line_count: int = 40) -> dict:
        """Expand a passage by reading exact lines, without a model decision."""
        if start_line < 1 or not 1 <= line_count <= 100:
            raise ValueError("Require positive start_line and 1-100 lines")
        path, content = read_file(root, file)
        lines = content.splitlines(keepends=True)
        if start_line > len(lines):
            raise ValueError("start_line is beyond the end of the file")
        return {"source": path.relative_to(root).as_posix(), "start_line": start_line,
                "text": "".join(lines[start_line - 1:start_line - 1 + line_count])}

    server.run(transport="stdio")
