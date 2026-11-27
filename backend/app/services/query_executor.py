import time
import sqlite3
from typing import Dict, Any, Optional, List
from app.core.sql_validator import validate_sql_security
from app.core.telemetry import langfuse_observation

DEFAULT_QUERY_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_DISPLAY_ROWS = 1000

def execute_query_safely(
    db_path: str,
    sql: str,
    allowed_tables: Optional[List[str]] = None,
    allowed_columns: Optional[List[str]] = None,
    timeout_seconds: float = DEFAULT_QUERY_TIMEOUT_SECONDS,
    max_display_rows: int = DEFAULT_MAX_DISPLAY_ROWS
) -> Dict[str, Any]:
    """
    Executes a SQL query against an SQLite database with layered security:
    1. Pre-execution AST security validation (sqlglot).
    2. Read-only connection URI enforcement (?mode=ro).
    3. Query runtime deadline enforcement via SQLite progress handler.
    4. Explicit row cap and truncation detection.
    """
    # Validator and executor are separate child observations under the graph node.
    validation_started = time.perf_counter()
    with langfuse_observation("validator") as observation:
        is_safe, security_error = validate_sql_security(
            sql=sql,
            allowed_tables=allowed_tables,
            allowed_columns=allowed_columns
        )
        if observation is not None:
            try:
                observation.update(metadata={"status": "accepted" if is_safe else "rejected"})
            except Exception:
                pass
    validation_latency_seconds = time.perf_counter() - validation_started
    if not is_safe:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "is_truncated": False,
            "is_empty": False,
            "is_security_violation": True,
            "latency_seconds": 0.0,
            "error": security_error,
            "_telemetry": {"validator_seconds": validation_latency_seconds, "executor_seconds": None}
        }

    execution_started = time.perf_counter()
    with langfuse_observation("executor") as observation:
        result = _execute_validated_query(
            db_path=db_path,
            sql=sql,
            timeout_seconds=timeout_seconds,
            max_display_rows=max_display_rows,
        )
        if observation is not None:
            try:
                observation.update(metadata={
                    "status": "success" if result.get("success") else "error",
                    "row_count": result.get("row_count", 0),
                    "latency_ms": round(result.get("latency_seconds", 0.0) * 1000, 2),
                })
            except Exception:
                pass
        result["_telemetry"] = {
            "validator_seconds": validation_latency_seconds,
            "executor_seconds": time.perf_counter() - execution_started,
        }
        return result


def _execute_validated_query(
    db_path: str,
    sql: str,
    timeout_seconds: float,
    max_display_rows: int,
) -> Dict[str, Any]:
    """Execute already-validated SQL with read-only, timeout, and row-limit controls."""
    # Enforce read-only connection
    start_time = time.time()
    conn_uri = f"file:{db_path}?mode=ro"

    try:
        conn = sqlite3.connect(conn_uri, uri=True)
    except Exception as e:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "is_truncated": False,
            "is_empty": False,
            "is_security_violation": False,
            "latency_seconds": 0.0,
            "error": f"Database connection error: {str(e)}"
        }

    # 3. Setup progress handler for query execution timeout
    deadline = start_time + timeout_seconds

    def timeout_progress_handler():
        if time.time() > deadline:
            return 1  # Non-zero interrupts the SQLite VM immediately
        return 0

    # Call progress handler every 1000 SQLite opcodes
    conn.set_progress_handler(timeout_progress_handler, 1000)

    try:
        cursor = conn.cursor()
        cursor.execute(sql)

        # Get column names
        col_names = [d[0] for d in cursor.description] if cursor.description else []

        # Fetch up to max_display_rows + 1 to detect truncation
        fetched_rows = cursor.fetchmany(max_display_rows + 1)
        elapsed = time.time() - start_time

        is_truncated = False
        if len(fetched_rows) > max_display_rows:
            is_truncated = True
            fetched_rows = fetched_rows[:max_display_rows]

        # Convert to list of dicts
        dict_rows = [dict(zip(col_names, row)) for row in fetched_rows]
        is_empty = (len(dict_rows) == 0)

        return {
            "success": True,
            "columns": col_names,
            "rows": dict_rows,
            "row_count": len(dict_rows),
            "is_truncated": is_truncated,
            "is_empty": is_empty,
            "is_security_violation": False,
            "latency_seconds": round(elapsed, 3),
            "error": None
        }

    except sqlite3.OperationalError as oe:
        elapsed = time.time() - start_time
        err_msg = str(oe)
        if "interrupted" in err_msg.lower():
            err_msg = f"Query Execution Timeout: Query exceeded the {timeout_seconds}s execution deadline."
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "is_truncated": False,
            "is_empty": False,
            "is_security_violation": False,
            "latency_seconds": round(elapsed, 3),
            "error": err_msg
        }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "is_truncated": False,
            "is_empty": False,
            "is_security_violation": False,
            "latency_seconds": round(elapsed, 3),
            "error": f"SQL Execution Error: {str(e)}"
        }
    finally:
        conn.close()
