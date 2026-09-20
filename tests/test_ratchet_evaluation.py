import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.build_ratchet_holdout import normalize_traceback
from scripts.evaluate_ratchet_holdout import atomic_save, complete_coverage, incremental, metrics, validate_freeze


class EvaluationTests(unittest.TestCase):
    def test_partial_duplicate_and_wrong_case_coverage_cannot_pass(self):
        self.assertFalse(complete_coverage("STOPPED_PROVIDER_ERROR", [{"id": "a"}], ["a"]))
        self.assertFalse(complete_coverage("COMPLETE", [{"id": "a"}], ["a", "b"]))
        self.assertFalse(complete_coverage("COMPLETE", [{"id": "a"}, {"id": "a"}], ["a", "b"]))
        self.assertTrue(complete_coverage("COMPLETE", [{"id": "b"}, {"id": "a"}], ["a", "b"]))

    def test_no_same_predictions_fails_and_critical_false_positive_fails(self):
        missed = [{"expected": "same_blocker", "relationship": "insufficient_evidence", "critical": False}]
        self.assertFalse(metrics(missed)["classification_gate"])
        rows = [{"expected": "same_blocker", "relationship": "same_blocker", "critical": False}] * 100
        rows += [{"expected": "different_blocker", "relationship": "same_blocker", "critical": True}]
        result = metrics(rows)
        self.assertGreater(result["same_precision"], .95)
        self.assertFalse(result["classification_gate"])

    def test_incremental_gate_requires_three_recoveries_and_no_new_false_positive(self):
        base = [{"id": str(i), "expected": "same_blocker", "relationship": "insufficient_evidence"} for i in range(3)]
        current = [{**r, "relationship": "same_blocker"} for r in base]
        self.assertTrue(incremental(current, base)["incremental_semantic_gate"])
        base += [{"id": "negative", "expected": "different_blocker", "relationship": "insufficient_evidence"}]
        current += [{"id": "negative", "expected": "different_blocker", "relationship": "same_blocker"}]
        self.assertFalse(incremental(current, base)["incremental_semantic_gate"])
        with self.assertRaises(ValueError):
            incremental(current[:-1], base)

    def test_atomic_checkpoint_keeps_prior_receipt_on_replace_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "receipt.json"
            path.write_text('{"rows": [1]}', encoding="utf-8")
            with patch("scripts.evaluate_ratchet_holdout.os.replace", side_effect=OSError("interrupted")):
                with self.assertRaises(OSError):
                    atomic_save(path, {"rows": [1, 2]})
            self.assertEqual(json.loads(path.read_text()), {"rows": [1]})
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_freeze_must_include_required_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "fixtures/ratchet/holdout-v1/freeze.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"status": "FROZEN_BEFORE_SCORING", "threshold": .9,
                "model": "jev-1.13.0", "checkpoint": "b60386f", "corpus": "fixtures/ratchet/holdout-v1/corpus.json",
                "review": "fixtures/ratchet/holdout-v1/review.json", "sha256": {}}), encoding="utf-8")
            with patch("scripts.evaluate_ratchet_holdout.ROOT", root), self.assertRaisesRegex(ValueError, "incomplete"):
                validate_freeze(path)

    def test_path_normalization_does_not_rewrite_literal_causal_evidence(self):
        text = "C:\\source\\module.py:12: in <genexpr>\n    raise ValueError(r'a\\b')\nE   ValueError: a\\b\n"
        normalized = normalize_traceback(text, [("C:\\source", "<PUBLIC>")])
        # Prefix matching uses the host separator, but slash normalization is
        # restricted to the frame either way. Source/message bytes stay exact.
        self.assertEqual(normalized.splitlines()[1:], text.splitlines()[1:])
        self.assertNotIn("\\", normalized.splitlines()[0])
