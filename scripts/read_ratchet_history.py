"""Print both complete original files for the plain worker or a local fallback."""
import argparse
import hashlib
import json
from pathlib import Path


def read_history(root):
    result = []
    for side in (0, 1):
        path = root / f"attempt-{side}.jsonl"
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 8_000_000:
            raise ValueError("invalid history file")
        raw = path.read_bytes()
        result.append({"file": path.name, "sha256": hashlib.sha256(raw).hexdigest(),
                       "text": raw.decode("utf-8")})
    return {"kind": "complete_local_history", "records": result}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(read_history(args.root)))
