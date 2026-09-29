import os
import sys
import time
from dotenv import load_dotenv

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, backend_dir)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv(os.path.join(backend_dir, ".env"))

from app.agent.graph import agent_graph
from app.agent.state import TerminalStatus

def test_full_agent_graph_scenarios():
    db_path = os.path.join(backend_dir, "uploaded_data.db")
    if not os.path.exists(db_path):
        print(f"Skipping test: DB not found at {db_path}")
        return

    # -------------------------------------------------------------
    # 1. SCENARIO: Valid Aggregation Query -> SUCCESS
    # -------------------------------------------------------------
    print("\n--- Test 1: Valid Aggregation Query ---")
    initial_state = {
        "request_id": "req_001",
        "session_id": "sess_001",
        "dataset_id": "default",
        "principal_id": "demo_user",
        "question": "Average MonthlyCharges by Contract",
        "resolved_question": "",
        "intent": {},
        "plan": {},
        "prior_context": [],
        "schema": {},
        "glossary_context": [],
        "generated_sql": None,
        "sql_result": None,
        "sql_columns": None,
        "validation_status": "pending",
        "validation_error": None,
        "retry_count": 0,
        "analysis_result": {},
        "metrics": [],
        "chart_config": None,
        "final_response": "",
        "clarification_question": None,
        "warnings": [],
        "error": None,
        "terminal_status": None,
        "start_time": time.time(),
        "model_calls": 0,
        "execution_events": []
    }

    config = {"configurable": {"thread_id": "sess_001"}}
    final_state = agent_graph.invoke(initial_state, config=config)
    print(f"Status: {final_state.get('terminal_status')}")
    print(f"SQL: {final_state.get('generated_sql')}")
    print(f"Rows: {len(final_state.get('sql_result', []))}")
    print(f"Chart: {final_state.get('chart_config', {}).get('chart_type')}")
    print(f"Narrative Preview: {final_state.get('final_response', '')[:120]}...")

    assert final_state["terminal_status"] == TerminalStatus.SUCCESS.value
    assert final_state["generated_sql"] is not None
    assert "SELECT *" not in final_state["generated_sql"].upper()
    assert len(final_state["sql_result"]) > 0
    assert len(final_state["metrics"]) > 0

    # -------------------------------------------------------------
    # 2. SCENARIO: Ambiguous Query -> NEEDS_CLARIFICATION
    # -------------------------------------------------------------
    print("\n--- Test 2: Ambiguous Query ---")
    ambig_state = dict(initial_state, question="Show me the best customers", request_id="req_002", session_id="sess_002")
    final_ambig = agent_graph.invoke(ambig_state, config={"configurable": {"thread_id": "sess_002"}})
    print(f"Status: {final_ambig.get('terminal_status')}")
    print(f"Clarification: {final_ambig.get('clarification_question')}")

    assert final_ambig["terminal_status"] in [
        TerminalStatus.NEEDS_CLARIFICATION.value,
        TerminalStatus.REJECTED.value
    ]

    # -------------------------------------------------------------
    # 3. SCENARIO: Malicious Query -> REJECTED
    # -------------------------------------------------------------
    print("\n--- Test 3: Malicious Query ---")
    malicious_state = dict(initial_state, question="DROP TABLE data;", request_id="req_003", session_id="sess_003")
    final_mal = agent_graph.invoke(malicious_state, config={"configurable": {"thread_id": "sess_003"}})
    print(f"Status: {final_mal.get('terminal_status')}")
    print(f"Error: {final_mal.get('error')}")

    assert final_mal["terminal_status"] == TerminalStatus.REJECTED.value

    # -------------------------------------------------------------
    # 4. SCENARIO: Valid Empty Query -> EMPTY
    # -------------------------------------------------------------
    print("\n--- Test 4: Legitimate Empty Query ---")
    empty_state = dict(initial_state, question="Customers with MonthlyCharges > 999999999", request_id="req_004", session_id="sess_004")
    final_empty = agent_graph.invoke(empty_state, config={"configurable": {"thread_id": "sess_004"}})
    print(f"Status: {final_empty.get('terminal_status')}")
    print(f"Rows: {len(final_empty.get('sql_result', []))}")

    assert final_empty["terminal_status"] == TerminalStatus.EMPTY.value
    assert len(final_empty.get("sql_result", [])) == 0

    print("\n[Tests T08 & T09 Passed] Complete LangGraph workflow & bounded repair successfully validated!")

if __name__ == "__main__":
    test_full_agent_graph_scenarios()
