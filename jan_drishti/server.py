"""Small zero-dependency HTTP server for the JAN-DRISHTI AI web prototype."""

from __future__ import annotations

import argparse
import json
import mimetypes
import secrets
from datetime import datetime
from email.message import Message
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import unquote, urlparse, parse_qs

from jan_drishti.config import CONFIG
from jan_drishti.engine import analyze_records_json
from jan_drishti.services.ingestion import IngestionError, load_records
from jan_drishti.services.auth import AuthManager, AuthenticationError, AuthorizationError
from jan_drishti.services.database import DatabaseManager
from jan_drishti.services.access_analytics import AccessAnalytics
from jan_drishti.services.transparency import get_model_documentation, explain_project_score_breakdown
from jan_drishti.services.chatbot import JanDrishtiChatbot

REPO_ROOT = Path(__file__).resolve().parents[1]
WEBSITE_DIR = REPO_ROOT / "website"
DATA_DIR = REPO_ROOT / "data"

# Initialize auth, database, and chatbot managers
auth_manager = AuthManager()
db_manager = DatabaseManager()
chatbot = JanDrishtiChatbot()
access_analytics = AccessAnalytics(db_manager)


class JanDrishtiHandler(BaseHTTPRequestHandler):
    """Routes API requests and serves the website assets."""

    server_version = "JanDrishtiAI/1.0-Secure"

    def do_GET(self) -> None:  # noqa: N802 - inherited method name
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        # Public routes
        if path in {"/", "/index.html"}:
            self._send_file(WEBSITE_DIR / "index.html")
            return
        if path == "/health":
            self._send_json({"status": "ok", "app": CONFIG.app_name, "version": "1.0-Secure"})
            return
        if path == "/sample.csv":
            self._send_file(DATA_DIR / "sample_projects.csv")
            return

        # Protected API routes
        if path == "/api/model-transparency":
            self._handle_model_transparency()
            return
        
        if path.startswith("/api/audit-log"):
            self._handle_audit_log(parsed)
            return
        
        if path.startswith("/api/analysis-history"):
            self._handle_analysis_history()
            return

        # Login / access analytics dashboard (aggregate counts for every role,
        # client IPs only for administrators)
        if path.startswith("/api/access-analytics"):
            self._handle_access_analytics(parsed)
            return

        # Static files
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
        
        # Login endpoint (public)
        if parsed.path == "/api/login":
            self._handle_login()
            return
        
        # Analysis endpoint (requires authentication)
        if parsed.path == "/api/analyze":
            self._handle_analysis()
            return
        
        # Chatbot endpoint (requires authentication)
        if parsed.path == "/api/chatbot":
            self._handle_chatbot()
            return

        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
    
    def _get_client_ip(self) -> str:
        """Get client IP address for audit logging."""
        return self.client_address[0] if self.client_address else "unknown"
    
    def _extract_token(self) -> Optional[str]:
        """Extract Bearer token from Authorization header."""
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        return None
    
    def _require_auth(self, permission: str = "view") -> Optional[Dict[str, Any]]:
        """Verify authentication and authorization.
        
        Returns user payload if authorized, None otherwise (sends error response).
        """
        token = self._extract_token()
        
        if not token:
            self._send_json(
                {"error": "Authentication required", "message": "Missing authorization token"},
                status=HTTPStatus.UNAUTHORIZED
            )
            return None
        
        try:
            user_payload = auth_manager.require_permission(token, permission)
            return user_payload
        except AuthenticationError as e:
            self._send_json(
                {"error": "Authentication failed", "message": str(e)},
                status=HTTPStatus.UNAUTHORIZED
            )
            db_manager.log_action(
                "AUTH_FAILED",
                ip_address=self._get_client_ip(),
                details=str(e),
                success=False
            )
            return None
        except AuthorizationError as e:
            self._send_json(
                {"error": "Authorization failed", "message": str(e)},
                status=HTTPStatus.FORBIDDEN
            )
            return None
    
    def _handle_login(self) -> None:
        """Handle user login."""
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)
            
            username = data.get("username", "").strip()
            password = data.get("password", "")
            
            if not username or not password:
                self._send_json(
                    {"error": "Username and password required"},
                    status=HTTPStatus.BAD_REQUEST
                )
                return
            
            # Get user from database
            user = db_manager.get_user(username)
            
            if not user:
                db_manager.log_action(
                    "LOGIN_FAILED",
                    username=username,
                    ip_address=self._get_client_ip(),
                    details="User not found",
                    success=False
                )
                self._send_json(
                    {"error": "Invalid username or password"},
                    status=HTTPStatus.UNAUTHORIZED
                )
                return
            
            # Verify password
            if not auth_manager.verify_password(password, user["password_hash"], user["salt"]):
                db_manager.log_action(
                    "LOGIN_FAILED",
                    user_id=user["user_id"],
                    username=username,
                    ip_address=self._get_client_ip(),
                    details="Invalid password",
                    success=False
                )
                self._send_json(
                    {"error": "Invalid username or password"},
                    status=HTTPStatus.UNAUTHORIZED
                )
                return
            
            # Generate token
            token = auth_manager.create_token(
                user["user_id"],
                user["username"],
                user["role"]
            )
            
            # Update last login
            db_manager.update_last_login(user["user_id"])
            
            # Log successful login
            db_manager.log_action(
                "LOGIN",
                user_id=user["user_id"],
                username=user["username"],
                ip_address=self._get_client_ip(),
                details=f"Role: {user['role']}"
            )
            
            # Return token and user info (without sensitive data)
            self._send_json({
                "token": token,
                "user": {
                    "user_id": user["user_id"],
                    "username": user["username"],
                    "role": user["role"],
                    "full_name": user["full_name"],
                    "email": user["email"]
                }
            })
            
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._send_json(
                {"error": "Login failed", "details": str(exc)},
                status=HTTPStatus.INTERNAL_SERVER_ERROR
            )
    
    def _handle_analysis(self) -> None:
        """Handle file analysis (requires authentication)."""
        user = self._require_auth(permission="analyze")
        if not user:
            return

        try:
            filename, content = self._read_uploaded_file()
            records = load_records(filename, content)
            report = analyze_records_json(records, source_name=filename)
            
            # Save analysis to database
            try:
                run_id = secrets.token_hex(16)
                db_manager.save_analysis_run(
                    run_id=run_id,
                    user_id=user["user_id"],
                    username=user["username"],
                    report=report
                )
                
                # Log the action
                db_manager.log_action(
                    "ANALYZE",
                    user_id=user["user_id"],
                    username=user["username"],
                    resource=filename,
                    details=f"Analyzed {report['summary']['projects_analyzed']} projects",
                    ip_address=self._get_client_ip()
                )
                
                # Add run_id to report
                report["run_id"] = run_id
            except Exception as db_error:
                # If database save fails, still return the report but log the error
                print(f"Database save failed: {db_error}")
                import traceback
                traceback.print_exc()
                report["run_id"] = "not_saved"
                report["warning"] = "Analysis completed but not saved to database"
            
            self._send_json(report)
            
        except IngestionError as exc:
            print(f"Ingestion error: {exc}")
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except ValueError as exc:
            print(f"Value error: {exc}")
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            print(f"Analysis failed with exception: {exc}")
            import traceback
            traceback.print_exc()
            self._send_json(
                {"error": "Analysis failed", "details": str(exc)},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
    
    def _handle_model_transparency(self) -> None:
        """Handle model transparency documentation request."""
        user = self._require_auth(permission="view")
        if not user:
            return
        
        try:
            doc = get_model_documentation()
            self._send_json(doc)
            
            db_manager.log_action(
                "VIEW_TRANSPARENCY",
                user_id=user["user_id"],
                username=user["username"],
                resource="model_documentation",
                ip_address=self._get_client_ip()
            )
        except Exception as exc:
            self._send_json(
                {"error": "Failed to load documentation", "details": str(exc)},
                status=HTTPStatus.INTERNAL_SERVER_ERROR
            )
    
    def _handle_chatbot(self) -> None:
        """Handle chatbot query (requires authentication)."""
        user = self._require_auth(permission="view")
        if not user:
            return
        
        try:
            # Read JSON request body
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self._send_json({"error": "Empty request body"}, status=HTTPStatus.BAD_REQUEST)
                return
            
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))
            
            query = data.get("query", "").strip()
            context = data.get("context", {})
            
            if not query:
                response = chatbot.get_response("", context)
            else:
                response = chatbot.get_response(query, context)
            
            self._send_json({
                "response": response,
                "timestamp": datetime.now().isoformat()
            })
            
            # Log chatbot usage
            db_manager.log_action(
                "CHATBOT_QUERY",
                user_id=user["user_id"],
                username=user["username"],
                resource="chatbot",
                details=f"Query: {query[:50]}..." if len(query) > 50 else f"Query: {query}",
                ip_address=self._get_client_ip()
            )
            
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON in request body"}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            print(f"Chatbot error: {exc}")
            import traceback
            traceback.print_exc()
            self._send_json(
                {"error": "Chatbot request failed", "details": str(exc)},
                status=HTTPStatus.INTERNAL_SERVER_ERROR
            )
    
    def _handle_access_analytics(self, parsed) -> None:
        """Login and access analytics built from the platform's own audit trail.

        Requires ``view`` permission: every signed-in role may see how much the
        platform is being used. Client IP addresses are withheld unless the
        viewer is an administrator, matching the audit-log endpoint's model.

        This endpoint deliberately does not write an audit row of its own - the
        dashboard polls it, and logging each poll would drown the very table it
        reports on.
        """
        user = self._require_auth(permission="view")
        if not user:
            return

        try:
            query = parse_qs(parsed.query)
            try:
                days = int(query.get("days", ["14"])[0])
            except (TypeError, ValueError):
                days = 14

            is_admin = user.get("role") == "admin"
            payload = access_analytics.summarize(
                days=days,
                recent_limit=15,
                include_ips=is_admin,
                user_admin=is_admin,
            )
            self._send_json(payload)
        except Exception as exc:
            self._send_json(
                {"error": "Failed to build access analytics", "details": str(exc)},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _handle_audit_log(self, parsed) -> None:
        """Handle audit log request (admin only)."""
        user = self._require_auth(permission="manage_users")
        if not user:
            return
        
        try:
            # Parse query parameters
            query_params = parse_qs(parsed.query)
            limit = int(query_params.get("limit", ["50"])[0])
            
            logs = db_manager.get_audit_log(limit=limit)
            self._send_json(logs)
            
        except Exception as exc:
            self._send_json(
                {"error": "Failed to load audit log", "details": str(exc)},
                status=HTTPStatus.INTERNAL_SERVER_ERROR
            )
    
    def _handle_analysis_history(self) -> None:
        """Handle analysis history request."""
        user = self._require_auth(permission="view")
        if not user:
            return
        
        try:
            # Admins see all history, others see only their own
            user_id = None if user["role"] == "admin" else user["user_id"]
            history = db_manager.get_analysis_history(user_id=user_id, limit=50)
            self._send_json(history)
            
        except Exception as exc:
            self._send_json(
                {"error": "Failed to load history", "details": str(exc)},
                status=HTTPStatus.INTERNAL_SERVER_ERROR
            )

    def _read_uploaded_file(self) -> Tuple[str, bytes]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            raise ValueError("No upload body received.")
        if content_length > CONFIG.max_upload_bytes:
            raise ValueError(f"Upload too large. Limit is {CONFIG.max_upload_mb} MB.")

        content_type = self.headers.get("Content-Type", "")
        msg = Message()
        msg['content-type'] = content_type
        media_type = msg.get_content_type()

        if media_type == "multipart/form-data":
            boundary = msg.get_param('boundary')
            if not boundary:
                raise ValueError("multipart/form-data requires boundary parameter")
            
            # Read the entire body
            body = self.rfile.read(content_length)
            
            # Parse multipart manually
            filename, content = self._parse_multipart(body, boundary)
            return filename, content

        if media_type in {"application/json", "text/json"}:
            return "uploaded.json", self.rfile.read(content_length)

        if media_type in {"text/csv", "application/csv", "text/plain"}:
            return "uploaded.csv", self.rfile.read(content_length)

        raise ValueError("Use multipart upload with a CSV/JSON file, or send CSV/JSON directly.")
    
    def _parse_multipart(self, body: bytes, boundary: str) -> Tuple[str, bytes]:
        """Parse multipart/form-data manually for Python 3.13+ compatibility."""
        boundary_bytes = f"--{boundary}".encode()
        parts = body.split(boundary_bytes)
        
        for part in parts:
            if not part or part == b'--\r\n' or part == b'--':
                continue
            
            # Split headers from content
            if b'\r\n\r\n' in part:
                headers_section, content = part.split(b'\r\n\r\n', 1)
            elif b'\n\n' in part:
                headers_section, content = part.split(b'\n\n', 1)
            else:
                continue
            
            # Remove trailing boundary markers
            content = content.rstrip(b'\r\n-')
            
            # Parse headers
            headers_text = headers_section.decode('utf-8', errors='replace')
            if 'name="file"' in headers_text:
                # Extract filename
                filename = "uploaded.csv"
                if 'filename="' in headers_text:
                    start = headers_text.index('filename="') + len('filename="')
                    end = headers_text.index('"', start)
                    filename = headers_text[start:end]
                
                return filename, content
        
        raise ValueError("Upload field must be named 'file'.")

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
