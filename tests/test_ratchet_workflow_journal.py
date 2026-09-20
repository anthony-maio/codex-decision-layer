from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_ratchet_workflow as runner
import ratchet_atomic
from ratchet_workflow_metrics import schedule


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ratchet-journal-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "repo"
        self.root.mkdir()
        self.freeze = self.base / "freeze.json"
        self.freeze.write_text("{}")
        self.keyfile = self.base / "placeholder.env"
        self.keyfile.write_text("# no credentials; no actual worker launches\n")
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for target, value in [("ROOT", self.root), ("FREEZE", self.freeze)]:
            self.stack.enter_context(patch.object(runner, target, value))
        self.stack.enter_context(patch.object(runner, "validate", return_value=({"original_platform": sys.platform,
            "codex_cli": "codex-cli 0.146.0", "schedule": schedule()}, "frozen-test-commit")))
        self.stack.enter_context(patch.object(runner, "validate_history", return_value={"test": True}))
        self.stack.enter_context(patch.object(runner, "version", side_effect=lambda name: "8.4.2" if name == "pytest" else "1.30.0"))
        self.stack.enter_context(patch.object(runner.shutil, "which", return_value="codex"))
        self.stack.enter_context(patch.object(runner.subprocess, "check_output", return_value="codex-cli 0.146.0"))

    def invoke(self, private, *extra):
        with patch.object(sys, "argv", ["runner", "--private-dir", str(private), "--history-dir", str(self.base / "history"),
                                      "--env-file", str(self.keyfile), *extra]):
            runner.main()

    def test_changing_private_directory_cannot_retry_a_claimed_slot(self):
        with patch.object(runner, "run_trial", side_effect=RuntimeError("injected interruption")) as worker:
            with self.assertRaises(RuntimeError):
                self.invoke(self.base / "first")
            with self.assertRaisesRegex(ValueError, "attempted slot"):
                self.invoke(self.base / "second")
            self.assertEqual(worker.call_count, 1)
        result = json.loads((self.root / "results/ratchet/workflow-v1.json").read_text())
        self.assertEqual(result["pending"]["slot"]["index"], 0)
        self.assertEqual(result["trials"], [])

    def test_output_lock_prevents_concurrent_private_directories(self):
        def attempt(slot, private, *args, **kwargs):
            with self.assertRaises(FileExistsError):
                self.invoke(self.base / "second")
            return {**slot, "quality_pass": False, "method_compliance": False, "elapsed_seconds": 1, "total_cost": {"lower_usd": None, "upper_usd": None}}
        with patch.object(runner, "run_trial", side_effect=attempt):
            self.invoke(self.base / "first")

    def test_completed_private_receipt_is_recovered_without_relaunch(self):
        private_root = self.base / "first"
        def attempt(slot, private, *args, **kwargs):
            (private / "worker").mkdir(parents=True)
            raw = b'{}\n'
            (private / "worker/events.jsonl").write_bytes(raw)
            result = {**slot, "status": "COMPLETE", "worker_events_sha256": hashlib.sha256(raw).hexdigest()}
            (private / "result.json").write_text(json.dumps(result))
            raise RuntimeError("after result saved")
        with patch.object(runner, "run_trial", side_effect=attempt) as worker:
            with self.assertRaises(RuntimeError):
                self.invoke(private_root)
            self.invoke(private_root, "--recover-completed")
            self.assertEqual(worker.call_count, 1)
        result = json.loads((self.root / "results/ratchet/workflow-v1.json").read_text())
        self.assertEqual(len(result["trials"]), 1)
        self.assertNotIn("pending", result)

    def test_prelaunch_failure_can_be_finalized_without_a_worker(self):
        private = self.base / "first"
        with patch.object(runner, "run_trial", side_effect=RuntimeError("before launch")) as worker:
            with self.assertRaises(RuntimeError):
                self.invoke(private)
            self.invoke(private, "--finalize-interrupted")
            self.assertEqual(worker.call_count, 1)
        result = json.loads((self.root / "results/ratchet/workflow-v1.json").read_text())
        self.assertEqual(result["trials"][0]["status"], "INTERRUPTED")
        self.assertIsNone(result["trials"][0]["total_cost"]["upper_usd"])

    def test_interrupted_atomic_write_preserves_last_complete_receipt(self):
        target = self.base / "receipt.json"
        ratchet_atomic.atomic(target, {"state": "old"})
        with patch.object(ratchet_atomic.os, "replace", side_effect=OSError("injected failed replace")):
            with self.assertRaises(OSError):
                ratchet_atomic.atomic(target, {"state": "new"})
        self.assertEqual(json.loads(target.read_text()), {"state": "old"})


if __name__ == "__main__":
    unittest.main()
