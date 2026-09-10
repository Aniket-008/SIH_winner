"""Test CSV processing to debug data cleaning issues."""

import csv
from jan_drishti.services.data_cleaning import standardize_records

# Read the CSV file
with open('data/RS_Session_259_AU_2160_3_A_to_C.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    raw_records = list(reader)

# Process first 3 records
print(f"Total records: {len(raw_records)}")
print("\n=== Processing first 3 records ===\n")

projects, issues = standardize_records(raw_records[:3])

for i, project in enumerate(projects):
    print(f"\n--- Project {i+1} ---")
    print(f"ID: {project.project_id}")
    print(f"Name: {project.project_name}")
    print(f"State: {project.state}")
    print(f"Status: {project.status}")
    print(f"Sanctioned: {project.sanctioned_amount}")
    print(f"Spent: {project.spent_amount}")
    print(f"Start Date: {project.start_date}")
    print(f"Planned End: {project.planned_end_date}")
    print(f"Financial Progress: {project.financial_progress_pct}%")
    
print(f"\n\n=== Issues Found: {len(issues)} ===")
for issue in issues:
    print(f"Row {issue['row']}, {issue['field']}: {issue['message']}")
