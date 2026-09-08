"""Project-level data validation rules.

Validation findings are separated from anomaly detection so teams can improve
data quality without accidentally changing the fraud-risk logic.
"""

from __future__ import annotations

from typing import Dict, List

from jan_drishti.models import Finding, ProjectRecord


RECOMMENDED_FIELDS = [
    "project_id",
    "project_name",
    "department",
    "district",
    "sanctioned_amount",
    "spent_amount",
    "physical_progress_pct",
    "planned_end_date",
    "status",
]


def validate_projects(projects: List[ProjectRecord]) -> Dict[str, List[Finding]]:
    """Return validation findings keyed by project ID."""

    findings: Dict[str, List[Finding]] = {project.project_id: [] for project in projects}

    for project in projects:
        project_findings = findings[project.project_id]

        if not project.project_name or project.project_name == "Unnamed Project":
            project_findings.append(
                Finding(
                    type="missing_project_name",
                    severity="medium",
                    title="Project name missing",
                    message="A project name is required to detect duplicate or overlapping works.",
                    evidence={"row": project.row_number},
                )
            )

        if project.sanctioned_amount is None:
            project_findings.append(
                Finding(
                    type="missing_sanctioned_amount",
                    severity="medium",
                    title="Sanctioned amount missing",
                    message="Budget or sanctioned amount is missing, reducing cost-overrun confidence.",
                    evidence={"row": project.row_number},
                )
            )
        elif project.sanctioned_amount <= 0:
            project_findings.append(
                Finding(
                    type="invalid_sanctioned_amount",
                    severity="high",
                    title="Invalid sanctioned amount",
                    message="Sanctioned amount should be a positive value.",
                    evidence={"sanctioned_amount": project.sanctioned_amount},
                )
            )

        if project.spent_amount is not None and project.spent_amount < 0:
            project_findings.append(
                Finding(
                    type="negative_expenditure",
                    severity="high",
                    title="Negative expenditure",
                    message="Spent amount is negative, which is unusual for project expenditure records.",
                    evidence={"spent_amount": project.spent_amount},
                )
            )

        for field_name in ("physical_progress_pct", "financial_progress_pct"):
            value = getattr(project, field_name)
            if value is not None and not 0 <= value <= 100:
                project_findings.append(
                    Finding(
                        type="invalid_progress_percentage",
                        severity="medium",
                        title="Progress percentage outside 0-100",
                        message=f"{field_name} should be between 0 and 100.",
                        evidence={field_name: value},
                    )
                )

        if project.start_date and project.planned_end_date and project.start_date > project.planned_end_date:
            project_findings.append(
                Finding(
                    type="invalid_schedule",
                    severity="high",
                    title="Start date after planned end date",
                    message="The project schedule is internally inconsistent.",
                    evidence={
                        "start_date": project.start_date.isoformat(),
                        "planned_end_date": project.planned_end_date.isoformat(),
                    },
                )
            )

        if project.actual_end_date and project.start_date and project.actual_end_date < project.start_date:
            project_findings.append(
                Finding(
                    type="invalid_completion_date",
                    severity="high",
                    title="Completion date before start date",
                    message="Actual completion date is before the recorded start date.",
                    evidence={
                        "actual_end_date": project.actual_end_date.isoformat(),
                        "start_date": project.start_date.isoformat(),
                    },
                )
            )

    return findings
