import io
import json
import unittest
from unittest.mock import patch
import urllib.error

from evidence_selector.providers import DecisionError
from evidence_selector.ratchet.records import Run
from evidence_selector.ratchet.semantic import CRITERIA, JevChoice, compare_with_jev


def run(identity, text, complete=True):
    report = {"stage": "call", "nodeid": "test_case", "outcome": "failed", "longrepr": text}
    return Run(identity, "private/repo", identity, (report,), 1, complete,
               "private-task", ("-q",), ("test_case",))


def response(**override):
    answer = {"type": "choice", "choice": "same_blocker", "confidence": 0.7,
              "probabilities": {"same_blocker": 0.9, "different_blocker": 0.05, "insufficient_evidence": 0.05}}
    answer.update(override)
    return {"model": "jev-1.13.0", "answers": {"relationship": answer},
            "usage": {"input_tokens": 120, "output_tokens": 20}}


class Opener:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def open(self, request, **kwargs):
        self.calls.append(request)
        if isinstance(self.value, Exception):
            raise self.value
        return io.BytesIO(json.dumps(self.value).encode())


class SemanticTests(unittest.TestCase):
    def provider(self, value):
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "test-only"}):
            provider = JevChoice(allow_hosted=True)
        provider.transport.opener = Opener(value)
        return provider

    def test_hosted_upload_requires_opt_in(self):
        with self.assertRaises(ValueError):
            JevChoice()

    def test_unresolved_comparison_uses_choices_without_private_metadata(self):
        provider = self.provider(response())
        result = compare_with_jev(run("a", "E old wrapper"), run("b", "E new wrapper"), provider)
        self.assertEqual(result["relationship"], "same_blocker")
        self.assertIsNone(result["advisory"])
        payload = json.loads(provider.transport.opener.calls[0].data)
        self.assertEqual(set(payload["questions"]["relationship"]["criteria"]), set(CRITERIA))
        self.assertNotIn("private/repo", json.dumps(payload))
        self.assertNotIn("private-task", json.dumps(payload))

    def test_partial_and_exact_evidence_do_not_call_provider(self):
        provider = self.provider(response())
        for first, second in ((run("a", "E a", False), run("b", "E b")),
                              (run("a", "E identical"), run("b", "E identical"))):
            self.assertEqual(compare_with_jev(first, second, provider)["provider_calls"], 0)
        self.assertEqual(provider.transport.opener.calls, [])

    def test_large_evidence_abstains_without_truncation_or_upload(self):
        provider = self.provider(response())
        result = compare_with_jev(run("a", "E " + "a" * 25000), run("b", "E b"), provider)
        self.assertEqual(result["reason"], "semantic_input_too_large")
        self.assertEqual(provider.transport.opener.calls, [])

    def test_provider_failures_preserve_evidence_without_retry(self):
        errors = [TimeoutError(), urllib.error.URLError("private error body"),
                  urllib.error.HTTPError("https://api.typesafe.ai", 429, "quota", {}, None),
                  urllib.error.HTTPError("https://api.typesafe.ai", 503, "unavailable", {}, None)]
        for error in errors:
            provider = self.provider(error)
            result = compare_with_jev(run("a", "E a"), run("b", "E b"), provider)
            self.assertEqual(result["relationship"], "insufficient_evidence")
            self.assertEqual(result["evidence"], ["a", "b"])
            self.assertEqual(len(provider.transport.opener.calls), 1)
            self.assertNotIn("private error", json.dumps(result))
            self.assertIsNone(result["advisory"])

    def test_invalid_distributions_and_malformed_responses_fail_open(self):
        invalid = [response(probabilities={"same_blocker": 1.0}),
                   response(choice="different_blocker"), response(confidence=float("nan")),
                   response(probabilities={k: 0.9 for k in CRITERIA}), {"answers": {}},
                   response(probabilities={"same_blocker": True, "different_blocker": 0, "insufficient_evidence": 0})]
        for value in invalid:
            result = compare_with_jev(run("a", "E a"), run("b", "E b"), self.provider(value))
            self.assertEqual(result["reason"], "provider_failure")
            self.assertEqual(result["relationship"], "insufficient_evidence")

    def test_uncertain_answer_does_not_become_same_blocker(self):
        provider = self.provider(response(probabilities={"same_blocker": 0.6, "different_blocker": 0.3,
                                                         "insufficient_evidence": 0.1}))
        result = compare_with_jev(run("a", "E a"), run("b", "E b"), provider)
        self.assertEqual(result["relationship"], "insufficient_evidence")
        self.assertEqual(result["reason"], "semantic_abstention")


if __name__ == "__main__":
    unittest.main()
