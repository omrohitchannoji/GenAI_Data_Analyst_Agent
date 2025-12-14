# backend/app/services/llm_charts.py

import os
import json
import requests

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"


def call_groq(prompt):
    """Safely call Groq for chart recommendation."""
    if not GROQ_API_KEY:
        print("⚠️ No GROQ_API_KEY → returning fallback chart.")
        return {"chart": "table", "x": None, "y": None, "group": None}

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 200,
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=20)
        print("🔥 CHART LLM RAW:", resp.text[:500])

        if resp.status_code != 200:
            return None

        data = resp.json()
        content = data["choices"][0]["message"]["content"]

        return content

    except Exception as e:
        print("❌ Chart LLM Error:", str(e))
        return None


def llm_chart_recommendation(question, df, schema):
    """Main function that returns a chart spec JSON."""
    preview = df.head(20).to_dict(orient="records")

    prompt = f"""
You are a data visualization expert.

Based on the QUESTION, COLUMN TYPES, and DATA PREVIEW,
output the BEST chart type in STRICT JSON.

Rules:
- Trend over time → line
- Category vs numeric → bar
- Distribution → histogram
- Relationship → scatter
- Single number → kpi
- Otherwise → table

Return EXACT JSON:
{{
  "chart": "...",
  "x": "...",
  "y": "...",
  "group": "..."
}}

QUESTION: {question}

COLUMNS: {list(df.columns)}
TYPES: {schema}
DATA SAMPLE: {preview}
"""

    raw = call_groq(prompt)

    # If LLM failed → fallback
    if not raw:
        return {"chart": "table", "x": None, "y": None, "group": None}

    # Try parse JSON
    try:
        parsed = json.loads(raw)
        return parsed
    except:
        print("⚠️ LLM chart JSON parse failed. Using fallback.")
        return {"chart": "table", "x": None, "y": None, "group": None}
