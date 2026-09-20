import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import HTTPServer
from unittest.mock import patch

from evidence_selector.cli import evaluate, load_env
from evidence_selector.core import Candidate, evaluate_case, retrieve, select
from evidence_selector.eve_server import EveBackend, handler_for
from evidence_selector.providers import Answer, DecisionError, HttpProvider, NoRedirect


class Stub:
    name = "stub"

    def __init__(self, values):
        self.values = iter(values)
        self.calls = []

    def ask(self, state, question):
        self.calls.append((state, question))
        value = next(self.values)
        if isinstance(value, Exception):
            raise value
        return Answer(value, "stub-v1", {})


def candidates():
    return [Candidate("a", "x.py", "exact source\r\n", 8), Candidate("b", "y.py", "other source", 2)]


class SelectionTests(unittest.TestCase):
    def test_shadow_preserves_all_original_text_and_order(self):
        cs = candidates()
        result = select("query", cs, Stub([0.01, 0.99]))
        self.assertEqual(result["returned_ids"], ["a", "b"])
        self.assertEqual(result["proposed_drop_ids"], ["a"])
        self.assertEqual([c["text"] for c in result["candidates"]], [c.text for c in cs])
        self.assertEqual(result["actual_evidence_bytes_removed"], 0)

    def test_uncertain_and_threshold_boundary_retained(self):
        result = select("query", candidates(), Stub([0.1, 0.5]))
        self.assertFalse(result["proposed_drop_ids"])
        self.assertTrue(all(d["reason"] == "uncertain" for d in result["decisions"]))

    def test_transport_failure_opens_circuit_and_retains(self):
        provider = Stub([DecisionError("connection_failed")])
        result = select("query", candidates(), provider)
        self.assertFalse(result["proposed_drop_ids"])
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(result["decisions"][1]["error"], "circuit_open")

    def test_oversize_preserves_without_calling(self):
        provider = Stub([])
        result = select("query", candidates(), provider, max_state_bytes=1)
        self.assertFalse(provider.calls)
        self.assertFalse(result["proposed_drop_ids"])

    def test_length_rejection_does_not_suppress_next_snippet(self):
        result = select("query", candidates(), Stub([DecisionError("http_422"), 0.99]))
        self.assertEqual(result["decisions"][1]["probability"], 0.99)

    def test_labels_and_paths_not_sent_to_model(self):
        provider = Stub([0.5])
        candidate = Candidate.parse({"id": "critical-secret", "source": "private-path", "text": "passage", "label": True})
        select("query", [candidate], provider)
        self.assertEqual(json.loads(provider.calls[0][0]), {"query": "query", "passage": "passage"})

    def test_bad_probabilities_fail_open(self):
        for value in (float("nan"), float("inf"), True, "0.1", -0.1, 1.1):
            with self.subTest(value=value):
                result = select("query", candidates(), Stub([value]))
                self.assertFalse(result["proposed_drop_ids"])
                self.assertEqual(result["decisions"][0]["error"], "invalid_probability")

    def test_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):
            select("query", [candidates()[0]] * 2)

    def test_invalid_thresholds_rejected(self):
        for value in (float("nan"), -1, 1):
            with self.assertRaises(ValueError):
                select("query", candidates(), drop_below=value)

    def test_eval_reports_missed_critical_evidence(self):
        result = select("query", candidates(), Stub([0.01, 0.99]))
        metrics = evaluate_case({"id": "case", "labels": {"a": True, "b": False}, "critical_ids": ["a"]}, result)
        self.assertEqual(metrics["missed_critical_ids"], ["a"])
        self.assertEqual(metrics["proposed_recall"], 0)
        self.assertEqual(metrics["proposed_precision"], 0)

    def test_invalid_labels_rejected_before_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cases.json"
            path.write_text(json.dumps({"cases": [{"id": "case", "query": "q", "candidates": [{"id": "a", "source": "x", "text": "y"}], "labels": {}}]}))
            provider = Stub([])
            with self.assertRaises(ValueError):
                evaluate(path, provider)
            self.assertFalse(provider.calls)

    def test_retrieve_exact_spans_and_stable_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.txt"
            path.write_bytes(b"one\r\ntwo\r\nthree")
            result = retrieve(tmp, ["x.txt", "x.txt"], 2)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0].text, "one\r\ntwo\r\n")
            self.assertEqual(result[1].start_line, 3)
            self.assertEqual(result, retrieve(tmp, ["x.txt"], 2))
            path.write_bytes(b"changed")
            self.assertNotEqual(result[0].id, retrieve(tmp, ["x.txt"], 2)[0].id)

    def test_path_escape_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            (Path(tmp) / "outside.txt").write_text("secret")
            with self.assertRaises(ValueError):
                retrieve(root, ["../outside.txt"])

    def test_baseline_scores_are_not_probabilities(self):
        result = select("exact", candidates())
        self.assertTrue(all(d["probability"] is None for d in result["decisions"]))


class TransportTests(unittest.TestCase):
    @contextlib.contextmanager
    def endpoint(self, backend):
        server = HTTPServer(("127.0.0.1", 0), handler_for(backend))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/v1/systemone"
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_eve_http_roundtrip_with_fake_backend(self):
        class Backend:
            def decide(self, body):
                assert body["questions"]["relevant"]["type"] == "noul"
                return {"model": "fixture-only", "answers": {"relevant": {"type": "noul", "noul": 0.8}}}
        with self.endpoint(Backend()) as url:
            answer = HttpProvider("eve", url).ask("state", "Relevant?")
            self.assertEqual(answer.probability, 0.8)
            self.assertEqual(answer.model, "fixture-only")

    def test_malformed_answer_retains_evidence(self):
        class Backend:
            def decide(self, body):
                return {"model": "fixture-only", "answers": {}}
        with self.endpoint(Backend()) as url:
            result = select("query", candidates(), HttpProvider("eve", url))
            self.assertFalse(result["proposed_drop_ids"])
            self.assertEqual(result["decisions"][0]["error"], "invalid_response")

    def test_rejects_nonlocal_eve_and_redirected_hosted_endpoint(self):
        for args in (("eve", "http://example.com/v1/systemone"), ("typesafe", "https://example.com")):
            with self.assertRaises(ValueError):
                HttpProvider(*args)

    def test_dotenv_does_not_expand_or_print_secrets(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            path = Path(tmp) / ".env"
            path.write_text('SECRET="literal$(command)$OTHER" # comment\nEXISTING=new\n')
            os.environ["EXISTING"] = "original"
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                load_env(path)
            self.assertEqual(os.environ["SECRET"], "literal$(command)$OTHER")
            self.assertEqual(os.environ["EXISTING"], "original")
            self.assertEqual(output.getvalue(), "")

    def test_hosted_adapters_send_expected_contract(self):
        for provider, endpoint in (("typesafe", "https://api.typesafe.ai/v1/systemone"),
                                   ("openrouter", "https://openrouter.ai/api/alpha/decisions")):
            with self.subTest(provider=provider), patch.dict(os.environ, {"TEST_KEY": "fixture-key"}):
                client = HttpProvider(provider, key_env="TEST_KEY")
                class Opener:
                    def open(inner, request, timeout):
                        self.assertEqual(request.full_url, endpoint)
                        self.assertEqual(request.get_header("Authorization"), "Bearer fixture-key")
                        body = json.loads(request.data)
                        self.assertEqual(body["state"], "state")
                        self.assertEqual(body["questions"]["relevant"], {"type": "noul", "instructions": "Relevant?"})
                        return io.BytesIO(json.dumps({"model": "fixture-model", "answers": {
                            "relevant": {"type": "noul", "noul": 0.3}},
                            "usage": {"cost": 0.0001, "input_tokens": 42, "arbitrary": "not retained"}}).encode())
                client.opener = Opener()
                answer = client.ask("state", "Relevant?")
                self.assertEqual(answer.probability, 0.3)
                self.assertEqual(answer.usage, {"cost": 0.0001, "input_tokens": 42})

    def test_redirects_refused(self):
        with self.assertRaisesRegex(DecisionError, "redirect_refused"):
            NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://other.example")


class EveBudgetTests(unittest.TestCase):
    def backend(self):
        from types import SimpleNamespace
        backend = EveBackend.__new__(EveBackend)
        backend.model = "eve-local"
        backend.noul = lambda text: text
        backend.to_question = lambda state, question: question
        backend.prefix = lambda state: "Context: " + state
        backend.suffix = lambda question: " Question: " + question
        backend.decider = SimpleNamespace(
            tok=SimpleNamespace(encode=lambda text, **kw: list(text)),
            policy=SimpleNamespace(prepend_bos=False),
            ask=lambda state, questions, **kw: [{"p_true": 0.7} for q in questions])
        return backend

    def test_length_rejected_before_inference(self):
        backend = self.backend()
        backend.decider.ask = lambda *a, **kw: self.fail("Inference must not run on oversized prompts")
        with self.assertRaisesRegex(ValueError, "512"):
            backend.decide({"model": "eve-local", "state": "x" * 500,
                            "questions": {"a": {"type": "noul", "instructions": "Relevant?"}}})

    def test_real_api_shape_and_no_truncation_receipt(self):
        result = self.backend().decide({"model": "eve-local", "state": "short passage",
                                       "questions": {"a": {"type": "noul", "instructions": "Relevant?"}}})
        self.assertEqual(result["answers"]["a"], {"type": "noul", "noul": 0.7})
        self.assertFalse(result["diagnostics"]["truncated"])


if __name__ == "__main__":
    unittest.main()
