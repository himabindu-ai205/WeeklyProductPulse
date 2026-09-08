"""Local dashboard server for the Stitch-based Weekly Review Pulse UI.

Serves ``frontend/`` and reads ``data/artifacts/pulse.json`` / ``pulse.md``.
No extra dependencies — stdlib only.
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .config import ROOT, load_settings

FRONTEND = ROOT / "frontend"
ARTIFACTS = ROOT / "data" / "artifacts"


class PulseHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND), **kwargs)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/api/pulse":
            self._send_json_file(ARTIFACTS / "pulse.json")
            return
        if path == "/api/pulse.md":
            self._send_text_file(ARTIFACTS / "pulse.md", "text/markdown; charset=utf-8")
            return
        if path == "/api/meta":
            self._send_meta()
            return

        super().do_GET()

    def _send_meta(self) -> None:
        try:
            settings = load_settings()
            payload = {
                "product_name": settings.app.product_name,
                "email_subject": settings.app.delivery.email_subject,
            }
        except Exception:  # noqa: BLE001
            payload = {
                "product_name": "Groww",
                "email_subject": "Weekly Review Pulse — Groww — {week_ending}",
            }
        self._send_json(payload)

    def _send_json_file(self, path: Path) -> None:
        if not path.is_file():
            self._send_json({"detail": "No pulse report yet"}, status=404)
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self._send_json({"detail": "pulse.json is invalid"}, status=500)
            return
        self._send_json(data)

    def _send_text_file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self.send_error(404, "No pulse markdown yet")
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def serve(host: str = "127.0.0.1", port: int = 8080) -> int:
    if not FRONTEND.is_dir():
        raise SystemExit(f"Frontend not found: {FRONTEND}")
    httpd = ThreadingHTTPServer((host, port), PulseHandler)
    print(f"Weekly Review Pulse -> http://{host}:{port}/", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the Weekly Review Pulse dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)
    return serve(host=args.host, port=args.port)


if __name__ == "__main__":
    raise SystemExit(main())
