"""Quick test of analysis engine."""
from jan_drishti.services.ingestion import load_records
from jan_drishti.engine import analyze_records_json

with open('data/sample_projects.csv', 'rb') as f:
    content = f.read()

records = load_records('sample.csv', content)
report = analyze_records_json(records, 'sample.csv')

print(f"✓ Analysis works! Analyzed {report['summary']['projects_analyzed']} projects")
print(f"  High risk: {report['summary']['high_risk_count']}")
print(f"  Critical risk: {report['summary']['critical_risk_count']}")
