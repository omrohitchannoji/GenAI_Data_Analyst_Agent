import os
import sqlite3
from typing import Optional, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from app.agent.state import AgentState, TerminalStatus
from app.agent.nodes import (
    validate_scope_node,
    analyzer_planner_node,
    sql_generator_node,
    sql_validator_executor_node,
    repair_node,
    analytics_insights_node,
    narrative_explainer_node,
    fail_node
)

# ============================================================
# CONDITIONAL ROUTING FUNCTIONS
# ============================================================

def route_after_scope(state: AgentState) -> str:
    status = state.get("terminal_status")
    if status in [TerminalStatus.REJECTED.value, TerminalStatus.FAILED.value]:
        return END
    return "analyzer_planner"

def route_after_planner(state: AgentState) -> str:
    status = state.get("terminal_status")
    if status in [
        TerminalStatus.NEEDS_CLARIFICATION.value,
        TerminalStatus.REJECTED.value,
        TerminalStatus.FAILED.value
    ]:
        return END
    return "sql_generator"

def route_after_execution(state: AgentState) -> str:
    status = state.get("terminal_status")
    if status in [TerminalStatus.REJECTED.value, TerminalStatus.EMPTY.value]:
        return END

    val_status = state.get("validation_status")
    if val_status == "valid":
        return "analytics_insights"

    if val_status == "recoverable_error":
        # Hard bounded repair budget: max 2 repairs (3 total SQL attempts)
        retry_count = state.get("retry_count", 0)
        if retry_count < 2:
            return "repair"
        return "fail"

    return "fail"

def route_after_repair(state: AgentState) -> str:
    status = state.get("terminal_status")
    if status == TerminalStatus.FAILED.value:
        return "fail"
    return "sql_execution"

# ============================================================
# GRAPH COMPILATION WITH PERSISTENT CHECKPOINTER
# ============================================================

def get_default_checkpointer(db_path: Optional[str] = None):
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    checkpoints_path = db_path or os.path.join(backend_dir, "agent_checkpoints.db")
    conn = sqlite3.connect(checkpoints_path, check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver

def build_agent_graph(checkpointer: Optional[Any] = None):
    builder = StateGraph(AgentState)

    # 1. Add Nodes
    builder.add_node("validate_scope", validate_scope_node)
    builder.add_node("analyzer_planner", analyzer_planner_node)
    builder.add_node("sql_generator", sql_generator_node)
    builder.add_node("sql_execution", sql_validator_executor_node)
    builder.add_node("repair", repair_node)
    builder.add_node("analytics_insights", analytics_insights_node)
    builder.add_node("narrative_explainer", narrative_explainer_node)
    builder.add_node("fail", fail_node)

    # 2. Set Entry Point
    builder.set_entry_point("validate_scope")

    # 3. Add Edges & Conditional Branches
    builder.add_conditional_edges(
        "validate_scope",
        route_after_scope,
        {
            "analyzer_planner": "analyzer_planner",
            END: END
        }
    )

    builder.add_conditional_edges(
        "analyzer_planner",
        route_after_planner,
        {
            "sql_generator": "sql_generator",
            END: END
        }
    )

    builder.add_edge("sql_generator", "sql_execution")

    builder.add_conditional_edges(
        "sql_execution",
        route_after_execution,
        {
            "analytics_insights": "analytics_insights",
            "repair": "repair",
            "fail": "fail",
            END: END
        }
    )

    builder.add_conditional_edges(
        "repair",
        route_after_repair,
        {
            "sql_execution": "sql_execution",
            "fail": "fail"
        }
    )

    builder.add_edge("analytics_insights", "narrative_explainer")
    builder.add_edge("narrative_explainer", END)
    builder.add_edge("fail", END)

    if checkpointer is not None:
        return builder.compile(checkpointer=checkpointer)
    return builder.compile()

# Global checkpointer and compiled graph
default_checkpointer = get_default_checkpointer()
agent_graph = build_agent_graph(checkpointer=default_checkpointer)

# ============================================================
# MULTI-TURN INVOCATION WRAPPER (R02, R08, R13)
# ============================================================

def run_agent_turn(
    question: str,
    dataset_id: str = "default",
    session_id: str = "default",
    principal_id: str = "demo_user",
    graph: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Executes a conversational turn through the durable checkpointer.
    Manages session thread namespacing, dataset context switching,
    and history resolution.
    """
    active_graph = graph or agent_graph
    thread_id = f"{principal_id}:{session_id}"
    config = {"configurable": {"thread_id": thread_id}}

    # Retrieve current state from checkpointer if available
    try:
        prev_snapshot = active_graph.get_state(config)
        prev_state = prev_snapshot.values if prev_snapshot and prev_snapshot.values else {}
    except Exception:
        prev_state = {}

    prior_context = list(prev_state.get("prior_context", []))

    # Dataset switching check (R08: switching dataset starts fresh context)
    if prev_state.get("dataset_id") and prev_state.get("dataset_id") != dataset_id:
        prior_context = []
    elif prev_state.get("generated_sql") and prev_state.get("terminal_status") == TerminalStatus.SUCCESS.value:
        prior_context.append({
            "question": prev_state.get("question"),
            "resolved_question": prev_state.get("resolved_question"),
            "sql": prev_state.get("generated_sql"),
            "columns": prev_state.get("sql_columns")
        })
        # Retain only last 3 turns to bound history
        if len(prior_context) > 3:
            prior_context = prior_context[-3:]

    turn_state: AgentState = {
        "request_id": f"req_{int(sqlite3.time.time()*1000)}",
        "session_id": session_id,
        "dataset_id": dataset_id,
        "principal_id": principal_id,
        "question": question,
        "resolved_question": "",
        "intent": {},
        "plan": {},
        "prior_context": prior_context,
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
        "start_time": sqlite3.time.time(),
        "model_calls": 0,
        "execution_events": []
    }

    final_state = active_graph.invoke(turn_state, config=config)
    return final_state
