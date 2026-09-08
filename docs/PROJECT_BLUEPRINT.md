# JAN-DRISHTI AI Blueprint

## Problem statement

**SIH26102 — Government project fraud/anomaly detection** asks for detection of unusual patterns, delays, cost overruns, duplicate works and potential misuse, with risk-based alerts and dashboards.

## Product vision

JAN-DRISHTI AI is an early-warning system for government development projects. It ingests project data, validates it, detects anomalies, predicts fraud/risk likelihood and explains why a project is risky in officer-friendly language.

```text
Government Project Data
        ↓
Data Cleaning & Validation
        ↓
AI Engine
   ┌────┴────┐
   ↓         ↓
Anomaly    Risk
Detection  Prediction
   ↓         ↓
Fraud/Risk Score
        ↓
AI Explanation
        ↓
Officer Dashboard
        ↓
Early Warning 🚨
```

## Module responsibilities

| Module | File | Responsibility |
| --- | --- | --- |
| Upload/API | `jan_drishti/server.py` | Serves website and `/api/analyze` upload endpoint |
| Ingestion | `jan_drishti/services/ingestion.py` | Converts CSV/JSON documents into raw project rows |
| Cleaning | `jan_drishti/services/data_cleaning.py` | Maps messy headers, parses dates/amounts/progress |
| Validation | `jan_drishti/services/data_validation.py` | Flags missing or inconsistent source data |
| Anomaly detection | `jan_drishti/services/anomaly_detector.py` | Detects cost overrun, delay, stale reporting, duplicate works, payment-progress mismatch, outliers and concentration risk |
| Scoring | `jan_drishti/services/risk_predictor.py` | Produces transparent risk score, fraud score and risk level |
| Explanation | `jan_drishti/services/explanation_engine.py` | Converts findings into clear reasons and officer actions |
| Report | `jan_drishti/services/report_builder.py` | Builds summary metrics and priority alerts for dashboard |
| UI | `website/index.html`, `website/styles.css`, `website/app.js` | Upload flow, dashboard, explanations and report download |

## Current anomaly signals

1. **Cost overrun** — spent amount exceeds sanctioned amount by threshold.
2. **Schedule delay** — planned end date has passed and project is not terminal, or actual completion is late.
3. **Slow physical progress** — expected schedule progress is much higher than reported physical progress.
4. **Financial/physical mismatch** — fund utilisation is significantly ahead of physical completion.
5. **Stale reporting** — no update for 45+ days on active work.
6. **Duplicate works** — similar names in the same area with matching amount/contractor/department.
7. **Duplicate IDs** — repeated project IDs.
8. **Amount outliers** — budget much higher than uploaded-batch median.
9. **Contractor concentration** — one contractor controls a large share of count or value.
10. **Data conflicts** — completion status conflicts with low physical progress, invalid dates or invalid amounts.

## Suggested hackathon extensions

- Upload PDFs/XLSX using `openpyxl`/OCR in `ingestion.py`.
- Add login roles for officer, auditor and admin.
- Store analysis history in SQLite/PostgreSQL.
- Add map view with district-level heatmap.
- Add LLM-based explanation refinement while keeping deterministic findings as evidence.
- Train a supervised model using past audit labels; feed rule findings as features.
- Add procurement anomaly checks: single bidder, repeated bid winners, tender value splits just below approval thresholds.
