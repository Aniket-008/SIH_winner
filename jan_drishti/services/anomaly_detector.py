"""Explainable anomaly detection for government development projects."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from difflib import SequenceMatcher
from math import atan2, cos, radians, sin, sqrt
from statistics import median
from typing import Dict, List, Optional

from jan_drishti.config import CONFIG
from jan_drishti.models import Finding, ProjectRecord


_COMPLETED_STATUSES = {"completed", "complete", "closed", "finished", "done"}
_CANCELLED_STATUSES = {"cancelled", "canceled", "dropped", "terminated", "abandoned"}


def detect_anomalies(projects: List[ProjectRecord], today: date) -> Dict[str, List[Finding]]:
    """Detect project-specific and cross-project anomalies."""

    findings: Dict[str, List[Finding]] = {project.project_id: [] for project in projects}

    for project in projects:
        _calculate_derived_metrics(project, today)
        findings[project.project_id].extend(_detect_single_project_anomalies(project))

    _detect_duplicate_works(projects, findings)
    _detect_amount_outliers(projects, findings)
    _detect_contractor_concentration(projects, findings)

    return findings


def _detect_single_project_anomalies(project: ProjectRecord) -> List[Finding]:
    thresholds = CONFIG.thresholds
    findings: List[Finding] = []

    cost_overrun_pct = project.derived.get("cost_overrun_pct")
    if cost_overrun_pct is not None and cost_overrun_pct > thresholds.low_cost_overrun_pct:
        if cost_overrun_pct >= thresholds.critical_cost_overrun_pct:
            severity = "critical"
        elif cost_overrun_pct >= thresholds.high_cost_overrun_pct:
            severity = "high"
        elif cost_overrun_pct >= thresholds.medium_cost_overrun_pct:
            severity = "medium"
        else:
            severity = "low"
        findings.append(
            Finding(
                type="cost_overrun",
                severity=severity,
                title="Cost overrun detected",
                message=f"Expenditure is {cost_overrun_pct:.1f}% above the sanctioned amount.",
                evidence={
                    "sanctioned_amount": project.sanctioned_amount,
                    "spent_amount": project.spent_amount,
                    "cost_overrun_pct": round(cost_overrun_pct, 2),
                },
            )
        )

    delay_days = project.derived.get("delay_days") or 0
    if delay_days > 0:
        if delay_days >= thresholds.critical_delay_days:
            severity = "critical"
        elif delay_days >= thresholds.high_delay_days:
            severity = "high"
        elif delay_days >= thresholds.medium_delay_days:
            severity = "medium"
        else:
            severity = "low"
        findings.append(
            Finding(
                type="schedule_delay",
                severity=severity,
                title="Project delay detected",
                message=f"Project is delayed by {delay_days} day(s) against planned completion.",
                evidence={
                    "planned_end_date": project.planned_end_date.isoformat() if project.planned_end_date else None,
                    "actual_end_date": project.actual_end_date.isoformat() if project.actual_end_date else None,
                    "delay_days": delay_days,
                    "status": project.status,
                },
            )
        )

    schedule_gap = project.derived.get("schedule_progress_gap_pct")
    if schedule_gap is not None and schedule_gap > thresholds.schedule_slippage_medium_pct:
        severity = "high" if schedule_gap >= thresholds.schedule_slippage_high_pct else "medium"
        findings.append(
            Finding(
                type="slow_physical_progress",
                severity=severity,
                title="Physical progress below expected pace",
                message=(
                    f"Based on elapsed schedule, physical progress is approximately "
                    f"{schedule_gap:.1f}% behind expected progress."
                ),
                evidence={
                    "expected_progress_pct": round(project.derived.get("expected_schedule_progress_pct") or 0, 2),
                    "physical_progress_pct": project.physical_progress_pct,
                    "gap_pct": round(schedule_gap, 2),
                },
            )
        )

    fin_phys_gap = project.derived.get("financial_physical_gap_pct")
    if fin_phys_gap is not None and fin_phys_gap > thresholds.medium_financial_physical_gap_pct:
        severity = "high" if fin_phys_gap >= thresholds.high_financial_physical_gap_pct else "medium"
        findings.append(
            Finding(
                type="financial_physical_mismatch",
                severity=severity,
                title="High spending with low physical progress",
                message=(
                    f"Financial progress is {fin_phys_gap:.1f}% higher than physical progress, "
                    "which can indicate front-loaded payments or inflated bills."
                ),
                evidence={
                    "financial_progress_pct": round(project.derived.get("effective_financial_progress_pct") or 0, 2),
                    "physical_progress_pct": project.physical_progress_pct,
                    "gap_pct": round(fin_phys_gap, 2),
                },
            )
        )

    stale_days = project.derived.get("stale_update_days")
    if stale_days is not None and stale_days > thresholds.stale_update_days and not _is_terminal(project.status):
        severity = "high" if stale_days >= thresholds.very_stale_update_days else "medium"
        findings.append(
            Finding(
                type="stale_reporting",
                severity=severity,
                title="Project reporting is stale",
                message=f"No update has been recorded for {stale_days} day(s).",
                evidence={
                    "last_updated": project.last_updated.isoformat() if project.last_updated else None,
                    "stale_update_days": stale_days,
                },
            )
        )

    if _is_completed(project.status) and project.physical_progress_pct is not None and project.physical_progress_pct < 95:
        findings.append(
            Finding(
                type="completion_progress_conflict",
                severity="medium",
                title="Completed status conflicts with progress",
                message="Project is marked completed even though physical progress is below 95%.",
                evidence={"status": project.status, "physical_progress_pct": project.physical_progress_pct},
            )
        )

    if _is_completed(project.status) and project.spent_amount is not None and project.sanctioned_amount:
        utilisation = project.spent_amount / project.sanctioned_amount * 100
        if utilisation < 50:
            findings.append(
                Finding(
                    type="low_utilisation_completed",
                    severity="low",
                    title="Completed project with low fund utilisation",
                    message="Completion is reported with unusually low fund utilisation.",
                    evidence={"fund_utilisation_pct": round(utilisation, 2)},
                )
            )

    if project.sanctioned_amount and project.sanctioned_amount >= 1_000_000:
        if project.sanctioned_amount % 1_000_000 == 0:
            findings.append(
                Finding(
                    type="round_amount_watch",
                    severity="low",
                    title="Round sanctioned amount",
                    message="Sanctioned amount is a large exact round number. Treat only as a weak signal.",
                    evidence={"sanctioned_amount": project.sanctioned_amount},
                )
            )

    return findings


def _calculate_derived_metrics(project: ProjectRecord, today: date) -> None:
    sanctioned = project.sanctioned_amount or 0
    spent = project.spent_amount

    if sanctioned > 0 and spent is not None:
        project.derived["cost_overrun_pct"] = max(0.0, (spent - sanctioned) / sanctioned * 100)
        project.derived["effective_financial_progress_pct"] = spent / sanctioned * 100
    elif project.financial_progress_pct is not None:
        project.derived["cost_overrun_pct"] = None
        project.derived["effective_financial_progress_pct"] = project.financial_progress_pct
    else:
        project.derived["cost_overrun_pct"] = None
        project.derived["effective_financial_progress_pct"] = None

    if project.financial_progress_pct is not None:
        project.derived["effective_financial_progress_pct"] = project.financial_progress_pct

    if project.physical_progress_pct is not None and project.derived.get("effective_financial_progress_pct") is not None:
        project.derived["financial_physical_gap_pct"] = (
            project.derived["effective_financial_progress_pct"] - project.physical_progress_pct
        )
    else:
        project.derived["financial_physical_gap_pct"] = None

    if project.planned_end_date:
        if _is_completed(project.status) and project.actual_end_date:
            project.derived["delay_days"] = max(0, (project.actual_end_date - project.planned_end_date).days)
        elif not _is_terminal(project.status):
            project.derived["delay_days"] = max(0, (today - project.planned_end_date).days)
        else:
            project.derived["delay_days"] = 0
    else:
        project.derived["delay_days"] = None

    if project.last_updated:
        project.derived["stale_update_days"] = max(0, (today - project.last_updated).days)
    else:
        project.derived["stale_update_days"] = None

    if project.start_date and project.planned_end_date and project.physical_progress_pct is not None:
        total_days = max(1, (project.planned_end_date - project.start_date).days)
        elapsed_days = min(max(0, (today - project.start_date).days), total_days)
        expected_progress = elapsed_days / total_days * 100
        project.derived["expected_schedule_progress_pct"] = expected_progress
        project.derived["schedule_progress_gap_pct"] = max(0.0, expected_progress - project.physical_progress_pct)
    else:
        project.derived["expected_schedule_progress_pct"] = None
        project.derived["schedule_progress_gap_pct"] = None


def _detect_duplicate_works(projects: List[ProjectRecord], findings: Dict[str, List[Finding]]) -> None:
    thresholds = CONFIG.thresholds
    for idx, left in enumerate(projects):
        for right in projects[idx + 1 :]:
            if left.project_id == right.project_id:
                _add_pair_finding(
                    left,
                    right,
                    findings,
                    finding_type="duplicate_project_id",
                    title="Duplicate project ID",
                    message="Two rows share the same project ID.",
                    severity="critical",
                    evidence={"project_id": left.project_id},
                )
                continue

            name_similarity = _similarity(left.project_name, right.project_name)
            location_match = _location_match(left, right)
            amount_match = _amount_match(left.sanctioned_amount, right.sanctioned_amount, thresholds.duplicate_amount_tolerance_pct)
            contractor_match = _safe_lower(left.contractor) == _safe_lower(right.contractor) and _safe_lower(left.contractor) != "unknown"
            department_match = _safe_lower(left.department) == _safe_lower(right.department)

            if name_similarity >= thresholds.duplicate_name_similarity and location_match and (amount_match or contractor_match or department_match):
                severity = "critical" if amount_match and contractor_match else "high"
                _add_pair_finding(
                    left,
                    right,
                    findings,
                    finding_type="possible_duplicate_work",
                    title="Possible duplicate work",
                    message="Similar project names appear in the same area with matching cost/contractor signals.",
                    severity=severity,
                    evidence={
                        "name_similarity": round(name_similarity, 3),
                        "location_match": location_match,
                        "amount_match": amount_match,
                        "contractor_match": contractor_match,
                    },
                )


def _add_pair_finding(
    left: ProjectRecord,
    right: ProjectRecord,
    findings: Dict[str, List[Finding]],
    finding_type: str,
    title: str,
    message: str,
    severity: str,
    evidence: Dict[str, object],
) -> None:
    left_evidence = dict(evidence, matched_project_id=right.project_id, matched_project_name=right.project_name)
    right_evidence = dict(evidence, matched_project_id=left.project_id, matched_project_name=left.project_name)
    findings[left.project_id].append(Finding(finding_type, severity, title, message, left_evidence))
    findings[right.project_id].append(Finding(finding_type, severity, title, message, right_evidence))


def _detect_amount_outliers(projects: List[ProjectRecord], findings: Dict[str, List[Finding]]) -> None:
    amounts = [project.sanctioned_amount for project in projects if project.sanctioned_amount and project.sanctioned_amount > 0]
    if len(amounts) < 5:
        return
    med = median(amounts)
    absolute_deviations = [abs(amount - med) for amount in amounts]
    mad = median(absolute_deviations) or 1

    for project in projects:
        amount = project.sanctioned_amount
        if not amount:
            continue
        modified_z = 0.6745 * (amount - med) / mad
        if modified_z > 3.5 and amount > med * 2:
            findings[project.project_id].append(
                Finding(
                    type="amount_outlier",
                    severity="medium",
                    title="Budget amount is an outlier",
                    message="Sanctioned amount is much higher than the median for uploaded projects.",
                    evidence={"sanctioned_amount": amount, "median_amount": med, "modified_z_score": round(modified_z, 2)},
                )
            )


def _detect_contractor_concentration(projects: List[ProjectRecord], findings: Dict[str, List[Finding]]) -> None:
    groups: Dict[str, List[ProjectRecord]] = defaultdict(list)
    total_amount = sum(project.sanctioned_amount or 0 for project in projects)
    for project in projects:
        contractor = _safe_lower(project.contractor)
        if contractor and contractor != "unknown":
            groups[contractor].append(project)

    for _, contractor_projects in groups.items():
        if len(contractor_projects) < 3 or len(projects) < 5:
            continue
        amount = sum(project.sanctioned_amount or 0 for project in contractor_projects)
        count_share = len(contractor_projects) / len(projects)
        amount_share = amount / total_amount if total_amount else 0
        if count_share >= 0.4 or amount_share >= 0.5:
            for project in contractor_projects:
                findings[project.project_id].append(
                    Finding(
                        type="contractor_concentration",
                        severity="medium",
                        title="Contractor concentration risk",
                        message="A single contractor controls a large share of the uploaded work package.",
                        evidence={
                            "contractor": project.contractor,
                            "project_count_share_pct": round(count_share * 100, 2),
                            "amount_share_pct": round(amount_share * 100, 2),
                        },
                    )
                )


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, _safe_lower(left), _safe_lower(right)).ratio()


def _safe_lower(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _location_match(left: ProjectRecord, right: ProjectRecord) -> bool:
    district_match = _safe_lower(left.district) == _safe_lower(right.district) and _safe_lower(left.district) != "unknown"
    block_match = _safe_lower(left.block) == _safe_lower(right.block) and _safe_lower(left.block) != "unknown"
    geo_distance = _geo_distance_km(left, right)
    geo_match = geo_distance is not None and geo_distance <= 0.5
    return geo_match or (district_match and (block_match or _safe_lower(left.block) == "unknown" or _safe_lower(right.block) == "unknown"))


def _amount_match(left: Optional[float], right: Optional[float], tolerance_pct: float) -> bool:
    if not left or not right:
        return False
    base = max(abs(left), abs(right), 1)
    return abs(left - right) / base * 100 <= tolerance_pct


def _geo_distance_km(left: ProjectRecord, right: ProjectRecord) -> Optional[float]:
    if None in {left.latitude, left.longitude, right.latitude, right.longitude}:
        return None
    earth_radius_km = 6371.0
    lat1, lon1, lat2, lon2 = map(radians, [left.latitude, left.longitude, right.latitude, right.longitude])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return earth_radius_km * c


def _is_completed(status: str) -> bool:
    return _safe_lower(status) in _COMPLETED_STATUSES


def _is_terminal(status: str) -> bool:
    return _safe_lower(status) in _COMPLETED_STATUSES | _CANCELLED_STATUSES
