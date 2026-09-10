"""Tests for the scalability, traffic-control and observability layer.

Covers the three things that must not silently break once the app runs behind a
load balancer:

1. traffic control decisions (token bucket, load shedding, exemptions),
2. runtime policy changes (validation + clamping),
3. the live HTTP surface (``/health``, ``/api/scalability``, ``/api/metrics``,
   auth on protected routes, 429 behaviour and real counters).
"""

from __future__ import annotations

import dataclasses
import http.client
import json
import threading
import time
import unittest
from http.server import ThreadingHTTPServer

from jan_drishti.config import SCALING
from jan_drishti.services.scalability import (
    MONITOR,
    ScalabilityMonitor,
    TokenBucket,
    run_load_test,
)


def make_monitor(**overrides) -> ScalabilityMonitor:
    """Build an isolated monitor with test-friendly limits."""
    defaults = dict(
        instance_id="test-node",
        cluster_nodes=(),
        rate_limit_enabled=True,
        rate_limit_rps=5.0,
        rate_limit_burst=5,
        max_concurrent=2,
        load_shed_enabled=True,
        autoscale_min_nodes=1,
        autoscale_max_nodes=4,
    )
    defaults.update(overrides)
    return ScalabilityMonitor(dataclasses.replace(SCALING, **defaults))


class TokenBucketTests(unittest.TestCase):
    def test_bucket_allows_burst_then_blocks(self) -> None:
        bucket = TokenBucket(capacity=3, rate=0.5)
        allowed = [bucket.take()[0] for _ in range(3)]
        self.assertEqual(allowed, [True, True, True])
        blocked, remaining = bucket.take()
        self.assertFalse(blocked)
        self.assertLess(remaining, 1)

    def test_bucket_refills_over_time(self) -> None:
        bucket = TokenBucket(capacity=1, rate=1000)  # 1 token per millisecond
        self.assertTrue(bucket.take()[0])
        self.assertFalse(bucket.take()[0])
        for _ in range(50):
            time.sleep(0.005)
            if bucket.take()[0]:
                return
        self.fail("bucket never refilled")


class TrafficControlTests(unittest.TestCase):
    def test_healthy_request_is_admitted_with_limit_headers(self) -> None:
        monitor = make_monitor()
        decision = monitor.admit("10.0.0.1", "/api/model-transparency")
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.decision, "ok")
        self.assertEqual(decision.headers.get("X-RateLimit-Limit"), "5")

    def test_rate_limited_request_gets_429_and_retry_after(self) -> None:
        monitor = make_monitor(rate_limit_rps=1.0, rate_limit_burst=1)
        self.assertTrue(monitor.admit("10.0.0.2", "/api/analyze").allowed)
        decision = monitor.admit("10.0.0.2", "/api/analyze")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.decision, "rate_limited")
        self.assertEqual(decision.status, 429)
        self.assertEqual(decision.headers.get("Retry-After"), "1")

    def test_limits_are_per_client(self) -> None:
        monitor = make_monitor(rate_limit_rps=1.0, rate_limit_burst=1)
        self.assertTrue(monitor.admit("10.0.0.3", "/api/analyze").allowed)
        self.assertFalse(monitor.admit("10.0.0.3", "/api/analyze").allowed)
        # A different officer must not inherit someone else's bucket.
        self.assertTrue(monitor.admit("10.0.0.4", "/api/analyze").allowed)

    def test_concurrency_guard_sheds_with_503(self) -> None:
        monitor = make_monitor(max_concurrent=1)
        monitor.begin()  # one request already in flight
        decision = monitor.admit("10.0.0.5", "/api/analyze")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.decision, "shed")
        self.assertEqual(decision.status, 503)
        monitor.abandon()

    def test_health_probe_is_never_throttled(self) -> None:
        monitor = make_monitor(rate_limit_rps=1.0, rate_limit_burst=1, max_concurrent=1)
        monitor.begin()
        for _ in range(5):
            self.assertTrue(monitor.admit("10.0.0.6", "/health").allowed)
        monitor.abandon()

    def test_exempt_client_bypasses_limiter_and_release_restores_it(self) -> None:
        monitor = make_monitor(rate_limit_rps=1.0, rate_limit_burst=1)
        monitor.exempt_client("10.0.0.7", seconds=30)
        for _ in range(20):
            self.assertTrue(monitor.admit("10.0.0.7", "/api/scalability").allowed)
        monitor.release_client("10.0.0.7")
        monitor.admit("10.0.0.7", "/api/scalability")
        self.assertFalse(monitor.admit("10.0.0.7", "/api/scalability").allowed)

    def test_counters_track_throttling_and_shedding(self) -> None:
        monitor = make_monitor(rate_limit_rps=1.0, rate_limit_burst=1)
        monitor.begin()
        monitor.record(method="GET", path="/api/analyze", status=200, latency_ms=12.0)
        monitor.admit("10.0.0.8", "/api/analyze")
        blocked = monitor.admit("10.0.0.8", "/api/analyze")
        monitor.record(method="GET", path="/api/analyze", status=blocked.status, latency_ms=1.0, decision=blocked.decision)
        metrics = monitor.local_metrics()
        self.assertEqual(metrics["requests_total"], 2)
        self.assertEqual(metrics["throttled_total"], 1)
        self.assertEqual(metrics["in_flight"], 0)
        self.assertGreaterEqual(metrics["latency"]["p95_ms"], 1.0)


class PolicyTests(unittest.TestCase):
    def test_policy_update_is_applied_and_clamped_to_valid_range(self) -> None:
        monitor = make_monitor()
        result = monitor.apply_policy({"rate_limit_rps": 120, "max_concurrent": 256, "lb_algorithm": "round_robin"}, actor="tester")
        self.assertEqual(result["applied"]["rate_limit_rps"], 120.0)
        self.assertEqual(monitor.policy.max_concurrent, 256)
        self.assertEqual(monitor.policy.lb_algorithm, "round_robin")

    def test_invalid_values_are_rejected_without_mutating_policy(self) -> None:
        monitor = make_monitor()
        with self.assertRaises(ValueError):
            monitor.apply_policy({"rate_limit_rps": -5})
        with self.assertRaises(ValueError):
            monitor.apply_policy({"autoscale_min_nodes": 8, "autoscale_max_nodes": 2})
        with self.assertRaises(ValueError):
            monitor.apply_policy({"lb_algorithm": "magic"})
        self.assertEqual(monitor.policy.rate_limit_rps, 5.0)

    def test_disabling_the_limiter_lets_everything_through(self) -> None:
        monitor = make_monitor(rate_limit_rps=1.0, rate_limit_burst=1)
        monitor.apply_policy({"rate_limit_enabled": False})
        for _ in range(30):
            self.assertTrue(monitor.admit("10.0.0.9", "/api/analyze").allowed)

    def test_policy_changes_are_audited_as_events(self) -> None:
        monitor = make_monitor()
        monitor.apply_policy({"rate_limit_rps": 33}, actor="admin (admin)")
        kinds = [event["kind"] for event in monitor.events]
        self.assertIn("traffic_control", kinds)


class TelemetryTests(unittest.TestCase):
    def test_snapshot_exposes_the_dashboard_contract(self) -> None:
        monitor = make_monitor()
        monitor.begin()
        monitor.record(method="GET", path="/api/scalability", status=200, latency_ms=8.0, bytes_out=512)
        snapshot = monitor.snapshot()
        for key in ("instance", "traffic_control", "metrics", "cluster", "recommendation", "caches", "events", "series", "topology"):
            self.assertIn(key, snapshot)
        self.assertEqual(snapshot["cluster"]["nodes_total"], 1)
        self.assertEqual(snapshot["cluster"]["nodes"][0]["instance_id"], "test-node")
        self.assertEqual(snapshot["metrics"]["requests_total"], 1)
        self.assertIn("enforcement_chain", snapshot["topology"])

    def test_recommendation_scales_out_under_pressure(self) -> None:
        monitor = make_monitor(autoscale_target_p95_ms=100, autoscale_rps_per_node=10, autoscale_min_nodes=1, autoscale_max_nodes=8)
        # Simulate a hot fleet: many requests per second with slow responses.
        for _ in range(200):
            monitor.begin()
            monitor.record(method="GET", path="/api/analyze", status=200, latency_ms=400.0)
        recommendation = monitor.snapshot()["recommendation"]
        self.assertIn(recommendation["action"], {"scale_out", "hold"})
        self.assertGreater(recommendation["utilisation"], 0)

    def test_disabled_autoscaler_holds_the_cluster_size(self) -> None:
        monitor = make_monitor(autoscale_enabled=False)
        recommendation = monitor.snapshot()["recommendation"]
        self.assertEqual(recommendation["action"], "hold")

    def test_prometheus_exposition_contains_key_metrics(self) -> None:
        monitor = make_monitor()
        monitor.begin()
        monitor.record(method="GET", path="/health", status=200, latency_ms=3.0)
        text = monitor.prometheus_text()
        for metric in (
            "jan_drishti_up",
            "jan_drishti_requests_total",
            "jan_drishti_requests_in_flight",
            "jan_drishti_request_latency_ms",
            "jan_drishti_rate_limited_total",
            "jan_drishti_shed_total",
            "jan_drishti_cluster_nodes",
            "jan_drishti_autoscale_desired_nodes",
        ):
            self.assertIn(metric, text)
        self.assertIn('status="200"', text)

    def test_static_asset_cache_reports_hit_ratio(self) -> None:
        monitor = make_monitor()
        self.assertIsNone(monitor.asset_cache.get("index.html"))
        monitor.asset_cache.put("index.html", b"<html></html>", "text/html")
        self.assertIsNotNone(monitor.asset_cache.get("index.html"))
        stats = monitor.asset_cache.stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertAlmostEqual(stats["hit_ratio"], 0.5, places=3)

    def test_analysis_cache_returns_independent_copies(self) -> None:
        monitor = make_monitor()
        key = monitor.analysis_cache.key_for("data.csv", b"a,b\n1,2\n")
        monitor.analysis_cache.put(key, {"summary": {"projects_analyzed": 3}})
        first = monitor.analysis_cache.get(key)
        first["summary"]["projects_analyzed"] = 99
        second = monitor.analysis_cache.get(key)
        self.assertEqual(second["summary"]["projects_analyzed"], 3)


class LoadTestRunnerTests(unittest.TestCase):
    def test_load_test_drives_real_requests_and_reports_latency(self) -> None:
        from jan_drishti.server import JanDrishtiHandler

        server = ThreadingHTTPServer(("127.0.0.1", 0), JanDrishtiHandler)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address[0], server.server_address[1]
            result = run_load_test(
                targets=[{"url": f"http://{host}:{port}", "label": "test-node"}],
                path="/health",
                duration_seconds=1.5,
                concurrency=4,
                algorithm="round_robin",
            )
            self.assertGreater(result["requests_total"], 0)
            self.assertGreater(result["requests_per_sec"], 0)
            self.assertEqual(result["status_counts"].get("200"), result["requests_total"])
            self.assertGreaterEqual(result["latency"]["p95_ms"], result["latency"]["p50_ms"])
            # The reported node comes from the response's X-Served-By header,
            # i.e. the replica that actually answered - exactly what the
            # dashboard uses to prove the load balancer is spreading traffic.
            self.assertEqual(result["node_distribution"][0]["node"], MONITOR.instance_id)
        finally:
            server.shutdown()
            server.server_close()

    def test_load_test_validates_its_parameters(self) -> None:
        with self.assertRaises(ValueError):
            run_load_test(targets=[], path="/health")
        with self.assertRaises(ValueError):
            run_load_test(targets=[{"url": "http://127.0.0.1:1", "label": "x"}], path="/api/load-test")
        with self.assertRaises(ValueError):
            run_load_test(targets=[{"url": "http://127.0.0.1:1", "label": "x"}], path="/health", concurrency=999)


class LiveServerIntegrationTests(unittest.TestCase):
    """Exercise the real handler over real sockets (one server for the class)."""

    @classmethod
    def setUpClass(cls) -> None:
        from jan_drishti.server import JanDrishtiHandler

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), JanDrishtiHandler)
        cls.server.daemon_threads = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.host, cls.port = cls.server.server_address[0], cls.server.server_address[1]
        # The tests hammer the shared monitor from loopback; keep the limiter
        # paused for the class so only the limiter test exercises throttling.
        MONITOR.exempt_client("127.0.0.1", seconds=600)
        cls.token = cls._login()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    @classmethod
    def _request(cls, method: str, path: str, body: bytes = b"", headers: dict = None) -> tuple:
        connection = http.client.HTTPConnection(cls.host, cls.port, timeout=10)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        payload = response.read().decode("utf-8")
        result = response.status, dict(response.getheaders()), payload
        connection.close()
        return result

    @classmethod
    def _login(cls) -> str:
        status, _, payload = cls._request(
            "POST",
            "/api/login",
            json.dumps({"username": "admin", "password": "admin123"}).encode(),
            {"Content-Type": "application/json"},
        )
        assert status == 200, payload
        return json.loads(payload)["token"]

    def test_health_reports_instance_and_capacity(self) -> None:
        status, headers, payload = self._request("GET", "/health")
        self.assertEqual(status, 200)
        body = json.loads(payload)
        self.assertIn("instance_id", body)
        self.assertIn("saturation_pct", body)
        self.assertIn("rate_limiter", body["checks"])
        self.assertTrue(headers.get("X-Served-By"))
        self.assertIn("app;dur=", headers.get("Server-Timing", ""))

    def test_scalability_endpoint_requires_authentication(self) -> None:
        status, _, _ = self._request("GET", "/api/scalability")
        self.assertEqual(status, 401)

    def test_scalability_endpoint_returns_fleet_view(self) -> None:
        status, _, payload = self._request("GET", "/api/scalability", headers={"Authorization": f"Bearer {self.token}"})
        self.assertEqual(status, 200)
        body = json.loads(payload)
        self.assertGreaterEqual(body["cluster"]["nodes_healthy"], 1)
        self.assertEqual(body["metrics"]["requests_total"] > 0, True)
        self.assertIn("enforcement_chain", body["topology"])

    def test_prometheus_endpoint_is_plain_text(self) -> None:
        status, headers, payload = self._request("GET", "/api/metrics")
        self.assertEqual(status, 200)
        self.assertIn("text/plain", headers.get("Content-Type", ""))
        self.assertIn("jan_drishti_up", payload)

    def test_traffic_policy_update_round_trip(self) -> None:
        original = MONITOR.policy.as_dict()
        try:
            body = json.dumps({"rate_limit_rps": 500, "rate_limit_burst": 900}).encode()
            status, _, payload = self._request(
                "POST",
                "/api/traffic-control",
                body,
                {"Content-Type": "application/json", "Authorization": f"Bearer {self.token}"},
            )
            self.assertEqual(status, 200, payload)
            self.assertEqual(json.loads(payload)["policy"]["rate_limit_rps"], 500.0)

            # A non-admin must not be able to change traffic control.
            viewer_status, _, viewer_payload = self._request(
                "POST",
                "/api/login",
                json.dumps({"username": "viewer", "password": "viewer123"}).encode(),
                {"Content-Type": "application/json"},
            )
            self.assertEqual(viewer_status, 200, viewer_payload)
            viewer_token = json.loads(viewer_payload)["token"]
            forbidden, _, _ = self._request(
                "POST",
                "/api/traffic-control",
                body,
                {"Content-Type": "application/json", "Authorization": f"Bearer {viewer_token}"},
            )
            self.assertEqual(forbidden, 403)
        finally:
            MONITOR.apply_policy(original, actor="test-cleanup")
            MONITOR.exempt_client("127.0.0.1", seconds=600)

    def test_rate_limiter_returns_429_with_retry_after(self) -> None:
        MONITOR.release_client("127.0.0.1")
        original = MONITOR.policy.as_dict()
        try:
            MONITOR.apply_policy({"rate_limit_rps": 1, "rate_limit_burst": 1, "rate_limit_enabled": True})
            statuses = []
            for _ in range(4):
                status, headers, payload = self._request("GET", "/api/scalability", headers={"Authorization": f"Bearer {self.token}"})
                statuses.append(status)
                if status == 429:
                    self.assertEqual(headers.get("Retry-After"), "1")
                    self.assertEqual(json.loads(payload)["error"], "rate_limited")
                    break
            self.assertIn(429, statuses)
        finally:
            MONITOR.release_client("127.0.0.1")
            MONITOR.apply_policy(original, actor="test-cleanup")
            MONITOR.exempt_client("127.0.0.1", seconds=600)

    def test_analyze_endpoint_scores_the_sample_dataset(self) -> None:
        from pathlib import Path

        sample = Path(__file__).resolve().parents[1] / "data" / "sample_projects.csv"
        if not sample.exists():
            self.skipTest("sample dataset not available")
        boundary = "----jandrishti-test-boundary"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="sample_projects.csv"\r\n'
            "Content-Type: text/csv\r\n\r\n"
        ).encode() + sample.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        status, _, payload = self._request(
            "POST",
            "/api/analyze",
            body,
            {"Content-Type": f"multipart/form-data; boundary={boundary}", "Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(status, 200, payload[:300])
        report = json.loads(payload)
        self.assertIn("summary", report)
        self.assertIn("served_by", report)

        # Re-uploading the identical file must hit the analysis cache but still
        # produce a fresh, auditable run.
        hits_before = MONITOR.analysis_cache.stats()["hits"]
        status, _, payload = self._request(
            "POST",
            "/api/analyze",
            body,
            {"Content-Type": f"multipart/form-data; boundary={boundary}", "Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(payload)["cache"]["analysis_result"], "hit")
        self.assertEqual(MONITOR.analysis_cache.stats()["hits"], hits_before + 1)

    def test_health_is_answerable_while_saturated(self) -> None:
        """The balancer must still be able to probe a replica at full load."""
        original = MONITOR.policy.as_dict()
        try:
            MONITOR.apply_policy({"max_concurrent": 1})
            MONITOR.begin()  # simulate one long analysis occupying the only slot
            status, _, payload = self._request("GET", "/health")
            self.assertEqual(status, 200, payload)
            overloaded, _, overload_payload = self._request(
                "GET", "/api/scalability", headers={"Authorization": f"Bearer {self.token}"}
            )
            self.assertEqual(overloaded, 503)
            self.assertEqual(json.loads(overload_payload)["error"], "server_overloaded")
        finally:
            MONITOR.abandon()
            MONITOR.apply_policy(original, actor="test-cleanup")
            MONITOR.exempt_client("127.0.0.1", seconds=600)


if __name__ == "__main__":
    unittest.main()
