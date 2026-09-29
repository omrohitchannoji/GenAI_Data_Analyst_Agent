import os
import json
import requests
import time

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"

HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

SUMMARY_PROMPT = """
You are a senior data analyst.

You will receive:
- Column names + data types
- A preview of the dataset
- Row count

Your task:
Return STRICT JSON ONLY, matching this EXACT shape:

{
  "summary": "High-level overview of the dataset.",
  "issues": ["Potential data quality issues, missing values, skew, etc."],
  "recommendation": "One actionable recommendation to improve the dataset."
}

Rules:
- Do NOT include backticks.
- Do NOT add any text outside JSON.
- Be concise but useful.
"""


def call_llm(prompt):
    """Call Groq safely and return the assistant message content."""

    if not GROQ_API_KEY:
        print(" No GROQ_API_KEY → dataset summary will fallback.")
        return None

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 150
    }

    try:
        for attempt in range(2): #try atmost 2 times
            resp = requests.post(GROQ_URL, headers=HEADERS, json=payload, timeout=20)
            if resp.status_code == 429:
                print("Rate Limit Hit, Backing off ...")
                time.sleep(5)
                continue

            print("RAW SUMMARY RESPONSE", resp.text[:600])

        if resp.status_code != 200:
            return None
        
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content

    except Exception as e:
        print(" Dataset summary LLM error:", str(e))
        return None


def generate_dataset_summary(column_types, preview_rows, num_rows):
    """
    Main function that produces dataset-level summary JSON.
    """

    prompt = SUMMARY_PROMPT + f"""

COLUMNS + TYPES:
{column_types}

DATA PREVIEW (first rows):
{preview_rows}

TOTAL ROW COUNT:
{num_rows}
"""

    raw = call_llm(prompt)

    # fallback structure if LLM failed
    fallback = {
        "summary": "This dataset contains structured rows and columns suitable for analysis.",
        "issues": ["LLM could not evaluate dataset quality."],
        "recommendation": "Verify column types and handle missing values if present."
    }

    if not raw:
        return fallback

    # Parse JSON safely
    try:
        parsed = json.loads(raw)
        return parsed
    except Exception:
        print(" Dataset summary failed to parse JSON → using fallback.")
        return fallback