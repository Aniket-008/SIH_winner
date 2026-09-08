from __future__ import annotations

from datetime import date
from pathlib import Path
import unittest

from jan_drishti.engine import analyze_records_json
from jan_drishti.services.ingestion import load_records


class JanDrishtiEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        sample_path = Path(__file__).resolve().parents[1] / "data" / "sample_projects.csv"
        self.records = load_records("sample_projects.csv", sample_path.read_bytes())
        self.report = analyze_records_json(self.records, source_name="sample_projects.csv", today=date(2026, 9, 8))

    def test_sample_generates_dashboard_summary(self) -> None:
        summary = self.report["summary"]
        self.assertEqual(summary["projects_analyzed"], 8)
        self.assertGreaterEqual(summary["high_risk_count"] + summary["critical_risk_count"], 1)
        self.assertGreater(summary["total_findings"], 0)

    def test_duplicate_work_is_detected(self) -> None:
        finding_types = [
            finding["type"]
            for project in self.report["projects"]
            for finding in project["findings"]
        ]
        self.assertIn("possible_duplicate_work", finding_types)

    def test_explanations_are_returned_for_each_project(self) -> None:
        for project in self.report["projects"]:
            self.assertIn("risk_score", project)
            self.assertIn("explanation", project)
            self.assertTrue(project["recommendations"])


if __name__ == "__main__":
    unittest.main()
