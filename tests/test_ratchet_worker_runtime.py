from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ratchet_worker_runtime import run_worker, transport_observations


class WorkerRuntimeTests(unittest.TestCase):
    def test_retry_notices_are_observations_not_an_exact_retry_count(self):
        observed = transport_observations([{"type": "error", "message": "Reconnecting... 1/5"}],
                                          "stream disconnected: retrying\n")
        self.assertEqual(observed["retry_notice_events"], 1)
        self.assertEqual(observed["retry_notice_stderr_lines"], 1)
        self.assertIsNone(observed["retry_count"])
        self.assertIsNone(transport_observations([], "")["retry_count"])

    def test_duplicate_usage_is_unknown_instead_of_choosing_last(self):
        with tempfile.TemporaryDirectory(prefix="ratchet-worker-") as folder:
            code = "import json; e={'type':'turn.completed','usage':{'input_tokens':1}}; print(json.dumps(e)); print(json.dumps(e))"
            result = run_worker([sys.executable, "-c", code], "", Path(folder) / "worker", timeout=10)
            self.assertEqual(result["completed_turns"], 2)
            self.assertEqual(result["usage_status"], "AMBIGUOUS_DUPLICATES")
            self.assertIsNone(result["usage"])

    def test_timeout_is_preserved_without_invented_usage(self):
        with tempfile.TemporaryDirectory(prefix="ratchet-worker-") as folder:
            result = run_worker([sys.executable, "-c", "import time; time.sleep(20)"],
                                "", Path(folder) / "worker", timeout=.1)
            self.assertTrue(result["timed_out"])
            self.assertLess(result["elapsed_seconds"], 10)
            self.assertIsNone(result["usage"])
            self.assertEqual(result["completed_turns"], 0)


if __name__ == "__main__":
    unittest.main()
