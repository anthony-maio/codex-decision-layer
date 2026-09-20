import hashlib
import json
from pathlib import Path
import unittest

from evidence_selector.benchmark import bm25, replay
from evidence_selector.core import Candidate

ROOT = Path(__file__).resolve().parents[1]


class BenchmarkTests(unittest.TestCase):
    def test_frozen_inputs_are_unchanged(self):
        manifest = json.loads((ROOT / "fixtures/public/frozen.json").read_text())
        for file, expected in manifest["sha256"].items():
            with self.subTest(file=file):
                self.assertEqual(hashlib.sha256((ROOT/file).read_bytes()).hexdigest(), expected)

    def test_split_isolation_and_labels(self):
        splits = {}
        for split in ("dev", "holdout"):
            data = json.loads((ROOT/f"fixtures/public/{split}.json").read_text())
            hashes, sources = set(), set()
            for case in data["cases"]:
                self.assertTrue(set(case["critical_ids"]) <= {k for k,v in case["labels"].items() if v})
                self.assertTrue(set(case["contradiction_ids"]) <= {k for k,v in case["labels"].items() if v})
                self.assertTrue(all(not case["labels"][i] for i in case["hard_negative_ids"]))
                hashes.update(hashlib.sha256(c["text"].encode()).hexdigest() for c in case["candidates"])
                sources.update(c["source"] for c in case["candidates"])
            splits[split] = hashes, sources
            result = replay(data, "retain-all")
            self.assertTrue(result["summary"]["gates"]["Q1"])
            self.assertFalse(result["summary"]["gates"]["U1"])
        self.assertFalse(splits["dev"][0] & splits["holdout"][0])
        self.assertFalse(splits["dev"][1] & splits["holdout"][1])

    def test_bm25_ties_preserve_original_order(self):
        candidates = [Candidate(str(i), "public", "same tokens") for i in range(6)]
        self.assertEqual(bm25("missing", candidates), {"0", "1", "2"})
