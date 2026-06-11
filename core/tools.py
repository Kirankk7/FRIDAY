from agents.vision.vision_agent import vision_agent
import platform
import requests

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


# 🔥 TOOL FUNCTIONS

def chat_tool(input_text):
    return call_llm(f"""
Respond like a natural human assistant.

Rules:
- No robotic phrases
- No "Here is" / "Sure"
- Keep it conversational
- Slightly friendly tone

User: {input_text}
""")


def news_search_tool(input_text):
    vision_agent.search(input_text)
    return "News data fetched."


def summarize_tool(_):
    return vision_agent.summarize()


def system_info_tool(_):
    return f"System: {platform.system()} {platform.version()}"


# 🔥 TOOL REGISTRY

TOOLS = {
    "chat": {
        "function": chat_tool,
        "description": "General conversation and explanations"
    },
    "news_search": {
        "function": news_search_tool,
        "description": "Search latest news"
    },
    "summarize": {
        "function": summarize_tool,
        "description": "Summarize fetched data"
    },
    "system_info": {
        "function": system_info_tool,
        "description": "Get system information"
    }
}