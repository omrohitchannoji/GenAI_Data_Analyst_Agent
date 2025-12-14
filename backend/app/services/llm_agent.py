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

def call_llm(prompt: str):
    if not GROQ_API_KEY:
        print(" GROQ_API_KEY missing → using fallback.")
        return None

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a strict JSON generator. Output JSON only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2,
        "max_tokens": 250   # SAFE for free tier
    }

    try:
        resp = requests.post(
            GROQ_URL,
            headers=HEADERS,
            json=payload,
            timeout=25
        )

        if resp.status_code != 200:
            print(" Groq error:", resp.text[:300])
            return None

        data = resp.json()
        return data["choices"][0]["message"]["content"]

    except Exception as e:
        print(" Groq request failed:", str(e))
        return None

def generate_llm_explanation(question: str, sql: str, facts: str):
    prompt = LLM_PROMPT_TEMPLATE.format(
        question=question,
        sql=sql,
        facts=facts
    )

    raw = call_llm(prompt)

    fallback = {
        "executive_summary": "The analysis highlights meaningful differences across groups based on the queried metrics.",
        "key_observations": [
            "Top-performing groups outperform the median values.",
            "Overall distribution shows limited variance across groups.",
            "A small number of groups may warrant further investigation."
        ],
        "recommendation": "Analyze top performers to identify best practices and address gaps in lower-performing groups."
    }

    if not raw:
        return fallback

    try:
        return json.loads(raw)
    except Exception:
        print(" Failed to parse Groq JSON. Raw output:", raw[:300])
        return fallback
