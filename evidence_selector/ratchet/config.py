"""Machine-local root configuration; no credential values or implicit uploads."""
import json
import os
from pathlib import Path
import tempfile


def config_path():
    return Path(os.environ.get("RATCHET_CONFIG", Path.home() / ".codex" / "ratchet.json"))


def configure(root):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("record root must be a directory")
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"schema": 1, "root": str(root), "mode": "shadow", "provider": "deterministic"}
    if path.exists():
        backup = path.with_suffix(".json.bak")
        backup.write_bytes(path.read_bytes())
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


def saved_root():
    path = config_path()
    if not path.exists():
        raise ValueError("Run ratchet configure --root PATH before starting the plugin")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("schema") != 1 or data.get("mode") != "shadow"
        or data.get("provider") != "deterministic" or not isinstance(data.get("root"), str)
        or not data["root"].strip() or not Path(data["root"]).is_absolute()):
        raise ValueError("Invalid Ratchet settings; repair with ratchet configure --root PATH")
    return data["root"]
