"""Horizontal scalability, traffic control and observability layer.

This module is what turns the single-process JAN-DRISHTI prototype into
something you can put behind a real edge tier (Nginx, Apache httpd or
Microsoft IIS) and scale out on.

It provides four things, all with the Python standard library only:

1. **Live telemetry** - request counters, concurrency (in-flight), rolling
   throughput/latency series, latency percentiles and error rates.
2. **Traffic control** - a token-bucket rate limiter (per client IP) and a
   load-shedding gate (max concurrent requests) that protect the model engine
   from overload. Both are tunable at runtime from the officer dashboard.
3. **Cluster awareness** - each instance exposes :meth:`ScalabilityMonitor.peer_snapshot`
   so any node can aggregate the whole fleet (the "nodes" view in the UI) and
   the load balancer can health-check every replica independently.
4. **Autoscaling signals** - a transparent scale-out/scale-in recommendation
   derived from measured p95 latency and requests/second, plus a Prometheus
   exposition endpoint for Grafana/Alertmanager.

The numbers here are real measurements of this process; nothing is simulated
except the cluster-size *recommendation*, which is clearly labelled in the UI.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import threading
import time
import urllib.error
import urllib.request
from collections import Counter, OrderedDict, deque
from dataclasses import dataclass, replace
from typing import Any, Deque, Dict, List, Optional, Tuple

from jan_drishti.config import SCALING, ScalingConfig

# Paths that are never rate limited or shed: they must stay answerable so the
# load balancer can decide whether to keep sending us traffic.
GATE_EXEMPT_PREFIXES: Tuple[str, ...] = ("/health", "/api/cluster/self")


# ---------------------------------------------------------------------------
# Traffic control primitives
# ---------------------------------------------------------------------------
class TokenBucket:
    """Classic token bucket: `rate` tokens per second, burst up to `capacity`."""

    __slots__ = ("capacity", "rate", "tokens", "updated_at")

    def __init__(self, capacity: float, rate: float) -> None:
        now = time.monotonic()
        self.capacity = float(max(capacity, 1.0))
        self.rate = float(max(rate, 0.01))
        self.tokens = self.capacity
        self.updated_at = now

    def retune(self, capacity: float, rate: float) -> None:
        self.capacity = float(max(capacity, 1.0))
        self.rate = float(max(rate, 0.01))
        self.tokens = min(self.tokens, self.capacity)

    def take(self, cost: float = 1.0) -> Tuple[bool, float]:
        """Try to spend `cost` tokens. Returns (allowed, tokens_left)."""
        now = time.monotonic()
        elapsed = max(now - self.updated_at, 0.0)
        self.updated_at = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        if self.tokens >= cost:
            self.tokens -= cost
            return True, self.tokens
        return False, self.tokens


@dataclass(frozen=True)
class AdmitDecision:
    """Result of the traffic-control gate for one request."""

    allowed: bool
    decision: str = "ok"  # ok | rate_limited | shed
    status: int = 200
    retry_after: int = 0
    detail: str = ""
    limit: int = 0
    remaining: int = 0

    @property
    def headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self.limit:
            headers["X-RateLimit-Limit"] = str(self.limit)
            headers["X-RateLimit-Remaining"] = str(max(self.remaining, 0))
        if self.retry_after:
            headers["Retry-After"] = str(self.retry_after)
        return headers


@dataclass
class TrafficPolicy:
    """Runtime-tunable traffic control + autoscaling policy."""

    rate_limit_enabled: bool
    rate_limit_rps: float
    rate_limit_burst: int
    max_concurrent: int
    load_shed_enabled: bool
    lb_algorithm: str
    autoscale_enabled: bool
    autoscale_target_p95_ms: float
    autoscale_rps_per_node: float
    autoscale_min_nodes: int
    autoscale_max_nodes: int

    def as_dict(self) -> Dict[str, Any]:
        return {
            "rate_limit_enabled": self.rate_limit_enabled,
            "rate_limit_rps": self.rate_limit_rps,
            "rate_limit_burst": self.rate_limit_burst,
            "max_concurrent": self.max_concurrent,
            "load_shed_enabled": self.load_shed_enabled,
            "lb_algorithm": self.lb_algorithm,
            "autoscale_enabled": self.autoscale_enabled,
            "autoscale_target_p95_ms": self.autoscale_target_p95_ms,
            "autoscale_rps_per_node": self.autoscale_rps_per_node,
            "autoscale_min_nodes": self.autoscale_min_nodes,
            "autoscale_max_nodes": self.autoscale_max_nodes,
        }


def policy_from_config(config: ScalingConfig = SCALING) -> TrafficPolicy:
    return TrafficPolicy(
        rate_limit_enabled=config.rate_limit_enabled,
        rate_limit_rps=config.rate_limit_rps,
        rate_limit_burst=config.rate_limit_burst,
        max_concurrent=config.max_concurrent,
        load_shed_enabled=config.load_shed_enabled,
        lb_algorithm=config.lb_algorithm,
        autoscale_enabled=config.autoscale_enabled,
        autoscale_target_p95_ms=config.autoscale_target_p95_ms,
        autoscale_rps_per_node=config.autoscale_rps_per_node,
        autoscale_min_nodes=config.autoscale_min_nodes,
        autoscale_max_nodes=config.autoscale_max_nodes,
    )


# ---------------------------------------------------------------------------
# Caches (shown live in the dashboard as cache hit ratio)
# ---------------------------------------------------------------------------
class StaticAssetCache:
    """Tiny TTL cache for website assets so repeat hits skip disk I/O.

    In production the edge tier (Nginx/Apache/IIS output cache or a CDN) does
    this; keeping it in-process as well makes the demo measurable.
    """

    def __init__(self, max_entries: int, ttl_seconds: float) -> None:
        self._max_entries = max_entries
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._entries: "OrderedDict[str, Tuple[float, bytes, str]]" = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.bytes_served_from_cache = 0

    def get(self, key: str) -> Optional[Tuple[bytes, str]]:
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if not entry:
                self.misses += 1
                return None
            expires_at, content, mime = entry
            if expires_at < now:
                self._entries.pop(key, None)
                self.misses += 1
                return None
            self._entries.move_to_end(key)
            self.hits += 1
            self.bytes_served_from_cache += len(content)
            return content, mime

    def put(self, key: str, content: bytes, mime: str) -> None:
        with self._lock:
            self._entries[key] = (time.monotonic() + self._ttl, content, mime)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
                self.evictions += 1

    def invalidate_all(self) -> int:
        with self._lock:
            removed = len(self._entries)
            self._entries.clear()
            return removed

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self.hits + self.misses
            return {
                "entries": len(self._entries),
                "max_entries": self._max_entries,
                "ttl_seconds": self._ttl,
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
                "hit_ratio": round(self.hits / total, 4) if total else 0.0,
                "bytes_served_from_cache": self.bytes_served_from_cache,
            }


class AnalysisCache:
    """Caches the (expensive) model pipeline output keyed by upload hash.

    Re-uploading the same Census/PRAGATI extract is common during a review
    meeting, and scoring is the most CPU-hungry step of the request path, so
    this is the first thing worth caching when traffic grows. Audit logging and
    the saved run id still happen for every request - only the computation is
    reused.
    """

    def __init__(self, max_entries: int) -> None:
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._entries: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key_for(filename: str, content: bytes) -> str:
        digest = hashlib.sha256(content).hexdigest()[:32]
        return f"{filename}:{digest}"

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cached = self._entries.get(key)
            if cached is None:
                self.misses += 1
                return None
            self._entries.move_to_end(key)
            self.hits += 1
            return json.loads(json.dumps(cached))  # deep copy, callers mutate

    def put(self, key: str, report: Dict[str, Any]) -> None:
        with self._lock:
            self._entries[key] = json.loads(json.dumps(report))
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self.hits + self.misses
            return {
                "entries": len(self._entries),
                "max_entries": self._max_entries,
                "hits": self.hits,
                "misses": self.misses,
                "hit_ratio": round(self.hits / total, 4) if total else 0.0,
            }


# ---------------------------------------------------------------------------
# The monitor
# ---------------------------------------------------------------------------
class ScalabilityMonitor:
    """Thread-safe, in-process telemetry + traffic control + cluster aggregation."""

    def __init__(self, config: ScalingConfig = SCALING) -> None:
        self.config = config
        self.instance_id = config.instance_id
        self.started_at = time.time()
        self.started_monotonic = time.monotonic()
        self._lock = threading.Lock()
        self._policy_lock = threading.Lock()

        # Counters
        self.total_requests = 0
        self.total_bytes_out = 0
        self.status_counts: Counter = Counter()
        self.endpoint_counts: Counter = Counter()
        self.throttled_total = 0
        self.shed_total = 0
        self.server_error_total = 0
        self.peak_inflight = 0
        self._inflight = 0
        self.proxied_requests = 0

        # Latency reservoir (bounded) -> percentiles
        self._latencies: Deque[float] = deque(maxlen=config.latency_reservoir)

        # Rolling per-second series for the dashboard charts
        self._series: "OrderedDict[int, List[float]]" = OrderedDict()

        # Recent activity + scaling events
        self.recent_requests: Deque[Dict[str, Any]] = deque(maxlen=config.recent_request_log)
        self.events: Deque[Dict[str, Any]] = deque(maxlen=config.event_log)

        # Traffic control state
        self.policy = policy_from_config(config)
        self._buckets: Dict[str, TokenBucket] = {}
        self._buckets_lock = threading.Lock()
        self.policy_changes: List[Dict[str, Any]] = []
        self.last_recommendation: Optional[Dict[str, Any]] = None

        # Caches
        self.asset_cache = StaticAssetCache(
            max_entries=config.asset_cache_max_entries,
            ttl_seconds=config.asset_cache_ttl_seconds,
        )
        self.analysis_cache = AnalysisCache(max_entries=config.analysis_cache_entries)

        self._peer_cache: Optional[Dict[str, Any]] = None
        self._peer_cache_at = 0.0

        # Loopback exemption used while a capacity test is running (so the test
        # measures the engine, not the limiter). Throttle-verification runs keep
        # the limiter fully armed.
        self._exempt_clients: Dict[str, float] = {}
        self.load_tests_run = 0

        self.log_event(
            "startup",
            "info",
            f"Instance {self.instance_id} online on pid {config.pid} "
            f"(rate limit {self.policy.rate_limit_rps:.0f} req/s/IP, "
            f"max concurrency {self.policy.max_concurrent}).",
        )

    # -- time series helpers -------------------------------------------------
    def _bucket(self, ts: int) -> List[float]:
        """Return [requests, errors, throttled+shed, latency_sum_ms] for second ts."""
        series = self._series
        bucket = series.get(ts)
        if bucket is None:
            bucket = [0.0, 0.0, 0.0, 0.0]
            series[ts] = bucket
            cutoff = ts - self.config.series_window_seconds
            while series:
                oldest = next(iter(series))
                if oldest < cutoff:
                    series.popitem(last=False)
                else:
                    break
        return bucket

    # -- traffic control -----------------------------------------------------
    def _bucket_for(self, client_ip: str) -> TokenBucket:
        with self._buckets_lock:
            bucket = self._buckets.get(client_ip)
            policy = self.policy
            if bucket is None:
                # Bounded map: keep the hottest ~512 clients, drop the rest.
                if len(self._buckets) > 512:
                    self._buckets.clear()
                bucket = TokenBucket(policy.rate_limit_burst, policy.rate_limit_rps)
                self._buckets[client_ip] = bucket
            else:
                bucket.retune(policy.rate_limit_burst, policy.rate_limit_rps)
            return bucket

    def exempt_client(self, client_ip: str, seconds: float = 45.0) -> None:
        """Temporarily bypass the per-client token bucket (load tests only)."""
        with self._buckets_lock:
            self._exempt_clients[client_ip] = time.monotonic() + seconds

    def release_client(self, client_ip: str) -> None:
        """Re-arm the limiter for a client (end of a capacity test)."""
        with self._buckets_lock:
            self._exempt_clients.pop(client_ip, None)

    def _is_exempt(self, client_ip: str) -> bool:
        with self._buckets_lock:
            expiry = self._exempt_clients.get(client_ip)
            if not expiry:
                return False
            if expiry < time.monotonic():
                self._exempt_clients.pop(client_ip, None)
                return False
            return True

    def admit(self, client_ip: str, path: str) -> AdmitDecision:
        """Traffic-control gate. Called before any work is done for a request."""
        if any(path.startswith(prefix) for prefix in GATE_EXEMPT_PREFIXES):
            return AdmitDecision(allowed=True)

        policy = self.policy

        # 1) Global concurrency guard -> load shedding (returns 503 + Retry-After)
        with self._lock:
            inflight = self._inflight
        if policy.load_shed_enabled and inflight >= policy.max_concurrent:
            return AdmitDecision(
                allowed=False,
                decision="shed",
                status=503,
                retry_after=1,
                detail=(
                    f"Server at capacity: {inflight}/{policy.max_concurrent} concurrent requests "
                    "in flight. Request shed to protect model latency."
                ),
            )

        # 2) Per-client token bucket -> rate limiting (returns 429 + Retry-After)
        if policy.rate_limit_enabled and not self._is_exempt(client_ip):
            allowed, tokens_left = self._bucket_for(client_ip).take(1.0)
            if not allowed:
                return AdmitDecision(
                    allowed=False,
                    decision="rate_limited",
                    status=429,
                    retry_after=1,
                    detail=(
                        f"Rate limit exceeded for {client_ip}: "
                        f"{policy.rate_limit_rps:.0f} req/s sustained, burst {policy.rate_limit_burst}."
                    ),
                    limit=int(policy.rate_limit_rps),
                    remaining=0,
                )
            return AdmitDecision(
                allowed=True,
                limit=int(policy.rate_limit_rps),
                remaining=int(tokens_left),
            )
        return AdmitDecision(allowed=True)

    def begin(self) -> None:
        with self._lock:
            self._inflight += 1
            if self._inflight > self.peak_inflight:
                self.peak_inflight = self._inflight

    def abandon(self) -> None:
        """Release an in-flight slot for a connection that closed without a request."""
        with self._lock:
            self._inflight = max(self._inflight - 1, 0)

    def record(
        self,
        *,
        method: str,
        path: str,
        status: int,
        latency_ms: float,
        bytes_out: int = 0,
        client: str = "-",
        decision: str = "ok",
        node: Optional[str] = None,
        proxied: bool = False,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a finished request (called for every response, incl. 4xx/5xx)."""
        now = time.time()
        node = node or self.instance_id
        with self._lock:
            self._inflight = max(self._inflight - 1, 0)
            self.total_requests += 1
            self.total_bytes_out += max(int(bytes_out), 0)
            self.status_counts[str(status)] += 1
            self.endpoint_counts[self._endpoint_label(path)] += 1
            self._latencies.append(latency_ms)
            if status >= 500:
                self.server_error_total += 1
            if decision == "rate_limited":
                self.throttled_total += 1
            elif decision == "shed":
                self.shed_total += 1
            if proxied:
                self.proxied_requests += 1

            bucket = self._bucket(int(now))
            bucket[0] += 1
            bucket[1] += 1 if status >= 500 else 0
            bucket[2] += 1 if decision != "ok" else 0
            bucket[3] += latency_ms

            entry = {
                "timestamp": now,
                "time": time.strftime("%H:%M:%S", time.localtime(now)),
                "method": method,
                "path": path,
                "status": status,
                "latency_ms": round(latency_ms, 2),
                "decision": decision,
                "client": client,
                "node": node,
            }
            self.recent_requests.append(entry)
        return entry

    @staticmethod
    def _endpoint_label(path: str) -> str:
        """Group dynamic ids so the per-endpoint table stays readable."""
        if path.startswith("/api/"):
            return "/".join(path.split("/")[:3])
        if path.startswith("/assets/"):
            return "/assets/*"
        return path or "/"

    def log_event(self, kind: str, level: str, message: str) -> Dict[str, Any]:
        event = {
            "timestamp": time.time(),
            "time": time.strftime("%H:%M:%S", time.localtime()),
            "kind": kind,
            "level": level,
            "node": self.instance_id,
            "message": message,
        }
        with self._lock:
            self.events.append(event)
        print(f"[{kind}] {message}")
        return event

    # -- percentiles ---------------------------------------------------------
    def _latency_stats(self) -> Dict[str, float]:
        with self._lock:
            samples = sorted(self._latencies)
        if not samples:
            return {"count": 0, "avg_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0, "max_ms": 0.0}

        def pct(p: float) -> float:
            idx = min(int(round(p * (len(samples) - 1))), len(samples) - 1)
            return round(samples[idx], 2)

        return {
            "count": len(samples),
            "avg_ms": round(sum(samples) / len(samples), 2),
            "p50_ms": pct(0.50),
            "p95_ms": pct(0.95),
            "p99_ms": pct(0.99),
            "max_ms": round(samples[-1], 2),
        }

    def live_rps(self, window_seconds: int = 5) -> float:
        now = int(time.time())
        with self._lock:
            recent = [bucket[0] for ts, bucket in self._series.items() if ts > now - window_seconds]
        if not recent:
            return 0.0
        return round(sum(recent) / max(min(window_seconds, max(now - (now - window_seconds), 1)), 1), 2)

    def _series_payload(self, window: int = 60) -> List[Dict[str, Any]]:
        now = int(time.time())
        start = now - window + 1
        with self._lock:
            snapshot = {ts: list(bucket) for ts, bucket in self._series.items() if ts >= start}
        series: List[Dict[str, Any]] = []
        for ts in range(start, now + 1):
            count, errors, limited, latency_sum = snapshot.get(ts, [0.0, 0.0, 0.0, 0.0])
            series.append(
                {
                    "t": ts,
                    "time": time.strftime("%H:%M:%S", time.localtime(ts)),
                    "requests": int(count),
                    "errors": int(errors),
                    "limited": int(limited),
                    "avg_ms": round(latency_sum / count, 2) if count else 0.0,
                }
            )
        return series

    # -- autoscaling ---------------------------------------------------------
    def _recommendation(self, nodes: int, rps: float, p95_ms: float, policy: TrafficPolicy) -> Dict[str, Any]:
        if not policy.autoscale_enabled:
            return {
                "desired_nodes": nodes,
                "action": "hold",
                "reason": "Autoscaling policy is disabled - cluster size held at the operator setting.",
                "utilisation": 0.0,
            }

        capacity_rps = max(policy.autoscale_rps_per_node, 1.0)
        latency_pressure = p95_ms / policy.autoscale_target_p95_ms if policy.autoscale_target_p95_ms else 0.0
        throughput_pressure = (rps / capacity_rps) if nodes else 0.0
        pressure = max(latency_pressure, throughput_pressure)

        desired = nodes
        if pressure > 0.75:
            desired = min(policy.autoscale_max_nodes, max(nodes + 1, int(nodes * pressure + 0.999)))
        elif pressure < 0.35 and nodes > policy.autoscale_min_nodes:
            desired = max(policy.autoscale_min_nodes, nodes - 1)

        if desired > nodes:
            action = "scale_out"
            reason = (
                f"p95 {p95_ms:.0f} ms (target {policy.autoscale_target_p95_ms:.0f} ms) and "
                f"{rps:.1f} req/s across {nodes} node(s) -> add {desired - nodes} node(s)."
            )
        elif desired < nodes:
            action = "scale_in"
            reason = (
                f"Load dropped to {rps:.1f} req/s with p95 {p95_ms:.0f} ms -> "
                f"remove {nodes - desired} node(s) during the next maintenance window."
            )
        else:
            action = "hold"
            reason = (
                f"{rps:.1f} req/s with p95 {p95_ms:.0f} ms fits current capacity "
                f"({nodes} node(s), {capacity_rps:.0f} req/s target each)."
            )

        return {
            "desired_nodes": max(policy.autoscale_min_nodes, min(desired, policy.autoscale_max_nodes)),
            "action": action,
            "reason": reason,
            "utilisation": round(min(pressure, 9.99), 2),
            "capacity_rps": capacity_rps,
            "target_p95_ms": policy.autoscale_target_p95_ms,
        }

    # -- cluster view --------------------------------------------------------
    def _probe_peer(self, url: str) -> Dict[str, Any]:
        """Fetch a peer node's compact snapshot over HTTP (short timeout)."""
        request = urllib.request.Request(
            f"{url.rstrip('/')}/api/cluster/self",
            headers={
                "X-Cluster-Token": self.config.cluster_token,
                "User-Agent": f"jan-drishti-monitor/{self.instance_id}",
            },
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.config.peer_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            payload["status"] = "healthy"
            payload["probe_ms"] = round((time.perf_counter() - started) * 1000, 2)
            payload["url"] = url
            return payload
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return {
                "instance_id": url,
                "url": url,
                "status": "down",
                "error": str(exc),
                "probe_ms": round((time.perf_counter() - started) * 1000, 2),
                "metrics": {},
                "series": [],
            }

    def peer_snapshot(self) -> Dict[str, Any]:
        """Compact payload other nodes download to build the fleet view."""
        return {
            "instance_id": self.instance_id,
            "pid": self.config.pid,
            "uptime_seconds": round(time.time() - self.started_at, 1),
            "metrics": self.local_metrics(),
            "series": self._series_payload(60),
            "policy": self.policy.as_dict(),
        }

    def local_metrics(self) -> Dict[str, Any]:
        with self._lock:
            inflight = self._inflight
            total = self.total_requests
            throttled = self.throttled_total
            shed = self.shed_total
            errors = self.server_error_total
            bytes_out = self.total_bytes_out
            statuses = dict(self.status_counts)
            endpoints = dict(self.endpoint_counts.most_common(12))
            peak = self.peak_inflight
            proxied = self.proxied_requests
            recent = list(self.recent_requests)[-25:]
        latency = self._latency_stats()
        return {
            "instance_id": self.instance_id,
            "pid": self.config.pid,
            "uptime_seconds": round(time.time() - self.started_at, 1),
            "requests_total": total,
            "requests_per_sec": self.live_rps(),
            "in_flight": inflight,
            "peak_in_flight": peak,
            "max_concurrent": self.policy.max_concurrent,
            "saturation_pct": round(100.0 * inflight / self.policy.max_concurrent, 1)
            if self.policy.max_concurrent
            else 0.0,
            "throttled_total": throttled,
            "shed_total": shed,
            "server_errors_total": errors,
            "error_rate": round(errors / total, 4) if total else 0.0,
            "bytes_out": bytes_out,
            "status_counts": statuses,
            "top_endpoints": endpoints,
            "latency": latency,
            "proxied_requests": proxied,
            "recent_requests": recent,
        }

    def cluster_snapshot(self, force: bool = False) -> Dict[str, Any]:
        """Aggregate this node plus all configured peers into one fleet view."""
        now = time.monotonic()
        if not force and self._peer_cache and (now - self._peer_cache_at) < self.config.peer_cache_seconds:
            return self._peer_cache

        local_entry: Dict[str, Any] = {
            "instance_id": self.instance_id,
            "url": self.config.public_url,
            "status": "healthy",
            "probe_ms": 0.0,
            "metrics": self.local_metrics(),
            "series": None,  # use our own series directly
            "is_self": True,
        }

        peer_entries: List[Dict[str, Any]] = []
        threads = []
        results: Dict[str, Dict[str, Any]] = {}

        def worker(target: str) -> None:
            results[target] = self._probe_peer(target)

        own_url = self.config.public_url.rstrip("/") if self.config.public_url else ""
        for peer in self.config.cluster_nodes:
            if own_url and peer.rstrip("/") == own_url:
                continue  # this node is in its own peer list - count it once, as "self"
            thread = threading.Thread(target=worker, args=(peer,), daemon=True)
            thread.start()
            threads.append((peer, thread))
        for _, thread in threads:
            thread.join(timeout=self.config.peer_timeout_seconds + 0.5)

        for peer, _ in threads:
            payload = results.get(peer)
            if payload is None:
                payload = {"instance_id": peer, "url": peer, "status": "down", "metrics": {}, "series": []}
            if payload.get("instance_id") == self.instance_id:
                continue  # reached ourselves through a proxy/alias - do not double count
            payload.setdefault("is_self", False)
            peer_entries.append(payload)

        entries = [local_entry] + peer_entries
        up = [e for e in entries if e.get("status") == "healthy"]

        # Fleet totals
        def total_of(key: str) -> float:
            return sum(float(e.get("metrics", {}).get(key, 0) or 0) for e in up)

        rps = round(total_of("requests_per_sec"), 2)
        inflight = int(total_of("in_flight"))
        capacity = int(total_of("max_concurrent"))
        latencies = [e["metrics"]["latency"]["p95_ms"] for e in up if e.get("metrics", {}).get("latency")]
        p95 = round(max(latencies), 2) if latencies else 0.0
        p95_avg = round(sum(latencies) / len(latencies), 2) if latencies else 0.0

        # Merge per-second series for the fleet chart
        merged: Dict[int, List[float]] = {}
        for entry in up:
            series = entry.get("series")
            if series is None:
                series = self._series_payload(60)
            for point in series or []:
                slot = merged.setdefault(int(point["t"]), [0, 0, 0, 0.0])
                slot[0] += int(point.get("requests", 0))
                slot[1] += int(point.get("errors", 0))
                slot[2] += int(point.get("limited", 0))
                slot[3] += float(point.get("avg_ms", 0.0))
        fleet_series = [
            {
                "t": ts,
                "time": time.strftime("%H:%M:%S", time.localtime(ts)),
                "requests": int(values[0]),
                "errors": int(values[1]),
                "limited": int(values[2]),
                "avg_ms": round(values[3] / len(up), 2) if up else 0.0,
            }
            for ts, values in sorted(merged.items())
        ]

        recommendation = self._recommendation(len(up), rps, p95, self.policy)
        previous = self.last_recommendation
        if previous is None or previous.get("action") != recommendation["action"]:
            if previous is not None and recommendation["action"] != "hold":
                level = "warning" if recommendation["action"] == "scale_out" else "info"
                self.log_event("autoscale", level, recommendation["reason"])
            self.last_recommendation = recommendation

        node_rows = []
        for entry in entries:
            metrics = entry.get("metrics", {}) or {}
            node_rows.append(
                {
                    "instance_id": entry.get("instance_id", "unknown"),
                    "url": entry.get("url", "-"),
                    "status": entry.get("status", "unknown"),
                    "is_self": bool(entry.get("is_self")),
                    "probe_ms": entry.get("probe_ms", 0.0),
                    "requests_total": metrics.get("requests_total", 0),
                    "requests_per_sec": metrics.get("requests_per_sec", 0),
                    "in_flight": metrics.get("in_flight", 0),
                    "max_concurrent": metrics.get("max_concurrent", self.policy.max_concurrent),
                    "saturation_pct": metrics.get("saturation_pct", 0.0),
                    "p95_ms": metrics.get("latency", {}).get("p95_ms", 0.0),
                    "p95_avg_ms": metrics.get("latency", {}).get("avg_ms", 0.0),
                    "error_rate": metrics.get("error_rate", 0.0),
                    "throttled_total": metrics.get("throttled_total", 0),
                    "shed_total": metrics.get("shed_total", 0),
                    "uptime_seconds": metrics.get("uptime_seconds", 0.0),
                    "error": entry.get("error"),
                }
            )

        total_requests = int(total_of("requests_total")) or 1
        for row in node_rows:
            row["traffic_share_pct"] = round(100.0 * row["requests_total"] / total_requests, 1)

        payload = {
            "cluster": {
                "nodes_total": len(node_rows),
                "nodes_healthy": len(up),
                "nodes_down": len(node_rows) - len(up),
                "requests_total": int(total_of("requests_total")),
                "requests_per_sec": rps,
                "in_flight": inflight,
                "capacity_concurrent": capacity,
                "saturation_pct": round(100.0 * inflight / capacity, 1) if capacity else 0.0,
                "throttled_total": int(total_of("throttled_total")),
                "shed_total": int(total_of("shed_total")),
                "server_errors_total": int(total_of("server_errors_total")),
                "bytes_out": int(total_of("bytes_out")),
                "p95_ms": p95,
                "p95_avg_ms": p95_avg,
                "nodes": node_rows,
                "series": fleet_series,
            },
            "local": local_entry,
            "recommendation": recommendation,
            "caches": {
                "static_assets": self.asset_cache.stats(),
                "analysis_results": self.analysis_cache.stats(),
            },
            "generated_at": time.time(),
        }
        self._peer_cache = payload
        self._peer_cache_at = now
        return payload

    # -- public snapshot -----------------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        cluster = self.cluster_snapshot()
        with self._lock:
            events = list(self.events)[-25:]
            recent = list(self.recent_requests)[-25:]
            changes = list(self.policy_changes)[-10:]
        local = self.local_metrics()
        return {
            "instance": {
                "instance_id": self.instance_id,
                "pid": self.config.pid,
                "uptime_seconds": local["uptime_seconds"],
                "started_at": self.started_at,
                "environment": self.config.environment,
                "public_url": self.config.public_url,
            },
            "traffic_control": self.policy.as_dict(),
            "policy_changes": changes,
            "metrics": local,
            "cluster": cluster["cluster"],
            "recommendation": cluster["recommendation"],
            "caches": cluster["caches"],
            "events": events,
            "recent_requests": recent,
            "series": self._series_payload(60),
            "topology": self.topology(),
            "generated_at": time.time(),
        }

    def topology(self) -> Dict[str, Any]:
        """Describe the edge tier so the dashboard can show the real request path."""
        return {
            "proxy_layer": self.config.proxy_layer,
            "proxy_layer_label": {
                "nginx": "Nginx reverse proxy + upstream load balancer",
                "apache": "Apache httpd mod_proxy_balancer",
                "iis": "Microsoft IIS + ARR (Application Request Routing)",
                "traefik": "Traefik / cloud load balancer",
                "none": "Direct to app server (no edge tier attached yet)",
            }.get(self.config.proxy_layer, self.config.proxy_layer),
            "enforcement_chain": [
                {
                    "layer": "1. Edge / WAF",
                    "what": "TLS termination, connection + request rate limits, IP reputation, DDoS absorption",
                    "where": "Nginx limit_req_zone / Apache mod_qos / IIS Dynamic IP Restrictions",
                    "status": "active" if self.config.proxy_layer != "none" else "ready",
                },
                {
                    "layer": "2. Load balancer",
                    "what": "Spread traffic over N app replicas, health-check them, retry the next upstream",
                    "where": "nginx upstream keepalive / balancer:// (lbmethod) / IIS ARR server farm",
                    "status": "active" if self.config.cluster_nodes else "single node",
                },
                {
                    "layer": "3. App traffic control",
                    "what": "Per-IP token bucket (429) and concurrency guard with load shedding (503)",
                    "where": "jan_drishti/services/scalability.py",
                    "status": "active" if (self.policy.rate_limit_enabled or self.policy.load_shed_enabled) else "off",
                },
                {
                    "layer": "4. Caches",
                    "what": "Static asset cache, analysis-result cache, DB read path",
                    "where": "in-process LRU + proxy_cache / mod_cache / IIS output caching",
                    "status": "active",
                },
                {
                    "layer": "5. Autoscaler",
                    "what": "Scale replicas from measured p95 latency and req/s",
                    "where": "Kubernetes HPA or VM scale set (see deploy/kubernetes)",
                    "status": "recommend-only" if self.policy.autoscale_enabled else "off",
                },
            ],
            "nodes": [
                {"instance_id": self.instance_id, "url": self.config.public_url, "role": "app replica"},
            ]
            + [{"instance_id": url, "url": url, "role": "app replica"} for url in self.config.cluster_nodes],
        }

    # -- runtime policy ------------------------------------------------------
    def apply_policy(self, updates: Dict[str, Any], actor: str = "system") -> Dict[str, Any]:
        """Validate and apply traffic-control/autoscale changes at runtime."""
        with self._policy_lock:
            current = self.policy.as_dict()
            new_values = dict(current)
            applied: Dict[str, Any] = {}

            def clamp_float(key: str, low: float, high: float) -> None:
                if key in updates and updates[key] is not None:
                    value = float(updates[key])
                    if value < low or value > high:
                        raise ValueError(f"{key} must be between {low} and {high}.")
                    new_values[key] = value
                    applied[key] = value

            def clamp_int(key: str, low: int, high: int) -> None:
                if key in updates and updates[key] is not None:
                    value = int(updates[key])
                    if value < low or value > high:
                        raise ValueError(f"{key} must be between {low} and {high}.")
                    new_values[key] = value
                    applied[key] = value

            def flag(key: str) -> None:
                if key in updates and updates[key] is not None:
                    value = bool(updates[key])
                    new_values[key] = value
                    applied[key] = value

            clamp_float("rate_limit_rps", 0.5, 20000.0)
            clamp_int("rate_limit_burst", 1, 100000)
            clamp_int("max_concurrent", 1, 4096)
            clamp_float("autoscale_target_p95_ms", 10.0, 10000.0)
            clamp_float("autoscale_rps_per_node", 1.0, 100000.0)
            clamp_int("autoscale_min_nodes", 1, 512)
            clamp_int("autoscale_max_nodes", 1, 512)
            flag("rate_limit_enabled")
            flag("load_shed_enabled")
            flag("autoscale_enabled")

            if "lb_algorithm" in updates and updates["lb_algorithm"]:
                algorithm = str(updates["lb_algorithm"]).strip().lower()
                if algorithm not in {"round_robin", "least_conn", "ip_hash", "weighted"}:
                    raise ValueError("lb_algorithm must be one of round_robin, least_conn, ip_hash, weighted.")
                new_values["lb_algorithm"] = algorithm
                applied["lb_algorithm"] = algorithm

            if int(new_values["autoscale_min_nodes"]) > int(new_values["autoscale_max_nodes"]):
                raise ValueError("autoscale_min_nodes cannot exceed autoscale_max_nodes.")

            self.policy = replace(self.policy, **new_values)
            # Retune existing buckets immediately so the change is felt at once.
            with self._buckets_lock:
                for bucket in self._buckets.values():
                    bucket.retune(self.policy.rate_limit_burst, self.policy.rate_limit_rps)
            self._peer_cache = None  # force a fresh fleet view on next poll

            if applied:
                change = {
                    "timestamp": time.time(),
                    "time": time.strftime("%H:%M:%S", time.localtime()),
                    "actor": actor,
                    "changed": applied,
                    "policy": self.policy.as_dict(),
                }
                self.policy_changes.append(change)
                summary = ", ".join(f"{key}={value}" for key, value in applied.items())
                self.log_event("traffic_control", "warning", f"{actor} updated traffic control: {summary}")
            return {"applied": applied, "policy": self.policy.as_dict()}

    def reset_counters(self) -> None:
        with self._lock:
            self.total_requests = 0
            self.total_bytes_out = 0
            self.status_counts.clear()
            self.endpoint_counts.clear()
            self.throttled_total = 0
            self.shed_total = 0
            self.server_error_total = 0
            self.peak_inflight = 0
            self._latencies.clear()
            self._series.clear()
            self.recent_requests.clear()
        with self._buckets_lock:
            self._buckets.clear()
        self.log_event("maintenance", "info", "Counters reset by operator (window restarted).")

    # -- Prometheus ----------------------------------------------------------
    def prometheus_text(self) -> str:
        cluster = self.cluster_snapshot()
        local = self.local_metrics()
        latency = local["latency"]
        policy = self.policy
        node = self.instance_id
        lines: List[str] = []

        def emit(name: str, value: Any, help_text: str, metric_type: str = "gauge", labels: str = "") -> None:
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} {metric_type}")
            lines.append(f"{name}{labels} {value}")

        emit("jan_drishti_up", 1, "1 when the JAN-DRISHTI app replica is serving traffic.", "gauge", f'{{node="{node}"}}')
        emit("jan_drishti_uptime_seconds", round(time.time() - self.started_at, 1), "Replica uptime in seconds.", "gauge", f'{{node="{node}"}}')
        emit("jan_drishti_requests_total", local["requests_total"], "Requests handled by this replica.", "counter", f'{{node="{node}"}}')
        emit("jan_drishti_requests_in_flight", local["in_flight"], "Requests currently being processed.", "gauge", f'{{node="{node}"}}')
        emit("jan_drishti_request_latency_ms", latency["p50_ms"], "Request latency quantile (ms).", "gauge", f'{{node="{node}",quantile="0.5"}}')
        lines.append(f'jan_drishti_request_latency_ms{{node="{node}",quantile="0.95"}} {latency["p95_ms"]}')
        lines.append(f'jan_drishti_request_latency_ms{{node="{node}",quantile="0.99"}} {latency["p99_ms"]}')
        emit("jan_drishti_rate_limited_total", local["throttled_total"], "Requests rejected by the per-IP token bucket (HTTP 429).", "counter", f'{{node="{node}"}}')
        emit("jan_drishti_shed_total", local["shed_total"], "Requests shed to protect the cluster (HTTP 503).", "counter", f'{{node="{node}"}}')
        emit("jan_drishti_server_errors_total", local["server_errors_total"], "5xx responses.", "counter", f'{{node="{node}"}}')
        emit("jan_drishti_rate_limit_rps", policy.rate_limit_rps, "Configured per-client rate limit.", "gauge", f'{{node="{node}"}}')
        emit("jan_drishti_max_concurrent", policy.max_concurrent, "Configured concurrency ceiling.", "gauge", f'{{node="{node}"}}')
        for status, count in sorted(local["status_counts"].items()):
            lines.append(f'jan_drishti_responses_total{{node="{node}",status="{status}"}} {count}')
        assets = self.asset_cache.stats()
        emit("jan_drishti_cache_hits_total", assets["hits"], "Static asset cache hits.", "counter", f'{{node="{node}"}}')
        emit("jan_drishti_cache_misses_total", assets["misses"], "Static asset cache misses.", "counter", f'{{node="{node}"}}')
        analysis = self.analysis_cache.stats()
        emit("jan_drishti_analysis_cache_hits_total", analysis["hits"], "Analysis pipeline cache hits.", "counter", f'{{node="{node}"}}')

        cluster_meta = cluster["cluster"]
        emit("jan_drishti_cluster_nodes", cluster_meta["nodes_healthy"], "Healthy replicas seen by this node.", "gauge", f'{{node="{node}"}}')
        emit("jan_drishti_cluster_nodes_down", cluster_meta["nodes_down"], "Replicas that failed the health probe.", "gauge", f'{{node="{node}"}}')
        emit("jan_drishti_cluster_requests_per_sec", cluster_meta["requests_per_sec"], "Fleet throughput (req/s).", "gauge", f'{{node="{node}"}}')
        emit("jan_drishti_cluster_p95_ms", cluster_meta["p95_ms"], "Worst p95 latency across the fleet (ms).", "gauge", f'{{node="{node}"}}')
        emit("jan_drishti_autoscale_desired_nodes", cluster["recommendation"]["desired_nodes"], "Replicas the autoscaler policy recommends.", "gauge", f'{{node="{node}"}}')
        lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Built-in load generator (used by the dashboard's "Run load test" button)
# ---------------------------------------------------------------------------
def run_load_test(
    targets: List[Dict[str, Any]],
    path: str,
    token: str = "",
    duration_seconds: float = 8.0,
    concurrency: int = 8,
    algorithm: str = "round_robin",
    verify_throttling: bool = False,
    label: str = "load-test",
) -> Dict[str, Any]:
    """Drive real HTTP traffic at the fleet and report what came back.

    This is a small in-app load generator: `concurrency` worker threads reuse
    keep-alive connections and blast `path` at the targets for
    `duration_seconds`. It exists so a reviewer can watch the dashboard move
    without installing Locust/k6/ab first. For serious benchmarks use the
    scripts in ``scripts/``.
    """
    if not targets:
        raise ValueError("No targets to test.")
    if not 1 <= concurrency <= 64:
        raise ValueError("concurrency must be between 1 and 64.")
    if not 1 <= duration_seconds <= 30:
        raise ValueError("duration_seconds must be between 1 and 30.")
    if not path.startswith("/"):
        raise ValueError("path must start with '/'.")
    if path.startswith("/api/load-test"):
        raise ValueError("Refusing to load-test the load-test endpoint (recursion guard).")

    lock = threading.Lock()
    latencies: List[float] = []
    status_counts: Counter = Counter()
    node_counts: Counter = Counter()
    total = 0
    in_flight_per_node: Counter = Counter()
    deadline = time.monotonic() + duration_seconds
    started = time.perf_counter()
    cursor = 0

    headers = {"Accept": "application/json", "User-Agent": f"jan-drishti-{label}"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def pick_target() -> Dict[str, Any]:
        nonlocal cursor
        if algorithm in {"least_conn", "weighted"}:
            with lock:
                return min(targets, key=lambda t: in_flight_per_node[t["url"]])
        with lock:
            target = targets[cursor % len(targets)]
            cursor += 1
        return target

    def worker() -> None:
        nonlocal total
        connection: Optional[http.client.HTTPConnection] = None
        current_url: Optional[str] = None
        while time.monotonic() < deadline:
            target = pick_target()
            url = target["url"]
            if connection is None or current_url != url:
                if connection is not None:
                    connection.close()
                host, port = _split_base_url(url)
                connection = http.client.HTTPConnection(host, port, timeout=5)
                current_url = url
            with lock:
                in_flight_per_node[url] += 1
            request_started = time.perf_counter()
            status = 0
            served_by = target.get("label") or url
            try:
                connection.request("GET", path, headers=headers)
                response = connection.getresponse()
                response.read()
                status = response.status
                served_by = response.getheader("X-Served-By") or served_by
            except Exception:  # noqa: BLE001 - a failed probe is just a failed probe
                status = 0
                try:
                    connection.close()
                except Exception:  # noqa: BLE001
                    pass
                connection = None
                current_url = None
            elapsed_ms = (time.perf_counter() - request_started) * 1000
            with lock:
                in_flight_per_node[url] -= 1
                latencies.append(elapsed_ms)
                status_counts[str(status)] += 1
                node_counts[served_by] += 1
                total += 1
        if connection is not None:
            connection.close()

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(concurrency)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=duration_seconds + 10)

    wall_seconds = max(time.perf_counter() - started, 0.0001)
    ordered = sorted(latencies)

    def pct(p: float) -> float:
        if not ordered:
            return 0.0
        idx = min(int(round(p * (len(ordered) - 1))), len(ordered) - 1)
        return round(ordered[idx], 2)

    ok = status_counts.get("200", 0) + status_counts.get("201", 0) + status_counts.get("204", 0)
    grid_nodes = max(len(targets), 1)
    result = {
        "label": label,
        "path": path,
        "targets": [t.get("url") for t in targets],
        "lb_algorithm": algorithm,
        "concurrency": concurrency,
        "duration_seconds": round(wall_seconds, 2),
        "requests_total": total,
        "requests_ok": ok,
        "requests_per_sec": round(total / wall_seconds, 2),
        "success_rate": round(ok / total, 4) if total else 0.0,
        "status_counts": dict(status_counts),
        "latency": {
            "avg_ms": round(sum(ordered) / len(ordered), 2) if ordered else 0.0,
            "p50_ms": pct(0.50),
            "p95_ms": pct(0.95),
            "p99_ms": pct(0.99),
            "max_ms": round(ordered[-1], 2) if ordered else 0.0,
        },
        "node_distribution": [
            {
                "node": node,
                "requests": count,
                "share_pct": round(100.0 * count / total, 1) if total else 0.0,
            }
            for node, count in node_counts.most_common()
        ],
        "expected_node_share_pct": round(100.0 / grid_nodes, 1),
        "throttling_verified": bool(status_counts.get("429")) if verify_throttling else None,
        "shed_503": status_counts.get("503", 0),
        "errors": status_counts.get("0", 0),
        "finished_at": time.time(),
    }
    return result


def _split_base_url(url: str) -> Tuple[str, int]:
    """'http://127.0.0.1:8001' -> ('127.0.0.1', 8001)."""
    without_scheme = url.split("://", 1)[-1].rstrip("/")
    host_port = without_scheme.split("/", 1)[0]
    if ":" in host_port:
        host, port = host_port.rsplit(":", 1)
        return host, int(port)
    return host_port, 80


def arm_fleet(targets: List[Dict[str, Any]], seconds: float, cluster_token: str) -> List[Dict[str, Any]]:
    """Tell every replica to hold off rate limiting for a loopback load test.

    A distributed load generator is one logical client; without this each replica
    would throttle it independently and the capacity numbers would measure the
    limiter instead of the engine. Replicas acknowledge through the
    cluster-token-protected control endpoint.
    """
    armed: List[Dict[str, Any]] = []
    lock = threading.Lock()

    def worker(target: Dict[str, Any]) -> None:
        url = target["url"]
        host, port = _split_base_url(url)
        payload = json.dumps({"seconds": seconds, "client_ips": ["127.0.0.1", "::1"]}).encode("utf-8")
        headers = {"Content-Type": "application/json", "X-Cluster-Token": cluster_token}
        try:
            connection = http.client.HTTPConnection(host, port, timeout=2)
            connection.request("POST", "/api/cluster/arm", body=payload, headers=headers)
            response = connection.getresponse()
            body = response.read().decode("utf-8", errors="replace")
            connection.close()
            result = {"target": url, "status": response.status, "ok": response.status == 200}
            if response.status != 200:
                result["detail"] = body[:200]
        except Exception as exc:  # noqa: BLE001 - report and keep going
            result = {"target": url, "status": 0, "ok": False, "detail": str(exc)}
        with lock:
            armed.append(result)

    threads = [threading.Thread(target=worker, args=(t,), daemon=True) for t in targets]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)
    return armed


# Module-level singleton used by the HTTP server.
MONITOR = ScalabilityMonitor()
