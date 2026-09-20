"""Foreground lifecycle shared by local adapters. Never stops unrelated processes."""
import signal
import socket
from http.server import HTTPServer


def bind_server(port):
    if not 0 <= port <= 65535:
        raise ValueError("port must be between 0 and 65535")
    # Reserve the port before loading weights or starting a child process.
    class ExclusiveServer(HTTPServer):
        allow_reuse_address = not hasattr(socket, "SO_EXCLUSIVEADDRUSE")
        def server_bind(self):
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()
    return ExclusiveServer(("127.0.0.1", port), lambda *args: None)


def require_no_listener(port):
    """Check a llama port without confusing its SO_REUSEPORT TIME_WAIT with a listener."""
    import errno
    try:
        with bind_server(port):
            return
    except OSError:
        pass
    with socket.socket() as probe:
        probe.settimeout(3)
        result = probe.connect_ex(("127.0.0.1", port))
    if result not in (errno.ECONNREFUSED, 10061):
        raise ValueError("llama port is occupied or cannot be checked")


def install_stop_signal():
    previous = signal.getsignal(signal.SIGTERM)
    def stop(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    return previous


def serve(server, backend, label):
    from .eve_server import handler_for
    server.RequestHandlerClass = handler_for(backend)
    previous = signal.getsignal(signal.SIGTERM)
    def stop(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    try:
        print(f"{label} ready at http://127.0.0.1:{server.server_port}/v1/systemone", flush=True)
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        signal.signal(signal.SIGTERM, previous)
