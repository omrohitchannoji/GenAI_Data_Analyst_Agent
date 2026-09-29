import os
import requests

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"

HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

SQL_PROMPT_TEMPLATE = """
You convert English questions into correct SQLITE SQL.

CRITICAL RULES:
- ALWAYS include the grouping column when GROUP BY is used.
- If the question says "by X", return: SELECT X AS group_col, <AGG>(metric) AS value FROM data GROUP BY X ORDER BY value DESC;
- The result must always have either:
    - one column: value
    - OR two columns: group_col, value
- Column names must match exactly.

Return ONLY the SQL.
No explanations.
No markdown.

Table: data
Columns: {columns}

Question: {question}
"""

def clean_sql(text: str) -> str:
    if not text:
        return ""

    text = text.strip()

    # remove ```sql fences
    if text.startswith("```"):
        text = text.replace("```sql", "").replace("```", "").strip()

    # clean leftover ``` anywhere
    text = text.replace("```", "").strip()

    # keep only starting from SELECT
    idx = text.lower().find("select")
    if idx != -1:
        text = text[idx:]

    # remove trailing semicolon (SQLite allows both but we clean it)
    if text.endswith(";"):
        text = text[:-1]

    return text.strip()


def call_llm_for_sql(question, schema_cols):
    if not GROQ_API_KEY:
        print(" LLM SQL: Missing GROQ_API_KEY → returning None")
        return None

    prompt = SQL_PROMPT_TEMPLATE.format(
        question=question,
        columns=", ".join(schema_cols)
    )

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 200
    }

    try:
        resp = requests.post(GROQ_URL, headers=HEADERS, json=payload, timeout=30)

        print(" LLM SQL Status:", resp.status_code)
        print(" LLM SQL Raw Response:", resp.text[:500])

        if resp.status_code != 200:
            return None

        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            return None

        return choices[0]["message"]["content"]

    except Exception as e:
        print(" LLM SQL Exception:", str(e))
        return None

def call_llm_extract_sql(prompt: str):
    """Call LLM and extract pure SQL text."""
    raw = call_llm_for_sql("IGNORE", [])  # temporary dummy (will override)
    # We call GROQ properly below:

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 200
    }

    try:
        resp = requests.post(GROQ_URL, headers=HEADERS, json=payload, timeout=30)
        if resp.status_code != 200:
            return None

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        if not content:
            return None

        # Clean markdown + extract SELECT block
        return clean_sql(content)

    except Exception as e:
        print(" SQL Extract Error:", str(e))
        return None

def generate_sql_with_llm(prompt: str, schema_cols=None):
    """
    If schema_cols is provided → schema-based SQL generation
    If schema_cols is None → prompt already contains RAG context
    """
    if schema_cols:
        raw = call_llm_for_sql(prompt, schema_cols)
    else:
        raw = call_llm_extract_sql(prompt)

    if not raw:
        return None

    sql = clean_sql(raw)

    if "select" not in sql.lower():
        print(" LLM SQL invalid (missing SELECT). SQL returned:", sql)
        return None

    return sql


def fix_sql_with_llm(question: str, schema: dict, broken_sql: str, error_msg: str):
    """
    Ask the LLM to FIX an invalid SQL query.
    Returns cleaned SQL string or fallback to the old SQL.
    """

    prompt = f"""
You are an expert SQL repair assistant.

A SQL query caused an error. Your job is to FIX the SQL.

# RULES
- Return ONLY valid SQL.
- Do NOT explain anything.
- No markdown.
- No backticks.
- Use ONLY columns mentioned in the context below::
{schema}

BROKEN SQL:
{broken_sql}

ERROR MESSAGE:
{error_msg}

Return ONLY corrected SQL.
"""

    sql = call_llm_extract_sql(prompt)

    if not sql or "select" not in sql.lower():
        print(" SQL Fix failed, using fallback SQL.")
        return broken_sql

    return sql.strip()