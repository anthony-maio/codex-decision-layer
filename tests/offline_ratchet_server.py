"""Start the event loop, then deny DNS and new connections during MCP serving."""
import asyncio
import socket
import sys

from evidence_selector.ratchet.mcp_server import create_server


async def main():
    # Windows creates a loopback socketpair when constructing its event loop.
    # It is runtime plumbing, created before the service's network denial.
    def denied(*args, **kwargs):
        raise RuntimeError("network denied during Ratchet serving")
    socket.socket.connect = denied
    socket.socket.connect_ex = denied
    socket.getaddrinfo = denied
    await create_server(sys.argv[1]).run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
