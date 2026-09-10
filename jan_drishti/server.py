"""Small zero-dependency HTTP server for the JAN-DRISHTI AI web prototype."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import mimetypes
import secrets
import socket
import threading
import time
from datetime import datetime
from email.message import Message
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse, parse_qs

from jan_drishti.config import CONFIG, SCALING
from jan_drishti.engine import analyze_records_json
from jan_drishti.services.ingestion import IngestionError, load_records
from jan_drishti.services.auth import AuthManager, AuthenticationError, AuthorizationError
from jan_drishti.services.database import DatabaseManager
from jan_drishti.services.scalability import MONITOR, arm_fleet, run_load_test
from jan_drishti.services.transparency import get_model_documentation, explain_project_score_breakdown
from jan_drishti.services.chatbot import JanDrishtiChatbot

REPO_ROOT = Path(__file__).resolve().parents[1]
WEBSITE_DIR = REPO_ROOT / "website"
DATA_DIR = REPO_ROOT / "data"

# Initialize auth, database, and chatbot managers
auth_manager = AuthManager()
db_manager = DatabaseManager()
chatbot = JanDrishtiChatbot()


class JanDrishtiHandler(BaseHTTPRequestHandler):
    """Routes API requests and serves the website assets.

    Every request passes through :data:`MONITOR` (see
    ``jan_drishti/services/scalability.py``): the traffic-control gate runs
    before any work happens, and latency/concurrency/status are recorded on the
    way out so the scalability dashboard and ``/api/metrics`` stay honest.
    """

    server_version = "JanDrishtiAI/1.1-Scalable"
    # HTTP/1.1 keeps connections alive: fewer TCP handshakes per dashboard poll,
    # which is what lets the edge tier reuse upstream keepalive pools.
    protocol_version = "HTTP/1.1"
    # Buffer header+body writes so a response leaves as ONE TCP segment.
    # Without this, Nagle vs delayed-ACK adds ~40 ms to every small response
    # (headers in one segment, JSON body in the next), which caps a single
    # replica at ~25 req/s no matter how fast the analysis code is.
    wbufsize = 64 * 1024

    # Per-request telemetry state (reset for every request)
    _response_status: Optional[int] = None
    _response_bytes: int = 0
    _decision: str = "ok"
    _gated: bool = False
    _extra_headers: Dict[str, str] = {}

    # ------------------------------------------------------------------ #
    # Telemetry + traffic-control plumbing                                #
    # ------------------------------------------------------------------ #
    def setup(self) -> None:
        """Per-connection socket tuning that matters at scale."""
        super().setup()
        try:
            # Never let Nagle hold a response back, even if a proxy disables
            # buffering or a response is written in several pieces.
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass

    def _reset_request_state(self) -> None:
        self._request_started = time.perf_counter()
        self.command = None
        self.path = None
        self._response_status = None
        self._response_bytes = 0
        self._decision = "ok"
        self._gated = False
        self._extra_headers = {}

    def handle_one_request(self) -> None:  # noqa: N802 - inherited method name
        """Time the request, keep the concurrency gauge accurate, log the result."""
        self._reset_request_state()
        MONITOR.begin()
        try:
            super().handle_one_request()
        finally:
            if self.path is None and self._response_status is None:
                # Connection closed between requests (keep-alive idle timeout):
                # release the concurrency slot without logging a phantom request.
                MONITOR.abandon()
            else:
                MONITOR.record(
                    method=self.command or "-",
                    # A malformed request line has no path but still produced a
                    # 4xx, so it is counted (as "-") rather than dropped.
                    path=unquote(urlparse(self.path).path) if self.path else "-",
                    status=int(self._response_status or 499),  # 499 = client closed mid-request
                    latency_ms=(time.perf_counter() - self._request_started) * 1000,
                    bytes_out=self._response_bytes,
                    client=self._get_client_ip(),
                    decision=self._decision,
                    proxied=bool(self.headers.get("X-Forwarded-For") or self.headers.get("X-Real-IP")),
                )

    def send_response(self, code: int, message: Optional[str] = None) -> None:  # noqa: N802
        self._response_status = int(code)
        super().send_response(code, message)

    def _gate(self, path: str) -> bool:
        """Run the traffic-control gate once per request. False = already answered."""
        if self._gated:
            return True
        self._gated = True
        decision = MONITOR.admit(self._get_client_ip(), path)
        self._decision = decision.decision
        self._extra_headers.update(decision.headers)
        if not decision.allowed:
            self._extra_headers["Connection"] = "close"
            error = "rate_limited" if decision.decision == "rate_limited" else "server_overloaded"
            self._send_json(
                {
                    "error": error,
                    "message": decision.detail,
                    "retry_after_seconds": decision.retry_after,
                    "instance_id": MONITOR.instance_id,
                },
                status=HTTPStatus(decision.status),
            )
            return False
        return True

    def do_GET(self) -> None:  # noqa: N802 - inherited method name
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if not self._gate(path):
            return

        # Public routes
        if path in {"/", "/index.html"}:
            self._send_file(WEBSITE_DIR / "index.html")
            return
        if path == "/health":
            self._handle_health()
            return
        if path == "/sample.csv":
            self._send_file(DATA_DIR / "sample_projects.csv")
            return

        # Scalability / observability routes
        if path == "/api/scalability":
            self._handle_scalability()
            return
        if path == "/api/cluster/self":
            self._handle_cluster_self()
            return
        if path in {"/api/metrics", "/metrics"}:
            self._send_prometheus()
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

        # Static files
        requested = (WEBSITE_DIR / path.lstrip("/")).resolve()
        if WEBSITE_DIR in requested.parents and requested.exists() and requested.is_file():
            self._send_file(requested)
            return

        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_HEAD(self) -> None:  # noqa: N802 - inherited method name
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if not self._gate(path):
            return
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
        path = unquote(parsed.path)

        if not self._gate(path):
            return

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

        # Traffic-control policy update + cache administration (admin only)
        if parsed.path == "/api/traffic-control":
            self._handle_traffic_control()
            return

        # Cluster control plane: let a sibling replica arm/disarm its limiter
        # for a coordinated load test (cluster token required, see scalability.py)
        if parsed.path == "/api/cluster/arm":
            self._handle_cluster_arm()
            return

        # Cluster cache flush (admin only) - used after a deployment
        if parsed.path == "/api/cache/flush":
            self._handle_cache_flush()
            return

        # Reset the telemetry window (admin only) - start a clean measurement
        if parsed.path == "/api/metrics/reset":
            self._handle_metrics_reset()
            return

        # In-app load generator: load-test the fleet from the dashboard (admin only)
        if parsed.path == "/api/load-test":
            self._handle_load_test()
            return

        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
    
    def _get_client_ip(self) -> str:
        """Client IP, honouring the edge tier's forwarding headers.

        Behind Nginx (``proxy_set_header X-Forwarded-For``), Apache
        (``mod_remoteip``) or IIS ARR (``X-Forwarded-For``) the socket peer is
        the proxy, so the real client has to come from the header - otherwise
        the per-client rate limiter would put every officer in one bucket.
        """
        for header in ("X-Forwarded-For", "X-Real-IP", "CF-Connecting-IP"):
            value = self.headers.get(header)
            if value:
                return value.split(",")[0].strip()
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

            # Analysis-result cache: the anomaly/risk pipeline is the most
            # CPU-hungry step in the request path. Re-uploading the same extract
            # (common in review meetings) reuses the previous computation.
            # Telemetry, audit logging and the saved run id stay per-request so
            # the compliance trail is never short-circuited.
            cache_key = MONITOR.analysis_cache.key_for(filename, content)
            report = MONITOR.analysis_cache.get(cache_key)
            cache_hit = report is not None
            if cache_hit:
                print(f"Analysis cache hit for {filename} ({len(content)} bytes) on {MONITOR.instance_id}")
            else:
                records = load_records(filename, content)
                report = analyze_records_json(records, source_name=filename)
                MONITOR.analysis_cache.put(cache_key, report)
            
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
                report["served_by"] = MONITOR.instance_id
                report["cache"] = {"analysis_result": "hit" if cache_hit else "miss"}
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

    def _handle_health(self) -> None:
        """Liveness + readiness probe used by Nginx/Apache/IIS and Kubernetes.

        Kept cheap and always answerable (never rate limited or shed) because the
        load balancer's failover decision depends on it.
        """
        metrics = MONITOR.local_metrics()
        healthy = metrics["error_rate"] < 0.5
        self._send_json(
            {
                "status": "ok" if healthy else "degraded",
                "app": CONFIG.app_name,
                "version": "1.1-Scalable",
                "instance_id": MONITOR.instance_id,
                "uptime_seconds": metrics["uptime_seconds"],
                "in_flight": metrics["in_flight"],
                "saturation_pct": metrics["saturation_pct"],
                "requests_per_sec": metrics["requests_per_sec"],
                "p95_ms": metrics["latency"]["p95_ms"],
                "checks": {
                    "database": "ok",
                    "analysis_engine": "ok",
                    "concurrency_guard": "ok" if metrics["in_flight"] < MONITOR.policy.max_concurrent else "saturated",
                    "rate_limiter": "on" if MONITOR.policy.rate_limit_enabled else "off",
                },
            },
            status=HTTPStatus.OK if healthy else HTTPStatus.SERVICE_UNAVAILABLE,
        )

    def _handle_scalability(self) -> None:
        """Full scalability snapshot: telemetry, cluster, caches, events, policy."""
        user = self._require_auth(permission="view")
        if not user:
            return
        payload = MONITOR.snapshot()
        payload["viewer"] = {"username": user["username"], "role": user["role"]}
        payload["node_capacity_note"] = (
            "Requests/second and latency are measured on the live request path of every replica. "
            "The cluster-size number is a recommendation derived from those measurements."
        )
        self._send_json(payload)

    def _handle_cluster_self(self) -> None:
        """Peer-to-peer endpoint the sibling replicas poll for the fleet view."""
        provided = self.headers.get("X-Cluster-Token", "")
        if provided != SCALING.cluster_token:
            self._send_json(
                {"error": "forbidden", "message": "Cluster token required to read node telemetry."},
                status=HTTPStatus.FORBIDDEN,
            )
            return
        self._send_json(MONITOR.peer_snapshot())

    def _send_prometheus(self) -> None:
        """Prometheus/OpenMetrics scrape endpoint (wire it to Grafana)."""
        content = MONITOR.prometheus_text().encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self._send_common_headers()
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self._response_bytes = len(content)
        self.end_headers()
        self.wfile.write(content)

    def _handle_traffic_control(self) -> None:
        """Runtime traffic-control policy update (admin only)."""
        user = self._require_auth(permission="configure")
        if not user:
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
            updates = json.loads(body or "{}")
            if not isinstance(updates, dict):
                raise ValueError("Request body must be a JSON object of policy fields.")
            actor = f"{user['username']} ({user['role']})"
            result = MONITOR.apply_policy(updates, actor=actor)
            db_manager.log_action(
                "TRAFFIC_CONTROL",
                user_id=user["user_id"],
                username=user["username"],
                resource="traffic_policy",
                details=json.dumps(result["applied"]) if result["applied"] else "no change",
                ip_address=self._get_client_ip(),
            )
            self._send_json({"status": "updated", **result, "instance_id": MONITOR.instance_id})
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, status=HTTPStatus.BAD_REQUEST)

    def _handle_cluster_arm(self) -> None:
        """Cluster control endpoint used by a coordinated load test."""
        if self.headers.get("X-Cluster-Token", "") != SCALING.cluster_token:
            self._send_json(
                {"error": "forbidden", "message": "Cluster token required."},
                status=HTTPStatus.FORBIDDEN,
            )
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
            options = json.loads(body or "{}") or {}
            seconds = min(max(float(options.get("seconds", 30)), 1.0), 300.0)
            clients = options.get("client_ips") or ["127.0.0.1"]
            if not isinstance(clients, list):
                raise ValueError("client_ips must be a list of IP strings.")
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        for client in clients:
            if seconds <= 0:
                MONITOR.release_client(str(client))  # 0 seconds = re-arm the limiter
            else:
                MONITOR.exempt_client(str(client), seconds=seconds)
        MONITOR.log_event(
            "traffic_control",
            "info",
            f"Limiter paused for {','.join(map(str, clients))} for {seconds:.0f}s "
            "(coordinated load test) on " + MONITOR.instance_id + ".",
        )
        self._send_json(
            {
                "status": "armed",
                "instance_id": MONITOR.instance_id,
                "exempt_clients": clients,
                "seconds": seconds,
            }
        )

    def _handle_cache_flush(self) -> None:
        """Flush static + analysis caches on this replica (admin only)."""
        user = self._require_auth(permission="configure")
        if not user:
            return
        removed = MONITOR.asset_cache.invalidate_all()
        MONITOR.log_event(
            "cache",
            "info",
            f"{user['username']} flushed {removed} cached assets on {MONITOR.instance_id}.",
        )
        self._send_json({"status": "flushed", "assets_removed": removed, "instance_id": MONITOR.instance_id})

    def _handle_metrics_reset(self) -> None:
        """Clear counters/latency reservoir so the next measurement starts clean."""
        user = self._require_auth(permission="configure")
        if not user:
            return
        MONITOR.reset_counters()
        db_manager.log_action(
            "METRICS_RESET",
            user_id=user["user_id"],
            username=user["username"],
            resource="scalability_telemetry",
            details="Telemetry window restarted",
            ip_address=self._get_client_ip(),
        )
        self._send_json({"status": "reset", "instance_id": MONITOR.instance_id})

    def _handle_load_test(self) -> None:
        """Run the built-in load generator against this replica or the fleet."""
        user = self._require_auth(permission="manage_users")
        if not user:
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
            options = json.loads(body or "{}") or {}
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, status=HTTPStatus.BAD_REQUEST)
            return

        duration = float(options.get("duration_seconds", 8))
        concurrency = int(options.get("concurrency", 8))
        scope = str(options.get("scope", "cluster")).lower()
        path = str(options.get("path", "/api/scalability"))
        # "capacity" temporarily exempts loopback from the per-IP bucket so the
        # test measures the engine; "throttle" keeps the limiter armed on purpose.
        mode = str(options.get("mode", "capacity")).lower()

        host, port = self.server.server_address[0], self.server.server_address[1]
        host = "127.0.0.1" if host in {"0.0.0.0", "::", ""} else host
        self_url = f"http://{host}:{port}"
        targets: List[Dict[str, Any]] = [{"url": self_url, "label": MONITOR.instance_id}]
        if scope == "cluster":
            for peer in SCALING.cluster_nodes:
                clean = peer.rstrip("/")
                if clean == self_url or clean == SCALING.public_url.rstrip("/"):
                    continue  # never count this replica twice
                targets.append({"url": clean, "label": clean})

        token = self._extract_token() or ""
        armed: List[Dict[str, Any]] = []
        peer_targets = [t for t in targets if t["url"] != self_url]
        # Always start from a clean limiter state: a previous capacity test must
        # never leak its exemption into a throttle-verification run.
        MONITOR.release_client("127.0.0.1")
        MONITOR.release_client("::1")
        if peer_targets:
            arm_fleet(peer_targets, seconds=0, cluster_token=SCALING.cluster_token)

        if mode == "capacity":
            # Pause the per-IP limiter on every replica we are about to hit, so
            # the test measures the engine rather than the limiter.
            window = duration + 15
            MONITOR.exempt_client("127.0.0.1", seconds=window)
            MONITOR.exempt_client("::1", seconds=window)
            if peer_targets:
                armed = arm_fleet(peer_targets, seconds=window, cluster_token=SCALING.cluster_token)

        MONITOR.log_event(
            "load_test",
            "info",
            f"{user['username']} started a {duration:.0f}s load test "
            f"({concurrency} virtual users, {mode} mode) over {len(targets)} target(s).",
        )
        try:
            result = run_load_test(
                targets=targets,
                path=path,
                token=token,
                duration_seconds=duration,
                concurrency=concurrency,
                algorithm=MONITOR.policy.lb_algorithm,
                verify_throttling=(mode == "throttle"),
                label=f"load-test-{user['username']}",
            )
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        MONITOR.load_tests_run += 1
        result["mode"] = mode
        result["scope"] = scope
        result["run_by"] = user["username"]
        result["limiter_armed_nodes"] = [t["target"] for t in armed if t.get("ok")]
        result["limiter_skipped_nodes"] = [t for t in armed if not t.get("ok")]
        MONITOR.log_event(
            "load_test",
            "info" if result["success_rate"] > 0.9 else "warning",
            f"Load test finished: {result['requests_total']} requests, "
            f"{result['requests_per_sec']} req/s, p95 {result['latency']['p95_ms']} ms, "
            f"success {result['success_rate'] * 100:.1f}%.",
        )
        db_manager.log_action(
            "LOAD_TEST",
            user_id=user["user_id"],
            username=user["username"],
            resource=path,
            details=(
                f"{result['requests_total']} req in {result['duration_seconds']}s, "
                f"{result['requests_per_sec']} req/s, p95 {result['latency']['p95_ms']} ms"
            ),
            ip_address=self._get_client_ip(),
        )
        self._send_json(result)

    def _send_file(self, path: Path, head_only: bool = False) -> None:
        if not path.exists():
            self._send_json({"error": "File not found"}, status=HTTPStatus.NOT_FOUND, head_only=head_only)
            return
        mime_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"

        # Static assets are the cheapest thing to hoist out of the request path.
        # In production the edge tier caches them (nginx proxy_cache / Apache
        # mod_cache / IIS output caching); this in-process cache makes the same
        # effect measurable in the dashboard.
        cacheable = path.suffix.lower() in {".css", ".js", ".csv", ".html", ".svg", ".ico", ".png", ".woff2"}
        cache_key = str(path)
        content: Optional[bytes] = None
        cache_state = "bypass"
        if cacheable:
            cached = MONITOR.asset_cache.get(cache_key)
            if cached is not None:
                content, mime_type = cached
                cache_state = "hit"
            else:
                cache_state = "miss"

        if content is None:
            content = path.read_bytes()
            if cacheable:
                MONITOR.asset_cache.put(cache_key, content, mime_type)

        self.send_response(HTTPStatus.OK)
        self._send_common_headers()
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Cache", cache_state.upper())
        self.send_header(
            "Cache-Control",
            "public, max-age=300, stale-while-revalidate=60" if cacheable else "no-store",
        )
        self.send_header("ETag", f'W/"{hashlib_short(content)}"')
        self._response_bytes = len(content)
        self.end_headers()
        if not head_only:
            self.wfile.write(content)

    def _send_json(self, payload: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK, head_only: bool = False) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._send_common_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self._response_bytes = len(content)
        self.end_headers()
        if not head_only:
            self.wfile.write(content)

    def _send_common_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Cluster-Token")
        self.send_header("Access-Control-Expose-Headers", "X-Served-By, X-RateLimit-Remaining, X-Cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        # Who answered this request - how the dashboard proves the balancer is spreading load.
        self.send_header("X-Served-By", MONITOR.instance_id)
        self.send_header("X-Traffic-Decision", self._decision)
        self.send_header("Server-Timing", f"app;dur={(time.perf_counter() - self._request_started) * 1000:.2f}")
        for name, value in self._extra_headers.items():
            self.send_header(name, value)

    def do_OPTIONS(self) -> None:  # noqa: N802 - inherited method name
        parsed = urlparse(self.path)
        if not self._gate(unquote(parsed.path)):
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_common_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - inherited argument
        print(f"{MONITOR.instance_id} | {self.address_string()} - {format % args}")


def hashlib_short(content: bytes) -> str:
    """Short, stable ETag value for a static asset (cheap content hash)."""
    return hashlib.sha1(content).hexdigest()[:16]


def run(host: str = CONFIG.host, port: int = CONFIG.port) -> None:
    server = ThreadingHTTPServer((host, port), JanDrishtiHandler)
    server.daemon_threads = True
    server.request_queue_size = 256  # socket backlog: absorbs bursts at the edge
    MONITOR.log_event(
        "startup",
        "info",
        f"JAN-DRISHTI AI listening on http://{host}:{port} "
        f"(instance {MONITOR.instance_id}, cluster peers: {len(SCALING.cluster_nodes)}).",
    )
    print("Upload dashboard: open / in your browser")
    print(f"Scalability dashboard data: /api/scalability  |  Prometheus: /metrics  |  Health: /health")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the JAN-DRISHTI AI prototype server.")
    parser.add_argument("--host", default=CONFIG.host, help="Host to bind. Use 0.0.0.0 for live preview.")
    parser.add_argument("--port", type=int, default=CONFIG.port, help="Port to bind.")
    args = parser.parse_args()
    run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
