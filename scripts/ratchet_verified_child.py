"""Bind experiment child imports to the inspected checkout and report hashes."""
from __future__ import annotations
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import sys
from ratchet_atomic import atomic

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def provenance(mode, require_freeze=False):
    names = ["evidence_selector", "evidence_selector.ratchet.records"]
    names += (["evidence_selector.ratchet.pytest_reporter"] if mode == "pytest" else
              ["evidence_selector.cli", "evidence_selector.providers", "evidence_selector.ratchet.cli",
               "evidence_selector.ratchet.mcp_server", "evidence_selector.ratchet.secure_io",
               "evidence_selector.ratchet.semantic"])
    hashes = {}
    for name in names:
        module = importlib.import_module(name)
        actual = Path(module.__file__).resolve()
        relative = name.replace(".", "/")
        expected = ROOT / (relative + ".py")
        if not expected.exists():
            expected = ROOT / relative / "__init__.py"
        if actual != expected.resolve():
            raise ValueError("child imported an unexpected module origin")
        hashes[actual.relative_to(ROOT).as_posix()] = hashlib.sha256(actual.read_bytes()).hexdigest()
    freeze_path = ROOT / "fixtures/ratchet/workflow-v1/freeze.json"
    freeze_sha = None
    if require_freeze:
        raw = freeze_path.read_bytes()
        frozen = json.loads(raw)
        for relative, observed in hashes.items():
            if frozen["sha256"].get(relative) != observed:
                raise ValueError("child module differs from the frozen input")
        own = Path(__file__).resolve().relative_to(ROOT).as_posix()
        if frozen["sha256"].get(own) != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
            raise ValueError("child verifier differs from frozen input")
        freeze_sha = hashlib.sha256(raw).hexdigest()
    return {"status": "VERIFIED", "mode": mode, "module_sha256": hashes, "freeze_sha256": freeze_sha}


def main():
    p = argparse.ArgumentParser(allow_abbrev=False)
    p.add_argument("mode", choices=("pytest", "mcp"))
    p.add_argument("--provenance", type=Path, required=True)
    p.add_argument("--require-freeze", action="store_true")
    p.add_argument("--test-proof", action="store_true")
    args, child_args = p.parse_known_args()
    receipt = provenance(args.mode, args.require_freeze)
    child_args = child_args[1:] if child_args[:1] == ["--"] else child_args
    with args.provenance.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(receipt, indent=2) + "\n")
    if args.mode == "pytest":
        import pytest
        before = hashlib.sha256(Path("product.py").read_bytes()).hexdigest() if args.test_proof else None
        code = pytest.main(child_args)
        if args.test_proof:
            index = child_args.index("--ratchet-output")
            record = Path(child_args[index + 1])
            if record.resolve().parent != Path.cwd().resolve():
                raise ValueError("worker test proof requires a workspace-local record")
            receipt.update(test_exit_code=int(code), test_completed=True,
                           source_sha256_before=before,
                           source_sha256_after=hashlib.sha256(Path("product.py").read_bytes()).hexdigest(),
                           record=record.name, record_sha256=hashlib.sha256(record.read_bytes()).hexdigest())
            atomic(args.provenance, receipt)
        return code
    from evidence_selector.ratchet.cli import main as server_main
    sys.argv = ["ratchet", "mcp", *child_args]
    return server_main()


if __name__ == "__main__":
    raise SystemExit(main())
