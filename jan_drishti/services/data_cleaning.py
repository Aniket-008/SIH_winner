"""Data cleaning and canonical schema mapping.

Government datasets rarely use identical headers. This module maps common field
names (project code, work ID, district name, expenditure etc.) into one internal
schema consumed by the anomaly engine.
"""

from __future__ import annotations

from datetime import date, datetime
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from jan_drishti.models import ProjectRecord


COLUMN_ALIASES: Dict[str, List[str]] = {
    "project_id": [
        "project_id",
        "project code",
        "project_code",
        "work_id",
        "work id",
        "scheme_id",
        "id",
        "uid",
        "sanction_id",
    ],
    "project_name": [
        "project_name",
        "project name",
        "work_name",
        "work name",
        "name",
        "title",
        "scheme_name",
        "description",
    ],
    "department": ["department", "dept", "ministry", "line_department", "sector"],
    "district": ["district", "district_name", "dist", "city"],
    "block": ["block", "taluka", "tehsil", "mandal", "ulb", "village", "ward"],
    "state": ["state", "state_name"],
    "agency": ["agency", "implementing_agency", "executing_agency", "pia", "office"],
    "contractor": ["contractor", "vendor", "supplier", "firm", "beneficiary", "company"],
    "sanctioned_amount": [
        "sanctioned_amount",
        "sanction amount",
        "approved_cost",
        "approved amount",
        "estimated_cost",
        "budget",
        "project_cost",
        "sanctioned_cost",
    ],
    "revised_amount": ["revised_amount", "revised cost", "revised_budget", "revised_project_cost"],
    "spent_amount": [
        "spent_amount",
        "expenditure",
        "amount_spent",
        "released_amount",
        "paid_amount",
        "utilized_amount",
        "payment",
        "total_expenditure",
    ],
    "physical_progress_pct": [
        "physical_progress_pct",
        "physical_progress",
        "progress",
        "completion_pct",
        "work_progress",
        "progress_percent",
    ],
    "financial_progress_pct": [
        "financial_progress_pct",
        "financial_progress",
        "fund_utilization_pct",
        "expenditure_pct",
        "payment_progress",
    ],
    "start_date": ["start_date", "commencement_date", "work_start_date", "date_started"],
    "planned_end_date": [
        "planned_end_date",
        "target_completion_date",
        "expected_completion_date",
        "end_date",
        "deadline",
        "planned_completion",
    ],
    "actual_end_date": ["actual_end_date", "completion_date", "actual_completion_date"],
    "last_updated": ["last_updated", "updated_at", "last_update_date", "report_date", "measurement_date"],
    "status": ["status", "project_status", "work_status", "stage"],
    "latitude": ["latitude", "lat", "geo_lat"],
    "longitude": ["longitude", "lon", "lng", "geo_lon"],
}

NUMERIC_FIELDS = {
    "sanctioned_amount",
    "revised_amount",
    "spent_amount",
    "physical_progress_pct",
    "financial_progress_pct",
    "latitude",
    "longitude",
}

DATE_FIELDS = {"start_date", "planned_end_date", "actual_end_date", "last_updated"}

_TEXT_DEFAULTS = {
    "project_name": "Unnamed Project",
    "department": "Unknown",
    "district": "Unknown",
    "block": "Unknown",
    "state": "Unknown",
    "agency": "Unknown",
    "contractor": "Unknown",
    "status": "Unknown",
}

_MULTIPLIERS = {
    "crore": 10_000_000,
    "cr": 10_000_000,
    "lakh": 100_000,
    "lac": 100_000,
    "lakhs": 100_000,
    "thousand": 1_000,
    "k": 1_000,
    "million": 1_000_000,
    "mn": 1_000_000,
}


def expected_columns() -> Dict[str, List[str]]:
    """Expose accepted aliases for the UI and README."""

    return COLUMN_ALIASES


def standardize_records(raw_records: Iterable[Dict[str, Any]]) -> Tuple[List[ProjectRecord], List[Dict[str, Any]]]:
    """Map raw rows to ProjectRecord objects and collect cleaning warnings."""

    projects: List[ProjectRecord] = []
    issues: List[Dict[str, Any]] = []

    for row_number, raw in enumerate(raw_records, start=1):
        normalised_row = {_normalise_header(key): value for key, value in raw.items()}
        alias_to_original = {_normalise_header(key): key for key in raw.keys()}
        canonical_values: Dict[str, Any] = {}
        used_headers = set()

        for canonical, aliases in COLUMN_ALIASES.items():
            for alias in aliases:
                alias_key = _normalise_header(alias)
                if alias_key in normalised_row:
                    canonical_values[canonical] = normalised_row[alias_key]
                    used_headers.add(alias_to_original.get(alias_key, alias_key))
                    break

        extra_fields = {key: value for key, value in raw.items() if key not in used_headers}

        project_id = _clean_text(canonical_values.get("project_id")) or f"ROW-{row_number:04d}"
        if project_id.startswith("ROW-"):
            issues.append(
                {
                    "row": row_number,
                    "field": "project_id",
                    "severity": "low",
                    "message": "Project ID missing; generated a temporary row ID.",
                }
            )

        converted: Dict[str, Any] = {
            "row_number": row_number,
            "project_id": project_id,
            "raw": dict(raw),
            "extra_fields": extra_fields,
        }

        for field, default in _TEXT_DEFAULTS.items():
            converted[field] = _clean_text(canonical_values.get(field)) or default

        for field in NUMERIC_FIELDS:
            value, warning = _parse_number(canonical_values.get(field), field)
            converted[field] = value
            if warning:
                issues.append({"row": row_number, "field": field, "severity": "medium", "message": warning})

        for field in DATE_FIELDS:
            value, warning = _parse_date(canonical_values.get(field))
            converted[field] = value
            if warning:
                issues.append({"row": row_number, "field": field, "severity": "medium", "message": warning})

        for progress_field in ("physical_progress_pct", "financial_progress_pct"):
            progress = converted.get(progress_field)
            if progress is not None and 0 <= progress <= 1:
                converted[progress_field] = progress * 100

        projects.append(ProjectRecord(**converted))

    return projects, issues


def _normalise_header(header: Any) -> str:
    header = str(header or "").strip().lower()
    header = re.sub(r"[%₹$()]+", " ", header)
    header = re.sub(r"[^a-z0-9]+", "_", header)
    return header.strip("_")


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _parse_number(value: Any, field_name: str) -> Tuple[Optional[float], Optional[str]]:
    if value is None or str(value).strip() == "":
        return None, None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value), None

    original = str(value).strip()
    lowered = original.lower().replace(",", "")
    multiplier = 1.0
    for token, factor in _MULTIPLIERS.items():
        if re.search(rf"\b{re.escape(token)}\b", lowered):
            multiplier = float(factor)
            lowered = re.sub(rf"\b{re.escape(token)}\b", "", lowered)
            break

    # Remove currency symbols and percentage markers but keep minus/decimal signs.
    cleaned = re.sub(r"[^0-9.\-]", "", lowered)
    if cleaned in {"", ".", "-", "-."}:
        return None, f"Could not parse numeric value '{original}'."

    try:
        number = float(cleaned) * multiplier
    except ValueError:
        return None, f"Could not parse numeric value '{original}'."

    if field_name in {"latitude", "longitude"}:
        if field_name == "latitude" and not -90 <= number <= 90:
            return number, f"Latitude '{original}' is outside the valid range -90 to 90."
        if field_name == "longitude" and not -180 <= number <= 180:
            return number, f"Longitude '{original}' is outside the valid range -180 to 180."

    return number, None


def _parse_date(value: Any) -> Tuple[Optional[date], Optional[str]]:
    if value is None or str(value).strip() == "":
        return None, None
    if isinstance(value, date):
        return value, None

    text = str(value).strip()
    if text.isdigit() and len(text) in {5, 6}:
        # Excel serial date support (1900 date system, leap-year bug approximated).
        try:
            return date.fromordinal(date(1899, 12, 30).toordinal() + int(text)), None
        except ValueError:
            pass

    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%d.%m.%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%b %d %Y",
        "%B %d %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date(), None
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date(), None
    except ValueError:
        return None, f"Could not parse date value '{text}'. Use YYYY-MM-DD or DD/MM/YYYY."
