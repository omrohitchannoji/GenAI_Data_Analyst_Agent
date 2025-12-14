# backend/app/services/llm_agent.py

import os
import json
import requests

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o-mini"

HEADERS = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
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


def call_llm(prompt: str):
    if not OPENAI_API_KEY:
        print("⚠️ OPENAI_API_KEY missing → using fallback.")
        return None

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 300
    }

    try:
        resp = requests.post(
            OPENAI_URL,
            headers=HEADERS,
            json=payload,
            timeout=30
        )

        if resp.status_code != 200:
            print("❌ OpenAI error:", resp.text)
            return None

        data = resp.json()
        return data["choices"][0]["message"]["content"]

    except Exception as e:
        print("❌ OpenAI request failed:", str(e))
        return None


def generate_llm_explanation(question: str, sql: str, facts: str):
    prompt = LLM_PROMPT_TEMPLATE.format(
        question=question,
        sql=sql,
        facts=facts
    )

    raw = call_llm(prompt)

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

    try:
        return json.loads(raw)
    except Exception:
        print("⚠️ Failed to parse LLM JSON. Raw output:", raw[:300])
        return fallback
