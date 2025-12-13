# utils.py
import sqlite3
import pandas as pd
import numpy as np
import warnings

# Suppress noisy pandas warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pandas")


# ---------------------------------------------------------
# FAST, SAFE DATE DETECTION
# ---------------------------------------------------------
def detect_date_column(series: pd.Series) -> bool:
    """
    Detect if a column should be treated as a date.
    Uses safe heuristic: if 70%+ values convert to datetime -> date column.
    """

    # Numeric or boolean → definitely NOT date
    if pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series):
        return False

    # Try safe conversion (no warnings)
    converted = pd.to_datetime(series.astype(str), errors="coerce")

    # If enough values convert → classify as date
    return converted.notna().mean() >= 0.7


# ---------------------------------------------------------
# DETECT COLUMN TYPES (numeric, categorical, date)
# ---------------------------------------------------------
def detect_column_types(df: pd.DataFrame):
    numeric_cols = df.select_dtypes(include=["int64", "float64"]).columns.tolist()
    categorical_cols = []
    date_cols = []

    for col in df.columns:
        s = df[col]

        # already numeric
        if col in numeric_cols:
            continue

        # check date
        if detect_date_column(s):
            date_cols.append(col)
        else:
            categorical_cols.append(col)

    # Return both naming styles (for compatibility)
    return {
        "numeric": numeric_cols,
        "categorical": categorical_cols,
        "date": date_cols,
        "numerical_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "date_columns": date_cols
    }


# ---------------------------------------------------------
# SQL CLEANING & SAFETY HELPERS
# ---------------------------------------------------------
def clean_sql_string(sql: str) -> str:
    """Remove markdown noise and trailing semicolons."""
    if not sql:
        return sql

    sql = (
        sql.replace("```sql", "")
           .replace("```", "")
           .replace(";", "")
           .strip()
    )
    return sql


def sanitize_sql(sql: str) -> str:
    """
    Basic SQL safety: block destructive commands.
    """
    sql = clean_sql_string(sql)
    forbidden = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER"]

    upper_sql = sql.upper()
    for word in forbidden:
        if word in upper_sql:
            raise ValueError(f"Unsafe SQL detected: {word}")

    return sql


# ---------------------------------------------------------
# DATABASE HELPERS (SQLite)
# ---------------------------------------------------------
DB_FILE = "uploaded_data.db"


def save_uploaded_file_to_db(df: pd.DataFrame, table_name="data"):
    """Save uploaded CSV to SQLite."""
    conn = sqlite3.connect(DB_FILE)
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    conn.close()


def run_sql_query(sql: str):
    """
    Execute SQL safely on SQLite.
    Returns DataFrame or error string.
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query(sql, conn)
        conn.close()
        return df
    except Exception as e:
        return str(e)


def get_table_schema(table_name="data"):
    """
    Fetch table schema + inferred column types.
    Used by frontend and SQL engine.
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query(f"SELECT * FROM {table_name} LIMIT 5000", conn)
        conn.close()

        col_types = detect_column_types(df)

        return {
            "columns": df.columns.tolist(),
            "column_types": col_types
        }

    except Exception as e:
        return {"error": str(e)}
