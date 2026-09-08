# JAN-DRISHTI AI

**AI-Powered Government Project Fraud & Risk Intelligence Platform** for SIH26102 — Government project fraud/anomaly detection.

JAN-DRISHTI AI acts like an explainable AI auditor for government development projects. Officers can upload project data and receive early-warning alerts for unusual patterns, delays, cost overruns, duplicate works, suspicious payment-progress mismatch, contractor concentration and data-quality problems.

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

```bash
python -m jan_drishti.server --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in your browser.

For Arena/live preview environments, the server already binds to `0.0.0.0` and uses relative API URLs, so it works behind a preview proxy.

## Try the demo

1. Start the server.
2. Click **Try Sample Data** on the homepage, or upload `data/sample_projects.csv`.
3. Review:
   - Summary cards
   - Priority alerts
   - Risk distribution
   - Project risk register
   - Per-project explanation drawer

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
  server.py                         # Upload API + static website server
  services/
    ingestion.py                    # CSV/JSON upload parsing
    data_cleaning.py                # Header mapping, number/date cleaning
    data_validation.py              # Data-quality validation checks
    anomaly_detector.py             # Delay, overrun, duplicate, mismatch checks
    risk_predictor.py               # Transparent risk/fraud scoring model
    explanation_engine.py           # Officer-friendly explanations/actions
    report_builder.py               # Dashboard summaries and alerts
website/
  index.html                        # UI page structure
  styles.css                        # UI/UX design system
  app.js                            # Upload, API calls, dashboard rendering
data/
  sample_projects.csv               # Demo dataset
tests/
  test_engine.py                    # Engine unit tests
```

## Run tests

```bash
python -m unittest discover
```

## API

### `POST /api/analyze`

Send multipart form-data with a file field named `file`.

```bash
curl -F "file=@data/sample_projects.csv" http://localhost:8000/api/analyze
```

Response contains:

- `summary`: dashboard metrics
- `alerts`: top early warnings
- `projects`: each project with `risk_score`, `fraud_score`, `risk_level`, `findings`, `explanation`, and `recommendations`
- `validation_issues`: upload cleaning warnings
- `metadata`: analysis date/source/engine version

## Upgrade roadmap

Because every feature lives in its own file, future upgrades are straightforward:

- Add PDF/XLSX parsing inside `services/ingestion.py`.
- Replace or enhance rules with ML models inside `services/risk_predictor.py`.
- Add geospatial clustering in `services/anomaly_detector.py`.
- Add authentication, database storage and audit history behind `server.py`.
- Add maps, charts and officer workflows inside `website/`.

## Important note

This is a hackathon-ready explainable prototype. It flags risk signals and prioritises audit attention; final fraud decisions should be made by authorised officers after document and field verification.
