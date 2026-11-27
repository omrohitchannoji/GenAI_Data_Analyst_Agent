import os
import sys
import pytest

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, backend_dir)

from app.core.telemetry import (
    MODEL_PRICING_TABLE,
    calculate_model_cost_usd,
    sanitize_telemetry_payload,
    record_node_span,
    TraceContext
)


def test_pricing_table_exact_calculation():
    """Verify inference cost computation conforms strictly to the documented pricing table."""
    # openai/gpt-oss-120b: $0.15 / 1M prompt, $0.60 / 1M completion
    prompt_tokens = 1_000_000
    completion_tokens = 1_000_000
    cost = calculate_model_cost_usd("openai/gpt-oss-120b", prompt_tokens, completion_tokens, cached_prompt_tokens=0)
    assert cost == 0.75

    # Zero tokens = $0.00
    assert calculate_model_cost_usd("openai/gpt-oss-120b", 0, 0, cached_prompt_tokens=0) == 0.0

    # Small query token batch (e.g. 500 prompt, 150 completion)
    # (500 / 1e6) * 0.15 + (150 / 1e6) * 0.60 = 0.000075 + 0.00009 = 0.000165
    small_cost = calculate_model_cost_usd("openai/gpt-oss-120b", 500, 150, cached_prompt_tokens=0)
    assert small_cost == 0.000165

    cached_cost = calculate_model_cost_usd("openai/gpt-oss-120b", 1_000_000, 0, cached_prompt_tokens=1_000_000)
    assert cached_cost == 0.075


def test_privacy_redaction_by_default():
    """Verify that user questions, SQL text, and raw dataset rows are redacted from external logs."""
    raw_payload = {
        "node": "sql_execution",
        "question": "What is the churn rate for high-value customers?",
        "sql": "SELECT COUNT(*) FROM data WHERE MonthlyCharges > 100",
        "rows": [{"customerID": "7590-VHVEG", "MonthlyCharges": 110.5}],
        "non_sensitive_counter": 42
    }

    sanitized = sanitize_telemetry_payload(raw_payload, opt_in=False)
    assert sanitized["question"] == "[REDACTED_BY_POLICY]"
    assert sanitized["sql"] == "[REDACTED_BY_POLICY]"
    assert sanitized["rows"] == "[REDACTED_BY_POLICY]"
    assert sanitized["non_sensitive_counter"] == 42


def test_privacy_opt_in_preserves_content():
    """Verify that with opt-in explicitly true, raw content is preserved for debugging."""
    raw_payload = {
        "question": "Show churned users",
        "sql": "SELECT * FROM data"
    }
    sanitized = sanitize_telemetry_payload(raw_payload, opt_in=True)
    assert sanitized["question"] == "Show churned users"
    assert sanitized["sql"] == "SELECT * FROM data"


def test_record_node_span_accumulation():
    """Verify that record_node_span properly measures timing, token usage, and cost."""
    import time
    state = {"node_spans": []}
    start_time = time.time() - 0.05  # Simulate 50ms execution

    spans = record_node_span(
        state=state,
        node_name="sql_generator",
        start_time=start_time,
        status="completed",
        usage={"prompt_tokens": 800, "completion_tokens": 120, "total_tokens": 920, "cached_prompt_tokens": 0},
        model="openai/gpt-oss-120b",
        details={"model_attempt": 1}
    )

    assert len(spans) == 1
    span = spans[0]
    assert span["node_name"] == "sql_generator"
    assert span["status"] == "completed"
    assert span["latency_seconds"] >= 0.04
    assert span["prompt_tokens"] == 800
    assert span["completion_tokens"] == 120
    assert span["total_tokens"] == 920
    assert span["cost_usd"] > 0.0
