"""Small CLI for shadow comparison and a clearly labeled offline replay."""
import argparse
import json
from importlib.resources import files
from pathlib import Path

from evidence_selector.cli import load_env
from .records import compare, read_run
from .semantic import JevChoice, compare_with_jev


def main():
    parser = argparse.ArgumentParser(prog="ratchet", description="Experimental, evidence-preserving failure comparison")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Offline replay of recorded development examples; no model calls")
    demo.add_argument("--json", action="store_true")
    configure = commands.add_parser("configure", help="Save a local record root; deterministic shadow mode")
    configure.add_argument("--root", type=Path, required=True)
    mcp = commands.add_parser("mcp", help="Run read-only stdio MCP tools; never executes tests")
    mcp.add_argument("--root", type=Path)
    mcp.add_argument("--jev", action="store_true")
    mcp.add_argument("--allow-hosted", action="store_true")
    mcp.add_argument("--env-file", type=Path)
    pair = commands.add_parser("compare", help="Compare two completed pytest records in shadow mode")
    pair.add_argument("previous", type=Path)
    pair.add_argument("current", type=Path)
    pair.add_argument("--jev", action="store_true")
    pair.add_argument("--allow-hosted", action="store_true", help="Allow sending complete failure text to TypeSafe")
    pair.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    if args.command == "configure":
        from .config import configure as save_config
        try:
            path = save_config(args.root)
        except (OSError, ValueError):
            parser.error("Cannot save Ratchet settings; --root must name an accessible directory")
        print(json.dumps({"mode": "shadow", "config": str(path), "provider": "deterministic"}))
        return 0
    if args.command == "mcp":
        from .config import saved_root
        try:
            from .mcp_server import create_server
            root = args.root or saved_root()
            provider = None
            if args.jev:
                if not args.allow_hosted:
                    parser.error("--jev requires --allow-hosted")
                if args.env_file:
                    load_env(args.env_file)
                provider = JevChoice(allow_hosted=True)
            create_server(root, provider).run(transport="stdio")
        except ImportError:
            parser.error("MCP requires the mcp extra: install codex-evidence-selector[mcp]")
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        return 0
    if args.command == "demo":
        replay = json.loads(files("evidence_selector.ratchet").joinpath("data/replay.json").read_text(encoding="utf-8"))
        if args.json:
            print(json.dumps({**replay, "provider_calls_this_run": 0}, indent=2))
        else:
            print("Ratchet: recorded development replay")
            print("Offline. No tests executed, no model calls, no commands blocked.")
            print("These authored examples do not establish saved time or retries.\n")
            for case in replay["examples"]:
                print(case["title"])
                print("  " + case["recorded_decision"]["relationship"] + " / " + case["recorded_decision"]["reason"])
                print("  " + case["explanation"])
                print("  Original normalized reports: ratchet demo --json\n")
            print("Shadow mode. Advisory and workflow gates have not passed.")
        return 0
    if args.jev and not args.allow_hosted:
        parser.error("--jev requires --allow-hosted; failure text may contain private values")
    try:
        previous, current = read_run(args.previous), read_run(args.current)
        if args.jev:
            if args.env_file:
                load_env(args.env_file)
            provider = JevChoice(allow_hosted=True)
            result = compare_with_jev(previous, current, provider, threshold=0.9)
        else:
            result = compare(previous, current)
    except (OSError, ValueError):
        print(json.dumps({"status": "unavailable", "reason": "invalid_record_or_provider_configuration",
                          "advisory": None, "originals_modified": False}))
        return 2
    print(json.dumps({"mode": "shadow", "originals_modified": False, **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
