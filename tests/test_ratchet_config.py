import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evidence_selector.ratchet.config import configure, saved_root


class ConfigTests(unittest.TestCase):
    def test_settings_require_absolute_nonempty_root(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "ratchet.json"
            with patch.dict(os.environ, {"RATCHET_CONFIG": str(config)}):
                for root in ("", " ", "..", "records", None):
                    config.write_text(json.dumps({"schema": 1, "mode": "shadow",
                        "provider": "deterministic", "root": root}), encoding="utf-8")
                    with self.subTest(root=root), self.assertRaisesRegex(ValueError, "repair"):
                        saved_root()
                configure(temp)
                self.assertEqual(saved_root(), str(Path(temp).resolve()))
                before = config.read_bytes()
                configure(temp)
                self.assertEqual(config.with_suffix(".json.bak").read_bytes(), before)
