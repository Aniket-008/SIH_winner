#!/usr/bin/env python3
"""External load generator for JAN-DRISHTI AI (standard library only).

The dashboard has a built-in load test for a quick demo; this script is the
"real" benchmark you run from a machine that is not the server:

    # capacity test: measure how much the fleet can serve
    python scripts/load_test.py --url http://127.0.0.1:8000 --duration 20 --concurrency 32

    # hit the whole fleet behind the balancer (watch the spread)
    python scripts/load_test.py --url http://127.0.0.1:8080 --duration 20 --concurrency 64

    # verify the rate limiter actually returns 429 + Retry-After
    python scripts/load_test.py --url http://127.0.0.1:8000 --path /api/model-transparency \
        --token <bearer-token> --expect-429

    # pause the in-app limiter on every replica first (capacity measurement),
    # then run the test and print the per-node distribution
    python scripts/load_test.py --url http://127.0.0.1:8000 --nodes \
        http://127.0.0.1:8000,http://127.0.0.1:8001 --arm --token <bearer-token>

Output: live one-line status while running, then a summary with
throughput, p50/p95/p99 latency, status mix and (if the balancer is in front)
how the requests were spread across replicas.
"""

from __future__ import annotations

import argparse
import http.client
import json
import statistics
import sys
import threading
import time
import urllib.parse
import urllib.request
from collections import Counter
from typing import Dict, List, Optional


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load test the JAN-DRISHTI AI API.")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Base URL to hit (balancer or single replica).")
    parser.add_argument("--path", default="/health", help="Request path (default /health).")
    parser.add_argument("--concurrency", type=int, default=16, help="Virtual users (default 16, max 512).")
    parser.add_argument("--duration", type=float, default=15.0, help="Seconds to run (default 15).")
    parser.add_argument("--token", default="", help="Bearer token for protected endpoints.")
    parser.add_argument("--username", default="", help="Login as this user to obtain a token automatically.")
    parser.add_argument("--password", default="", help="Password for --username.")
    parser.add_argument("--expect-429", action="store_true", help="Assert the rate limiter rejects with HTTP 429.")
    parser.add_argument("--arm", action="store_true", help="Ask each replica to pause its own limiter first.")
    parser.add_argument("--nodes", default="", help="Comma-separated replica URLs for --arm.")
    parser.add_argument("--cluster-token", default="jandrishti-cluster-demo", help="Token for /api/cluster/arm.")
    return parser.parse_args()


def login(base_url: str, username: str, password: str) -> str:
    payload = json.dumps({"username": username, "password": password}).encode()
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode())["token"]


def arm_nodes(nodes: List[str], cluster_token: str, seconds: float) -> None:
    for node in nodes:
        payload = json.dumps({"seconds": seconds, "client_ips": ["0.0.0.0"]}).encode()
        # client_ips = the load generator's IP; use your own public address here.
        request = urllib.request.Request(
            f"{node.rstrip('/')}/api/cluster/arm",
            data=payload,
            headers={"Content-Type": "application/json", "X-Cluster-Token": cluster_token},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                print(f"  armed {node}: HTTP {response.status}")
        except Exception as exc:  # noqa: BLE001
            print(f"  could not arm {node}: {exc}")


def main() -> int:
    args = parse_args()
    concurrency = max(1, min(args.concurrency, 512))
    parsed = urllib.parse.urlparse(args.url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = args.path if args.path.startswith("/") else f"/{args.path}"

    token = args.token
    if not token and args.username:
        token = login(args.url, args.username, args.password)
        print(f"Logged in as {args.username}")

    if args.arm:
        nodes = [node.strip() for node in args.nodes.split(",") if node.strip()] or [args.url]
        print(f"Pausing the in-app limiter on {len(nodes)} node(s) for {args.duration + 30:.0f}s…")
        arm_nodes(nodes, args.cluster_token, args.duration + 30)

    headers = {"Accept": "application/json", "User-Agent": "jan-drishti-load-test"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    latencies: List[float] = []
    status_counts: Counter = Counter()
    node_counts: Counter = Counter()
    lock = threading.Lock()
    stop_at = time.monotonic() + args.duration
    started = time.perf_counter()

    print(
        f"\nTarget {args.url}{path} | {concurrency} virtual users | {args.duration:.0f}s | "
        f"rate limit left {'on' if not args.arm else 'paused'}\n"
    )

    def worker() -> None:
        connection: Optional[http.client.HTTPConnection] = None
        while time.monotonic() < stop_at:
            if connection is None:
                connection = http.client.HTTPConnection(host, port, timeout=10)
            request_started = time.perf_counter()
            status = 0
            served_by = "-"
            try:
                connection.request("GET", path, headers=headers)
                response = connection.getresponse()
                response.read()
                status = response.status
                served_by = response.getheader("X-Served-By") or "-"
            except Exception:  # noqa: BLE001
                status = 0
                try:
                    connection.close()
                except Exception:  # noqa: BLE001
                    pass
                connection = None
            elapsed_ms = (time.perf_counter() - request_started) * 1000
            with lock:
                latencies.append(elapsed_ms)
                status_counts[str(status)] += 1
                node_counts[served_by] += 1
        if connection is not None:
            connection.close()

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(concurrency)]
    for thread in threads:
        thread.start()

    try:
        while any(thread.is_alive() for thread in threads):
            with lock:
                done = len(latencies)
                elapsed = max(time.perf_counter() - started, 0.001)
                ok = status_counts.get("200", 0)
            sys.stdout.write(f"\r  {done:>8,} requests | {done / elapsed:>8.1f} req/s | {ok:>8,} ok ")
            sys.stdout.flush()
            time.sleep(0.5)
    except KeyboardInterrupt:
        stop_at = time.monotonic()
    for thread in threads:
        thread.join(timeout=5)

    wall = max(time.perf_counter() - started, 0.001)
    total = len(latencies)
    print("\n")
    if total == 0:
        print("No requests completed - is the server running?", file=sys.stderr)
        return 1

    ordered = sorted(latencies)

    def pct(p: float) -> float:
        index = min(int(round(p * (len(ordered) - 1))), len(ordered) - 1)
        return ordered[index]

    ok = sum(count for status, count in status_counts.items() if status.startswith("2"))
    print("=" * 62)
    print("LOAD TEST SUMMARY")
    print("=" * 62)
    print(f"  throughput        : {total / wall:,.1f} req/s")
    print(f"  requests          : {total:,} in {wall:.1f}s ({concurrency} virtual users)")
    print(f"  success rate      : {ok / total * 100:.2f}%")
    print(f"  latency avg/median: {statistics.fmean(ordered):.1f} ms / {pct(0.5):.1f} ms")
    print(f"  latency p95/p99   : {pct(0.95):.1f} ms / {pct(0.99):.1f} ms")
    print(f"  latency max       : {ordered[-1]:.1f} ms")
    print("  status mix        : " + ", ".join(f"{code}: {count:,}" for code, count in sorted(status_counts.items())))
    if len(node_counts) > 1 or "-" not in node_counts:
        print("  replica spread    :")
        for node, count in node_counts.most_common():
            print(f"      {node:<28} {count:>8,} ({100 * count / total:.1f}%)")
    print("=" * 62)

    if args.expect_429:
        throttled = status_counts.get("429", 0)
        if throttled:
            print(f"PASS: rate limiter rejected {throttled:,} requests with HTTP 429.")
            return 0
        print("FAIL: no 429 responses - the limiter is disabled or the limit is too high.", file=sys.stderr)
        return 2

    if status_counts.get("503"):
        print(f"NOTE: {status_counts['503']:,} requests were shed (503) - the cluster is at capacity.")
    if status_counts.get("0"):
        print(f"NOTE: {status_counts['0']:,} requests failed to complete (connection errors).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
