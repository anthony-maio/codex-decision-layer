import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ratchet_atomic import atomic
from run_ratchet_workflow_amended import FLAG, MARKER, amended_command, audit_output, canonical_sha, guarded_write, validate_review


class AmendmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ratchet-amendment-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "result.json"
        self.rows = [{"index": i, "quality_pass": True, "method_compliance": i == 0,
                      "total_cost": None if i else 1} for i in range(3)]
        self.packet = {"original_first_three_sha256": canonical_sha(self.rows)}
        self.marker = "test-amendment-sha"
        self.result = {"kind": "ORIGINAL", "trials": copy.deepcopy(self.rows)}
        atomic(self.path, self.result)

    def write(self, result):
        guarded_write(self.path, result, self.packet, self.marker, atomic)

    def test_command_delta_is_only_required_flag_after_first_triplet(self):
        command = ["codex", "exec", "--json", "-"]
        for method in ("plain", "deterministic", "jev"):
            self.assertEqual(amended_command(command, method, 2), command)
        self.assertEqual(amended_command(command, "plain", 3), command)
        for method in ("deterministic", "jev"):
            self.assertEqual(amended_command(command, method, 3), command[:-1] + ["-c", FLAG, "-"])
        self.assertEqual(command, ["codex", "exec", "--json", "-"])

    def test_claim_and_recovered_base_receipt_preserve_amendment(self):
        self.result["pending"] = {"slot": {"index": 3}, "phase": "PREPARING"}
        self.write(self.result)
        self.assertEqual(self.result["pending"][MARKER], self.marker)
        self.result["pending"]["phase"] = "LAUNCHING"
        self.write(self.result)
        self.result.pop("pending")
        self.result["trials"].append({"index": 3, "status": "COMPLETE"})
        self.write(self.result)
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved["trials"][:3], self.rows)
        self.assertEqual(saved["trials"][3][MARKER], self.marker)
        self.assertEqual(saved["execution_amendment"]["sha256"], self.marker)

    def test_interrupted_claim_retains_attribution_and_failure(self):
        self.result["pending"] = {"slot": {"index": 3}, "phase": "PREPARING"}
        self.write(self.result)
        self.result.pop("pending")
        self.result["trials"].append({"index": 3, "status": "INTERRUPTED", "quality_pass": False})
        self.write(self.result)
        self.assertFalse(self.result["trials"][3]["quality_pass"])
        self.assertEqual(self.result["trials"][3][MARKER], self.marker)

    def test_unamended_pending_or_completed_attempt_is_detected(self):
        self.result["pending"] = {"slot": {"index": 3}, "phase": "LAUNCHING"}
        atomic(self.path, self.result)
        with self.assertRaisesRegex(ValueError, "lacks amendment"):
            self.write(self.result)
        self.result.pop("pending")
        self.result["trials"].append({"index": 3})
        atomic(self.path, self.result)
        with self.assertRaisesRegex(ValueError, "unamended entry point"):
            self.write(self.result)

    def test_original_failed_method_row_cannot_be_rewritten(self):
        self.result["trials"][1]["method_compliance"] = True
        with self.assertRaisesRegex(ValueError, "first three"):
            self.write(self.result)
        self.assertEqual(json.loads(self.path.read_text())["trials"], self.rows)

    def test_empty_input_manifest_cannot_freeze_amendment(self):
        with self.assertRaisesRegex(ValueError, "input coverage"):
            validate_review({"sha256": {}})

    def test_completed_state_audit_detects_unamended_final_rows(self):
        self.result["status"] = "COMPLETE"
        self.result["trials"] += [{"index": i} for i in range(3, 45)]
        atomic(self.path, self.result)
        with self.assertRaisesRegex(ValueError, "unamended entry point"):
            audit_output(self.path, self.packet, self.marker)
        self.assertFalse(self.path.with_suffix(".json.lock").exists())

    def test_audit_respects_existing_experiment_lock(self):
        lock = self.path.with_suffix(".json.lock")
        lock.write_text('{"pid":1}')
        with self.assertRaises(FileExistsError):
            audit_output(self.path, self.packet, self.marker)
        self.assertTrue(lock.exists())


if __name__ == "__main__":
    unittest.main()
