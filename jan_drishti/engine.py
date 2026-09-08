"""JAN-DRISHTI AI orchestration layer.

This file wires individual services together. Keep it thin: each service owns
one responsibility, making future upgrades (real ML model, PDF ingestion,
geospatial clustering, database storage) straightforward.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, List, Optional

from jan_drishti.config import analysis_today
from jan_drishti.models import AnalysisReport, Finding, ProjectRiskResult, to_jsonable
from jan_drishti.services.anomaly_detector import detect_anomalies
from jan_drishti.services.data_cleaning import expected_columns, standardize_records
from jan_drishti.services.data_validation import validate_projects
from jan_drishti.services.explanation_engine import explain_project
from jan_drishti.services.report_builder import build_alerts, build_summary, report_metadata
from jan_drishti.services.risk_predictor import score_project


def analyze_records(
    raw_records: Iterable[Dict[str, Any]],
    source_name: str = "uploaded-data",
    today: Optional[date] = None,
) -> AnalysisReport:
    """Run the complete government project risk-analysis pipeline."""

    raw_list = list(raw_records)
    analysis_date = today or analysis_today()

    projects, cleaning_issues = standardize_records(raw_list)
    validation_findings = validate_projects(projects)
    anomaly_findings = detect_anomalies(projects, analysis_date)

    results: List[ProjectRiskResult] = []
    for project in projects:
        findings: List[Finding] = []
        findings.extend(validation_findings.get(project.project_id, []))
        findings.extend(anomaly_findings.get(project.project_id, []))

        risk_score, fraud_score, risk_level, top_drivers = score_project(project, findings)
        explanation, recommendations = explain_project(project, findings, risk_score, fraud_score, risk_level)

        results.append(
            ProjectRiskResult(
                project=project,
                risk_score=risk_score,
                fraud_score=fraud_score,
                risk_level=risk_level,
                findings=findings,
                top_drivers=top_drivers,
                explanation=explanation,
                recommendations=recommendations,
            )
        )

    report = AnalysisReport(
        summary=build_summary(results),
        projects=sorted(results, key=lambda item: item.risk_score, reverse=True),
        alerts=build_alerts(results),
        validation_issues=cleaning_issues,
        expected_columns=expected_columns(),
        metadata=report_metadata(analysis_date, source_name, len(raw_list)),
    )
    return report


def analyze_records_json(
    raw_records: Iterable[Dict[str, Any]],
    source_name: str = "uploaded-data",
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Convenience wrapper returning plain JSON-ready dictionaries."""

    return to_jsonable(analyze_records(raw_records, source_name=source_name, today=today))
