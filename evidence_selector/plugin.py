"""User-local plugin configuration; never stores API key values."""
import json
import os
from pathlib import Path
import shutil


def config_path():
    return Path(os.environ.get("DECISION_LAYER_CONFIG", str(Path.home() / ".codex" / "decision-layer.json")))


def configure(args):
    from .core import Candidate, select
    from .providers import HttpProvider
    select("configuration check", [Candidate("check", "check", "check")], drop_below=args.drop_below, keep_above=args.keep_above)
    if args.provider != "baseline":
        HttpProvider(args.provider, args.endpoint, args.key_env, args.model, args.timeout, require_key=False)
    if args.env_file and not Path(args.env_file).is_file():
        raise ValueError("env-file must be an existing file")
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
    import tempfile
    staged = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            staged = Path(stream.name)
            stream.write(json.dumps(data, indent=2) + "\n")
        os.replace(staged, path)
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)
    return path


def serve():
    from argparse import Namespace
    from .cli import provider_from
    from .mcp_server import run

    path = config_path()
    if not path.exists():
        raise ValueError("Run evidence-selector configure --root PATH before starting the plugin")
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {"root", "provider", "endpoint", "model", "key_env", "env_file", "timeout", "drop_below", "keep_above"}
    if not isinstance(config, dict) or not required <= config.keys():
        raise ValueError("Invalid plugin settings. Repair with evidence-selector configure --root PATH")
    provider = provider_from(Namespace(**config))
    run(config["root"], provider, config["drop_below"], config["keep_above"])
