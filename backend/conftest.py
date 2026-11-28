import sys
import os
import sqlite3
import pandas as pd
import pytest

backend_dir = os.path.abspath(os.path.dirname(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Ensure a default uploaded_data.db exists for testing and set test auth secret."""
    os.environ.setdefault("AUTH_SECRET_KEY", "test_ci_secure_secret_key_2026_32bytes")
    db_file = os.path.join(backend_dir, "uploaded_data.db")
    fixture_csv = os.path.join(backend_dir, "eval", "fixtures", "telco_churn_data.csv")

    if os.path.exists(fixture_csv):
        df = pd.read_csv(fixture_csv)
        conn = sqlite3.connect(db_file)
        df.to_sql("data", conn, if_exists="replace", index=False)
        conn.close()

