"""User-local plugin configuration; never stores API key values."""
import json
import os
from pathlib import Path
import shutil


def config_path():
    return Path(os.environ.get("DECISION_LAYER_CONFIG", str(Path.home() / ".codex" / "decision-layer.json")))


def configure(args):
    root = Path(args.root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Evidence root must be a directory")
    data = {"root": str(root), "provider": args.provider, "endpoint": args.endpoint,
            "model": args.model, "key_env": args.key_env,
            "env_file": str(Path(args.env_file).resolve(strict=True)) if args.env_file else None,
            "timeout": args.timeout, "drop_below": args.drop_below, "keep_above": args.keep_above}
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copyfile(path, path.with_suffix(".json.bak"))
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def serve():
    from argparse import Namespace
    from .cli import provider_from
    from .mcp_server import run

    path = config_path()
    if not path.exists():
        raise ValueError("Run evidence-selector configure --root PATH before starting the plugin")
    config = json.loads(path.read_text(encoding="utf-8"))
    provider = provider_from(Namespace(**config))
    run(config["root"], provider, config["drop_below"], config["keep_above"])
