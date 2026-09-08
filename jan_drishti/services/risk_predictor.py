"""Risk and fraud scoring model.

The first version is a transparent weighted model. This keeps the prototype
explainable for officers and gives a clean upgrade path to train an ML model
later using the same finding types as features.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from jan_drishti.config import CONFIG
from jan_drishti.models import Finding, ProjectRecord


SEVERITY_WEIGHTS = {"low": 5, "medium": 13, "high": 24, "critical": 36}

FINDING_MULTIPLIERS = {
    "possible_duplicate_work": 1.35,
    "duplicate_project_id": 1.5,
    "financial_physical_mismatch": 1.25,
    "cost_overrun": 1.2,
    "schedule_delay": 1.0,
    "slow_physical_progress": 0.95,
    "stale_reporting": 0.85,
    "contractor_concentration": 0.9,
    "amount_outlier": 0.85,
}

FRAUD_RELEVANT_TYPES = {
    "possible_duplicate_work",
    "duplicate_project_id",
    "financial_physical_mismatch",
    "cost_overrun",
    "amount_outlier",
    "contractor_concentration",
    "negative_expenditure",
    "invalid_sanctioned_amount",
}


def score_project(project: ProjectRecord, findings: Iterable[Finding]) -> Tuple[int, int, str, List[str]]:
    """Return risk score, fraud score, level and top explainable drivers."""

    finding_list = list(findings)
    risk_score = 5.0
    fraud_score = 3.0
    driver_scores: Dict[str, float] = {}

    for finding in finding_list:
        base = SEVERITY_WEIGHTS.get(finding.severity, 8)
        multiplier = FINDING_MULTIPLIERS.get(finding.type, 0.75)
        contribution = base * multiplier
        risk_score += contribution
        driver_scores[finding.title] = max(driver_scores.get(finding.title, 0), contribution)

        if finding.type in FRAUD_RELEVANT_TYPES:
            fraud_score += contribution * 1.15
        else:
            fraud_score += contribution * 0.35

    # Continuous derived metrics add gradient risk, not just threshold risk.
    overrun = project.derived.get("cost_overrun_pct")
    if overrun:
        risk_score += min(18, overrun * 0.25)
        fraud_score += min(15, overrun * 0.2)

    delay_days = project.derived.get("delay_days")
    if delay_days:
        risk_score += min(14, delay_days / 30 * 1.2)

    gap = project.derived.get("financial_physical_gap_pct")
    if gap and gap > 0:
        fraud_score += min(18, gap * 0.3)

    risk_score_int = int(round(max(0, min(100, risk_score))))
    fraud_score_int = int(round(max(0, min(100, fraud_score))))
    risk_level = _risk_level(risk_score_int)
    top_drivers = [title for title, _ in sorted(driver_scores.items(), key=lambda item: item[1], reverse=True)[:4]]

    if not top_drivers:
        top_drivers = ["No major anomaly detected"]

    return risk_score_int, fraud_score_int, risk_level, top_drivers


def _risk_level(score: int) -> str:
    thresholds = CONFIG.thresholds
    if score >= thresholds.critical_risk:
        return "Critical"
    if score >= thresholds.high_risk:
        return "High"
    if score >= thresholds.medium_risk:
        return "Medium"
    return "Low"
