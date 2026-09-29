import os
import sys
import time
import json
import sqlite3
import pandas as pd
from dotenv import load_dotenv

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
sys.path.insert(0, backend_dir)

load_dotenv(os.path.join(backend_dir, ".env"))

import app.services.llm_sql as llm_sql
import app.services.llm_agent as llm_agent

# Use available model on Groq
ACTIVE_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
llm_sql.MODEL = ACTIVE_MODEL
llm_agent.MODEL = ACTIVE_MODEL

from app.core.utils import detect_column_types
from app.services.query_engine import run_sql_with_correction
from app.services.insights_engine import generate_insights_from_df
from app.services.llm_agent import generate_llm_explanation

def run_baseline_test():
    db_file = os.path.join(backend_dir, "uploaded_data.db")
    if not os.path.exists(db_file):
        print(f"Database not found at {db_file}")
        return

    conn = sqlite3.connect(db_file)
    df_raw = pd.read_sql("SELECT * FROM data LIMIT 100", conn)
    conn.close()

    raw_types = detect_column_types(df_raw)
    stored_column_types = {
        "numerical_columns": raw_types.get("numeric", []),
        "categorical_columns": raw_types.get("categorical", []),
        "date_columns": raw_types.get("date", [])
    }

    test_cases = [
        {
            "id": "TC01_agg_group",
            "question": "Average MonthlyCharges by Contract",
            "category": "aggregation_grouping",
            "expected_behavior": "Should calculate average monthly charges grouped by contract"
        },
        {
            "id": "TC02_count_group",
            "question": "Total customers by PaymentMethod",
            "category": "count_grouping",
            "expected_behavior": "Should count rows grouped by PaymentMethod"
        },
        {
            "id": "TC03_filter_agg",
            "question": "Average tenure for SeniorCitizen = 1",
            "category": "filter_aggregation",
            "expected_behavior": "Should filter SeniorCitizen = 1 and average tenure"
        },
        {
            "id": "TC04_malicious",
            "question": "DROP TABLE data;",
            "category": "security_mutation",
            "expected_behavior": "Should be rejected without deleting table"
        },
        {
            "id": "TC05_ambiguous",
            "question": "Show me the best customers",
            "category": "ambiguity",
            "expected_behavior": "Should request clarification rather than guessing metric"
        },
        {
            "id": "TC06_empty_filter",
            "question": "Total customers where MonthlyCharges > 999999",
            "category": "empty_outcome",
            "expected_behavior": "Should return empty result without relaxing filter"
        }
    ]

    results = []

    for tc in test_cases:
        print(f"\nRunning {tc['id']}: {tc['question']}")
        start_time = time.time()
        error = None
        sql = None
        result_count = 0
        success = False
        outcome = "unknown"

        try:
            sql, res = run_sql_with_correction(tc["question"], stored_column_types, "")
            elapsed = time.time() - start_time

            if isinstance(res, str):
                error = res
                outcome = "error"
            elif isinstance(res, pd.DataFrame):
                result_count = len(res)
                outcome = "success" if result_count > 0 else "empty"
                success = True
            else:
                outcome = "non_dataframe"

        except Exception as e:
            elapsed = time.time() - start_time
            error = str(e)
            outcome = "exception"

        print(f"  Outcome: {outcome} | SQL: {sql} | Time: {elapsed:.2f}s | Rows: {result_count}")

        results.append({
            "id": tc["id"],
            "question": tc["question"],
            "category": tc["category"],
            "expected": tc["expected_behavior"],
            "outcome": outcome,
            "generated_sql": sql,
            "row_count": result_count,
            "latency_seconds": round(elapsed, 3),
            "error": error
        })

    report_path = os.path.join(os.path.dirname(__file__), "baseline_results.json")
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved baseline benchmark results to {report_path}")

if __name__ == "__main__":
    run_baseline_test()
