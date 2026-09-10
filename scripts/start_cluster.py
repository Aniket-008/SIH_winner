#!/usr/bin/env python3
"""Launch a local cluster of JAN-DRISHTI AI replicas wired to each other.

Use it to demo horizontal scaling without Docker or Kubernetes:

    python scripts/start_cluster.py                     # 3 replicas on 8000-8002
    python scripts/start_cluster.py --nodes 4           # 4 replicas
    python scripts/start_cluster.py --nodes 2 --base-port 9000
    python scripts/start_cluster.py --nodes 3 --proxy-layer nginx

Every replica gets:
  * a stable instance id (node-1 ... node-N) shown on the dashboard,
  * the full peer list, so any replica can render the whole fleet view,
  * one shared signing key, so a login on one replica works on all of them
    (no sticky sessions at the load balancer),
  * one shared cluster token for the peer telemetry endpoints.

Press Ctrl+C once to stop the whole cluster. Logs go to
``logs/cluster/node-*.log`` unless --foreground is passed.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = REPO_ROOT / "logs" / "cluster"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start N JAN-DRISHTI AI replicas.")
    parser.add_argument("--nodes", type=int, default=3, help="Number of replicas (default 3, max 16).")
    parser.add_argument("--base-port", type=int, default=8000, help="Port of the first replica (default 8000).")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (use 0.0.0.0 in containers).")
    parser.add_argument(
        "--proxy-layer",
        default="none",
        choices=["none", "nginx", "apache", "iis", "traefik"],
        help="Which edge tier sits in front (only changes what the dashboard displays).",
    )
    parser.add_argument(
        "--secret-key",
        default="local-cluster-demo-signing-key-change-me",
        help="Shared token signing key. In production use JAN_DRISHTI_SECRET_KEY from a secret manager.",
    )
    parser.add_argument("--foreground", action="store_true", help="Stream logs to this terminal instead of files.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    node_count = max(1, min(args.nodes, 16))
    ports = [args.base_port + index for index in range(node_count)]
    # Replicas bind the requested host (usually 0.0.0.0 so containers/port
    # forwards reach them), but they must *connect* to each other through a
    # routable address - 0.0.0.0 works on Linux by accident and not at all on
    # Windows, so loopback is used for the peer list.
    peer_host = "127.0.0.1" if args.host in {"0.0.0.0", "::", ""} else args.host
    peers = ",".join(f"http://{peer_host}:{port}" for port in ports)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    processes = []

    print(f"JAN-DRISHTI AI cluster: {node_count} replica(s) on ports {ports[0]}-{ports[-1]}")
    print(f"  edge tier shown in the dashboard : {args.proxy_layer}")
    print(f"  shared peer list                 : {peers}")
    print("")

    for index, port in enumerate(ports):
        env = dict(os.environ)
        env.update(
            {
                "JAN_DRISHTI_INSTANCE_ID": f"node-{index + 1}",
                "JAN_DRISHTI_CLUSTER_NODES": peers,
                "JAN_DRISHTI_PUBLIC_URL": f"http://{peer_host}:{port}",
                "JAN_DRISHTI_SECRET_KEY": args.secret_key,
                "JAN_DRISHTI_CLUSTER_TOKEN": os.getenv("JAN_DRISHTI_CLUSTER_TOKEN", "jandrishti-cluster-demo"),
                "JAN_DRISHTI_PROXY_LAYER": args.proxy_layer,
            }
        )
        command = [sys.executable, "-m", "jan_drishti.server", "--host", args.host, "--port", str(port)]
        if args.foreground:
            process = subprocess.Popen(command, cwd=REPO_ROOT, env=env)
        else:
            log_path = LOG_DIR / f"node-{index + 1}.log"
            log_file = open(log_path, "w", buffering=1)  # noqa: SIM115 - closed at shutdown
            process = subprocess.Popen(command, cwd=REPO_ROOT, env=env, stdout=log_file, stderr=subprocess.STDOUT)
            print(f"  node-{index + 1:<2} http://{peer_host}:{port:<5} log: {log_path.relative_to(REPO_ROOT)}")
        processes.append(process)

    time.sleep(2.5)
    alive = [p for p in processes if p.poll() is None]
    if not alive:
        print("\nNo replica started. Run one in the foreground to see the error:", file=sys.stderr)
        print(f"  python -m jan_drishti.server --host {args.host} --port {ports[0]}", file=sys.stderr)
        return 1

    print(f"\n{len(alive)}/{node_count} replica(s) running.")
    display_host = "localhost" if args.host in {"0.0.0.0", "::", ""} else args.host
    print(f"  Application      : http://{display_host}:{ports[0]}/")
    print(f"  Fleet telemetry  : http://{display_host}:{ports[0]}/api/scalability   (login required)")
    print(f"  Health probe     : http://{display_host}:{ports[0]}/health")
    print(f"  Prometheus       : http://{display_host}:{ports[0]}/api/metrics")
    print(f"  Demo login       : admin / admin123")
    print("\nOpen the app and scroll to the 'Scalability & traffic control' section.")
    print("Ctrl+C to stop the cluster.")
    if args.proxy_layer == "none":
        print("\nTip: put Nginx/Apache/IIS in front (deploy/nginx|apache|iis) and pass")
        print("     --proxy-layer nginx so the dashboard shows the real request path.")

    stopping = {"flag": False}

    def shutdown(_signum=None, _frame=None) -> None:
        if stopping["flag"]:
            return
        stopping["flag"] = True
        print("\nStopping replicas…")
        for process in processes:
            if process.poll() is None:
                process.terminate()
        deadline = time.time() + 8
        for process in processes:
            remaining = max(deadline - time.time(), 0.5)
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                process.kill()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, shutdown)

    try:
        while any(process.poll() is None for process in processes):
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown()
    shutdown()
    print("Cluster stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
