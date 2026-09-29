import os
import sys
from dotenv import load_dotenv

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, backend_dir)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv(os.path.join(backend_dir, ".env"))

from app.services.glossary import default_glossary
from app.agent.graph import run_agent_turn
from app.agent.state import TerminalStatus

def test_business_glossary():
    # 1. Scoped Glossary Search
    telco_matches = default_glossary.search_glossary("High Value Customer", dataset_id="default")
    assert len(telco_matches) > 0
    assert telco_matches[0]["term_id"] == "GLOSS-001"
    assert "TotalCharges" in telco_matches[0]["sql_expression"]

    # 2. Dataset Scoping Isolation
    sales_matches = default_glossary.search_glossary("High Margin Order", dataset_id="sales")
    assert len(sales_matches) > 0
    assert sales_matches[0]["term_id"] == "GLOSS-003"

    # Cross-dataset isolation: sales terms should not appear under default
    cross_check = default_glossary.search_glossary("High Margin Order", dataset_id="default")
    assert len(cross_check) == 0

    # 3. Agent Execution with Approved Business Glossary Definition
    print("\n--- Test 3: Agent using Approved Glossary Term ---")
    res = run_agent_turn(
        question="Count of High Value Customers",
        dataset_id="default",
        session_id="glossary_test_01"
    )
    print("Status:", res.get("terminal_status"))
    print("Generated SQL:", res.get("generated_sql"))
    print("Glossary Terms Used:", [g["term_name"] for g in res.get("glossary_context", [])])

    assert res["terminal_status"] == TerminalStatus.SUCCESS.value
    # The generated SQL must use the approved TotalCharges threshold
    assert "TotalCharges" in res["generated_sql"]
    assert "5000" in res["generated_sql"]

    # 4. Undefined Business Term -> Clarification (R06, R09)
    print("\n--- Test 4: Undefined Business Term -> Clarification ---")
    res_undefined = run_agent_turn(
        question="Total count of Platinum Tier Customers",
        dataset_id="default",
        session_id="glossary_test_02"
    )
    print("Status:", res_undefined.get("terminal_status"))
    print("Clarification Question:", res_undefined.get("clarification_question"))

    assert res_undefined["terminal_status"] in [
        TerminalStatus.NEEDS_CLARIFICATION.value,
        TerminalStatus.REJECTED.value
    ]

    print("\n[Test T11 Passed] Scoped business glossary RAG, approved definitions, and missing term clarification verified.")

if __name__ == "__main__":
    test_business_glossary()
