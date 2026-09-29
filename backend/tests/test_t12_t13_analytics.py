import os
import sys
import pandas as pd
from dotenv import load_dotenv

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, backend_dir)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv(os.path.join(backend_dir, ".env"))

from app.services.insights_engine import summarize_grouped, suggest_chart, detect_anomalies
from app.agent.nodes import analytics_insights_node, narrative_explainer_node
from app.agent.state import TerminalStatus

def test_analytics_and_explainer():
    # -------------------------------------------------------------
    # 1. Deterministic Grouped Analytics (Pandas)
    # -------------------------------------------------------------
    df = pd.DataFrame({
        "Department": ["Sales", "Engineering", "Marketing", "HR"],
        "Salary": [50000, 120000, 60000, 45000]
    })
    summary = summarize_grouped(df)
    assert summary["group_column"] == "Department"
    assert summary["value_column"] == "Salary"
    assert summary["top"][0]["Department"] == "Engineering"
    assert summary["mean"] == 68750.0

    # -------------------------------------------------------------
    # 2. Deterministic Chart Mapping (R11)
    # -------------------------------------------------------------
    assert suggest_chart(df) == "bar"

    date_df = pd.DataFrame({
        "order_date": pd.to_datetime(["2025-01-01", "2025-02-01"]),
        "revenue": [100.0, 150.0]
    })
    assert suggest_chart(date_df) == "line"

    scalar_df = pd.DataFrame({"total": [42]})
    assert suggest_chart(scalar_df) == "kpi"

    # -------------------------------------------------------------
    # 3. Anomaly Detection (Z-Score > 2)
    # -------------------------------------------------------------
    normal_plus_outlier = pd.Series([10, 11, 10, 12, 10, 11, 10, 100])
    anomalies, mean, std = detect_anomalies(normal_plus_outlier)
    assert len(anomalies) == 1
    assert anomalies[0] == 7  # Index of 100

    # -------------------------------------------------------------
    # 4. Analytics Node Integration & Fact Extraction
    # -------------------------------------------------------------
    state = {
        "sql_result": df.to_dict(orient="records"),
        "sql_columns": list(df.columns),
        "execution_events": []
    }
    insights_state = analytics_insights_node(state)
    assert len(insights_state["metrics"]) > 0
    assert insights_state["chart_config"]["chart_type"] == "bar"

    # -------------------------------------------------------------
    # 5. Narrative Explainer Grounding & Fallback (R11)
    # -------------------------------------------------------------
    explainer_input = {
        "question": "Show average salary by department",
        "resolved_question": "Average salary by department",
        "generated_sql": "SELECT Department, AVG(Salary) FROM employees GROUP BY Department;",
        "metrics": insights_state["metrics"],
        "analysis_result": insights_state["analysis_result"],
        "execution_events": [],
        "warnings": []
    }
    narrative_state = narrative_explainer_node(explainer_input)
    assert narrative_state["terminal_status"] == TerminalStatus.SUCCESS.value
    assert len(narrative_state["final_response"]) > 0
    print("\nNarrative Explainer Output Preview:")
    print(narrative_state["final_response"][:200] + "...")

    print("\n[Tests T12 & T13 Passed] Deterministic Pandas metrics, chart mapping, anomaly detection, and grounded explainer verified.")

if __name__ == "__main__":
    test_analytics_and_explainer()
