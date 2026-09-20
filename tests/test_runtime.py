import contextlib
import http.client
import io
import socket
import threading
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evidence_selector.core import Candidate, retrieve, select
from evidence_selector.providers import HttpProvider
from evidence_selector.server_runtime import bind_server


class RuntimeTests(unittest.TestCase):
    def test_truncated_http_response_retains_every_original(self):
        provider = HttpProvider("eve")
        provider.opener.open = lambda *a, **k: (_ for _ in ()).throw(http.client.IncompleteRead(b"private"))
        originals = [Candidate("a", "a", "first"), Candidate("b", "b", "second")]
        result = select("query", originals, provider)
        self.assertEqual(result["returned_ids"], ["a", "b"])
        self.assertEqual(result["proposed_drop_ids"], [])
        self.assertEqual([d["error"] for d in result["decisions"]], ["connection_failed", "circuit_open"])
        self.assertNotIn("private", str(result))

    def test_credential_path_case_variants_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in (".ENV", ".EnV.local", ".GIT/config"):
                path = root / name
                path.parent.mkdir(exist_ok=True)
                path.write_text("secret")
                with self.assertRaisesRegex(ValueError, "Credential"):
                    retrieve(root, [name])

    def test_occupied_port_fails_before_model_import(self):
        from evidence_selector.eve_server import main
        with bind_server(0) as server, contextlib.redirect_stderr(io.StringIO()) as output:
            with patch.dict("sys.modules", {"torch": None}):
                self.assertEqual(main(["--port", str(server.server_port)]), 1)
            self.assertIn("startup failed", output.getvalue())
            self.assertNotIn("Missing local runtime", output.getvalue())

    def test_missing_extra_actionable_and_releases_port(self):
        from evidence_selector.eve_server import main
        with bind_server(0) as server:
            port = server.server_port
        with patch.dict("sys.modules", {"torch": None}), contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(main(["--port", str(port)]), 1)
        self.assertIn("uv sync --extra local", output.getvalue())
        with bind_server(port):
            pass

    def test_managed_q8_hash_failure_starts_no_child(self):
        from evidence_selector.gguf_server import main
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            path = Path(tmp) / "wrong.gguf"
            path.write_bytes(b"wrong")
            with bind_server(0) as probe:
                port = probe.server_port
            with patch("subprocess.Popen") as spawn:
                self.assertEqual(main(["--port", "0", "--llama-endpoint", f"http://127.0.0.1:{port}",
                                       "--llama-server", "unused", "--gguf", str(path)]), 1)
                spawn.assert_not_called()

    def test_saved_configuration_missing_fields_is_actionable(self):
        from evidence_selector.cli import main
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text('{}')
            with patch.dict("os.environ", {"DECISION_LAYER_CONFIG": str(path)}), contextlib.redirect_stderr(io.StringIO()) as output:
                self.assertEqual(main(["plugin-mcp"]), 1)
            self.assertIn("configure --root", output.getvalue())

    def test_q8_readiness_deadline_includes_stalled_http(self):
        from evidence_selector.gguf_server import main
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            stop = threading.Event()
            def stall():
                conn, _ = listener.accept()
                with conn:
                    stop.wait(2)
            worker = threading.Thread(target=stall)
            worker.start()
            tick = time.monotonic()
            try:
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(["--port", "0", "--llama-endpoint", f"http://127.0.0.1:{listener.getsockname()[1]}", "--startup-timeout", ".15"]), 1)
                self.assertLess(time.monotonic()-tick, 1)
            finally:
                stop.set()
                worker.join(timeout=3)

    def test_failed_config_validation_preserves_previous(self):
        from evidence_selector.cli import main
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text('original')
            with patch.dict("os.environ", {"DECISION_LAYER_CONFIG": str(path)}), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["--drop-below", ".9", "--keep-above", ".1", "configure", "--root", tmp]), 1)
            self.assertEqual(path.read_text(), 'original')

    def test_shutdown_requires_secret_and_releases_server(self):
        import json
        from urllib.request import Request, build_opener, ProxyHandler
        from urllib.error import HTTPError
        from evidence_selector.eve_server import handler_for
        server = bind_server(0)
        server.RequestHandlerClass = handler_for(object())
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        opener = build_opener(ProxyHandler({}))
        url = f"http://127.0.0.1:{server.server_port}/shutdown"
        try:
            with patch.dict("os.environ", {"DECISION_LAYER_SHUTDOWN_TOKEN": "test-secret"}):
                with self.assertRaises(HTTPError) as caught:
                    opener.open(Request(url, b"{}"), timeout=2)
                self.assertEqual(caught.exception.code, 403)
                with opener.open(Request(url, b"{}", {"Authorization": "Bearer test-secret"}), timeout=2) as response:
                    self.assertEqual(json.load(response)["status"], "stopping")
                worker.join(timeout=2)
                self.assertFalse(worker.is_alive())
        finally:
            server.shutdown()
            server.server_close()

    def test_startup_sigterm_cleans_owned_child(self):
        import signal
        from evidence_selector.gguf_server import main
        with contextlib.redirect_stderr(io.StringIO()), patch("evidence_selector.owned_process.ChildJob"), \
                patch("evidence_selector.hf_backend.file_sha256", return_value="test"), \
                patch("evidence_selector.server_runtime.require_no_listener"), patch("subprocess.Popen") as spawn:
            child = spawn.return_value
            child.poll.return_value = None
            def stop(*args, **kwargs):
                signal.raise_signal(signal.SIGTERM)
            with patch("evidence_selector.gguf_server.GgufBackend", side_effect=stop):
                result = main(["--port", "0", "--llama-server", "fake", "--gguf", "fake", "--sha256", "test"])
            self.assertEqual(result, 130)
            child.terminate.assert_called_once()
            child.wait.assert_called_once()

    @unittest.skipUnless(__import__("os").name == "nt", "Windows job ownership")
    def test_windows_job_close_stops_owned_process(self):
        import subprocess
        import sys
        from evidence_selector.owned_process import ChildJob
        job = ChildJob()
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            job.attach(child)
            job.close()
            child.wait(timeout=5)
            self.assertIsNotNone(child.returncode)
        finally:
            job.close()
            if child.poll() is None:
                child.kill()
                child.wait()


if __name__ == "__main__":
    unittest.main()
