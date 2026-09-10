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
    auth.py                         # Authentication & authorization system
    database.py                     # Secure SQLite database with audit logging
    transparency.py                 # Model transparency documentation
website/
  index.html                        # UI with login, dashboard, transparency page
  styles.css                        # UI/UX design system with security features
  app.js                            # Auth, upload, API calls, dashboard rendering
data/
  sample_projects.csv               # Demo dataset with realistic government projects
  jandrishti.db                     # SQLite database (created on first run)
docs/
  PROJECT_BLUEPRINT.md              # Original project design document
  SECURITY.md                       # Complete security documentation
tests/
  test_engine.py                    # Engine unit tests
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

### `GET /api/analysis-history`

Get analysis history for current user (or all if admin).

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/analysis-history
```

## Upgrade roadmap

Because every feature lives in its own file, future upgrades are straightforward:

- Add PDF/XLSX parsing inside `services/ingestion.py`.
- Replace or enhance rules with ML models inside `services/risk_predictor.py`.
- Add geospatial clustering in `services/anomaly_detector.py`.
- Add authentication, database storage and audit history behind `server.py`.
- Add maps, charts and officer workflows inside `website/`.

## Important note

This is a hackathon-ready explainable prototype. It flags risk signals and prioritises audit attention; final fraud decisions should be made by authorised officers after document and field verification.
