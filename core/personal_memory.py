import json
import os
import datetime

PERSONAL_FILE = "data/personal_memory.json"
os.makedirs("data", exist_ok=True)

# Keyword triggers per fact key — used for auto-recall injection
RECALL_TRIGGERS = {
    "weight":        ["weight", "weigh", "kg", "lbs", "fat", "diet", "fitness", "bmi", "gym", "calories"],
    "location":      ["dubai", "location", "city", "country", "live", "move", "timezone", "uae", "based"],
    "education":     ["msc", "master", "degree", "university", "study", "thesis", "course", "dissertation"],
    "certifications":["cert", "oscp", "ceh", "certification", "exam", "comptia", "cissp", "eWPT", "study for"],
    "career":        ["job", "work", "career", "pentester", "hacker", "security", "role", "company", "salary", "profession"],
    "investments":   ["invest", "stock", "crypto", "etf", "bitcoin", "portfolio", "money", "finance", "market", "trading"],
    "health":        ["lasik", "eyes", "vision", "health", "surgery", "medical", "doctor", "pain", "sleep"],
    "name":          ["name", "call me", "who am i"],
}


def _load() -> dict:
    if not os.path.exists(PERSONAL_FILE):
        return {}
    try:
        with open(PERSONAL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict):
    try:
        with open(PERSONAL_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[personal] Save error: {e}")


def set_fact(key: str, value: str):
    data = _load()
    data[key.lower().strip()] = {
        "value": value.strip(),
        "updated": datetime.datetime.now().strftime("%Y-%m-%d")
    }
    _save(data)


def get_fact(key: str):
    entry = _load().get(key.lower().strip())
    return entry["value"] if entry else None


def get_all() -> dict:
    return _load()


def format_all() -> str:
    data = _load()
    if not data:
        return "No personal facts stored yet, boss."
    lines = [f"{k}: {v['value']} (updated {v['updated']})" for k, v in data.items()]
    return "\n".join(lines)


def get_relevant_context(query: str) -> str:
    """Returns personal facts relevant to the query — injected into LLM prompt."""
    data = _load()
    if not data:
        return ""
    query_lower = query.lower()
    relevant = []
    for key, triggers in RECALL_TRIGGERS.items():
        if key in data and any(t in query_lower for t in triggers):
            relevant.append(f"{key}: {data[key]['value']}")
    if not relevant:
        return ""
    return "Personal context (use naturally):\n" + "\n".join(f"- {r}" for r in relevant)
