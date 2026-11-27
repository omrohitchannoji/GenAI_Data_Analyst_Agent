import os
import re
import time
import pandas as pd
from typing import Dict, Any, List, Optional

from app.agent.state import (
    AgentState,
    TerminalStatus,
    FactMetric,
    ChartConfig,
    IntentPlanOutput,
    SQLGenerationOutput,
    RepairPlanOutput,
    InsightNarrativeOutput
)
from app.services.providers.groq_provider import GroqProvider
from app.services.query_executor import execute_query_safely
from app.core.schema_inspector import inspect_dataset_schema
from app.core.dataset_registry import default_registry
from app.services.insights_engine import summarize_grouped, suggest_chart
from app.services.glossary import default_glossary
from app.core.telemetry import append_duration_span, record_node_span

# ============================================================
# 1. SCOPE VALIDATION NODE
# ============================================================

def validate_scope_node(state: AgentState) -> Dict[str, Any]:
    start_t = time.time()
    dataset_id = state.get("dataset_id", "default")
    principal_id = state.get("principal_id", "demo_user")
    events = list(state.get("execution_events", []))

    events.append({
        "stage": "scope_validation",
        "timestamp": time.time(),
        "status": "started"
    })

    # Find dataset metadata or fallback to uploaded_data.db
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    default_db = os.path.join(backend_dir, "uploaded_data.db")

    ds_meta = default_registry.get_dataset(dataset_id, principal_id)
    if ds_meta:
        db_path = ds_meta["db_path"]
        table_name = ds_meta["table_name"]
    elif dataset_id == "default" and os.path.exists(default_db):
        db_path = default_db
        table_name = "data"
    else:
        events.append({"stage": "scope_validation", "timestamp": time.time(), "status": "unauthorized"})
        spans = record_node_span(state, "validate_scope", start_t, status="unauthorized", details={"dataset_id": dataset_id})
        return {
            "terminal_status": TerminalStatus.REJECTED.value,
            "error": f"Unauthorized or nonexistent dataset '{dataset_id}'.",
            "execution_events": events,
            "node_spans": spans
        }

    try:
        schema = inspect_dataset_schema(db_path, table_name)
        schema["db_path"] = db_path
    except Exception as e:
        events.append({"stage": "scope_validation", "timestamp": time.time(), "status": "schema_error"})
        spans = record_node_span(state, "validate_scope", start_t, status="error", details={"error": str(e)})
        return {
            "terminal_status": TerminalStatus.FAILED.value,
            "error": f"Failed to inspect dataset schema: {str(e)}",
            "execution_events": events,
            "node_spans": spans
        }

    events.append({"stage": "scope_validation", "timestamp": time.time(), "status": "authorized"})
    spans = record_node_span(state, "validate_scope", start_t, status="completed", details={"dataset_id": dataset_id, "table": table_name})
    return {
        "schema": schema,
        "execution_events": events,
        "node_spans": spans
    }

# ============================================================
# 2. ANALYZER & PLANNER NODE
# ============================================================

def analyzer_planner_node(state: AgentState, provider: Optional[Any] = None) -> Dict[str, Any]:
    if state.get("terminal_status") in [TerminalStatus.REJECTED.value, TerminalStatus.FAILED.value]:
        return {}

    start_t = time.time()
    events = list(state.get("execution_events", []))
    events.append({"stage": "analyzer_planner", "timestamp": time.time(), "status": "started"})

    provider = provider or GroqProvider()
    question = state.get("question", "")
    dataset_id = state.get("dataset_id", "default")
    schema = state.get("schema", {})
    prior_context = state.get("prior_context", [])

    # Search approved business glossary
    glossary_matches = default_glossary.search_glossary(question, dataset_id=dataset_id)

    prompt = f"""
Analyze this analytical user question and create an execution plan.

USER QUESTION: "{question}"

DATASET COLUMNS:
{schema.get('columns', [])}

COLUMN TYPES:
{schema.get('column_types', {})}

SAMPLE VALUES:
{schema.get('sample_values', {})}

PRIOR CONTEXT (Follow-ups):
{prior_context}

APPROVED BUSINESS DEFINITIONS:
{glossary_matches}

INSTRUCTIONS:
1. FOLLOW-UP RESOLUTION:
   - Check if PRIOR CONTEXT contains previous turns and executed SQL.
   - If the user question is a follow-up or filter modification (e.g. "Only for SeniorCitizen = 1", "Now filter by 2025", "Break down by region"), you MUST carry over the metric, aggregation, and grouping from PRIOR CONTEXT and apply the new filter or dimension!
   - Follow-up questions are NOT ambiguous if PRIOR CONTEXT provides the metric and dimension.
2. BUSINESS GLOSSARY:
   - If the user mentions a business term (e.g. "High Value Customer", "Churn Risk Customer") that matches an approved definition, use that definition's SQL expression in your plan!
   - If a business term has NO approved definition and cannot be determined from schema, mark is_ambiguous=True and ask for the definition.
3. AMBIGUITY:
   - If and only if the question cannot be resolved even with PRIOR CONTEXT or GLOSSARY, set is_ambiguous=True and provide a specific clarification_question.
4. UNSUPPORTED ACTIONS:
   - If the question requests data modifications (delete, drop, update) or non-analytical actions, set intent_type="unsupported".
5. RESOLVED QUESTION:
   - Combine the current question, prior context, and glossary terms into a complete, self-contained resolved_question.
"""
    try:
        result = provider.generate_structured(IntentPlanOutput, prompt)
        plan: IntentPlanOutput = result.data
        usage = getattr(result, "usage", None)
        model = getattr(result, "model", None)

        if plan.is_ambiguous:
            events.append({"stage": "analyzer_planner", "timestamp": time.time(), "status": "needs_clarification"})
            spans = record_node_span(state, "analyzer_planner", start_t, status="needs_clarification", usage=usage, model=model)
            return {
                "terminal_status": TerminalStatus.NEEDS_CLARIFICATION.value,
                "clarification_question": plan.clarification_question,
                "final_response": plan.clarification_question or "Could you clarify your analytical question?",
                "model_calls": state.get("model_calls", 0) + 1,
                "execution_events": events,
                "node_spans": spans
            }

        if plan.intent_type == "unsupported":
            events.append({"stage": "analyzer_planner", "timestamp": time.time(), "status": "unsupported"})
            spans = record_node_span(state, "analyzer_planner", start_t, status="unsupported", usage=usage, model=model)
            return {
                "terminal_status": TerminalStatus.REJECTED.value,
                "error": "The requested question is not a supported analytical operation.",
                "final_response": "The requested question is not a supported analytical operation.",
                "model_calls": state.get("model_calls", 0) + 1,
                "execution_events": events,
                "node_spans": spans
            }

        events.append({"stage": "analyzer_planner", "timestamp": time.time(), "status": "planned"})
        spans = record_node_span(state, "analyzer_planner", start_t, status="completed", usage=usage, model=model, details={"intent_type": plan.intent_type})
        return {
            "resolved_question": plan.resolved_question,
            "intent": {"intent_type": plan.intent_type},
            "plan": plan.model_dump(),
            "glossary_context": glossary_matches,
            "model_calls": state.get("model_calls", 0) + 1,
            "execution_events": events,
            "node_spans": spans
        }

    except Exception as e:
        events.append({"stage": "analyzer_planner", "timestamp": time.time(), "status": "error", "error": str(e)})
        spans = record_node_span(state, "analyzer_planner", start_t, status="error", model=getattr(provider, "model", None), details={"error": str(e)})
        return {
            "terminal_status": TerminalStatus.FAILED.value,
            "error": f"Failed during intent analysis: {str(e)}",
            "model_calls": state.get("model_calls", 0) + 1,
            "execution_events": events,
            "node_spans": spans
        }

# ============================================================
# 3. SQL GENERATOR NODE
# ============================================================

def sql_generator_node(state: AgentState, provider: Optional[Any] = None) -> Dict[str, Any]:
    if state.get("terminal_status") is not None:
        return {}

    start_t = time.time()
    events = list(state.get("execution_events", []))
    events.append({"stage": "sql_generator", "timestamp": time.time(), "status": "started"})

    provider = provider or GroqProvider()
    schema = state.get("schema", {})
    plan = state.get("plan", {})
    resolved_q = state.get("resolved_question", state.get("question", ""))
    glossary_context = state.get("glossary_context", [])
    table_name = schema.get("table_name", "data")

    prompt = f"""
Generate a strict SQLite SELECT query for the user question.

TABLE: {table_name}
COLUMNS: {schema.get('columns', [])}
COLUMN TYPES: {schema.get('column_types', {})}
SAMPLE VALUES: {schema.get('sample_values', {})}

QUESTION: "{resolved_q}"
PLAN: {plan}
APPROVED BUSINESS GLOSSARY EXPRESSIONS:
{glossary_context}

CRITICAL RULES:
1. ONLY return a single read-only SQLite SELECT statement.
2. NEVER use projection wildcards (SELECT * is STRICTLY FORBIDDEN). Always specify explicit columns or aggregates.
3. COUNT(*) is permitted only as an aggregate count.
4. If grouping is requested, ALWAYS include the group column in both SELECT and GROUP BY.
5. Column names must match the schema exactly.
6. If an approved business glossary definition applies, use its exact SQL expression!
7. Order results logically (e.g. ORDER BY metric DESC).
8. Return ONLY valid JSON with field "sql".
"""
    try:
        result = provider.generate_structured(SQLGenerationOutput, prompt)
        sql_out: SQLGenerationOutput = result.data
        usage = getattr(result, "usage", None)
        model = getattr(result, "model", None)

        events.append({"stage": "sql_generator", "timestamp": time.time(), "status": "sql_generated", "sql": sql_out.sql})
        spans = record_node_span(state, "sql_generator", start_t, status="completed", usage=usage, model=model, details={"sql": sql_out.sql})
        return {
            "generated_sql": sql_out.sql.strip(),
            "model_calls": state.get("model_calls", 0) + 1,
            "execution_events": events,
            "node_spans": spans
        }
    except Exception as e:
        events.append({"stage": "sql_generator", "timestamp": time.time(), "status": "error", "error": str(e)})
        spans = record_node_span(state, "sql_generator", start_t, status="error", model=getattr(provider, "model", None), details={"error": str(e)})
        return {
            "terminal_status": TerminalStatus.FAILED.value,
            "error": f"SQL generation failed: {str(e)}",
            "model_calls": state.get("model_calls", 0) + 1,
            "execution_events": events,
            "node_spans": spans
        }

# ============================================================
# 4. SQL VALIDATOR & EXECUTOR NODE
# ============================================================

def sql_validator_executor_node(state: AgentState) -> Dict[str, Any]:
    if state.get("terminal_status") is not None:
        return {}

    start_t = time.time()
    events = list(state.get("execution_events", []))
    events.append({"stage": "sql_execution", "timestamp": time.time(), "status": "started"})

    schema = state.get("schema", {})
    table_name = schema.get("table_name", "data")
    sql = state.get("generated_sql", "")

    # Locate database path
    db_path = schema.get("db_path")
    if not db_path:
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        db_path = os.path.join(backend_dir, "uploaded_data.db")

    # Execute with safety checks
    exec_res = execute_query_safely(
        db_path=db_path,
        sql=sql,
        allowed_tables=[table_name]
    )
    child_timing = exec_res.get("_telemetry", {})

    def with_sql_child_spans(parent_spans):
        append_duration_span(parent_spans, "validator", child_timing.get("validator_seconds"),
                             status="accepted" if not exec_res.get("is_security_violation") else "rejected")
        append_duration_span(parent_spans, "executor", child_timing.get("executor_seconds"),
                             status="success" if exec_res.get("success") else "error")
        return parent_spans

    if exec_res.get("is_security_violation"):
        events.append({"stage": "sql_execution", "timestamp": time.time(), "status": "rejected", "reason": exec_res["error"]})
        spans = with_sql_child_spans(record_node_span(state, "sql_validator_executor", start_t, status="rejected", details={"error": exec_res["error"]}))
        return {
            "terminal_status": TerminalStatus.REJECTED.value,
            "validation_status": "rejected",
            "error": exec_res["error"],
            "final_response": f"Query Rejected: {exec_res['error']}",
            "execution_events": events,
            "node_spans": spans
        }

    if not exec_res["success"]:
        events.append({"stage": "sql_execution", "timestamp": time.time(), "status": "error", "error": exec_res["error"]})
        spans = with_sql_child_spans(record_node_span(state, "sql_validator_executor", start_t, status="recoverable_error", details={"error": exec_res["error"]}))
        return {
            "validation_status": "recoverable_error",
            "validation_error": exec_res["error"],
            "execution_events": events,
            "node_spans": spans
        }

    if exec_res["is_empty"]:
        events.append({"stage": "sql_execution", "timestamp": time.time(), "status": "empty"})
        spans = with_sql_child_spans(record_node_span(state, "sql_validator_executor", start_t, status="empty"))
        return {
            "terminal_status": TerminalStatus.EMPTY.value,
            "validation_status": "empty",
            "sql_result": [],
            "sql_columns": exec_res["columns"],
            "final_response": "The query executed successfully, but no records matched the criteria. (Filters were not relaxed).",
            "execution_events": events,
            "node_spans": spans
        }

    warnings = list(state.get("warnings", []))
    is_truncated = exec_res.get("is_truncated", False)
    if is_truncated:
        warnings.append(f"Result set truncated to {exec_res.get('row_count')} rows (display limit exceeded).")

    events.append({"stage": "sql_execution", "timestamp": time.time(), "status": "success", "rows": exec_res["row_count"]})
    spans = with_sql_child_spans(record_node_span(state, "sql_validator_executor", start_t, status="valid", details={"row_count": exec_res["row_count"]}))
    return {
        "validation_status": "valid",
        "sql_result": exec_res["rows"],
        "sql_columns": exec_res["columns"],
        "is_truncated": is_truncated,
        "warnings": warnings,
        "execution_events": events,
        "node_spans": spans
    }

# ============================================================
# 5. REPAIR NODE
# ============================================================

def repair_node(state: AgentState, provider: Optional[Any] = None) -> Dict[str, Any]:
    start_t = time.time()
    events = list(state.get("execution_events", []))
    retry_count = state.get("retry_count", 0) + 1
    events.append({"stage": "repair", "timestamp": time.time(), "attempt": retry_count, "status": "started"})

    provider = provider or GroqProvider()
    schema = state.get("schema", {})
    failed_sql = state.get("generated_sql", "")
    error_msg = state.get("validation_error", "Unknown execution error")
    question = state.get("resolved_question", state.get("question", ""))
    table_name = schema.get("table_name", "data")

    prompt = f"""
A SQL query failed during execution. Diagnose the error and produce a corrected SQLite SELECT query.

ORIGINAL QUESTION: "{question}"
FAILED SQL: "{failed_sql}"
ERROR MESSAGE: "{error_msg}"

TABLE: {table_name}
COLUMNS: {schema.get('columns', [])}
COLUMN TYPES: {schema.get('column_types', {})}

CRITICAL RULES:
1. Fix column typos, missing GROUP BY columns, or syntax errors.
2. NEVER use SELECT *. Specify explicit columns.
3. Return ONLY a single read-only SELECT query.
"""
    try:
        result = provider.generate_structured(RepairPlanOutput, prompt)
        repair_out: RepairPlanOutput = result.data
        usage = getattr(result, "usage", None)
        model = getattr(result, "model", None)

        events.append({"stage": "repair", "timestamp": time.time(), "attempt": retry_count, "status": "repaired", "sql": repair_out.repaired_sql})
        spans = record_node_span(state, "repair", start_t, status="repaired", usage=usage, model=model, details={"attempt": retry_count, "sql": repair_out.repaired_sql})
        return {
            "generated_sql": repair_out.repaired_sql.strip(),
            "retry_count": retry_count,
            "validation_status": "repaired",
            "model_calls": state.get("model_calls", 0) + 1,
            "execution_events": events,
            "node_spans": spans
        }
    except Exception as e:
        events.append({"stage": "repair", "timestamp": time.time(), "attempt": retry_count, "status": "error", "error": str(e)})
        spans = record_node_span(state, "repair", start_t, status="error", model=getattr(provider, "model", None), details={"attempt": retry_count, "error": str(e)})
        return {
            "terminal_status": TerminalStatus.FAILED.value,
            "error": f"Repair formulation failed: {str(e)}",
            "retry_count": retry_count,
            "model_calls": state.get("model_calls", 0) + 1,
            "execution_events": events,
            "node_spans": spans
        }

# ============================================================
# 6. ANALYTICS & INSIGHTS NODE
# ============================================================

def analytics_insights_node(state: AgentState) -> Dict[str, Any]:
    start_t = time.time()
    events = list(state.get("execution_events", []))
    events.append({"stage": "analytics_insights", "timestamp": time.time(), "status": "started"})

    rows = state.get("sql_result", [])
    if not rows:
        spans = record_node_span(state, "analytics_insights", start_t, status="empty")
        return {"terminal_status": TerminalStatus.EMPTY.value, "node_spans": spans}

    df = pd.DataFrame(rows)
    metrics: List[Dict[str, Any]] = []
    chart_config: Dict[str, Any] = {}
    analysis_result: Dict[str, Any] = {}

    warnings = list(state.get("warnings", []))
    if state.get("is_truncated"):
        warnings.append("Computed statistics reflect a truncated result set (1,000 row cap). Complete dataset aggregations should use SQL aggregate functions.")

    try:
        # Determine chart type deterministically
        chart_type = suggest_chart(df)

        if df.shape[1] == 1 and len(df) == 1:
            # True scalar metric
            val = df.iloc[0, 0]
            col_name = df.columns[0]
            try:
                numeric_val = float(val)
                val_formatted = int(numeric_val) if numeric_val.is_integer() else round(numeric_val, 2)
            except (ValueError, TypeError):
                val_formatted = str(val)

            metrics.append({
                "fact_id": "F1",
                "metric_name": col_name,
                "value": val_formatted,
                "scope": "scalar"
            })
            chart_config = {
                "chart_type": "kpi",
                "x": None,
                "y": col_name,
                "title": f"Summary: {col_name}"
            }
        elif df.shape[1] == 1 and len(df) > 1:
            # Multirow single-column series / distribution (Issue 3 fix)
            col_name = df.columns[0]
            s = df[col_name]
            numeric_s = pd.to_numeric(s, errors="coerce")

            metrics.append({
                "fact_id": "F1",
                "metric_name": f"total_{col_name}_count",
                "value": len(df),
                "scope": col_name
            })
            if numeric_s.notna().sum() > 0:
                mean_val = float(numeric_s.dropna().mean())
                min_val = float(numeric_s.dropna().min())
                max_val = float(numeric_s.dropna().max())
                metrics.append({
                    "fact_id": "F2",
                    "metric_name": f"average_{col_name}",
                    "value": round(mean_val, 2),
                    "scope": col_name
                })
                metrics.append({
                    "fact_id": "F3",
                    "metric_name": f"range_{col_name}",
                    "value": f"{round(min_val, 2)} - {round(max_val, 2)}",
                    "scope": col_name
                })
            else:
                sample_items = [str(x) for x in s.dropna().unique()[:5]]
                metrics.append({
                    "fact_id": "F2",
                    "metric_name": "distinct_count",
                    "value": len(s.unique()),
                    "scope": col_name
                })
                metrics.append({
                    "fact_id": "F3",
                    "metric_name": "sample_values",
                    "value": ", ".join(sample_items),
                    "scope": col_name
                })
            chart_config = {
                "chart_type": "table",
                "x": None,
                "y": col_name,
                "title": f"Values of {col_name}"
            }
        else:
            # Grouped analytics
            summary = summarize_grouped(df.copy())
            analysis_result = summary

            if summary.get("top"):
                metrics.append({
                    "fact_id": "F1",
                    "metric_name": "top_group",
                    "value": f"{summary['top'][0].get(summary['group_column'])} ({round(summary['top'][0].get(summary['value_column'], 0), 2)})",
                    "scope": summary.get("group_column")
                })
            if summary.get("mean") is not None:
                metrics.append({
                    "fact_id": "F2",
                    "metric_name": "group_average",
                    "value": round(summary["mean"], 2),
                    "scope": summary.get("group_column")
                })
            if summary.get("percent_difference_top_vs_median") is not None:
                metrics.append({
                    "fact_id": "F3",
                    "metric_name": "top_vs_median_percent_diff",
                    "value": f"{round(summary['percent_difference_top_vs_median'], 1)}%",
                    "scope": summary.get("group_column")
                })

            x_col = summary.get("group_column", df.columns[0])
            y_col = summary.get("value_column", df.columns[-1])
            chart_config = {
                "chart_type": chart_type,
                "x": x_col,
                "y": y_col,
                "title": f"{y_col} by {x_col}"
            }

        events.append({"stage": "analytics_insights", "timestamp": time.time(), "status": "completed"})
        spans = record_node_span(state, "analytics_insights", start_t, status="completed", details={"metric_count": len(metrics)})
        return {
            "analysis_result": analysis_result,
            "metrics": metrics,
            "chart_config": chart_config,
            "warnings": warnings,
            "execution_events": events,
            "node_spans": spans
        }

    except Exception as e:
        events.append({"stage": "analytics_insights", "timestamp": time.time(), "status": "error", "error": str(e)})
        spans = record_node_span(state, "analytics_insights", start_t, status="error", details={"error": str(e)})
        return {
            "analysis_result": {"error": str(e)},
            "metrics": [],
            "chart_config": {"chart_type": "table"},
            "execution_events": events,
            "node_spans": spans
        }

# ============================================================
# 7. NARRATIVE EXPLAINER NODE
# ============================================================

def narrative_explainer_node(state: AgentState, provider: Optional[Any] = None) -> Dict[str, Any]:
    start_t = time.time()
    events = list(state.get("execution_events", []))
    events.append({"stage": "narrative_explainer", "timestamp": time.time(), "status": "started"})

    provider = provider or GroqProvider()
    question = state.get("resolved_question", state.get("question", ""))
    sql = state.get("generated_sql", "")
    metrics = state.get("metrics", [])
    analysis = state.get("analysis_result", {})

    prompt = f"""
Write an executive consulting summary answering the user question based strictly on verified analytical facts.

QUESTION: "{question}"
SQL USED: "{sql}"
COMPUTED FACTS:
{metrics}
ANALYSIS DETAILS:
{analysis}

RULES:
1. Executive summary must be 1-2 concise, professional sentences.
2. Key observations must directly cite the computed metrics (no hallucinations).
3. Recommendation must be 1 actionable business insight.
"""
    try:
        result = provider.generate_structured(InsightNarrativeOutput, prompt)
        narrative: InsightNarrativeOutput = result.data
        usage = getattr(result, "usage", None)
        model = getattr(result, "model", None)

        # R11 Fact Grounding Check: Validate fact IDs & numerical claims (Issue 2 fix)
        valid_fact_ids = {m["fact_id"] for m in metrics}
        warnings = list(state.get("warnings", []))
        fact_bullets = "\n".join(f"- **{m['metric_name']}**: {m['value']}" for m in metrics) if metrics else "- No numeric aggregates available."

        # Check 1: Fact ID subset validation
        unverified_fact_ids = bool(narrative.fact_ids_used and not set(narrative.fact_ids_used).issubset(valid_fact_ids))

        # Check 2: Numerical claims validation against computed metrics & analysis
        combined_text = f"{narrative.executive_summary} {' '.join(narrative.key_observations)}"
        claimed_numbers = [float(n) for n in re.findall(r"\b\d+(?:\.\d+)?\b", combined_text)]

        allowed_numbers = set()
        for m in metrics:
            for n in re.findall(r"\b\d+(?:\.\d+)?\b", str(m.get("value", ""))):
                allowed_numbers.add(round(float(n), 2))
        for k, v in analysis.items():
            if isinstance(v, (int, float)):
                allowed_numbers.add(round(float(v), 2))
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        for sub_v in item.values():
                            if isinstance(sub_v, (int, float)):
                                allowed_numbers.add(round(float(sub_v), 2))

        context_nums = set(re.findall(r"\b\d+(?:\.\d+)?\b", f"{question} {sql}"))
        has_hallucinated_num = False
        for c_num in claimed_numbers:
            rounded_c = round(c_num, 2)
            # Ignore trivial structural counters or numbers present in question/sql context
            if str(int(c_num)) in context_nums or str(c_num) in context_nums or c_num in [0.0, 1.0, 2.0, 3.0]:
                continue
            if not any(abs(rounded_c - a) < 0.05 or (a != 0 and abs(rounded_c - a) / abs(a) < 0.02) for a in allowed_numbers):
                has_hallucinated_num = True
                warnings.append(f"Unverified numeric claim '{c_num}' detected in model narrative; reverting to deterministic facts.")
                break

        if unverified_fact_ids or has_hallucinated_num:
            if unverified_fact_ids:
                warnings.append("Unverified fact reference detected in model narrative; reverting to deterministic facts.")
            final_text = (
                f"**Executive Summary:** {narrative.executive_summary}\n\n"
                f"**Verified Analytical Facts (Deterministic Grounding):**\n{fact_bullets}\n\n"
                f"**Recommendation:** {narrative.recommendation}"
            )
        else:
            final_text = (
                f"**Executive Summary:** {narrative.executive_summary}\n\n"
                f"**Verified Facts (Pandas Grounded):**\n{fact_bullets}\n\n"
                f"**Key Observations:**\n" + "\n".join(f"- {o}" for o in narrative.key_observations) + "\n\n"
                f"**Recommendation:** {narrative.recommendation}"
            )

        events.append({"stage": "narrative_explainer", "timestamp": time.time(), "status": "completed"})
        spans = record_node_span(state, "narrative_explainer", start_t, status="completed", usage=usage, model=model)
        return {
            "terminal_status": TerminalStatus.SUCCESS.value,
            "final_response": final_text,
            "warnings": warnings,
            "model_calls": state.get("model_calls", 0) + 1,
            "execution_events": events,
            "node_spans": spans
        }
    except Exception as e:
        # Fallback to deterministic summary if LLM narrative fails
        fact_bullets = "\n".join(f"- {m['metric_name']}: {m['value']}" for m in metrics) if metrics else "No numeric aggregates available."
        fallback_text = (
            f"**Verified Analytical Summary:**\n{fact_bullets}\n\n"
            f"(Generated via deterministic fallback due to narrative parsing limit)."
        )
        events.append({"stage": "narrative_explainer", "timestamp": time.time(), "status": "fallback", "error": str(e)})
        spans = record_node_span(state, "narrative_explainer", start_t, status="fallback", model=getattr(provider, "model", None), details={"error": str(e)})
        return {
            "terminal_status": TerminalStatus.SUCCESS.value,
            "final_response": fallback_text,
            "warnings": state.get("warnings", []) + [f"Narrative generation fallback used: {str(e)}"],
            "model_calls": state.get("model_calls", 0) + 1,
            "execution_events": events,
            "node_spans": spans
        }

# ============================================================
# 8. FAIL NODE
# ============================================================

def fail_node(state: AgentState) -> Dict[str, Any]:
    start_t = time.time()
    events = list(state.get("execution_events", []))
    err = state.get("validation_error") or state.get("error") or "Analysis failed after exceeding repair attempt budget."
    events.append({"stage": "failure", "timestamp": time.time(), "status": "failed", "error": err})
    spans = record_node_span(state, "fail", start_t, status="failed", details={"error": err})

    return {
        "terminal_status": TerminalStatus.FAILED.value,
        "error": err,
        "final_response": f"Analysis Failed: {err}",
        "execution_events": events,
        "node_spans": spans
    }
