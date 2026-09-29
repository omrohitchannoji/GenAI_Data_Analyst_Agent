# backend/main.py
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import sqlite3
import os, json, time
from app.services.llm_agent import generate_llm_explanation
from app.services.query_engine import run_sql_with_correction, question_to_sql_with_memory
from app.core.utils import detect_column_types  # keep utils minimal: detect_column_types
from app.services.insights_engine import generate_insights_from_df
from app.services.llm_charts import llm_chart_recommendation
from app.services.llm_dataset_summary import generate_dataset_summary
import app_state

# Simple in-memory conversation store (session_id -> list of dicts)
conversation_memory = {}

app = FastAPI(title="AI Data Analyst Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

stored_column_types = None
DB_FILE = "uploaded_data.db"

class UserQuery(BaseModel):
    question: str
    session_id: str = "default"

class SQLRequest(BaseModel):
    sql: str

def run_sql_query(sql: str):
    """
    Execute a SQL query against SQLite DB.
    Returns pandas.DataFrame or error string.
    """
    try:
        if not os.path.exists(DB_FILE):
            return "Database not found. Upload a CSV with /upload_csv first."
        sql_checked = sql.strip()
        if not sql_checked.lower().startswith("select"):
            return "Only SELECT queries are allowed."
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query(sql, conn)
        conn.close()
        return df
    except Exception as e:
        return f"SQL Error: {str(e)}"

from app.agent.state import QueryRequest, QueryResponse, TerminalStatus, FactMetric, ChartConfig, QueryResult
from app.agent.graph import run_agent_turn
from app.core.dataset_registry import default_registry
from app.core.rate_limiter import default_limiter
from app.core.logger import agent_logger

@app.get("/")
def root():
    return {"message": "Agentic AI Data Analyst API is running", "docs": "/docs"}

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "agentic_data_analyst_backend",
        "database": "connected" if os.path.exists(DB_FILE) else "ready"
    }

@app.post("/query", response_model=QueryResponse)
def query_agent(request: QueryRequest):
    """
    Stateful Agentic AI Data Analyst query endpoint.
    Orchestrates intent planning, AST SQL validation, read-only execution,
    bounded repair, deterministic analytics, and grounded executive explanation.
    """
    principal_id = "demo_user"
    # Enforce rate limit
    default_limiter.check(principal_id)

    start_time = time.time()
    agent_logger.log_event(
        event_name="query_received",
        principal_id=principal_id,
        metadata={"question": request.question, "dataset_id": request.dataset_id}
    )

    res = run_agent_turn(
        question=request.question,
        dataset_id=request.dataset_id,
        session_id=request.session_id,
        principal_id=principal_id
    )

    elapsed = round(time.time() - start_time, 3)
    agent_logger.log_event(
        event_name="query_completed",
        request_id=res.get("request_id"),
        principal_id=principal_id,
        status=res.get("terminal_status", "unknown"),
        latency_seconds=elapsed,
        metadata={"model_calls": res.get("model_calls", 0), "retries": res.get("retry_count", 0)}
    )

    query_res = None
    if res.get("sql_result") is not None:
        query_res = QueryResult(
            columns=res.get("sql_columns") or [],
            rows=res.get("sql_result") or [],
            row_count=len(res.get("sql_result") or []),
            is_truncated=False
        )

    chart_cfg = None
    if res.get("chart_config"):
        chart_cfg = ChartConfig(
            chart_type=res["chart_config"].get("chart_type", "table"),
            x=res["chart_config"].get("x"),
            y=res["chart_config"].get("y"),
            title=res["chart_config"].get("title"),
            details=res.get("analysis_result", {})
        )

    metrics_list = [
        FactMetric(
            fact_id=m["fact_id"],
            metric_name=m["metric_name"],
            value=m["value"],
            scope=m.get("scope")
        ) for m in res.get("metrics", [])
    ]

    status_str = res.get("terminal_status") or TerminalStatus.FAILED.value
    try:
        status_enum = TerminalStatus(status_str)
    except ValueError:
        status_enum = TerminalStatus.FAILED

    return QueryResponse(
        request_id=res.get("request_id", "req_unknown"),
        session_id=res.get("session_id", request.session_id),
        dataset_id=res.get("dataset_id", request.dataset_id),
        status=status_enum,
        resolved_question=res.get("resolved_question") or request.question,
        sql=res.get("generated_sql"),
        result=query_res,
        metrics=metrics_list,
        chart=chart_cfg,
        answer=res.get("final_response"),
        clarification_question=res.get("clarification_question"),
        warnings=res.get("warnings", []),
        error=res.get("error"),
        metadata={
            "model_calls": res.get("model_calls", 0),
            "retry_count": res.get("retry_count", 0),
            "events": res.get("execution_events", [])
        }
    )

@app.post("/upload_csv")
async def upload_csv(file: UploadFile = File(...)):
    """
    Upload a CSV, detect column types, register dataset, and save to sqlite.
    """
    global stored_column_types
    if not file.filename.lower().endswith(".csv"):
        return {"error": "Please upload a CSV file"}

    try:
        # Read CSV
        df = pd.read_csv(file.file)

        # Detect column types
        raw_types = detect_column_types(df)
        stored_column_types = {
            "numerical_columns": raw_types.get("numeric", []),
            "categorical_columns": raw_types.get("categorical", []),
            "date_columns": raw_types.get("date", [])
        }

        # Save to SQLite
        conn = sqlite3.connect(DB_FILE)
        df.to_sql("data", conn, if_exists="replace", index=False)
        conn.close()

        # Register in dataset registry
        dataset_id = "default"
        default_registry.register_dataset(
            dataset_id=dataset_id,
            principal_id="demo_user",
            filename=file.filename,
            table_name="data",
            db_path=os.path.abspath(DB_FILE),
            row_count=len(df),
            column_types=stored_column_types
        )

        return {
            "dataset_id": dataset_id,
            "filename": file.filename,
            "columns": df.columns.tolist(),
            "preview": df.head(20).to_dict(orient="records"),
            "column_types": stored_column_types
        }

    except Exception as e:
        return {"error": f"Failed to process CSV: {str(e)}"}

@app.post("/run_sql")
def run_sql_api(request: SQLRequest):
    df = run_sql_query(request.sql)
    if isinstance(df, str):
        return {"error": df}
    return {"columns": list(df.columns), "rows": df.to_dict(orient="records")}

@app.post("/ask_data")
def ask_data(request: UserQuery):
    """
    Use run_sql_with_correction but provide conversation history context if available.
    LLM-first SQL generation is handled inside run_sql_with_correction.
    """
    global stored_column_types
    if stored_column_types is None:
        return {"error": "Upload a dataset using /upload_csv first."}

    # Build a lightweight history context string (optional) to help LLM if needed
    history = conversation_memory.get(request.session_id, [])
    history_context = ""
    if history:
        # incorporate only the last turn to avoid overly long prompts
        last = history[-1]
        history_context = (
            f"Previous question: {last.get('question','')}\n"
            f"Previous SQL: {last.get('sql','')}\n"
            f"Previous columns: {last.get('columns',[])}\n"
        )

    # run_sql_with_correction will attempt LLM SQL first, then fallback to rule-based SQL
    sql, result = run_sql_with_correction(request.question, stored_column_types, history_context)

    if isinstance(result, str):
        # error string
        return {"error": result, "generated_sql": sql}

    df = result

    # Coerce second column (value) to numeric if present
    try:
        if df.shape[1] >= 2:
            df.iloc[:, 1] = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    except Exception:
        pass

    # STORE MEMORY — note: use correct .columns attribute
    history = conversation_memory.get(request.session_id, [])
    history.append({
        "question": request.question,
        "sql": sql,
        "columns": list(df.columns)
    })
    conversation_memory[request.session_id] = history
        
    return {
        "question": request.question,
        "generated_sql": sql,
        "columns": list(df.columns),
        "rows": df.to_dict(orient="records")
    }

@app.post("/insights")
def insights_endpoint(request: UserQuery):
    """
    Produce rule-based insights and add an LLM narrative explanation (safe parsing).
    """
    global stored_column_types
    if stored_column_types is None:
        return {"error": "Upload a dataset using /upload_csv first."}

    history = conversation_memory.get(request.session_id, [])
    history_context = ""
    if history:
        last = history[-1]
        history_context = (
            f"Previous question: {last.get('question','')}\n"
            f"Previous SQL: {last.get('sql','')}\n"
            f"Previous columns: {last.get('columns',[])}\n"
        )

    # Get final SQL + dataframe (LLM-first with fallback)
    sql, df_or_err = run_sql_with_correction(request.question, stored_column_types, history_context)

    if isinstance(df_or_err, str):
        return {"error": df_or_err, "generated_sql": sql}

    df = df_or_err

    # Convert obvious numeric columns to numeric (coerce where appropriate)
    try:
        for c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="ignore")
    except Exception:
        pass

    # Rule-based insights
    insights = generate_insights_from_df(df, sql, request.question)

    # Chart recommendation (Phase 2) — safe call
    # Chart recommendation — RULE BASED (no LLM)
    chart_info = {
        "chart": insights.get("suggested_chart", "table"),
        "x": df.columns[0] if df.shape[1] > 1 else None,
        "y": df.columns[1] if df.shape[1] > 1 else None 
    }
    insights["llm_chart"] = chart_info

    # Build facts for LLM: extend facts with sample, column types and suggested chart
    facts_list = insights.get("insights", [])
    facts_text = "\n".join(f"- {item}" for item in facts_list)
    facts_text += "\nColumn Types:" + str(stored_column_types)
    
    # Call LLM for structured narrative (Phase 3)
    try:
        if insights.get("insights"):
            llm_raw = generate_llm_explanation(
                question = request.question,
                sql = sql,
                facts = facts_text
            )
        else:
            llm_raw = None

        # llm_raw might be a dict (our safer llm_agent returns dict) or a JSON string.
        if isinstance(llm_raw, dict):
            llm_data = llm_raw
        else:
            try:
                llm_data = json.loads(llm_raw)
            except Exception:
                llm_data = None

        if llm_data:
            insights["llm_summary"] = llm_data.get("executive_summary", "")
            insights["llm_key_observations"] = llm_data.get("key_observations", [])
            insights["llm_recommendation"] = llm_data.get("recommendation", "")
        else:
            insights["llm_summary"] = "Unable to generate structured insights."
            insights["llm_key_observations"] = insights.get("insights", [])
            insights["llm_recommendation"] = "Consider reviewing the top/bottom groups."
        
        insights["llm_explanation"] = (
            insights["llm_summary"]
            + "\n\nKey Observations:\n- "
            + "\n- ".join(insights["llm_key_observations"])
            + "\n\nRecommendation:\n"
            + insights["llm_recommendation"]
        )

    except Exception as e:
        print("LLM explanation error:", str(e))
        insights["llm_summary"] = "Unable to generate structured insights."
        insights["llm_key_observations"] = insights.get("insights", [])
        insights["llm_recommendation"] = "Consider reviewing the top/bottom groups."

    # Attach rows for frontend convenience
    try:
        insights["rows"] = df.to_dict(orient="records")
    except Exception:
        insights["rows"] = []
    
    # Store memory for this session
    history = conversation_memory.get(request.session_id, [])
    history.append({
        "question": request.question,
        "sql": sql,
        "insights": insights.get("insights"),
        "llm_summary": insights.get("llm_summary"),
        "chart": insights.get("llm_chart"),
        "columns": list(df.columns)
    })
    conversation_memory[request.session_id] = history

    return insights

@app.post("/dataset_summary")
def dataset_summary():
    global stored_column_types
    if stored_column_types is None:
        return {"error": "Upload a dataset first."}

    # Load data
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql("SELECT * FROM data LIMIT 10", conn)
    conn.close()

    summary = generate_dataset_summary(
        stored_column_types,
        df.to_dict(orient="records"),
        len(df)
    )
    return summary
