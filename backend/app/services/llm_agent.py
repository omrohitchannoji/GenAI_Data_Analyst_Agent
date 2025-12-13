# backend/app/services/llm_agent.py

import os
import json
import requests

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"

HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

LLM_PROMPT_TEMPLATE = """
You are a Senior Data Analyst at a top consulting firm (McKinsey / BCG / Deloitte).  
Your job is to produce a clear, highly professional analytical summary based strictly on the provided SQL results and facts.

You MUST return STRICT JSON with the following structure:

{
  "executive_summary": "...",
  "key_observations": ["...", "...", "..."],
  "recommendation": "..."
}

## WRITING RULES
- Use a polished consulting tone.
- Be concise but insightful.
- ALWAYS quantify insights when numbers are provided.
- Highlight ranking, top vs bottom performers, variance, anomalies.
- DO NOT guess or hallucinate. Base insights ONLY on provided facts.
- Executive summary: 2–3 sentences.
- Key observations: 3–5 bullet points.
- Recommendation: 1 strategic business action.

## INPUTS

Question:
{question}

SQL Used:
{sql}

Data Facts:
{facts}

Produce ONLY valid JSON. 
No markdown, no commentary, no extra text.
"""


def clean_llm_text(text: str):
    """Remove unwanted markdown fences or text."""
    if not text:
        return ""

    text = text.strip()
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    return text


def call_llm(prompt):
    """Send request to Groq and return raw content."""
    if not GROQ_API_KEY:
        print("⚠️ Missing GROQ_API_KEY → using fallback.")
        return None

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 350
    }

    try:
        resp = requests.post(GROQ_URL, headers=HEADERS, json=payload, timeout=20)
        print("🔥 RAW LLM EXPLANATION RESPONSE:", resp.text[:600])

        if resp.status_code != 200:
            return None

        data = resp.json()
        return data["choices"][0]["message"]["content"]

    except Exception as e:
        print("❌ LLM agent error:", str(e))
        return None


def generate_llm_explanation(question: str, sql: str, facts: str):
    """
    Main public function. Returns explanation JSON.
    """

    prompt = LLM_PROMPT_TEMPLATE + f"""

QUESTION:
{question}

SQL EXECUTED:
{sql}

FACT SUMMARY:
{facts}
"""

    raw = call_llm(prompt)

    # Fallback narrative (used if LLM fails or JSON is invalid)
    fallback = {
        "executive_summary": "The analysis reveals meaningful differences across groups with identifiable trends.",
        "key_observations": [
            "Top-performing groups outperform the median values.",
            "Overall distribution appears stable with limited variance.",
            "Minor anomalies or outliers may be worth further investigation."
        ],
        "recommendation": "Investigate top groups to identify best practices; focus interventions on lower-performing groups."
    }

    if not raw:
        return fallback

    text = clean_llm_text(raw)

    try:
        parsed = json.loads(text)
        return parsed
    except Exception:
        print("⚠️ Failed to parse explanation JSON → using fallback.")
        return fallback
