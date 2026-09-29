import os
import sys
import tempfile
from dotenv import load_dotenv

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, backend_dir)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv(os.path.join(backend_dir, ".env"))

from app.agent.graph import (
    run_agent_turn,
    build_agent_graph,
    get_default_checkpointer
)
from app.agent.state import TerminalStatus

def test_multi_turn_and_session_durability():
    db_path = os.path.join(backend_dir, "uploaded_data.db")
    if not os.path.exists(db_path):
        print("Skipping test: DB not found.")
        return

    # Use a isolated checkpoint database for testing
    temp_cp_db = os.path.join(tempfile.gettempdir(), "test_checkpoints.db")
    if os.path.exists(temp_cp_db):
        os.remove(temp_cp_db)

    test_saver = get_default_checkpointer(db_path=temp_cp_db)
    test_graph = build_agent_graph(checkpointer=test_saver)

    session_id = "test_sess_456"
    principal_id = "user_test"

    # ------------------------------------------------------------------
    # 1. TURN 1: Initial Question
    # ------------------------------------------------------------------
    print("\n--- Turn 1: Initial Question ---")
    t1_res = run_agent_turn(
        question="Average MonthlyCharges by Contract",
        dataset_id="default",
        session_id=session_id,
        principal_id=principal_id,
        graph=test_graph
    )
    print("Turn 1 Status:", t1_res.get("terminal_status"))
    print("Turn 1 SQL:", t1_res.get("generated_sql"))
    assert t1_res["terminal_status"] == TerminalStatus.SUCCESS.value
    assert "Contract" in t1_res["generated_sql"]

    # ------------------------------------------------------------------
    # 2. TURN 2: Scoped Follow-up (Retaining metric & grouping)
    # ------------------------------------------------------------------
    print("\n--- Turn 2: Follow-up Question ---")
    t2_res = run_agent_turn(
        question="Only for SeniorCitizen = 1",
        dataset_id="default",
        session_id=session_id,
        principal_id=principal_id,
        graph=test_graph
    )
    print("Turn 2 Status:", t2_res.get("terminal_status"))
    print("Turn 2 SQL:", t2_res.get("generated_sql"))
    print("Turn 2 Prior Context Count:", len(t2_res.get("prior_context", [])))

    assert t2_res["terminal_status"] == TerminalStatus.SUCCESS.value
    assert len(t2_res.get("prior_context", [])) > 0
    # The follow-up query should retain SeniorCitizen filter and Contract grouping or MonthlyCharges
    assert "SeniorCitizen" in t2_res["generated_sql"]

    # ------------------------------------------------------------------
    # 3. TURN 3: Persistence Across Restart (Reloading from SQLite)
    # ------------------------------------------------------------------
    print("\n--- Turn 3: Restart Persistence Check ---")
    reloaded_saver = get_default_checkpointer(db_path=temp_cp_db)
    reloaded_graph = build_agent_graph(checkpointer=reloaded_saver)

    thread_id = f"{principal_id}:{session_id}"
    snapshot = reloaded_graph.get_state({"configurable": {"thread_id": thread_id}})
    assert snapshot is not None
    assert snapshot.values.get("session_id") == session_id
    assert snapshot.values.get("terminal_status") == TerminalStatus.SUCCESS.value

    # ------------------------------------------------------------------
    # 4. TURN 4: Dataset Switch Resets Context (R08)
    # ------------------------------------------------------------------
    print("\n--- Turn 4: Dataset Context Isolation ---")
    t4_res = run_agent_turn(
        question="Total count",
        dataset_id="other_dataset_id",
        session_id=session_id,
        principal_id=principal_id,
        graph=test_graph
    )
    # Upon dataset switch, prior_context should have been cleared
    assert len(t4_res.get("prior_context", [])) == 0
    print("Turn 4 Prior Context after dataset switch:", t4_res.get("prior_context"))

    print("\n[Test T10 Passed] Multi-turn follow-ups, restart persistence, and dataset switching isolation verified.")

if __name__ == "__main__":
    test_multi_turn_and_session_durability()
