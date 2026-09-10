"""Tests for the login / access analytics dashboard.

The dashboard is only useful if the numbers are trustworthy, so these tests fix
the counting rules: what counts as a sign-in, what counts as a failed attempt,
how "active users" is derived from the session lifetime, and who is allowed to
see client IP addresses.
"""

from __future__ import annotations

import json
import pathlib
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from jan_drishti.services.access_analytics import AccessAnalytics
from jan_drishti.services.database import DatabaseManager


class AccessAnalyticsUnitTests(unittest.TestCase):
    """Counting rules, against a throwaway database."""

    def setUp(self) -> None:
        self.tmp = pathlib.Path(tempfile.mkdtemp()) / "analytics.db"
        self.db = DatabaseManager(db_path=self.tmp)
        self.now = datetime(2026, 9, 10, 12, 0, 0)
        self.analytics = AccessAnalytics(self.db, now=self.now)

    def _seed(self) -> None:
        self.db.log_action("LOGIN", user_id="adm001", username="admin", ip_address="10.0.0.1", details="Role: admin")
        self.db.log_action("LOGIN", user_id="aud001", username="auditor", ip_address="10.0.0.2", details="Role: auditor")
        self.db.log_action("LOGIN_FAILED", username="admin", ip_address="10.0.0.9", details="Invalid password", success=False)
        self.db.log_action("AUTH_FAILED", ip_address="10.0.0.9", details="Invalid token signature", success=False)
        # Non-authentication actions must never be counted as logins.
        self.db.log_action("ANALYZE", user_id="aud001", username="auditor", resource="sample.csv")
        self.db.log_action("VIEW_TRANSPARENCY", user_id="aud001", username="auditor")

    def test_successful_and_failed_attempts_are_counted_separately(self) -> None:
        self._seed()
        summary = self.analytics.summarize()
        self.assertEqual(summary["logins"]["total"], 2)
        self.assertEqual(summary["failures"]["total"], 2)
        self.assertEqual(summary["failures"]["success_rate"], 0.5)

    def test_non_login_actions_are_not_counted_as_logins(self) -> None:
        self._seed()
        summary = self.analytics.summarize()
        self.assertEqual(summary["logins"]["total"], 2)  # not 4 (ANALYZE/VIEW excluded)
        self.assertEqual(summary["recent"][0]["action"] in {"LOGIN", "LOGIN_FAILED", "AUTH_FAILED"}, True)

    def test_user_table_reports_per_user_activity(self) -> None:
        self._seed()
        rows = {row["username"]: row for row in self.analytics.summarize()["user_table"]}
        self.assertEqual(rows["admin"]["logins"], 1)
        self.assertEqual(rows["admin"]["failed_attempts"], 1)
        self.assertEqual(rows["auditor"]["failed_attempts"], 0)
        # A user account that never signed in is still listed, flagged clearly.
        self.assertTrue(rows["viewer"]["never_logged_in"])
        self.assertEqual(rows["viewer"]["last_login_display"], "Never")

    def test_active_users_follow_the_session_lifetime(self) -> None:
        self._seed()
        summary = self.analytics.summarize()
        self.assertEqual(summary["users"]["active_now"], 2)
        self.assertEqual(summary["users"]["total"], 3)
        self.assertEqual(summary["users"]["by_role"], {"admin": 1, "auditor": 1, "viewer": 1})
        self.assertIn("8 hours", summary["definitions"]["active_user"])

        # Two hours later both users are inside the window; nine hours later they are not.
        later = AccessAnalytics(self.db, now=self.now + timedelta(hours=9)).summarize()
        self.assertEqual(later["users"]["active_now"], 0)

    def test_series_covers_the_requested_window_and_totals_match(self) -> None:
        self._seed()
        summary = self.analytics.summarize(days=7)
        self.assertEqual(len(summary["series"]), 7)
        self.assertEqual(summary["series"][-1]["date"], "2026-09-10")
        self.assertEqual(sum(point["logins"] for point in summary["series"]), 2)
        self.assertEqual(sum(point["failed"] for point in summary["series"]), 2)
        self.assertEqual(summary["window"]["days"], 7)

    def test_old_activity_falls_outside_the_window_but_stays_in_the_totals(self) -> None:
        self.db.log_action("LOGIN", user_id="adm001", username="admin")
        # Age every row by 40 days.
        with self.db.get_connection() as conn:
            conn.execute("UPDATE audit_log SET timestamp = ?", ((self.now - timedelta(days=40)).isoformat(),))
        summary = self.analytics.summarize(days=14)
        self.assertEqual(summary["logins"]["total"], 1)
        self.assertEqual(summary["logins"]["in_window"], 0)

    def test_window_is_clamped_to_a_sane_range(self) -> None:
        self._seed()
        self.assertEqual(self.analytics.summarize(days=0)["window"]["days"], 1)
        self.assertEqual(self.analytics.summarize(days=5000)["window"]["days"], 90)

    def test_client_ips_are_withheld_from_non_admins(self) -> None:
        self._seed()
        admin_view = self.analytics.summarize(include_ips=True, user_admin=True)
        self.assertTrue(admin_view["ip_visible"])
        self.assertEqual(admin_view["recent"][0]["ip_address"], "10.0.0.9")

        analyst_view = self.analytics.summarize(include_ips=False, user_admin=False)
        self.assertFalse(analyst_view["ip_visible"])
        self.assertTrue(all("ip_address" not in entry for entry in analyst_view["recent"]))
        # Aggregates are still available to non-admins.
        self.assertEqual(analyst_view["logins"]["total"], 2)

    def test_platform_activity_reports_analysis_usage(self) -> None:
        self.db.save_analysis_run(
            run_id="run-1",
            user_id="adm001",
            username="admin",
            report={"summary": {"projects_analyzed": 44, "high_risk": 3, "critical_risk": 1}},
        )
        activity = self.analytics.summarize()["activity"]
        self.assertEqual(activity["analyses_run"], 1)
        self.assertEqual(activity["projects_screened"], 44)
        self.assertEqual(activity["last_analysis_by"], "admin")


class AccessAnalyticsHttpTests(unittest.TestCase):
    """The endpoint the dashboard actually calls, over a real socket."""

    @classmethod
    def setUpClass(cls) -> None:
        from jan_drishti.server import JanDrishtiHandler

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), JanDrishtiHandler)
        cls.server.daemon_threads = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.host, cls.port = cls.server.server_address[0], cls.server.server_address[1]
        cls.admin_token = cls._login("admin", "admin123")
        cls.viewer_token = cls._login("viewer", "viewer123")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    @classmethod
    def _request(cls, method: str, path: str, body: bytes = b"", headers: dict | None = None):
        connection = HTTPConnection(cls.host, cls.port, timeout=10)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        payload = response.read().decode("utf-8")
        status = response.status
        connection.close()
        return status, payload

    @classmethod
    def _login(cls, username: str, password: str) -> str:
        status, payload = cls._request(
            "POST",
            "/api/login",
            json.dumps({"username": username, "password": password}).encode(),
            {"Content-Type": "application/json"},
        )
        assert status == 200, payload
        return json.loads(payload)["token"]

    def test_requires_authentication(self) -> None:
        status, _ = self._request("GET", "/api/access-analytics")
        self.assertEqual(status, 401)

    def test_admin_receives_the_full_payload_including_ips(self) -> None:
        status, payload = self._request(
            "GET",
            "/api/access-analytics?days=7",
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(status, 200, payload)
        body = json.loads(payload)
        for key in ("logins", "failures", "users", "activity", "series", "user_table", "recent", "definitions"):
            self.assertIn(key, body)
        self.assertEqual(len(body["series"]), 7)
        self.assertTrue(body["ip_visible"])
        # The admin login performed in setUp must be reflected in the counts.
        self.assertGreaterEqual(body["logins"]["total"], 1)
        self.assertTrue(any(row["username"] == "admin" for row in body["user_table"]))

    def test_viewer_sees_aggregates_but_no_ips(self) -> None:
        status, payload = self._request(
            "GET",
            "/api/access-analytics",
            headers={"Authorization": f"Bearer {self.viewer_token}"},
        )
        self.assertEqual(status, 200, payload)
        body = json.loads(payload)
        self.assertFalse(body["ip_visible"])
        self.assertTrue(all("ip_address" not in entry for entry in body["recent"]))
        self.assertGreaterEqual(body["users"]["total"], 1)

    def test_invalid_range_falls_back_to_the_default(self) -> None:
        status, payload = self._request(
            "GET",
            "/api/access-analytics?days=abc",
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(payload)["series"]), 14)

    def test_favicon_is_served_as_an_image(self) -> None:
        connection = HTTPConnection(self.host, self.port, timeout=10)
        connection.request("GET", "/favicon.svg")
        response = connection.getresponse()
        content = response.read()
        content_type = response.getheader("Content-Type", "")
        connection.close()
        self.assertEqual(response.status, 200)
        self.assertIn("image/svg+xml", content_type)
        self.assertIn(b"<svg", content)


if __name__ == "__main__":
    unittest.main()
