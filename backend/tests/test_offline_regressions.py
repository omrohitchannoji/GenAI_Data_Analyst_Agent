import os
import sys
import pytest
import pandas as pd
from typing import Dict, Any

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, backend_dir)

from app.agent.nodes import (
    analytics_insights_node,
    narrative_explainer_node,
    sql_validator_executor_node
)
from app.agent.state import TerminalStatus, InsightNarrativeOutput
from app.services.providers.base import LLMProvider, ProviderResult
from app.services.query_executor import execute_query_safely
from app.core.dataset_registry import default_registry, MAX_UPLOAD_SIZE_BYTES
from app.main import run_sql_query

class MockNarrativeProvider(LLMProvider):
    """Deterministic mock provider that returns a preset narrative without network calls."""
    def __init__(self, narrative_output: InsightNarrativeOutput):
        self.narrative_output = narrative_output

    def generate_structured(self, schema, prompt, system_prompt=None):
        return ProviderResult(
            data=self.narrative_output,
            raw_text="{}",
            provider="mock",
            model="mock_model",
            latency_seconds=0.01,
            usage={"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}
        )

    def generate_text(self, prompt, system_prompt=None):
        return ProviderResult(
            data="mock text",
            raw_text="mock text",
            provider="mock",
            model="mock_model",
            latency_seconds=0.01,
            usage={"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}
        )

# =========================================================================
# 1. ISSUE 2 TEST: Narrative Number Hallucination Detection
# =========================================================================
def test_narrative_hallucinated_number_detection():
    """Verify that claiming 999999 against a true metric of 10 triggers a grounding warning."""
    mock_hallucinated = InsightNarrativeOutput(
        executive_summary="The team achieved unprecedented growth.",
        key_observations=["Total active churners stood at 999999 customers."],
        recommendation="Maintain current strategies.",
        fact_ids_used=["F1"]
    )
    provider = MockNarrativeProvider(mock_hallucinated)

    state = {
        "question": "Count of churned customers",
        "generated_sql": "SELECT COUNT(*) FROM data WHERE Churn = 'Yes'",
        "metrics": [{"fact_id": "F1", "metric_name": "churn_count", "value": 10}],
        "analysis_result": {},
        "warnings": [],
        "execution_events": []
    }

    res = narrative_explainer_node(state, provider=provider)
    assert res["terminal_status"] == TerminalStatus.SUCCESS.value
    # Check that warning was appended for unverified number
    assert any("Unverified numeric claim" in w for w in res["warnings"])
    # Check that the hallucinated observation was replaced with verified facts
    assert "Verified Analytical Facts (Deterministic Grounding)" in res["final_response"]
    assert "churn_count" in res["final_response"] and "10" in res["final_response"]

def test_narrative_grounded_number_accepted():
    """Verify that citing true metric values passes with no hallucination warning."""
    mock_accurate = InsightNarrativeOutput(
        executive_summary="Churn rate remained stable at 10 customers.",
        key_observations=["Observed churn_count of 10 matches targets."],
        recommendation="Continue monitoring.",
        fact_ids_used=["F1"]
    )
    provider = MockNarrativeProvider(mock_accurate)

    state = {
        "question": "Count of churned customers",
        "generated_sql": "SELECT COUNT(*) FROM data WHERE Churn = 'Yes'",
        "metrics": [{"fact_id": "F1", "metric_name": "churn_count", "value": 10}],
        "analysis_result": {},
        "warnings": [],
        "execution_events": []
    }

    res = narrative_explainer_node(state, provider=provider)
    assert not any("Unverified numeric claim" in w for w in res["warnings"])
    assert "Verified Facts (Pandas Grounded)" in res["final_response"]

# =========================================================================
# 2. ISSUE 3 TEST: Multirow Single-Column Results vs True Scalars
# =========================================================================
def test_multirow_single_column_not_treated_as_scalar():
    """Verify that rows [10, 20, 30] produce series statistics, not just scalar 10."""
    state = {
        "sql_result": [{"MonthlyCharges": 10.0}, {"MonthlyCharges": 20.0}, {"MonthlyCharges": 30.0}],
        "sql_columns": ["MonthlyCharges"],
        "execution_events": [],
        "warnings": [],
        "is_truncated": False
    }

    res = analytics_insights_node(state)
    metrics = res["metrics"]
    fact_names = [m["metric_name"] for m in metrics]

    assert "total_MonthlyCharges_count" in fact_names
    assert "average_MonthlyCharges" in fact_names
    # Average of 10, 20, 30 is 20.0
    avg_metric = next(m for m in metrics if m["metric_name"] == "average_MonthlyCharges")
    assert avg_metric["value"] == 20.0
    # Chart should be table, NOT kpi
    assert res["chart_config"]["chart_type"] == "table"

def test_true_single_row_scalar():
    """Verify that a single-cell result [42] is correctly recognized as a scalar KPI."""
    state = {
        "sql_result": [{"total_count": 42}],
        "sql_columns": ["total_count"],
        "execution_events": [],
        "warnings": [],
        "is_truncated": False
    }

    res = analytics_insights_node(state)
    assert len(res["metrics"]) == 1
    assert res["metrics"][0]["scope"] == "scalar"
    assert res["metrics"][0]["value"] == 42
    assert res["chart_config"]["chart_type"] == "kpi"

# =========================================================================
# 3. ISSUE 4 TEST: Truncation Flag & Warning Preservation
# =========================================================================
def test_truncation_warning_propagation():
    """Verify that truncation metadata passes to state and triggers advisory warnings."""
    state = {
        "sql_result": [{"val": i} for i in range(100)],
        "sql_columns": ["val"],
        "execution_events": [],
        "warnings": [],
        "is_truncated": True
    }

    res = analytics_insights_node(state)
    assert any("truncated result set" in w for w in res["warnings"])

# =========================================================================
# 4. ISSUE 6 TEST: Legacy Endpoints Guarded with AST Security
# =========================================================================
def test_legacy_run_sql_blocks_stacked_and_ddl():
    """Verify that /run_sql executor rejects chained statements and DDL."""
    # Stacked statement
    res = run_sql_query("SELECT 1; DROP TABLE data;")
    assert isinstance(res, str)
    assert "Multiple statements detected" in res or "SQL Error" in res

    # DDL
    res_drop = run_sql_query("DROP TABLE data;")
    assert isinstance(res_drop, str)
    assert "read-only" in res_drop.lower() or "prohibited" in res_drop.lower() or "sql error" in res_drop.lower()

# =========================================================================
# 5. ISSUE 7 TEST: Upload Size Limit
# =========================================================================
def test_upload_size_limit_constant():
    """Verify MAX_UPLOAD_SIZE_BYTES is set to exactly 10 MiB."""
    assert MAX_UPLOAD_SIZE_BYTES == 10 * 1024 * 1024

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
