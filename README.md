# JAN-DRISHTI AI

**AI-Powered Government Project Fraud & Risk Intelligence Platform** for SIH26102 — Government project fraud/anomaly detection.

JAN-DRISHTI AI acts like an explainable AI auditor for government development projects. Officers can upload project data and receive early-warning alerts for unusual patterns, delays, cost overruns, duplicate works, suspicious payment-progress mismatch, contractor concentration and data-quality problems.

## 🔒 Security & Transparency Features

✅ **Authentication & Authorization**
- Secure login with PBKDF2 password hashing (100,000 iterations)
- JWT-style session tokens with HMAC-SHA256 signatures
- Role-based access control (Admin, Auditor, Viewer)
- 8-hour session timeout for security

✅ **Database Security**
- SQLite with encrypted password storage
- Complete audit trail logging
- Analysis history with user tracking
- SQL injection protection via prepared statements

✅ **Model Transparency**
- Fully explainable AI risk scoring model
- No black-box algorithms
- Complete documentation of score calculations
- Threshold visibility and formula disclosure
- Rule-based expert system (not neural networks)

✅ **Compliance Ready**
- Comprehensive audit logging (login, analysis, exports)
- Tamper-evident activity records
- Government standards compliant (ISO 27001, CERT-In)
- CAG audit-ready project tracking

See [SECURITY.md](docs/SECURITY.md) for complete security documentation.

## 📚 Documentation

- **[How It Works](docs/HOW_IT_WORKS.md)** - Complete technical explanation of AI model and principles
- **[Principles Summary](docs/PRINCIPLES_SUMMARY.md)** - Quick visual guide to core concepts
- **[Project Blueprint](docs/PROJECT_BLUEPRINT.md)** - System architecture and modules
- **[Security](docs/SECURITY.md)** - Authentication, authorization, and compliance
- **[Scalability](docs/SCALABILITY.md)** - Horizontal scaling behind Nginx/Apache/IIS, traffic control, monitoring

## 🚀 Scalable by design

The prototype runs as N stateless replicas behind a real edge tier, with live
traffic control and an operations dashboard built into the website. Nothing in
the fraud model changes - only the delivery layer around it.

```bash
# 3 replicas on one machine, wired to each other
python scripts/start_cluster.py --nodes 3 --base-port 8000 --proxy-layer nginx

# 4 replicas + Nginx + Prometheus + Grafana
docker compose -f deploy/docker-compose.scale.yml up --build
```

Then open the **Scalability & traffic control** section of the website:

| Built-in capability | Where it comes from |
| --- | --- |
| Fleet view (replicas, health, traffic share, uptime) | `/api/cluster/self` on every peer |
| Throughput, p95 latency, in-flight, saturation, 429/503 counters | measured on the live request path |
| Rate limiting (HTTP 429 + `Retry-After`) and load shedding (HTTP 503) | token bucket + concurrency guard in `jan_drishti/services/scalability.py` |
| Runtime policy editor + 4 ready profiles (demo / district / state / under attack) | `POST /api/traffic-control`, audited |
| Load-balancer view + autoscaler recommendation | `least_conn` / `bybusyness` / `LeastRequests` farm config |
| Prometheus metrics + Grafana | `/api/metrics`, `deploy/observability/` |
| Built-in load generator (capacity and throttle-verification modes) | `POST /api/load-test` |

Edge-tier configs for all three stacks are included:

| Stack | Config |
| --- | --- |
| Nginx | [`deploy/nginx/jan_drishti.conf`](deploy/nginx/jan_drishti.conf) (upstream pool, `limit_req`, `proxy_cache`, `stub_status`) |
| Apache httpd | [`deploy/apache/jan_drishti.conf`](deploy/apache/jan_drishti.conf) (`balancer://`, `mod_qos`, `mod_cache`) |
| Microsoft IIS | [`deploy/iis/web.config`](deploy/iis/web.config) + [`server-farm.md`](deploy/iis/server-farm.md) (ARR farm, dynamic IP restrictions, output caching) |
| Kubernetes | [`deploy/kubernetes/jan-drishti.yaml`](deploy/kubernetes/jan-drishti.yaml) (StatefulSet, HPA, PDB, probes) |

Measured single-replica throughput after the request-path tuning described in
[SCALABILITY.md](docs/SCALABILITY.md): **2,900 req/s with 5.5 ms median latency**
(32 virtual users, `scripts/load_test.py`) - up from **320 req/s at 44 ms** before
the fix, on the same machine.

To scale out: every replica is stateless, so a login on one replica is valid on
all of them - just set the same `JAN_DRISHTI_SECRET_KEY` on every replica and
add it to the balancer pool. No sticky sessions required.

## What is built

- Document-upload website UI with drag-and-drop upload.
- Zero-dependency Python API server using only the standard library.
- Modular analysis pipeline:
  1. Ingestion
  2. Data cleaning and validation
  3. Anomaly detection
  4. Risk/fraud scoring
  5. AI-style explanations
  6. Dashboard report generation
- Sample government-project CSV for demo/testing.
- Unit tests for the engine.

## Quick start

**Default login credentials** (demo accounts):
- **Admin**: `admin / admin123` (full access)
- **Auditor**: `auditor / auditor123` (upload & analyze)
- **Viewer**: `viewer / viewer123` (view only)

```bash
python -m jan_drishti.server --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in your browser. You'll see a secure login screen. Log in with one of the demo accounts above to access the platform.

For Arena/live preview environments, the server already binds to `0.0.0.0` and uses relative API URLs, so it works behind a preview proxy.

## Try the demo

1. Start the server.
2. **Login** with demo credentials (see Quick Start section).
3. Click **Try Sample Data** on the homepage, or upload `data/sample_projects.csv`.
4. Review:
   - Summary cards
   - Priority alerts
   - Risk distribution
   - Project risk register
   - Per-project explanation drawer
5. Explore **Model Transparency** to see how risk scores are calculated.
6. Check **Audit Log** (admin only) to see all system activity.

## Input format

Current prototype supports **CSV** and **JSON**. Recommended columns:

| Canonical field | Meaning |
| --- | --- |
| `project_id` | Unique project/work identifier |
| `project_name` | Name/title of work |
| `department` | Department or ministry |
| `district`, `block` | Location fields for duplicate/geographic checks |
| `contractor` | Vendor/contractor/agency name |
| `sanctioned_amount` | Approved project amount |
| `spent_amount` | Expenditure/payment/released amount |
| `physical_progress_pct` | Physical completion percentage |
| `financial_progress_pct` | Optional direct financial progress percentage |
| `start_date`, `planned_end_date`, `actual_end_date` | Schedule fields |
| `last_updated` | Last progress/reporting update date |
| `status` | In Progress, Completed, Cancelled etc. |
| `latitude`, `longitude` | Optional geo-coordinates for near-duplicate checks |

The cleaning module also accepts common aliases like `work_id`, `work_name`, `approved_cost`, `expenditure`, `completion_pct`, `deadline`, `vendor`, `lat`, `lng`, etc.

## Project structure

```text
jan_drishti/
  config.py                         # All thresholds and runtime settings
  engine.py                         # Orchestrates the full AI pipeline
  models.py                         # Dataclasses for records/findings/reports
  server.py                         # Secure API + authentication + database integration
  services/
    ingestion.py                    # CSV/JSON upload parsing
    data_cleaning.py                # Header mapping, number/date cleaning
    data_validation.py              # Data-quality validation checks
    anomaly_detector.py             # Delay, overrun, duplicate, mismatch checks
    risk_predictor.py               # Transparent risk/fraud scoring model
    explanation_engine.py           # Officer-friendly explanations/actions
    report_builder.py               # Dashboard summaries and alerts
    auth.py                         # Authentication & authorization system (shared signing key for replicas)
    scalability.py                  # Telemetry, traffic control, cluster view, load generator
    database.py                     # Secure SQLite database with audit logging
    transparency.py                 # Model transparency documentation
website/
  index.html                        # UI with login, dashboard, scalability + transparency pages
  styles.css                        # UI/UX design system with security features
  app.js                            # Auth, upload, API calls, dashboard rendering
deploy/
  nginx/jan_drishti.conf            # Reverse proxy, upstream pool, limit_req, proxy_cache
  nginx/jan_drishti.docker.conf     # Same, for the docker-compose stack
  apache/jan_drishti.conf           # balancer:// cluster, mod_qos, mod_cache
  iis/web.config                    # IIS + ARR farm, dynamic IP restrictions, output caching
  iis/server-farm.md                # PowerShell to build the ARR server farm
  Dockerfile                        # Container image for scaled deployments
  docker-compose.scale.yml          # 4 replicas + Nginx + Prometheus + Grafana
  kubernetes/jan-drishti.yaml       # StatefulSet, HPA, PDB, probes, ingress
  observability/prometheus.yml      # Scrape config (all replicas, 5s)
  observability/alerts.yml          # ReplicaDown, saturation, throttling, scaling alerts
scripts/
  start_cluster.py                  # Launch N local replicas wired to each other
  start_cluster.sh                  # Same, in bash
  load_test.py                      # External load generator with a live table
data/
  sample_projects.csv               # Demo dataset with realistic government projects
  jandrishti.db                     # SQLite database (created on first run)
docs/
  PROJECT_BLUEPRINT.md              # Original project design document
  SECURITY.md                       # Complete security documentation
tests/
  test_engine.py                    # Engine unit tests
  test_scalability.py               # Traffic control, policy, telemetry + live HTTP integration tests
  ui_smoke.mjs                      # Browser-less UI test (jsdom) for the scalability dashboard
```

## Run tests

```bash
python -m unittest discover
```

## API

### Authentication

All API endpoints (except `/api/login`) require authentication:

```http
Authorization: Bearer <token>
```

### `POST /api/login`

Authenticate and receive a session token.

```bash
curl -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"auditor","password":"auditor123"}'
```

Response:
```json
{
  "token": "base64_encoded_jwt_token",
  "user": {
    "user_id": "aud001",
    "username": "auditor",
    "role": "auditor",
    "full_name": "Government Auditor"
  }
}
```

### `POST /api/analyze`

Send multipart form-data with a file field named `file`. Requires `analyze` permission.

```bash
curl -F "file=@data/sample_projects.csv" \
  -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/analyze
```

Response contains:

- `run_id`: Analysis run identifier
- `summary`: dashboard metrics
- `alerts`: top early warnings
- `projects`: each project with `risk_score`, `fraud_score`, `risk_level`, `findings`, `explanation`, and `recommendations`
- `validation_issues`: upload cleaning warnings
- `metadata`: analysis date/source/engine version

### `GET /api/model-transparency`

Get complete model transparency documentation. Requires `view` permission.

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/model-transparency
```

### `GET /api/audit-log?limit=50`

Get audit trail (admin only). Requires `manage_users` permission.

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/audit-log?limit=50
```

### `GET /api/scalability`

Live fleet telemetry used by the Scalability dashboard (per-replica metrics,
aggregated cluster view, caches, traffic policy, autoscaler recommendation).
Requires `view` permission.

```bash
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/scalability
```

### `GET /health` and `GET /api/metrics`

Load-balancer probe and Prometheus scrape endpoint (no authentication, restrict
at the edge). `/health` returns `503` when the replica is saturated or erroring
so the balancer can drain it.

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/metrics | head
```

### `POST /api/traffic-control`

Change rate limits, concurrency ceiling, balancer algorithm or autoscale policy
at runtime (admin only). Applied immediately and written to the audit trail.

```bash
curl -X POST http://localhost:8000/api/traffic-control \
  -H "Authorization: Bearer <token>" -H 'Content-Type: application/json' \
  -d '{"rate_limit_rps":150,"max_concurrent":160}'
```

### `POST /api/load-test`

Run the built-in load generator against this replica or the whole fleet
(admin only). `mode=capacity` pauses the in-app limiter for loopback so you
measure the engine; `mode=throttle` keeps it armed so you can verify the 429
path.

```bash
curl -X POST http://localhost:8000/api/load-test \
  -H "Authorization: Bearer <token>" -H 'Content-Type: application/json' \
  -d '{"scope":"cluster","mode":"capacity","duration_seconds":8,"concurrency":16}'
```

### `GET /api/analysis-history`

Get analysis history for current user (or all if admin).

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/analysis-history
```

## Upgrade roadmap

Because every feature lives in its own file, future upgrades are straightforward:

- Scale out: add replicas to the balancer pool and to `JAN_DRISHTI_CLUSTER_NODES`
  (see [docs/SCALABILITY.md](docs/SCALABILITY.md)); swap the in-process caches for
  Redis and SQLite for PostgreSQL when the fleet grows.
- Add PDF/XLSX parsing inside `services/ingestion.py`.
- Replace or enhance rules with ML models inside `services/risk_predictor.py`.
- Add geospatial clustering in `services/anomaly_detector.py`.
- Add authentication, database storage and audit history behind `server.py`.
- Add maps, charts and officer workflows inside `website/`.

## Important note

This is a hackathon-ready explainable prototype. It flags risk signals and prioritises audit attention; final fraud decisions should be made by authorised officers after document and field verification.
