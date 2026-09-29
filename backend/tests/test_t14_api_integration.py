import os
import sys
from dotenv import load_dotenv
from starlette.testclient import TestClient

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, backend_dir)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv(os.path.join(backend_dir, ".env"))

from app.main import app

def test_api_query_endpoint():
    client = TestClient(app)

    # 1. Test POST /query with valid question
    payload = {
        "question": "Average MonthlyCharges by Contract",
        "dataset_id": "default",
        "session_id": "api_test_session"
    }
    response = client.post("/query", json=payload)
    assert response.status_code == 200, f"Error: {response.text}"

    data = response.json()
    print("\nAPI Response Status:", data.get("status"))
    print("API Response SQL:", data.get("sql"))
    print("API Metrics Count:", len(data.get("metrics", [])))
    print("API Chart Type:", data.get("chart", {}).get("chart_type"))
    print("API Answer Preview:", data.get("answer", "")[:120] + "...")

    assert data["status"] == "success"
    assert data["sql"] is not None
    assert len(data["metrics"]) > 0
    assert data["chart"]["chart_type"] in ["bar", "line", "kpi", "table"]

    # 2. Test Malicious Query -> REJECTED
    mal_payload = {
        "question": "DROP TABLE data;",
        "dataset_id": "default",
        "session_id": "api_test_session"
    }
    mal_resp = client.post("/query", json=mal_payload)
    assert mal_resp.status_code == 200
    assert mal_resp.json()["status"] == "rejected"

    print("\n[Test T14 Passed] FastAPI /query endpoint tested end-to-end with TestClient.")

if __name__ == "__main__":
    test_api_query_endpoint()
