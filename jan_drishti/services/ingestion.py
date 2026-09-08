"""Document ingestion for uploaded government project files.

The prototype intentionally supports CSV and JSON with only Python's standard
library so it runs in hackathon environments without setup friction. XLSX/PDF
parsers can be plugged in later without changing the AI engine or website.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

SUPPORTED_EXTENSIONS = {".csv", ".json"}


class IngestionError(ValueError):
    """Raised when an upload cannot be parsed into project rows."""


def decode_text(content: bytes) -> str:
    """Decode uploaded bytes using common government-data encodings."""

    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise IngestionError("Unable to decode file. Please upload UTF-8 CSV or JSON.")


def load_records(filename: str, content: bytes) -> List[Dict[str, Any]]:
    """Parse an uploaded file into a list of dictionaries."""

    extension = Path(filename or "").suffix.lower()
    if extension == ".csv":
        return _load_csv(content)
    if extension == ".json":
        return _load_json(content)
    raise IngestionError(
        f"Unsupported file type '{extension or 'unknown'}'. Upload CSV or JSON for this prototype."
    )


def _load_csv(content: bytes) -> List[Dict[str, Any]]:
    text = decode_text(content)
    if not text.strip():
        raise IngestionError("Uploaded CSV is empty.")

    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample)
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise IngestionError("CSV must contain a header row with column names.")

    records = [dict(row) for row in reader if any(str(value or "").strip() for value in row.values())]
    if not records:
        raise IngestionError("CSV has headers but no project rows.")
    return records


def _load_json(content: bytes) -> List[Dict[str, Any]]:
    text = decode_text(content)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise IngestionError(f"Invalid JSON: {exc.msg}") from exc

    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        for key in ("projects", "records", "data", "items"):
            if isinstance(payload.get(key), list):
                records = payload[key]
                break
        else:
            records = [payload]
    else:
        raise IngestionError("JSON must be an object, a list of projects, or contain a 'projects' list.")

    if not all(isinstance(item, dict) for item in records):
        raise IngestionError("Every project row in JSON must be an object.")
    if not records:
        raise IngestionError("JSON contains no project rows.")
    return list(records)


def records_to_csv(records: Iterable[Dict[str, Any]]) -> str:
    """Utility used by demos/tests to turn records into CSV text."""

    rows = list(records)
    if not rows:
        return ""
    fieldnames = sorted({key for row in rows for key in row.keys()})
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
