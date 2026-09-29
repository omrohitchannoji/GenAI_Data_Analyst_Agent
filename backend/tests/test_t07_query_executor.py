import os
import sys

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, backend_dir)

from app.services.query_executor import execute_query_safely

def test_query_executor_suite():
    db_path = os.path.join(backend_dir, "uploaded_data.db")
    if not os.path.exists(db_path):
        print(f"Skipping test, db not found at {db_path}")
        return

    allowed_tables = ["data"]

    # 1. Normal valid execution
    sql = "SELECT Contract, AVG(MonthlyCharges) AS avg_charges FROM data GROUP BY Contract;"
    res = execute_query_safely(db_path, sql, allowed_tables=allowed_tables)
    assert res["success"] is True, f"Failed: {res['error']}"
    assert res["is_empty"] is False
    assert res["is_truncated"] is False
    assert len(res["rows"]) > 0
    assert "Contract" in res["columns"]

    # 2. Legitimate empty result
    empty_sql = "SELECT Contract, MonthlyCharges FROM data WHERE MonthlyCharges > 999999999;"
    res_empty = execute_query_safely(db_path, empty_sql, allowed_tables=allowed_tables)
    assert res_empty["success"] is True
    assert res_empty["is_empty"] is True
    assert res_empty["row_count"] == 0

    # 3. Truncation handling
    res_trunc = execute_query_safely(db_path, "SELECT customerID, MonthlyCharges FROM data;", allowed_tables=allowed_tables, max_display_rows=25)
    assert res_trunc["success"] is True
    assert res_trunc["is_truncated"] is True
    assert res_trunc["row_count"] == 25

    # 4. Security violation blocked before execution
    res_sec = execute_query_safely(db_path, "DROP TABLE data;", allowed_tables=allowed_tables)
    assert res_sec["success"] is False
    assert res_sec["is_security_violation"] is True

    # 5. Query timeout enforcement via progress handler
    heavy_sql = """
    WITH RECURSIVE r(i) AS (
        SELECT 1
        UNION ALL
        SELECT i + 1 FROM r WHERE i < 100000000
    )
    SELECT COUNT(*) FROM r;
    """
    res_timeout = execute_query_safely(db_path, heavy_sql, allowed_tables=allowed_tables, timeout_seconds=0.2)
    assert res_timeout["success"] is False
    assert "timeout" in res_timeout["error"].lower() or "interrupted" in res_timeout["error"].lower()

    print("\n[Test T07 Passed] Query executor verified: valid queries, empty results, row truncation, AST security gating, and runtime timeout interruption.")

if __name__ == "__main__":
    test_query_executor_suite()
