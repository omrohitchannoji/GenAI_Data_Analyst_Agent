import os
import sys
from dotenv import load_dotenv
from pydantic import BaseModel

# Ensure backend is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, backend_dir)

load_dotenv(os.path.join(backend_dir, ".env"))

from app.agent.state import (
    QueryRequest,
    QueryResponse,
    TerminalStatus,
    FactMetric,
    ChartConfig,
    QueryResult,
    IntentPlanOutput
)
from app.services.providers.groq_provider import GroqProvider

class MockTestSchema(BaseModel):
    category: str
    confidence_score: float

def test_pydantic_contracts_instantiation():
    req = QueryRequest(question="What is the average revenue?", dataset_id="ds_123")
    assert req.question == "What is the average revenue?"
    assert req.dataset_id == "ds_123"

    res = QueryResponse(
        request_id="req_001",
        session_id="sess_001",
        dataset_id="ds_123",
        status=TerminalStatus.SUCCESS,
        resolved_question="Average revenue calculation",
        metrics=[FactMetric(fact_id="F1", metric_name="avg_rev", value=125.5)],
        chart=ChartConfig(chart_type="bar", x="category", y="avg_rev")
    )
    assert res.status == TerminalStatus.SUCCESS
    assert len(res.metrics) == 1
    assert res.chart.chart_type == "bar"

def test_groq_structured_generation():
    provider = GroqProvider()
    prompt = "Classify this question: 'What is the average revenue by region?' Return category 'aggregation' and confidence_score 0.95."
    result = provider.generate_structured(MockTestSchema, prompt)

    assert result is not None
    assert isinstance(result.data, MockTestSchema)
    assert result.data.category.lower() == "aggregation"
    assert result.data.confidence_score > 0.0
    assert result.provider == "groq"
    assert result.latency_seconds > 0.0
    assert "total_tokens" in result.usage
    print(f"\n[Test T04 Passed] Structured output: {result.data}, Tokens: {result.usage['total_tokens']}, Latency: {result.latency_seconds}s")

if __name__ == "__main__":
    test_pydantic_contracts_instantiation()
    test_groq_structured_generation()
    print("All T04 tests passed successfully!")
