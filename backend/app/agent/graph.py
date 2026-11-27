import os
import sqlite3
import time
from typing import Optional, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.runnables import RunnableConfig

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
from app.core.telemetry import (
    get_langfuse_client,
    langfuse_observation,
)
import logging

logger = logging.getLogger(__name__)

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


def _instrument_graph_node(node_name: str, fn, observation_name: str, generation: bool = False):
    """Wrap a graph node while recording only status, timing, model, and usage metadata."""
    def wrapped(state: AgentState, config: RunnableConfig | None = None):
        config_values = (config or {}).get("configurable", {})
        started = time.perf_counter()
        model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b") if generation else None
        with langfuse_observation(
            observation_name,
            as_type="generation" if generation else "span",
            trace_id=config_values.get("_langfuse_trace_id"),
            parent_observation_id=config_values.get("_langfuse_parent_observation_id"),
            model=model,
        ) as observation:
            try:
                result = fn(state)
            except Exception as exc:
                if observation is not None:
                    try:
                        observation.update(
                            level="ERROR",
                            status_message=type(exc).__name__,
                            metadata={"status": "error", "latency_ms": round((time.perf_counter() - started) * 1000, 2)},
                        )
                    except Exception:
                        logger.debug("Could not update Langfuse node error metadata.")
                raise

            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            node_spans = result.get("node_spans", []) if isinstance(result, dict) else []
            local_span = next((span for span in reversed(node_spans) if span.get("node_name") == node_name), {})
            status = local_span.get("status", "completed")
            metadata = {"status": status, "latency_ms": elapsed_ms}
            usage_details = None
            actual_model = local_span.get("model") or model
            if local_span.get("total_tokens") is not None:
                usage_details = {
                    "input_tokens": local_span.get("prompt_tokens", 0),
                    "output_tokens": local_span.get("completion_tokens", 0),
                    "total_tokens": local_span.get("total_tokens", 0),
                }
                if local_span.get("cached_prompt_tokens") is not None:
                    usage_details["input_cached_tokens"] = local_span["cached_prompt_tokens"]
            if observation is not None:
                try:
                    updates = {"metadata": metadata}
                    if generation and actual_model:
                        updates["model"] = actual_model
                    if generation and usage_details is not None:
                        updates["usage_details"] = usage_details
                    observation.update(**updates)
                except Exception as exc:
                    logger.debug("Could not update Langfuse node metadata (%s).", type(exc).__name__)
            return result

    wrapped.__name__ = getattr(fn, "__name__", node_name)
    return wrapped

def build_agent_graph(checkpointer: Optional[Any] = None):
    builder = StateGraph(AgentState)

    # 1. Add Nodes
    builder.add_node("validate_scope", _instrument_graph_node("validate_scope", validate_scope_node, "validate_scope"))
    builder.add_node("analyzer_planner", _instrument_graph_node("analyzer_planner", analyzer_planner_node, "planner", generation=True))
    builder.add_node("sql_generator", _instrument_graph_node("sql_generator", sql_generator_node, "generator", generation=True))
    builder.add_node("sql_execution", _instrument_graph_node("sql_validator_executor", sql_validator_executor_node, "sql_validator_executor"))
    builder.add_node("repair", _instrument_graph_node("repair", repair_node, "repair", generation=True))
    builder.add_node("analytics_insights", _instrument_graph_node("analytics_insights", analytics_insights_node, "insights"))
    builder.add_node("narrative_explainer", _instrument_graph_node("narrative_explainer", narrative_explainer_node, "narrative", generation=True))
    builder.add_node("fail", _instrument_graph_node("fail", fail_node, "fail"))

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
    request_id = f"req_{time.time_ns()}"
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
        "request_id": request_id,
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
        "is_truncated": False,
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
        "execution_events": [],
        "node_spans": [],
        "telemetry": None
    }

    model_name = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
    client = get_langfuse_client()
    if client is None:
        final_state = active_graph.invoke(turn_state, config=config)
    else:
        with langfuse_observation(
            "agent_turn",
            metadata={"request_id": request_id, "model": model_name},
        ) as root_observation:
            if root_observation is None:
                final_state = active_graph.invoke(turn_state, config=config)
            else:
                trace_id = client.get_current_trace_id()
                root_span_id = client.get_current_observation_id()
                trace_config = {"configurable": {
                    "thread_id": thread_id,
                    "_langfuse_trace_id": trace_id,
                    "_langfuse_parent_observation_id": root_span_id,
                }}
                final_state = active_graph.invoke(turn_state, config=trace_config)
                node_spans = final_state.get("node_spans", [])
                llm_spans = [span for span in node_spans if span.get("model")]
                token_usage_available = bool(llm_spans) and all(span.get("total_tokens") is not None for span in llm_spans)
                metadata = {
                    "status": final_state.get("terminal_status"),
                    "model_calls": final_state.get("model_calls", 0),
                    "repair_count": final_state.get("retry_count", 0),
                    "node_count": len(node_spans),
                    "total_tokens": sum(span["total_tokens"] for span in llm_spans) if token_usage_available else None,
                }
                try:
                    root_observation.update(metadata=metadata)
                except Exception as exc:
                    logger.debug("Could not update Langfuse root metadata (%s).", type(exc).__name__)

    # Compute aggregate telemetry summary
    node_spans = final_state.get("node_spans", [])
    llm_spans = [span for span in node_spans if span.get("model")]
    usage_complete = bool(llm_spans) and all(span.get("total_tokens") is not None for span in llm_spans)
    total_prompt = sum(span.get("prompt_tokens", 0) or 0 for span in llm_spans) if usage_complete else None
    total_comp = sum(span.get("completion_tokens", 0) or 0 for span in llm_spans) if usage_complete else None
    total_tokens = sum(span.get("total_tokens", 0) or 0 for span in llm_spans) if usage_complete else None
    cost_available = bool(llm_spans) and all(span.get("cost_usd") is not None for span in llm_spans)
    total_cost = round(sum(span.get("cost_usd", 0) or 0 for span in llm_spans), 8) if cost_available else None
    total_lat = round(time.time() - turn_state["start_time"], 4)

    final_state["telemetry"] = {
        "request_id": turn_state["request_id"],
        "total_latency_seconds": total_lat,
        "model_name": model_name,
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_comp,
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost,
        "repair_count": final_state.get("retry_count", 0),
        "spans": node_spans,
        "per_node_latency": {s["node_name"]: s["latency_seconds"] for s in node_spans}
    }
    return final_state
