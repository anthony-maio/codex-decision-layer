import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from evidence_selector.core import retrieve
from evidence_selector.gguf_server import GgufBackend, render_noul
from evidence_selector.plugin import configure


class GgufTests(unittest.TestCase):
    def backend(self, probabilities=None, tokens=None):
        backend = GgufBackend.__new__(GgufBackend)
        backend.model = "test"
        backend.letter_ids = (362, 425)
        calls = []
        def post(route, body):
            calls.append((route, body))
            if route == "/tokenize":
                return {"tokens": tokens if tokens is not None else [1, 2, 3]}
            return {"completion_probabilities": [{"top_probs": probabilities or [
                {"id": 362, "prob": 0.3}, {"id": 425, "prob": 0.1}, {"id": 220, "prob": 0.6}]}]}
        backend.post = post
        return backend, calls

    def payload(self):
        return {"model": "test", "state": "passage", "questions": {"relevant": {"type": "noul", "instructions": "Relevant?"}}}

    def test_renormalizes_only_decision_letters(self):
        backend, calls = self.backend()
        result = backend.decide(self.payload())
        self.assertAlmostEqual(result["answers"]["relevant"]["noul"], 0.75)
        self.assertEqual(calls[-1][1]["temperature"], 1.0)
        self.assertEqual(calls[-1][1]["samplers"], ["temperature"])
        self.assertFalse(calls[-1][1]["cache_prompt"])
        self.assertEqual(calls[-1][1]["prompt"], [1, 2, 3])

    def test_missing_letter_is_an_error(self):
        backend, _ = self.backend([{"id": 362, "prob": 1.0}])
        with self.assertRaises(KeyError):
            backend.decide(self.payload())

    def test_oversize_never_reaches_completion(self):
        backend, calls = self.backend(tokens=list(range(513)))
        with self.assertRaisesRegex(ValueError, "512"):
            backend.decide(self.payload())
        self.assertEqual(len(calls), 1)

    def test_invalid_probability_rejected(self):
        backend, _ = self.backend([{"id": 362, "prob": 1.5}, {"id": 425, "prob": 0.1}])
        with self.assertRaises(ValueError):
            backend.decide(self.payload())

    def test_prompt_matches_reference_format(self):
        self.assertEqual(render_noul(" passage \n", " Relevant? "),
            "User: Context:\npassage\n\nQuestion: Relevant?\nOptions:\nA) true\nB) false\nAnswer with the letter only.\nAssistant: The answer is")

    def test_remote_llama_endpoint_rejected(self):
        with self.assertRaises(ValueError):
            GgufBackend("https://example.com")


class PluginTests(unittest.TestCase):
    def test_config_has_paths_not_key_values_and_preserves_previous(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            env = Path(tmp) / ".env"
            env.write_text("TYPESAFE_API_KEY=never-copy-this")
            args = SimpleNamespace(root=tmp, provider="typesafe", endpoint=None, model=None,
                                   key_env=None, env_file=str(env), timeout=15, drop_below=.1, keep_above=.9)
            with patch.dict(os.environ, {"DECISION_LAYER_CONFIG": str(path)}):
                configure(args)
                first = path.read_text()
                self.assertNotIn("never-copy-this", first)
                args.provider = "baseline"
                configure(args)
                self.assertEqual(path.with_suffix(".json.bak").read_text(), first)
                self.assertEqual(json.loads(path.read_text())["provider"], "baseline")

    def test_dotenv_is_not_an_evidence_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".env").write_text("SECRET=value")
            with self.assertRaises(ValueError):
                retrieve(tmp, [".env"])


if __name__ == "__main__":
    unittest.main()
