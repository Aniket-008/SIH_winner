"""Small zero-dependency HTTP server for the JAN-DRISHTI AI web prototype."""

from __future__ import annotations

import argparse
import json
import mimetypes
import warnings

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    import cgi
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.parse import unquote, urlparse

from jan_drishti.config import CONFIG
from jan_drishti.engine import analyze_records_json
from jan_drishti.services.ingestion import IngestionError, load_records

REPO_ROOT = Path(__file__).resolve().parents[1]
WEBSITE_DIR = REPO_ROOT / "website"
DATA_DIR = REPO_ROOT / "data"


class JanDrishtiHandler(BaseHTTPRequestHandler):
    """Routes API requests and serves the website assets."""

    server_version = "JanDrishtiAI/0.1"

    def do_GET(self) -> None:  # noqa: N802 - inherited method name
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path in {"/", "/index.html"}:
            self._send_file(WEBSITE_DIR / "index.html")
            return
        if path == "/health":
            self._send_json({"status": "ok", "app": CONFIG.app_name})
            return
        if path == "/sample.csv":
            self._send_file(DATA_DIR / "sample_projects.csv")
            return

        requested = (WEBSITE_DIR / path.lstrip("/")).resolve()
        if WEBSITE_DIR in requested.parents and requested.exists() and requested.is_file():
            self._send_file(requested)
            return

        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_HEAD(self) -> None:  # noqa: N802 - inherited method name
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path in {"/", "/index.html"}:
            self._send_file(WEBSITE_DIR / "index.html", head_only=True)
            return
        if path == "/sample.csv":
            self._send_file(DATA_DIR / "sample_projects.csv", head_only=True)
            return
        requested = (WEBSITE_DIR / path.lstrip("/")).resolve()
        if WEBSITE_DIR in requested.parents and requested.exists() and requested.is_file():
            self._send_file(requested, head_only=True)
            return
        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND, head_only=True)

    def do_POST(self) -> None:  # noqa: N802 - inherited method name
        parsed = urlparse(self.path)
        if parsed.path != "/api/analyze":
            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            filename, content = self._read_uploaded_file()
            records = load_records(filename, content)
            report = analyze_records_json(records, source_name=filename)
            self._send_json(report)
        except IngestionError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover - defensive API boundary
            self._send_json(
                {"error": "Analysis failed", "details": str(exc)},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _read_uploaded_file(self) -> Tuple[str, bytes]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            raise ValueError("No upload body received.")
        if content_length > CONFIG.max_upload_bytes:
            raise ValueError(f"Upload too large. Limit is {CONFIG.max_upload_mb} MB.")

        content_type = self.headers.get("Content-Type", "")
        media_type, _ = cgi.parse_header(content_type)

        if media_type == "multipart/form-data":
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": content_type,
                    "CONTENT_LENGTH": str(content_length),
                },
            )
            if "file" not in form:
                raise ValueError("Upload field must be named 'file'.")
            item = form["file"]
            if isinstance(item, list):
                item = item[0]
            filename = item.filename or "uploaded.csv"
            content = item.file.read()
            return filename, content

        if media_type in {"application/json", "text/json"}:
            return "uploaded.json", self.rfile.read(content_length)

        if media_type in {"text/csv", "application/csv", "text/plain"}:
            return "uploaded.csv", self.rfile.read(content_length)

        raise ValueError("Use multipart upload with a CSV/JSON file, or send CSV/JSON directly.")

    def _send_file(self, path: Path, head_only: bool = False) -> None:
        if not path.exists():
            self._send_json({"error": "File not found"}, status=HTTPStatus.NOT_FOUND, head_only=head_only)
            return
        content = path.read_bytes()
        mime_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self._send_common_headers()
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        if not head_only:
            self.wfile.write(content)

    def _send_json(self, payload: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK, head_only: bool = False) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._send_common_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        if not head_only:
            self.wfile.write(content)

    def _send_common_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("X-Content-Type-Options", "nosniff")

    def do_OPTIONS(self) -> None:  # noqa: N802 - inherited method name
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_common_headers()
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - inherited argument
        print(f"{self.address_string()} - {format % args}")


def run(host: str = CONFIG.host, port: int = CONFIG.port) -> None:
    server = ThreadingHTTPServer((host, port), JanDrishtiHandler)
    print(f"JAN-DRISHTI AI running at http://{host}:{port}")
    print("Upload dashboard: open / in your browser")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the JAN-DRISHTI AI prototype server.")
    parser.add_argument("--host", default=CONFIG.host, help="Host to bind. Use 0.0.0.0 for live preview.")
    parser.add_argument("--port", type=int, default=CONFIG.port, help="Port to bind.")
    args = parser.parse_args()
    run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
