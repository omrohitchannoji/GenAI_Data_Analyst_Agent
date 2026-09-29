from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
from app.core.schema_inspector import inspect_dataset_schema
from app.services.query_executor import execute_query_safely

@tool
def inspect_schema_tool(db_path: str, table_name: str = "data") -> Dict[str, Any]:
    """
    Inspects database schema, extracting columns, normalized data types,
    and distinct sample values for categorical columns.
    """
    return inspect_dataset_schema(db_path=db_path, table_name=table_name)

@tool
def execute_sql_query_tool(
    db_path: str,
    sql: str,
    allowed_tables: Optional[List[str]] = None,
    timeout_seconds: float = 10.0
) -> Dict[str, Any]:
    """
    Executes a read-only SQL query with AST safety parsing, timeout interruption,
    and display truncation.
    """
    return execute_query_safely(
        db_path=db_path,
        sql=sql,
        allowed_tables=allowed_tables or ["data"],
        timeout_seconds=timeout_seconds
    )
