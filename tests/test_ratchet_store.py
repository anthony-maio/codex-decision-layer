import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from evidence_selector.ratchet.mcp_server import EvidenceStore


class EvidenceStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        replay = json.loads((Path(__file__).resolve().parents[1] /
            "evidence_selector/ratchet/data/replay.json").read_text(encoding="utf-8"))
        for i, events in enumerate(replay["examples"][0]["records"]):
            (self.root / f"attempt-{i}.jsonl").write_text(
                "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8", newline="\n")
        self.store = EvidenceStore(self.root)

    def test_all_original_text_is_recoverable_in_exact_windows(self):
        result = self.store.compare("attempt-0.jsonl", "attempt-1.jsonl")
        self.assertEqual(result["relationship"], "same_blocker")
        self.assertFalse(result["originals_modified"])
        source = result["sources"][0]
        offset = 0
        recovered = ""
        while offset is not None:
            page = self.store.evidence(source["file"], source["sha256"], offset, 127)
            recovered += page["text"]
            offset = page["next_offset"]
        self.assertEqual(recovered, (self.root / source["file"]).read_bytes().decode())

    def test_changed_evidence_refuses_stale_decision_hash(self):
        result = self.store.compare("attempt-0.jsonl", "attempt-1.jsonl")
        source = result["sources"][0]
        path = self.root / source["file"]
        data = path.read_text(encoding="utf-8").replace("required API_ENDPOINT", "changed API_ENDPOINT")
        path.write_text(data, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed_since"):
            self.store.evidence(source["file"], source["sha256"])

    def test_escape_hidden_absolute_and_nonrecord_paths_are_refused(self):
        for name in ("../outside.jsonl", "/outside.jsonl", "C:/outside.jsonl", "C:outside.jsonl",
                     "sub\\outside.jsonl", ".git/data.jsonl", ".env/data.jsonl", "notes.txt"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.store.load(name)

    def test_symlink_record_is_refused(self):
        linked = self.root / "linked.jsonl"
        try:
            linked.symlink_to(self.root / "attempt-0.jsonl")
        except OSError:
            self.skipTest("symlink creation unavailable")
        with self.assertRaisesRegex(ValueError, "linked_record"):
            self.store.load(linked.name)

    def test_ancestor_redirected_after_validation_is_refused(self):
        # Windows exercises a junction, Linux a symlink. Both are created after
        # the convenient path checks, immediately before the secure reader.
        nested = self.root / "nested"
        nested.mkdir()
        (nested / "record.jsonl").write_bytes((self.root / "attempt-0.jsonl").read_bytes())
        with tempfile.TemporaryDirectory() as outside:
            (Path(outside) / "record.jsonl").write_text("OUTSIDE SENTINEL", encoding="utf-8")
            original = self.store.reader.read
            def redirect(parts):
                nested.rename(self.root / "old-nested")
                if os.name == "nt":
                    import _winapi
                    _winapi.CreateJunction(outside, str(nested))
                else:
                    nested.symlink_to(outside, target_is_directory=True)
                return original(parts)
            with patch.object(self.store.reader, "read", side_effect=redirect):
                with self.assertRaises((OSError, ValueError)):
                    self.store.load("nested/record.jsonl")

    def test_file_redirected_after_validation_is_refused(self):
        target = self.root / "attempt-0.jsonl"
        original = self.store.reader.read
        def redirect(parts):
            target.rename(self.root / "old-record.jsonl")
            try:
                target.symlink_to(self.root / "attempt-1.jsonl")
            except OSError:
                self.skipTest("symlink creation unavailable")
            return original(parts)
        with patch.object(self.store.reader, "read", side_effect=redirect):
            with self.assertRaises((OSError, ValueError)):
                self.store.load(target.name)

    def test_replaced_root_is_refused(self):
        root = self.root / "scope"
        root.mkdir()
        store = EvidenceStore(root)
        root.rename(self.root / "original-scope")
        root.mkdir()
        (root / "record.jsonl").write_bytes((self.root / "attempt-0.jsonl").read_bytes())
        with self.assertRaisesRegex(ValueError, "root_replaced"):
            store.load("record.jsonl")

    @unittest.skipUnless(os.name == "nt", "Windows sharing semantics")
    def test_pinned_directory_excludes_reparse_writers_but_allows_child_creation(self):
        import ctypes
        # Interpose only to attempt the competing write immediately after the
        # directory has been opened and inspected by the real Windows API.
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        handles, checked = {}, []
        real_factory = ctypes.WinDLL
        def factory(*args, **kwargs):
            kernel = real_factory(*args, **kwargs)
            proxy = Mock(wraps=kernel)
            def create(*values):
                # The production reader declares signatures on the proxy;
                # forward those to the actual foreign function.
                kernel.CreateFileW.argtypes = proxy.CreateFileW.argtypes
                kernel.CreateFileW.restype = proxy.CreateFileW.restype
                handle = kernel.CreateFileW(*values)
                handles[handle] = values[0]
                return handle
            def info(handle, pointer):
                kernel.GetFileInformationByHandle.argtypes = proxy.GetFileInformationByHandle.argtypes
                kernel.GetFileInformationByHandle.restype = proxy.GetFileInformationByHandle.restype
                result = kernel.GetFileInformationByHandle(handle, pointer)
                # The store canonicalizes its configured root; Windows temp
                # paths may use an alias or short spelling for that directory.
                if Path(handles[handle]) == self.store.root:
                    api.CreateFileW.argtypes = kernel.CreateFileW.argtypes
                    api.CreateFileW.restype = kernel.CreateFileW.restype
                    writer = api.CreateFileW(str(self.store.root), 0x40000000, 7, None, 3, 0x02200000, None)
                    error = ctypes.get_last_error()
                    if writer != ctypes.c_void_p(-1).value:
                        kernel.CloseHandle.argtypes = proxy.CloseHandle.argtypes
                        kernel.CloseHandle(writer)
                    self.assertEqual(writer, ctypes.c_void_p(-1).value)
                    self.assertEqual(error, 32)  # ERROR_SHARING_VIOLATION
                    child = self.store.root / "new-child.txt"
                    child.write_text("child creation remains possible", encoding="utf-8")
                    checked.append(True)
                return result
            proxy.CreateFileW.side_effect = create
            proxy.GetFileInformationByHandle.side_effect = info
            def close(handle):
                kernel.CloseHandle.argtypes = proxy.CloseHandle.argtypes
                return kernel.CloseHandle(handle)
            def read(*values):
                kernel.ReadFile.argtypes = proxy.ReadFile.argtypes
                kernel.ReadFile.restype = proxy.ReadFile.restype
                return kernel.ReadFile(*values)
            proxy.CloseHandle.side_effect = close
            proxy.ReadFile.side_effect = read
            return proxy
        with patch("ctypes.WinDLL", side_effect=factory):
            self.store.load("attempt-0.jsonl")
        self.assertEqual(checked, [True])
