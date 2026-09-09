"""HTTP server for Weekly Review Pulse API (and optional local dashboard).

Railway (backend-only): ``python -m src --serve --backend-only``
Local UI: ``python -m src --serve``
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .archive import (
    PERIOD_WEEKS,
    list_period_weeks,
    load_pulse,
    load_pulse_md,
    resolve_week_query,
)
from .config import ROOT, load_settings
from .publish import (
    PublishError,
    append_pulse_to_google_doc,
    update_pulse_artifact_with_publish,
)
from .schemas import Pulse

FRONTEND = ROOT / "frontend"
ARTIFACTS = ROOT / "data" / "artifacts"


def _query_week(query: dict[str, list[str]]):
    week = (query.get("week") or [None])[0]
    week_ending = (query.get("week_ending") or [None])[0]
    return resolve_week_query(ARTIFACTS, week, week_ending)


def _publish_doc_for_week(week) -> dict:
    """Append selected week's pulse to GOOGLE_DOC_ID via MCP."""
    settings = load_settings()
    if not settings.env.mcp_http_token:
        raise PublishError("MCP_HTTP_TOKEN is not set")
    if not settings.env.google_doc_id:
        raise PublishError("GOOGLE_DOC_ID is not set")

    data = load_pulse(ARTIFACTS, week)
    md = load_pulse_md(ARTIFACTS, week)
    if data is None or md is None:
        detail = "No pulse report yet"
        if week is not None:
            detail = f"No pulse for week ending {week.isoformat()}"
        raise FileNotFoundError(detail)

    pulse = Pulse.model_validate(data)
    pub = append_pulse_to_google_doc(pulse, md, settings)
    update_pulse_artifact_with_publish(ARTIFACTS, pulse, pub)
    return {
        "ok": True,
        "doc_id": pub.doc_id,
        "doc_url": pub.doc_url,
        "week_ending": pulse.week_ending.isoformat(),
        "message": "Pulse appended to Google Doc",
    }


def _api_routes(handler: BaseHTTPRequestHandler, path: str, query: dict[str, list[str]]) -> bool:
    """Handle GET /api/* routes. Returns True if handled."""
    if path == "/api/health":
        handler._send_json(  # type: ignore[attr-defined]
            {
                "status": "ok",
                "service": "weekly-review-pulse",
                "mode": getattr(handler, "serve_mode", "full"),
            }
        )
        return True
    if path == "/api/weeks":
        reporting_days = 7
        try:
            reporting_days = load_settings().app.windows.reporting_days
        except Exception:  # noqa: BLE001
            pass
        weeks = list_period_weeks(
            ARTIFACTS, count=PERIOD_WEEKS, reporting_days=reporting_days
        )
        handler._send_json(  # type: ignore[attr-defined]
            {"weeks": weeks, "count": len(weeks)}
        )
        return True
    if path == "/api/pulse":
        week = _query_week(query)
        data = load_pulse(ARTIFACTS, week)
        if data is None:
            detail = "No pulse report yet"
            if week is not None:
                detail = (
                    f"No pulse for week ending {week.isoformat()}. "
                    f"Generate with: python -m src --week-ending {week.isoformat()} --skip-publish"
                )
            handler._send_json({"detail": detail}, status=404)  # type: ignore[attr-defined]
            return True
        handler._send_json(data)  # type: ignore[attr-defined]
        return True
    if path == "/api/pulse.md":
        week = _query_week(query)
        text = load_pulse_md(ARTIFACTS, week)
        if text is None:
            handler.send_error(404, "No pulse markdown yet")
            return True
        body = text.encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "text/markdown; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Cache-Control", "no-store")
        handler.end_headers()
        handler.wfile.write(body)
        return True
    if path == "/api/meta":
        handler._send_meta()  # type: ignore[attr-defined]
        return True
    return False


def _api_post_routes(
    handler: BaseHTTPRequestHandler, path: str, query: dict[str, list[str]]
) -> bool:
    """Handle POST /api/* routes. Returns True if handled."""
    if path == "/api/publish-doc":
        week = _query_week(query)
        try:
            payload = _publish_doc_for_week(week)
            handler._send_json(payload)  # type: ignore[attr-defined]
        except FileNotFoundError as e:
            handler._send_json({"ok": False, "detail": str(e)}, status=404)  # type: ignore[attr-defined]
        except PublishError as e:
            handler._send_json({"ok": False, "detail": str(e)}, status=502)  # type: ignore[attr-defined]
        except Exception as e:  # noqa: BLE001
            handler._send_json(  # type: ignore[attr-defined]
                {"ok": False, "detail": f"Publish failed: {e}"}, status=500
            )
        return True
    return False


class _JsonMixin:
    serve_mode = "full"

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

    def _send_meta(self) -> None:
        try:
            settings = load_settings()
            payload = {
                "product_name": settings.app.product_name,
                "email_subject": settings.app.delivery.email_subject,
                "default_recipient": settings.app.delivery.recipient,
                "google_doc_configured": bool(settings.env.google_doc_id),
                "mcp_configured": bool(settings.env.mcp_http_token),
            }
        except Exception:  # noqa: BLE001
            payload = {
                "product_name": "Groww",
                "email_subject": "Weekly Review Pulse — Groww — {week_ending}",
                "default_recipient": "",
                "google_doc_configured": False,
                "mcp_configured": False,
            }
        self._send_json(payload)

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _discard_body(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if length > 0:
            self.rfile.read(length)


class PulseHandler(_JsonMixin, SimpleHTTPRequestHandler):
    serve_mode = "full"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        if _api_routes(self, path, query):
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        self._discard_body()
        if _api_post_routes(self, path, query):
            return
        self._send_json({"detail": "Not Found"}, status=404)


class BackendOnlyHandler(_JsonMixin, BaseHTTPRequestHandler):
    """API-only handler for Railway (no static frontend)."""

    serve_mode = "backend"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        if path == "/":
            self._send_json(
                {
                    "service": "weekly-review-pulse",
                    "mode": "backend",
                    "endpoints": [
                        "/api/health",
                        "/api/weeks",
                        "/api/pulse",
                        "/api/pulse.md",
                        "/api/meta",
                        "POST /api/publish-doc",
                    ],
                }
            )
            return
        if _api_routes(self, path, query):
            return
        self._send_json({"detail": "Not Found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        self._discard_body()
        if _api_post_routes(self, path, query):
            return
        self._send_json({"detail": "Not Found"}, status=404)


def serve(
    host: str | None = None,
    port: int | None = None,
    *,
    backend_only: bool = False,
) -> int:
    host = host or os.getenv("HOST", "0.0.0.0")
    port = int(port if port is not None else os.getenv("PORT", "8080"))

    if backend_only:
        handler: type[BaseHTTPRequestHandler] = BackendOnlyHandler
    else:
        if not FRONTEND.is_dir():
            raise SystemExit(f"Frontend not found: {FRONTEND} (use --backend-only on Railway)")
        handler = PulseHandler

    httpd = ThreadingHTTPServer((host, port), handler)
    mode = "backend-only" if backend_only else "dashboard"
    print(f"Weekly Review Pulse ({mode}) -> http://{host}:{port}/", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the Weekly Review Pulse API/dashboard")
    parser.add_argument("--host", default=None, help="Bind host (default HOST env or 0.0.0.0)")
    parser.add_argument("--port", type=int, default=None, help="Bind port (default PORT env or 8080)")
    parser.add_argument(
        "--backend-only",
        action="store_true",
        help="Serve JSON API only (no static frontend)",
    )
    args = parser.parse_args(argv)
    backend = args.backend_only or os.getenv("BACKEND_ONLY", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    return serve(host=args.host, port=args.port, backend_only=backend)


if __name__ == "__main__":
    raise SystemExit(main())
