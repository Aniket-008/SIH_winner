"""Test the secure API endpoints."""

import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_login():
    """Test login endpoint."""
    print("Testing login...")
    response = requests.post(
        f"{BASE_URL}/api/login",
        json={"username": "auditor", "password": "auditor123"}
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Login successful! User: {data['user']['username']}, Role: {data['user']['role']}")
        return data['token']
    else:
        print(f"✗ Login failed: {response.text}")
        return None

def test_transparency(token):
    """Test model transparency endpoint."""
    print("\nTesting model transparency...")
    response = requests.get(
        f"{BASE_URL}/api/model-transparency",
        headers={"Authorization": f"Bearer {token}"}
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Model documentation loaded! Components: {len(data.get('risk_components', []))}")
        return True
    else:
        print(f"✗ Failed: {response.text}")
        return False

def test_analysis(token):
    """Test analysis endpoint."""
    print("\nTesting analysis...")
    with open("data/sample_projects.csv", "rb") as f:
        response = requests.post(
            f"{BASE_URL}/api/analyze",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("sample.csv", f, "text/csv")}
        )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Analysis successful! Projects analyzed: {data['summary']['projects_analyzed']}")
        print(f"  High risk: {data['summary']['high_risk_count']}, Critical: {data['summary']['critical_risk_count']}")
        return True
    else:
        print(f"✗ Failed: {response.text[:200]}")
        return False

if __name__ == "__main__":
    token = test_login()
    if token:
        test_transparency(token)
        test_analysis(token)
        print("\n✓ All tests completed!")
