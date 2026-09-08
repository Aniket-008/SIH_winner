"""Typed data structures used across the JAN-DRISHTI engine."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict, is_dataclass
from datetime import date
from typing import Any, Dict, List, Optional


Severity = str


@dataclass
class Finding:
    """A single explainable anomaly/risk observation."""

    type: str
    severity: Severity
    title: str
    message: str
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectRecord:
    """Canonical project schema after ingestion and cleaning."""

    row_number: int
    project_id: str
    project_name: str = "Unnamed Project"
    department: str = "Unknown"
    district: str = "Unknown"
    block: str = "Unknown"
    state: str = "Unknown"
    agency: str = "Unknown"
    contractor: str = "Unknown"
    sanctioned_amount: Optional[float] = None
    revised_amount: Optional[float] = None
    spent_amount: Optional[float] = None
    physical_progress_pct: Optional[float] = None
    financial_progress_pct: Optional[float] = None
    start_date: Optional[date] = None
    planned_end_date: Optional[date] = None
    actual_end_date: Optional[date] = None
    last_updated: Optional[date] = None
    status: str = "Unknown"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    raw: Dict[str, Any] = field(default_factory=dict)
    extra_fields: Dict[str, Any] = field(default_factory=dict)
    derived: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectRiskResult:
    """Final result returned for each project."""

    project: ProjectRecord
    risk_score: int
    fraud_score: int
    risk_level: str
    findings: List[Finding]
    top_drivers: List[str]
    explanation: str
    recommendations: List[str]


@dataclass
class AnalysisReport:
    """Top-level API response model."""

    summary: Dict[str, Any]
    projects: List[ProjectRiskResult]
    alerts: List[Dict[str, Any]]
    validation_issues: List[Dict[str, Any]]
    expected_columns: Dict[str, List[str]]
    metadata: Dict[str, Any]


def to_jsonable(value: Any) -> Any:
    """Convert dataclasses and dates into JSON-serialisable objects."""

    if is_dataclass(value):
        return {key: to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    return value
