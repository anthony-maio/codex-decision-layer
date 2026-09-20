"""Bounded record reads through pinned directories, refusing redirected paths."""
from contextlib import ExitStack
import os
from pathlib import Path
import stat


LIMIT = 8_000_001


class RootReader:
    def __init__(self, root):
        self.root = Path(root)
        self.identity = None
        self.identity, _ = self._read(None)

    def read(self, parts):
        return self._read(parts)[1]

    def _read(self, parts):
        return self._windows(parts) if os.name == "nt" else self._posix(parts)

    def _check(self, identity):
        if self.identity is not None and identity != self.identity:
            raise ValueError("record_root_replaced")

    def _posix(self, parts):
        with ExitStack() as stack:
            def opened(path, flags, parent=None):
                fd = os.open(path, flags | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                stack.callback(os.close, fd)
                return fd
            directory = opened(self.root, os.O_RDONLY | os.O_DIRECTORY)
            info = os.fstat(directory)
            identity = (info.st_dev, info.st_ino)
            self._check(identity)
            if parts is None:
                return identity, None
            for part in parts[:-1]:
                directory = opened(part, os.O_RDONLY | os.O_DIRECTORY, directory)
            fd = opened(parts[-1], os.O_RDONLY, directory)
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError("record_must_be_regular_file")
            chunks, remaining = [], LIMIT
            while remaining:
                chunk = os.read(fd, min(65536, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            return identity, b"".join(chunks)

    def _windows(self, parts):
        # Pin every ancestor with data-read access and no write/delete sharing.
        # Attribute-only access does not enforce Windows sharing against writers.
        # Excluding writes also prevents in-place conversion into a junction.
        # OPEN_REPARSE_POINT inspects the object itself, never a redirected target.
        import ctypes
        from ctypes import wintypes as w

        class Info(ctypes.Structure):
            _fields_ = [("attributes", w.DWORD), ("creation", w.FILETIME),
                        ("access", w.FILETIME), ("write", w.FILETIME),
                        ("volume", w.DWORD), ("size_high", w.DWORD),
                        ("size_low", w.DWORD), ("links", w.DWORD),
                        ("index_high", w.DWORD), ("index_low", w.DWORD)]

        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, w.LPVOID,
                                   w.DWORD, w.DWORD, w.HANDLE]
        api.CreateFileW.restype = w.HANDLE
        api.CloseHandle.argtypes = [w.HANDLE]
        api.CloseHandle.restype = w.BOOL
        api.GetFileInformationByHandle.argtypes = [w.HANDLE, ctypes.POINTER(Info)]
        api.GetFileInformationByHandle.restype = w.BOOL
        api.ReadFile.argtypes = [w.HANDLE, w.LPVOID, w.DWORD, ctypes.POINTER(w.DWORD), w.LPVOID]
        api.ReadFile.restype = w.BOOL
        with ExitStack() as stack:
            def opened(path, directory):
                # Child file creation remains possible; writes to the directory
                # object itself, including reparse-point mutation, are excluded.
                handle = api.CreateFileW(str(path), 0x80000000,
                                         1, None, 3,
                                         0x02200000, None)
                if handle == ctypes.c_void_p(-1).value:
                    raise ctypes.WinError(ctypes.get_last_error())
                stack.callback(api.CloseHandle, handle)
                info = Info()
                if not api.GetFileInformationByHandle(handle, ctypes.byref(info)):
                    raise ctypes.WinError(ctypes.get_last_error())
                if info.attributes & 0x400:
                    raise ValueError("linked_record_path_refused")
                if bool(info.attributes & 0x10) != directory or info.attributes & 0x40:
                    raise ValueError("record_path_type_mismatch")
                return handle, info

            for ancestor in reversed(self.root.parents):
                opened(ancestor, True)
            _, info = opened(self.root, True)
            identity = (info.volume, info.index_high, info.index_low)
            self._check(identity)
            if parts is None:
                return identity, None
            current = self.root
            for part in parts[:-1]:
                current /= part
                opened(current, True)
            handle, _ = opened(current / parts[-1], False)
            chunks, remaining = [], LIMIT
            buffer = ctypes.create_string_buffer(65536)
            while remaining:
                count = w.DWORD()
                if not api.ReadFile(handle, buffer, min(65536, remaining), ctypes.byref(count), None):
                    raise ctypes.WinError(ctypes.get_last_error())
                if not count.value:
                    break
                chunks.append(buffer.raw[:count.value])
                remaining -= count.value
            return identity, b"".join(chunks)
