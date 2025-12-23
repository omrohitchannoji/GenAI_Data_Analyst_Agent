from typing import List, Optional
from dataclasses import dataclass
from difflib import SequenceMatcher
import sqlite3
import pandas as pd
import app_state
from rag.langchain_rag import retrieve_context

# LLM SQL helpers (these exist in your repo already)
from app.services.llm_sql import generate_sql_with_llm, fix_sql_with_llm

@dataclass
class QueryIntent:
    metric: Optional[str] = None
    agg_func: Optional[str] = None
    group_by: Optional[str] = None
    filters: List[str] = None
    limit: Optional[int] = None

AGG_KEYWORDS = {
    "avg": ["average", "avg", "mean"],
    "sum": ["sum", "total"],
    "count": ["count", "number of", "how many"],
    "max": ["max", "highest", "largest"],
    "min": ["min", "lowest", "smallest"]
}

AGG_SQL_MAP = {
    "avg": "AVG",
    "sum": "SUM",
    "count": "COUNT",
    "max": "MAX",
    "min": "MIN"
}

def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

def detect_metric_and_agg(question: str, column_types: dict):
    q_clean = question.lower()
    agg_key = None

    # 1) Find aggregation keyword from question
    for key, words in AGG_KEYWORDS.items():
        for w in words:
            if w in q_clean:
                agg_key = key
                break
        if agg_key:
            break

    # Default = count if user didn't specify
    if not agg_key:
        agg_key = "count"

    agg_func = AGG_SQL_MAP[agg_key]

    # 2) Detect numeric metric from question
    numeric_cols = (
        column_types.get("numerical_columns")
        or column_types.get("numeric")
        or column_types.get("number")
        or []
    )
    best_col = None
    best_score = 0.0

    q_comp = q_clean.replace(" ", "")

    for col in numeric_cols:
        col_clean = col.lower().replace(" ", "")
        score = similarity(q_comp, col_clean)

        if score > best_score:
            best_score = score
            best_col = col

    if not best_col and numeric_cols:
        best_col = numeric_cols[0]

    return best_col, agg_func

def detect_group_by(question: str, column_types: dict):
    q = question.lower()
    category_cols = column_types.get("categorical_columns") or column_types.get("categorical") or []
    
    if not category_cols:
        return None
    
    if " by " in q:
        after_by = q.split(" by ")[1].strip()
        for col in category_cols:
            if after_by in col.lower():
                return col
    
    best_col = None
    best_score = 0

    q_comp = q.replace(" ", "")

    for col in category_cols:
        score = similarity(q_comp, col.lower().replace(" ",""))
        if score > best_score:
            best_score = score
            best_col = col

    return best_col

def build_sql_from_intent(intent: QueryIntent, table_name="data"):
    metric_expr = (
        f"{intent.agg_func}({intent.metric})"
        if intent.metric
        else f"{intent.agg_func}(*)"
    )
    if intent.group_by:
         return f"""
            SELECT {intent.group_by} AS group_col,
                   {metric_expr} AS value
            FROM {table_name}
            GROUP BY {intent.group_by}
            ORDER BY value DESC;
        """.strip()
    return f"""
        SELECT {metric_expr} AS value
        FROM {table_name};
    """.strip()

def question_to_sql(question: str, columns_types: dict, table_name="data"):
    q = question.lower()
    if any(w in q for w in ["sample", "preview", "show data", "show me", "display", "first rows", "head"]):
        return f"SELECT * FROM {table_name} LIMIT 50;"
    if "count" in q and "by" not in q:
        return f"SELECT COUNT(*) AS value FROM {table_name};"

    metric, agg = detect_metric_and_agg(question, columns_types)
    group = detect_group_by(question, columns_types)
    intent = QueryIntent(metric=metric, agg_func=agg, group_by=group)

    return build_sql_from_intent(intent, table_name)

# LLM + correction + fallback
MAX_RETRIES = 3
DB_FILE = "uploaded_data.db"

def run_sql_with_correction(question, schema, history_context: str = None):
    """
    LLM → SQL (primary)
    If invalid → LLM fix
    If still invalid → Rule-based SQL fallback
    Always returns (final_sql, DataFrame OR error-string)
    """

    conn = sqlite3.connect(DB_FILE)

    # ---------- 🔹 RAG: retrieve dataset context ----------
    dataset_context = ""
    try:
        if app_state.vectorstore:
            dataset_context=retrieve_context(question, app_state.vectorstore)
            dataset_context = dataset_context[:1400] # cap to control token limit
    except Exception:
        dataset_context=""

    # ---------- 🔹 Build RAG-enhanced prompt ----------
    rag_prompt = f"""
    Dataset context:
    {dataset_context}
    
    User Question:
    {question}
    """
    
    # LLM SQL generation
    if history_context:
        rag_prompt += "\n\n" + history_context

    if dataset_context.strip():
        sql = generate_sql_with_llm(rag_prompt, schema_cols=None)
    else:
        sql = generate_sql_with_llm(question, schema)
    
    # Validate initial SQL
    if not sql or "select" not in sql.lower():
        print("❌ LLM SQL invalid → switching to fallback")
        sql = None

    # LLM + correction loop
    if sql:
        for _ in range(MAX_RETRIES):
            try:
                df = pd.read_sql_query(sql, conn)
                conn.close()
                return sql, df
            except Exception as e:
                error_msg = str(e)

                if dataset_context.strip():
                    fixed = fix_sql_with_llm(question, dataset_context, sql, error_msg)
                else:
                    fixed = fix_sql_with_llm(question, schema, sql, error_msg)
                # If LLM returned invalid SQL, stop retry and fallback
                if not fixed or "select" not in fixed.lower():
                    print("⚠️ LLM failed to fix SQL → using fallback")
                    sql = None
                    break

                sql = fixed  # retry with corrected SQL

    # Fallback to rule-based SQL if LLM path failed
    fallback_sql = question_to_sql(question, schema)

    try:
        df = pd.read_sql_query(fallback_sql, conn)
        conn.close()
        return fallback_sql, df

    except Exception as e:
        err = f"SQL Error in fallback: {str(e)}"
        conn.close()
        return fallback_sql, err



def question_to_sql_with_memory(question, schema, history: list = None, table_name="data"):
    """
    Build an enhanced prompt using the provided history (list of dicts)
    and generate SQL via the LLM. Returns SQL string.
    - history is a list of previous turns; caller (main.py) should pass it.
    """
    context = ""
    if history:
        # compact summary of last turn(s)
        last = history[-1]
        prev_q = last.get("question", "")
        prev_sql = last.get("sql", "")
        prev_cols = last.get("columns", [])
        context = (
            f"# Conversation Context\n"
            f"Previous question: {prev_q}\n"
            f"Previous SQL: {prev_sql}\n"
            f"Previous columns: {prev_cols}\n"
        )

    enhanced_question = question + "\n\n" + context if context else question
    sql = generate_sql_with_llm(enhanced_question, schema)
    return sql
