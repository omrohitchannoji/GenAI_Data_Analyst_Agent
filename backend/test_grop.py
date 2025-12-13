import os, requests, json

url = "https://api.groq.com/openai/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {os.environ.get('GROQ_API_KEY')}",
    "Content-Type": "application/json"
}

payload = {
    "model": "llama-3.1-8b-instant",
    "messages": [{"role": "user", "content": "hello from test"}],
    "temperature": 0.1,
    "max_tokens": 128
}

resp = requests.post(url, headers=headers, json=payload, timeout=30)

print("STATUS:", resp.status_code)
print("BODY (first 500 chars):")
print(resp.text[:500])

try:
    print("JSON KEYS:", resp.json().keys())
except Exception as e:
    print("JSON PARSE ERROR:", e)
