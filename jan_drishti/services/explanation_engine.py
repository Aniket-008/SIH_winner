"""Natural-language explanations and officer recommendations."""

from __future__ import annotations

from typing import Iterable, List

from jan_drishti.models import Finding, ProjectRecord


RECOMMENDATIONS = {
    "cost_overrun": "Verify revised approvals, measurement books, bills and sanction notes before releasing additional funds.",
    "schedule_delay": "Ask the implementing agency for delay reasons, revised milestones and contractor penalty status.",
    "slow_physical_progress": "Schedule a field inspection and compare geo-tagged progress photos with reported milestones.",
    "financial_physical_mismatch": "Audit payment vouchers and work completion certificates for possible inflated or advance billing.",
    "possible_duplicate_work": "Check whether matched projects cover the same work scope/location before approving payment.",
    "duplicate_project_id": "Merge or correct duplicate IDs and block downstream payments until records are reconciled.",
    "stale_reporting": "Request an updated progress report with timestamped evidence from the field officer.",
    "amount_outlier": "Review technical estimates and tender justification because budget is unusually high for this batch.",
    "contractor_concentration": "Review procurement competition and tender allocation patterns for this contractor.",
    "invalid_schedule": "Correct project dates in the source system before relying on schedule alerts.",
    "missing_sanctioned_amount": "Add sanctioned amount to improve cost-overrun and fund-utilisation checks.",
}


def explain_project(
    project: ProjectRecord,
    findings: Iterable[Finding],
    risk_score: int,
    fraud_score: int,
    risk_level: str,
) -> tuple[str, List[str]]:
    """Create an officer-friendly explanation and next actions."""

    finding_list = list(findings)
    if not finding_list:
        return (
            f"{project.project_name} currently appears low risk. No major delay, cost overrun, duplicate-work, "
            "or payment-progress mismatch was detected in the uploaded data.",
            ["Continue routine monitoring and keep progress data updated."],
        )

    ordered = sorted(finding_list, key=lambda finding: _severity_rank(finding.severity), reverse=True)
    key_reasons = "; ".join(f"{finding.title.lower()} ({finding.severity})" for finding in ordered[:3])
    explanation = (
        f"{project.project_name} is classified as {risk_level} risk with a risk score of {risk_score}/100 "
        f"and fraud-likelihood score of {fraud_score}/100. Main drivers: {key_reasons}."
    )

    recommendations: List[str] = []
    seen = set()
    for finding in ordered:
        recommendation = RECOMMENDATIONS.get(finding.type)
        if recommendation and recommendation not in seen:
            recommendations.append(recommendation)
            seen.add(recommendation)
    if not recommendations:
        recommendations.append("Review source documents and request clarification from the implementing agency.")

    return explanation, recommendations[:5]


def _severity_rank(severity: str) -> int:
    return {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(severity, 0)
