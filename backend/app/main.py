# backend/main.py
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import sqlite3
import os, json
from app.services.llm_agent import generate_llm_explanation
from app.services.query_engine import run_sql_with_correction, question_to_sql_with_memory
from app.core.utils import detect_column_types  # keep utils minimal: detect_column_types
from app.services.insights_engine import generate_insights_from_df
from app.services.llm_charts import llm_chart_recommendation
from app.services.llm_dataset_summary import generate_dataset_summary

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

@app.post("/upload_csv")
async def upload_csv(file: UploadFile = File(...)):
    """
    Upload a CSV, detect column types, save to sqlite, and return a dataset summary.
    """
    global stored_column_types
    if not file.filename.lower().endswith(".csv"):
        return {"error": "Please upload a CSV file"}

    try:
        # Read CSV (stream)
        df = pd.read_csv(file.file)

        # Detect and normalize column types using your utils
        raw_types = detect_column_types(df)
        stored_column_types = {
            "numerical_columns": raw_types.get("numeric", []),
            "categorical_columns": raw_types.get("categorical", []),
            "date_columns": raw_types.get("date", [])
        }

        # Save to sqlite
        conn = sqlite3.connect(DB_FILE)
        df.to_sql("data", conn, if_exists="replace", index=False)
        conn.close()

        # create a sample for llm dataset summary
        sample_rows = df.head(10).to_dict(orient="records")
        num_rows = len(df)

        # NOTE: generate_dataset_summary signature expects (column_types, preview_rows, num_rows)
        dataset_summary = generate_dataset_summary(
            stored_column_types,
            sample_rows,
            num_rows
        )

        return {
            "filename": file.filename,
            "columns": df.columns.tolist(),
            "preview": df.head(20).to_dict(orient="records"),
            "column_types": stored_column_types,
            "dataset_summary": dataset_summary
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
        llm_raw = generate_llm_explanation(
            question = request.question,
            sql = sql,
            facts = facts_text
        )

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
