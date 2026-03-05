from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


@pytest.fixture()
def http_server():
    state = {
        "retry": 0,
        "429": 0,
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

        def _send(self, code: int, body: bytes, content_type: str = "text/plain; charset=utf-8") -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/json":
                payload = json.dumps({"ok": True, "path": self.path}).encode()
                self._send(200, payload, "application/json")
                return

            if self.path == "/text":
                self._send(200, b"hello world\n")
                return

            if self.path == "/cookie":
                payload = json.dumps({"cookie": self.headers.get("Cookie")}).encode()
                self._send(200, payload, "application/json")
                return

            if self.path == "/headers":
                payload = json.dumps(
                    {
                        "user_agent": self.headers.get("User-Agent"),
                        "referer": self.headers.get("Referer"),
                    }
                ).encode()
                self._send(200, payload, "application/json")
                return

            if self.path == "/retry":
                state["retry"] += 1
                if state["retry"] == 1:
                    self._send(500, b"try again")
                else:
                    self._send(200, b"retried ok\n")
                return

            if self.path == "/429":
                state["429"] += 1
                if state["429"] == 1:
                    self._send(429, b"slow down")
                else:
                    self._send(200, b"rate limit recovered\n")
                return

            if self.path == "/challenge":
                self.send_response(503)
                self.send_header("Server", "cloudflare")
                body = b"<html><script>var x=1;</script>_cf_chl_opt</html>"
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            self._send(404, b"not found\n")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield {
            "base_url": f"http://127.0.0.1:{server.server_address[1]}",
            "state": state,
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
