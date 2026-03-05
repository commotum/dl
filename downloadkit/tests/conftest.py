from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

DATA = b"0123456789abcdefghijklmnopqrstuvwxyz"


@pytest.fixture()
def http_server():
    state = {
        "range_headers": [],
        "fallback_hits": 0,
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

        def _send(self, code: int, body: bytes, content_type: str = "application/octet-stream") -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/file":
                self._send(200, DATA)
                return

            if self.path == "/html":
                self._send(200, b"<html>login page</html>", "text/html; charset=utf-8")
                return

            if self.path == "/primary-fail":
                self._send(500, b"nope")
                return

            if self.path == "/fallback-file":
                state["fallback_hits"] += 1
                self._send(200, DATA)
                return

            if self.path == "/range":
                range_header = self.headers.get("Range")
                state["range_headers"].append(range_header)
                if range_header and range_header.startswith("bytes="):
                    start = int(range_header.split("=", 1)[1].split("-", 1)[0])
                    body = DATA[start:]
                    self.send_response(206)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Content-Range", f"bytes {start}-{len(DATA)-1}/{len(DATA)}")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self._send(200, DATA)
                return

            if self.path == "/headers":
                payload = json.dumps(
                    {
                        "user_agent": self.headers.get("User-Agent"),
                        "cookie": self.headers.get("Cookie"),
                    }
                ).encode()
                self._send(200, payload, "application/json")
                return

            self._send(404, b"not found\n", "text/plain; charset=utf-8")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield {
            "base_url": f"http://127.0.0.1:{server.server_address[1]}",
            "state": state,
            "data": DATA,
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
