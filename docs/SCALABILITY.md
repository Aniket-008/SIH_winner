# JAN-DRISHTI AI - Scalability, Traffic Control & Observability

This document describes everything added to make the prototype survive a
state-level rollout: horizontal scaling behind a real edge tier
(**Nginx / Apache httpd / Microsoft IIS**), live traffic control, the officer
dashboard for it, and the monitoring hooks an operations team needs.

Nothing here changes the fraud model - it is the *delivery* layer around it.

---

## 1. The 60-second version

```text
officer browser
      │  HTTPS
      ▼
┌──────────────────────────────────────────────┐
│ LAYER 1  Edge / WAF                          │  TLS, connection + request limits, DDoS absorption
│          nginx · httpd · IIS                 │  deploy/nginx | deploy/apache | deploy/iis
├──────────────────────────────────────────────┤
│ LAYER 2  Load balancer                       │  spread traffic over N replicas, health check, failover
│          upstream / balancer:// / ARR farm   │  least-conn | bybusyness | LeastRequests
├──────────────────────────────────────────────┤
│ LAYER 3  App traffic control (in-process)    │  token bucket -> 429 + Retry-After
│          jan_drishti/services/scalability.py │  concurrency guard -> 503 + Retry-After
├──────────────────────────────────────────────┤
│ LAYER 4  Caches                              │  static asset cache, analysis-result cache,
│                                              │  proxy_cache / mod_cache / IIS output caching
├──────────────────────────────────────────────┤
│ LAYER 5  Autoscaler                          │  p95 latency + req/s -> recommended replica count
│          HPA / VMSS / scheduled script       │  deploy/kubernetes/jan-drishti.yaml
└──────────────────────────────────────────────┘
      │
      ▼
 app replica 1   app replica 2   app replica 3   app replica N
 (stateless: signed tokens, shared secret, no sticky sessions needed)
```

Every layer is visible in the website under
**Scalability & traffic control**, including which replica served each request.

---

## 2. Run it

### 2.1 Local multi-replica demo (no Docker, no Nginx install)

```bash
python scripts/start_cluster.py --nodes 3 --base-port 8000 --proxy-layer nginx
# or, if you prefer bash:
NODES=3 BASE_PORT=8000 scripts/start_cluster.sh
```

Open <http://127.0.0.1:8000>, log in with `admin / admin123`, and scroll to
**Scalability & traffic control**. You get a live fleet view of all three
replicas, a load-balancer table, the autoscaler recommendation and the traffic
policy editor.

Press `Ctrl+C` in the terminal (or `scripts/start_cluster.sh stop`) to stop the
whole cluster.

### 2.2 Full stack with Docker (4 replicas + Nginx + Prometheus + Grafana)

```bash
docker compose -f deploy/docker-compose.scale.yml up --build
# app      http://localhost:8080
# metrics  http://localhost:9090
# grafana  http://localhost:3000   (admin / jandrishti)
```

### 2.3 Windows Server / IIS

```bat
python scripts\start_cluster.py --nodes 4 --base-port 8001
```

then follow [`deploy/iis/server-farm.md`](../deploy/iis/server-farm.md) to create
the ARR server farm and copy [`deploy/iis/web.config`](../deploy/iis/web.config)
into the site root.

### 2.4 Kubernetes

```bash
docker build -f deploy/Dockerfile -t jan-drishti:1.1-scalable .
kubectl apply -f deploy/kubernetes/jan-drishti.yaml
kubectl -n jan-drishti port-forward svc/jan-drishti 8080:80
```

---

## 3. What the dashboard shows (and where each number comes from)

| Card / panel | Meaning | Source |
| --- | --- | --- |
| **Replicas healthy** | fleet size and failed health probes | `GET /health` on every peer |
| **Fleet throughput** | requests/second, aggregate and per replica | per-second buckets from the live request path |
| **p95 latency** | 95th percentile of real request latency vs the policy target | rolling latency reservoir per replica |
| **Concurrency** | in-flight requests / configured ceiling, plus saturation % | the concurrency guard itself |
| **Throttled / shed** | requests rejected with 429 (rate limit) or 503 (overload) | token bucket + load-shed counters |
| **Cache hit ratio** | static asset cache and analysis-result cache | in-process caches (mirrors the edge cache) |
| **Autoscaler** | `hold` / `scale out` / `scale in` plus the reason | derived from p95 and req/s vs policy |
| **Replica table** | status, traffic share, req/s, p95, in-flight, uptime | `/api/cluster/self` on each peer |
| **Fleet traffic chart** | last 60s of req/s, throttles and latency | merged per-second series from all replicas |
| **Live request feed** | per-request method, path, status, latency, node, decision | request recorder in the handler |
| **Ops log** | policy changes, scaling decisions, load tests, replica start-up | monitor event log |
| **Where each control lives** | the 5-layer map above, with the config file for each | `topology()` |

All of it is **measured**, not simulated. The only derived (rather than
measured) numbers are the autoscaler *recommendation* and the traffic shares,
which are computed from the measured counters - both are labelled as such in
the UI.

---

## 4. Traffic control

### 4.1 In the application (always on, last line of defence)

* **Per-client token bucket** - default `25 req/s` sustained with a `60` request
  burst, keyed on the real client IP (honours `X-Forwarded-For`, `X-Real-IP`,
  `CF-Connecting-IP` so every officer behind the proxy gets their own bucket).
  Exceeded → **HTTP 429** with `Retry-After`, `X-RateLimit-Limit`,
  `X-RateLimit-Remaining`.
* **Concurrency guard / load shedding** - default ceiling of `64` concurrent
  requests per replica. Beyond it → **HTTP 503** with `Retry-After: 1`, which
  tells a well-behaved balancer to try another replica.
* **Probe exemption** - `/health` is never throttled or shed, so the load
  balancer can always make a routing decision (verified by a test that saturates
  a replica and still expects a healthy probe).
* **Escalation-proof** - even if the proxy is bypassed or misconfigured, the
  app protects the model engine on its own.

### 4.2 At the edge (bulk of the work)

| Concern | Nginx | Apache httpd | Microsoft IIS |
| --- | --- | --- | --- |
| Sustained request rate | `limit_req_zone` + `limit_req` | `mod_qos` `QS_ClientMaxReqPerSec` | `dynamicIpSecurity` `denyByRequest` |
| Concurrent connections | `limit_conn_zone` + `limit_conn` | `QS_SrvMaxConnPerIP` | `dynamicIpSecurity` `denyByConcurrent` |
| Bandwidth cap for exports | `limit_rate` | `mod_ratelimit` | IIS bit-rate throttling / ARR |
| Upload size | `client_max_body_size 50m` | `LimitRequestBody` | `requestLimits maxAllowedContentLength` |
| Overload response | 429/503 + `Retry-After` | 503 via `QS_ErrorPage` | 403/429 via deny actions |
| Config file | `deploy/nginx/jan_drishti.conf` | `deploy/apache/jan_drishti.conf` | `deploy/iis/web.config` |

### 4.3 Changing the policy live

Administrators can tune it from the dashboard (the change is applied instantly
and written to the audit trail), or over the API:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")

curl -X POST http://localhost:8000/api/traffic-control \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"rate_limit_rps":150,"rate_limit_burst":400,"max_concurrent":160,"lb_algorithm":"least_conn"}'
```

Four ready-made profiles ship in the UI:

| Profile | Per-client rate | Concurrency | Balancer | Target p95 | Replicas |
| --- | --- | --- | --- | --- | --- |
| **Hackathon demo** | 25 req/s | 64 | least connections | 250 ms | 2-12 |
| **District pilot** | 150 req/s | 160 | least connections | 300 ms | 3-8 |
| **State scale** | 800 req/s | 512 | round robin | 400 ms | 6-40 |
| **Under attack** | 8 req/s | 32 | IP hash | 200 ms | 4-20 |

---

## 5. Horizontal scaling design decisions

1. **Stateless replicas.** A login on replica A is valid on replica B because
   every replica signs tokens with the same key (`JAN_DRISHTI_SECRET_KEY`, or a
   key derived from the shared cluster token in demo mode). No sticky sessions,
   no session table, no shared session store - the balancer can send any request
   anywhere, including retrying a failed one on the next replica.
2. **Self-describing fleet.** A replica learns its peers from
   `JAN_DRISHTI_CLUSTER_NODES` and pulls their compact metrics from
   `/api/cluster/self` (token-protected). Any replica can render the whole fleet
   view, so there is no single monitoring node to lose.
3. **Health signals that mean something.** `/health` reports concurrency,
   saturation and p95, and returns **503 when the replica is saturated or
   erroring** - so the balancer drains a struggling replica instead of letting it
   time every request out.
4. **Caches** - the analysis pipeline is the expensive step; results are cached
   by content hash, and audit logging plus the saved run id still happen for
   every request, so the compliance trail is never short-circuited.
5. **Backpressure before collapse.** Shedding a request with a fast 503 keeps
   p95 low for everyone else, instead of letting the queue grow until every
   officer times out.

---

## 6. Performance work that made this usable

Two real bottlenecks were found while building this (both fixed, both measured):

| Finding | Before | After |
| --- | --- | --- |
| **Nagle vs delayed-ACK** - responses were written as two TCP segments (headers, then body), so every small response paid a ~40 ms stall | median **43.99 ms**, cap ≈ **320 req/s** | median **0.26 ms** (`/health`) - `wbufsize = 64 KiB` + `TCP_NODELAY` in the handler `setup()` |
| **Per-request connection setup** - HTTP/1.0 responses closed the socket after every request, defeating proxy keepalive pools | new connection per request | `protocol_version = "HTTP/1.1"` + `keepalive 64` in the upstream |

Measured with `scripts/load_test.py --path /health --duration 6 --concurrency 32`:

```text
throughput        : 2,900.4 req/s
requests          : 17,462 in 6.0s (32 virtual users)
success rate      : 100.00%
latency avg/median: 11.0 ms / 5.5 ms
latency p95/p99   : 28.6 ms / 44.7 ms
```

The in-app load test across a 3-replica cluster spreads traffic evenly and shows
it in the dashboard:

```text
node-1  33.4%   node-2  33.3%   node-3  33.3%   (expected 33.3% each)
```

---

## 7. Load testing

**From the UI** (admin only): *Scalability → Load test the cluster*. Choose
scope (whole cluster / this replica), mode, virtual users, duration and target
path.

* `capacity` mode temporarily pauses the in-app limiter for loopback on every
  replica (coordinated through `/api/cluster/arm`) so you measure the engine.
* `throttle` mode leaves the limiter armed, which is how you *prove* the 429
  path: the result panel reports `throttling_verified: true` and the 429 count.

**From the command line:**

```bash
# capacity sweep across the whole fleet behind the balancer
python scripts/load_test.py --url http://127.0.0.1:8080 \
    --path /api/scalability --duration 20 --concurrency 64

# prove the rate limiter is working
python scripts/load_test.py --url http://127.0.0.1:8000 \
    --path /api/model-transparency --token "$TOKEN" --expect-429

# pause the in-app limiter on all replicas first, then measure
python scripts/load_test.py --url http://127.0.0.1:8000 --arm \
    --nodes http://127.0.0.1:8000,http://127.0.0.1:8001 --token "$TOKEN"
```

Existing tools work too - the API is plain HTTP:

```bash
ab -n 20000 -c 64 http://127.0.0.1:8080/health
k6 run --vus 50 --duration 60s - <<'EOF'
import http from 'k6/http';
export default function () { http.get('http://127.0.0.1:8080/health'); }
EOF
```

---

## 8. Monitoring and alerting

* **Prometheus** - every replica exposes text-format metrics at `/api/metrics`
  (no exporter sidecar needed):

  | Metric | Meaning |
  | --- | --- |
  | `jan_drishti_requests_total{node,status}` | counter per replica and status code |
  | `jan_drishti_requests_in_flight` | live concurrency |
  | `jan_drishti_request_latency_ms{quantile}` | p50 / p95 / p99 |
  | `jan_drishti_rate_limited_total`, `jan_drishti_shed_total` | 429s and 503s |
  | `jan_drishti_cluster_nodes`, `jan_drishti_cluster_nodes_down` | fleet health |
  | `jan_drishti_cluster_requests_per_sec`, `jan_drishti_cluster_p95_ms` | fleet load |
  | `jan_drishti_autoscale_desired_nodes` | autoscaler recommendation |
  | `jan_drishti_cache_hits_total`, `jan_drishti_analysis_cache_hits_total` | cache effectiveness |

  Scrape config: `deploy/observability/prometheus.yml` (5s interval, all
  replicas). Alert rules: `deploy/observability/alerts.yml` (`ReplicaDown`,
  `ReplicaSaturated`, `LatencyBudgetBreach`, `ScaleOutRecommended`,
  `HeavyThrottling`, `LoadShedding`, `ServerErrors`).
* **Grafana** - comes up with `docker compose -f deploy/docker-compose.scale.yml`
  at <http://localhost:3000>; useful queries are listed at the top of
  `prometheus.yml`.
* **Proxy-level** - `stub_status` (nginx), `/server-status` (httpd) and
  IIS Failed Request Tracing (configured for 429/5xx) give the edge view.
* **The app's own ops log** - policy changes, autoscale decisions and load tests
  are visible to officers in the dashboard and recorded in the audit trail.

---

## 9. Privacy note (important for a government deployment)

The dashboard shows **client IPs** in the live request feed so an operator can
identify an abusive source during an incident. Audit logs (not the dashboard)
are the durable record. If IP display is not acceptable in your environment, the
field to change is `client` in `ScalabilityMonitor.record()` - hash it
(`hashlib.sha256(ip + salt).hexdigest()[:12]`) and the throttle buckets keep
working because they only need a stable key.

---

## 10. API reference (added by this work)

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | none | liveness + readiness with concurrency and saturation (503 when unhealthy) |
| `GET` | `/api/scalability` | `view` | full fleet telemetry for the dashboard |
| `GET` | `/api/metrics` | none (restrict at the edge) | Prometheus exposition |
| `GET` | `/api/cluster/self` | `X-Cluster-Token` | compact per-replica snapshot for peer aggregation |
| `POST` | `/api/cluster/arm` | `X-Cluster-Token` | pause/re-arm the limiter for a coordinated load test |
| `POST` | `/api/traffic-control` | `configure` (admin) | apply a traffic/autoscale policy at runtime |
| `POST` | `/api/metrics/reset` | `configure` (admin) | restart the telemetry window |
| `POST` | `/api/cache/flush` | `configure` (admin) | drop cached assets on a replica |
| `POST` | `/api/load-test` | `manage_users` (admin) | run the built-in load generator |

Response headers on every request: `X-Served-By` (replica id),
`X-Traffic-Decision` (`ok`/`rate_limited`/`shed`), `X-Cache`
(`HIT`/`MISS`/`BYPASS`), `Server-Timing`, and `X-RateLimit-*` / `Retry-After`
when a limit applies.

---

## 11. Configuration reference

| Variable | Default | Purpose |
| --- | --- | --- |
| `JAN_DRISHTI_INSTANCE_ID` | `node-<pid>` | replica name shown in the dashboard |
| `JAN_DRISHTI_SECRET_KEY` | - | **shared** token signing key (required for multi-replica sessions) |
| `JAN_DRISHTI_CLUSTER_NODES` | - | comma-separated peer base URLs for the fleet view |
| `JAN_DRISHTI_PUBLIC_URL` | - | this replica's own URL (so it does not double count itself) |
| `JAN_DRISHTI_CLUSTER_TOKEN` | `jandrishti-cluster-demo` | protects `/api/cluster/*` |
| `JAN_DRISHTI_PROXY_LAYER` | `none` | `nginx` / `apache` / `iis` / `traefik` - what the dashboard displays |
| `JAN_DRISHTI_RATE_LIMIT_RPS` | `25` | per-client sustained rate |
| `JAN_DRISHTI_RATE_LIMIT_BURST` | `60` | burst allowance |
| `JAN_DRISHTI_MAX_CONCURRENT` | `64` | concurrency ceiling before shedding |
| `JAN_DRISHTI_RATE_LIMIT_ENABLED` / `JAN_DRISHTI_LOAD_SHED` | `1` | kill switches |
| `JAN_DRISHTI_TARGET_P95_MS` | `250` | autoscale latency budget |
| `JAN_DRISHTI_RPS_PER_NODE` | `40` | throughput one replica should carry |
| `JAN_DRISHTI_MIN_NODES` / `JAN_DRISHTI_MAX_NODES` | `2` / `12` | autoscaler bounds |
| `JAN_DRISHTI_LB_ALGORITHM` | `least_conn` | which algorithm the dashboard reports/tests with |
| `JAN_DRISHTI_ENV` | `demo` | environment label |
| `JAN_DRISHTI_MAX_UPLOAD_MB` | `50` | upload ceiling (keep equal at the edge!) |

`JAN_DRISHTI_PORT`, `JAN_DRISHTI_HOST` and `JAN_DRISHTI_MAX_UPLOAD_MB` keep their
previous meanings.

---

## 12. Tests

```bash
python -m unittest tests.test_scalability -v     # 29 tests, all passing
python -m unittest discover                      # full suite

# browser-less UI smoke test (jsdom) against a RUNNING cluster:
python scripts/start_cluster.py --nodes 3 --base-port 8000 &
npm install jsdom --no-save
node tests/ui_smoke.mjs                          # 29 UI assertions
```

`tests/ui_smoke.mjs` loads the real `website/index.html` + `app.js`, logs in as
both `admin` and `viewer`, and asserts that the fleet cards render, the canvas
chart actually draws, the policy editor applies a change, the preset profiles
work, the load-test panel reports throughput and per-replica distribution, and
that a viewer gets read-only controls (no policy change, no load test).

`tests/test_scalability.py` covers the token bucket, per-client isolation,
load shedding, probe exemption, policy validation and clamping, latency
percentiles, the Prometheus payload, cache hit ratios, the load-test runner, and
a live HTTP integration pass through the real handler: unauthenticated `401`,
fleet view `200`, admin-only policy changes (`403` for viewer), the `429` +
`Retry-After` path, the analysis cache hit on re-upload, and `/health` staying
`200` while `/api/scalability` returns `503` under saturation.

(The pre-existing `test_engine` / `test_csv_processing` / `test_secure_api`
failures on the base commit are unrelated to this work and were present before
it.)

---

## 13. What is honest about this demo

* Throughput, latency, saturation, throttle counts, cache ratios and traffic
  shares are **real measurements** of the running processes.
* The autoscaler **recommends** replica counts; it does not start machines
  unless you wire it to Kubernetes HPA / a VM scale set / a scheduled script
  (the manifests and thresholds are in `deploy/kubernetes` and this document).
* Running three replicas on one laptop is a *topology* demo: real capacity comes
  from real machines. The point is that the code paths, health checks, session
  handling and metrics are the same ones you would run in production - only the
  number of machines changes.
