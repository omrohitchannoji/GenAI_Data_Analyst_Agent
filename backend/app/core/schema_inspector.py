import sqlite3
import pandas as pd
from typing import Dict, Any, List, Optional
from app.core.utils import detect_column_types

def inspect_dataset_schema(db_path: str, table_name: str = "data") -> Dict[str, Any]:
    """
    Inspects an SQLite table to produce a structured schema dictionary.
    Includes normalized types and distinct sample values for categorical columns.
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cursor = conn.cursor()

    # Get column metadata
    cursor.execute(f"PRAGMA table_info({table_name});")
    pragma_rows = cursor.fetchall()

    if not pragma_rows:
        conn.close()
        raise ValueError(f"Table '{table_name}' does not exist or has no columns in {db_path}.")

    columns = [row[1] for row in pragma_rows]

    # Sample rows for type detection
    sample_df = pd.read_sql_query(f"SELECT * FROM {table_name} LIMIT 200;", conn)
    raw_types = detect_column_types(sample_df)

    column_types = {
        "numeric": raw_types.get("numeric", []),
        "categorical": raw_types.get("categorical", []),
        "date": raw_types.get("date", [])
    }

    # Fetch up to 3 distinct sample values for categorical columns
    sample_values: Dict[str, List[Any]] = {}
    for cat_col in column_types["categorical"][:15]:
        try:
            # Escape column name with double quotes
            cursor.execute(f'SELECT DISTINCT "{cat_col}" FROM {table_name} WHERE "{cat_col}" IS NOT NULL LIMIT 3;')
            vals = [r[0] for r in cursor.fetchall()]
            sample_values[cat_col] = vals
        except Exception:
            pass

    # Total row count
    cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
    total_rows = cursor.fetchone()[0]

    conn.close()

    return {
        "table_name": table_name,
        "columns": columns,
        "column_types": column_types,
        "sample_values": sample_values,
        "row_count": total_rows
    }
