import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"


def call_llm(prompt):
    try:
        res = requests.post(
            OLLAMA_URL,
            json={
                "model": "mistral:7b",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 200
                }
            },
            timeout=30
        )
        return res.json().get("response", "").strip()
    except:
        return ""


def create_plan(user_input, context):
    prompt = f"""
You are a planning agent.

Conversation context:
{context}

Decide what to do.

Tools:
- chat
- news_search
- summarize
- system_info

Rules:
- Use context if relevant
- Keep steps minimal
- Prefer chat unless real-time info needed
- Return ONLY JSON

Format:
{{
  "steps": [
    {{"tool": "chat", "input": "text"}}
  ]
}}

User: {user_input}
"""

    raw = call_llm(prompt)

    try:
        return json.loads(raw)
    except:
        return {
            "steps": [
                {"tool": "chat", "input": user_input}
            ]
        }