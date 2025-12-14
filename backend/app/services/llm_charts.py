import json
from app.services.openai_client import call_openai


def call_groq(prompt):
    """
    SAFELY call OpenAI (replacing Groq) for chart recommendation.
    Function name kept same to avoid architecture changes.
    """

    raw = call_openai(
        prompt,
        temperature=0.1,
        max_tokens=150   # lower to avoid Render output/token limits
    )

    if not raw:
        return None

    return raw

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
    except Exception:
        print("⚠️ LLM chart JSON parse failed. Using fallback.")
        return {"chart": "table", "x": None, "y": None, "group": None}
