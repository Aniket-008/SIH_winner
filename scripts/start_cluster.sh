#!/usr/bin/env bash
# =============================================================================
#  JAN-DRISHTI AI - start N replicas + (optionally) an Nginx load balancer.
#
#  Usage:
#     scripts/start_cluster.sh                       # 3 replicas on 8000-8002
#     NODES=4 scripts/start_cluster.sh               # 4 replicas
#     BASE_PORT=9000 scripts/start_cluster.sh
#     PROXY_LAYER=nginx scripts/start_cluster.sh
#     scripts/start_cluster.sh stop                  # stop everything it started
#
#  Requires: bash, python3. Nginx (if PROXY_LAYER=nginx) must be installed and
#  its config installed from deploy/nginx/jan_drishti.conf.
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NODES="${NODES:-3}"
BASE_PORT="${BASE_PORT:-8000}"
HOST="${HOST:-0.0.0.0}"
PROXY_LAYER="${PROXY_LAYER:-none}"
PID_DIR="${REPO_ROOT}/logs/cluster"
SHARED_SECRET="${JAN_DRISHTI_SECRET_KEY:-local-cluster-demo-signing-key-change-me}"

mkdir -p "${PID_DIR}"

stop_cluster() {
  echo "Stopping JAN-DRISHTI replicas…"
  shopt -s nullglob
  for pid_file in "${PID_DIR}"/node-*.pid; do
    pid="$(cat "${pid_file}")"
    if kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" && echo "  stopped pid ${pid}"
    fi
    rm -f "${pid_file}"
  done
}

if [[ "${1:-start}" == "stop" ]]; then
  stop_cluster
  exit 0
fi

PEERS=""
for ((i = 0; i < NODES; i++)); do
  PEERS="${PEERS}http://127.0.0.1:$((BASE_PORT + i)),"
done
PEERS="${PEERS%,}"

echo "Starting ${NODES} replica(s) on ${HOST}:${BASE_PORT}-$((BASE_PORT + NODES - 1))"
echo "  edge tier shown in the dashboard: ${PROXY_LAYER}"

for ((i = 0; i < NODES; i++)); do
  PORT=$((BASE_PORT + i))
  LOG="${PID_DIR}/node-$((i + 1)).log"
  JAN_DRISHTI_INSTANCE_ID="node-$((i + 1))" \
  JAN_DRISHTI_CLUSTER_NODES="${PEERS}" \
  JAN_DRISHTI_PUBLIC_URL="http://127.0.0.1:${PORT}" \
  JAN_DRISHTI_SECRET_KEY="${SHARED_SECRET}" \
  JAN_DRISHTI_PROXY_LAYER="${PROXY_LAYER}" \
  nohup python3 -m jan_drishti.server --host "${HOST}" --port "${PORT}" >"${LOG}" 2>&1 &
  echo $! >"${PID_DIR}/node-$((i + 1)).pid"
  echo "  node-$((i + 1)) -> http://127.0.0.1:${PORT}  (log: ${LOG#${REPO_ROOT}/})"
done

sleep 2
echo ""
echo "Replicas ready. Health probe: curl http://127.0.0.1:${BASE_PORT}/health"
echo "Prometheus scrape:           curl http://127.0.0.1:${BASE_PORT}/api/metrics | head"
if [[ "${PROXY_LAYER}" == "nginx" ]]; then
  echo ""
  echo "Install the Nginx edge config if you have not already:"
  echo "   sudo cp deploy/nginx/jan_drishti.conf /etc/nginx/conf.d/jan_drishti.conf"
  echo "   sudo nginx -t && sudo systemctl reload nginx   # then browse http://<host>/"
fi
echo ""
echo "Stop with: scripts/start_cluster.sh stop"
