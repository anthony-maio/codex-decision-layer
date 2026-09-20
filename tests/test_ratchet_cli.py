import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evidence_selector.ratchet.cli import main


class CliTests(unittest.TestCase):
    def test_recorded_demo_never_calls_network_and_contains_evidence(self):
        output = io.StringIO()
        with patch("sys.argv", ["ratchet", "demo", "--json"]), contextlib.redirect_stdout(output), \
             patch("socket.socket.connect", side_effect=AssertionError("network forbidden")), \
             patch("socket.getaddrinfo", side_effect=AssertionError("DNS forbidden")):
            self.assertEqual(main(), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["provider_calls_this_run"], 0)
        self.assertEqual(result["kind"], "recorded_authored_development_replay")
        self.assertTrue(all(case["records"] for case in result["examples"]))
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(result["receipt_sha256"], hashlib.sha256((root / "results/ratchet/dev-jev.json").read_bytes()).hexdigest())

    def test_compare_invalid_record_preserves_original(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "evidence.jsonl"
            path.write_text("not JSON\n", encoding="utf-8")
            original = path.read_bytes()
            with patch("sys.argv", ["ratchet", "compare", str(path), str(path)]), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(), 2)
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(json.loads(output.getvalue())["originals_modified"])


if __name__ == "__main__":
    unittest.main()
