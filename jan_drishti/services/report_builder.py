"""Build dashboard-ready reports from project analysis results."""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any, Dict, List

from jan_drishti.models import ProjectRiskResult
from jan_drishti.services.data_cleaning import expected_columns


def build_summary(results: List[ProjectRiskResult]) -> Dict[str, Any]:
    count = len(results)
    risk_scores = [result.risk_score for result in results]
    fraud_scores = [result.fraud_score for result in results]
    levels = Counter(result.risk_level for result in results)
    all_findings = [finding for result in results for finding in result.findings]
    finding_types = Counter(finding.type for finding in all_findings)

    sanctioned_total = sum(result.project.sanctioned_amount or 0 for result in results)
    spent_total = sum(result.project.spent_amount or 0 for result in results)
    project_level_overrun = sum(
        max(0, (result.project.spent_amount or 0) - (result.project.sanctioned_amount or 0))
        for result in results
        if result.project.sanctioned_amount is not None and result.project.spent_amount is not None
    )

    return {
        "projects_analyzed": count,
        "average_risk_score": round(sum(risk_scores) / count, 2) if count else 0,
        "average_fraud_score": round(sum(fraud_scores) / count, 2) if count else 0,
        "critical_risk_count": levels.get("Critical", 0),
        "high_risk_count": levels.get("High", 0),
        "medium_risk_count": levels.get("Medium", 0),
        "low_risk_count": levels.get("Low", 0),
        "total_sanctioned_amount": round(sanctioned_total, 2),
        "total_spent_amount": round(spent_total, 2),
        "potential_overrun_amount": round(project_level_overrun, 2),
        "delay_alert_count": finding_types.get("schedule_delay", 0),
        "cost_overrun_alert_count": finding_types.get("cost_overrun", 0),
        "duplicate_alert_count": finding_types.get("possible_duplicate_work", 0) + finding_types.get("duplicate_project_id", 0),
        "financial_mismatch_count": finding_types.get("financial_physical_mismatch", 0),
        "total_findings": len(all_findings),
    }


def build_alerts(results: List[ProjectRiskResult]) -> List[Dict[str, Any]]:
    """Return the most urgent dashboard alerts."""

    alerts: List[Dict[str, Any]] = []
    for result in sorted(results, key=lambda item: item.risk_score, reverse=True):
        top_finding = sorted(result.findings, key=lambda finding: _severity_rank(finding.severity), reverse=True)[:1]
        if not top_finding and result.risk_score < 35:
            continue
        finding = top_finding[0] if top_finding else None
        alerts.append(
            {
                "project_id": result.project.project_id,
                "project_name": result.project.project_name,
                "district": result.project.district,
                "risk_level": result.risk_level,
                "risk_score": result.risk_score,
                "fraud_score": result.fraud_score,
                "reason": finding.title if finding else "Risk score threshold crossed",
                "severity": finding.severity if finding else result.risk_level.lower(),
            }
        )
    return alerts[:10]


def report_metadata(today: date, source_name: str, raw_count: int) -> Dict[str, Any]:
    return {
        "analysis_date": today.isoformat(),
        "source_file": source_name,
        "raw_rows_received": raw_count,
        "engine_version": "explainable-rules-v0.1",
        "expected_columns": expected_columns(),
    }


def _severity_rank(severity: str) -> int:
    return {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(str(severity).lower(), 0)
