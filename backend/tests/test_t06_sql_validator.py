import os
import sys

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, backend_dir)

from app.core.sql_validator import validate_sql_security
from app.core.schema_inspector import inspect_dataset_schema

def test_sql_validator_rules():
    allowed_tables = ["data"]
    allowed_cols = ["region", "revenue", "order_date", "customer_id"]

    # 1. Valid SELECT query
    valid_sql = "SELECT region, SUM(revenue) AS total_rev FROM data GROUP BY region ORDER BY total_rev DESC;"
    ok, err = validate_sql_security(valid_sql, allowed_tables, allowed_cols)
    assert ok is True, f"Valid query failed: {err}"

    # 2. Valid CTE query
    valid_cte = "WITH summary AS (SELECT region, revenue FROM data) SELECT region, AVG(revenue) FROM summary GROUP BY region;"
    ok, err = validate_sql_security(valid_cte, allowed_tables, allowed_cols)
    assert ok is True, f"Valid CTE failed: {err}"

    # 3. Valid COUNT(*)
    valid_count = "SELECT COUNT(*) AS total_orders FROM data WHERE revenue > 500;"
    ok, err = validate_sql_security(valid_count, allowed_tables, allowed_cols)
    assert ok is True, f"Valid COUNT(*) failed: {err}"

    # 4. Disallowed SELECT * (projection wildcard)
    wildcard_sql = "SELECT * FROM data LIMIT 10;"
    ok, err = validate_sql_security(wildcard_sql, allowed_tables, allowed_cols)
    assert ok is False
    assert "Projection wildcards (SELECT *) are prohibited" in err

    # 5. Block DROP TABLE
    drop_sql = "DROP TABLE data;"
    ok, err = validate_sql_security(drop_sql, allowed_tables, allowed_cols)
    assert ok is False
    assert "Only read-only SELECT queries are allowed" in err or "Prohibited operation" in err

    # 6. Block chained/stacked statements
    chained_sql = "SELECT region FROM data; DROP TABLE data;"
    ok, err = validate_sql_security(chained_sql, allowed_tables, allowed_cols)
    assert ok is False
    assert "Multiple statements detected" in err

    # 7. Block DELETE statement
    del_sql = "DELETE FROM data WHERE region = 'North';"
    ok, err = validate_sql_security(del_sql, allowed_tables, allowed_cols)
    assert ok is False

    # 8. Block unauthorized table
    unauth_sql = "SELECT username, password FROM users;"
    ok, err = validate_sql_security(unauth_sql, allowed_tables, allowed_cols)
    assert ok is False
    assert "Unauthorized table access" in err

    print("\n[Test T06 Passed] All AST security checks (valid CTE, count, wildcard rejection, DDL rejection) verified.")

def test_schema_inspector():
    db_path = os.path.join(backend_dir, "uploaded_data.db")
    if os.path.exists(db_path):
        schema = inspect_dataset_schema(db_path, "data")
        assert "columns" in schema
        assert "column_types" in schema
        assert schema["row_count"] > 0
        print(f"[Test T06 Passed] Schema inspected: {len(schema['columns'])} columns, {schema['row_count']} rows.")

if __name__ == "__main__":
    test_sql_validator_rules()
    test_schema_inspector()
    print("All T06 tests passed successfully!")
