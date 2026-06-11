import json
import os

REFLECTION_FILE = "reflection_memory.json"


def load_reflections():
    if not os.path.exists(REFLECTION_FILE):
        return []
    try:
        with open(REFLECTION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_reflection(entry):
    data = load_reflections()
    data.append(entry)
    # Prune to last 200
    if len(data) > 200:
        data = data[-200:]
    with open(REFLECTION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def reflect_on_response(user_input: str, response: str) -> dict:
    issues = []
    positives = []

    r = response.lower()
    u = user_input.lower()
    words = response.split()

    # ── Negative patterns ──
    if len(words) < 5:
        issues.append("too_short")

    if len(words) > 200:
        issues.append("too_long")

    if any(p in r for p in ["i am an ai", "as an ai", "i'm an ai", "i am a language model"]):
        issues.append("generic_ai_phrase")

    if any(p in r for p in ["i don't know", "i cannot", "i'm unable", "i am unable"]):
        issues.append("low_confidence")

    if "error" in r or "exception" in r or "traceback" in r:
        issues.append("possible_failure")

    if r.startswith(("sure", "certainly", "of course", "absolutely", "happy to")):
        issues.append("filler_opener")

    if any(p in r for p in ["boss, boss", "boss. boss"]):
        issues.append("repetitive")

    # Check if response is off-topic (very different from input keywords)
    input_keywords = set(w for w in u.split() if len(w) > 4)
    response_keywords = set(w for w in r.split() if len(w) > 4)
    if input_keywords and len(input_keywords & response_keywords) == 0 and len(words) > 15:
        issues.append("possibly_off_topic")

    # ── Positive patterns ──
    if 10 <= len(words) <= 80:
        positives.append("good_length")

    if any(p in r for p in ["boss", "on it", "got it", "alright"]):
        positives.append("good_persona")

    if not any(p in r for p in ["sure,", "certainly,", "of course,"]):
        positives.append("no_filler_opener")

    # ── Score ──
    score = 10 - (len(issues) * 2) + len(positives)
    score = max(1, min(10, score))

    return {
        "input": user_input[:200],
        "response": response[:400],
        "issues": issues,
        "positives": positives,
        "score": score
    }


def get_reflection_bias() -> str:
    """Return prompt modifier based on recent response patterns."""
    reflections = load_reflections()
    if not reflections:
        return ""

    recent = reflections[-20:]
    issues = [i for r in recent for i in r.get("issues", [])]

    lines = []

    counts = {}
    for issue in issues:
        counts[issue] = counts.get(issue, 0) + 1

    if counts.get("too_short", 0) >= 3:
        lines.append("Give slightly more detailed responses — recent ones were too brief.")
    if counts.get("too_long", 0) >= 3:
        lines.append("Keep responses tighter — recent ones were too long.")
    if counts.get("generic_ai_phrase", 0) >= 2:
        lines.append("Avoid AI disclaimer phrases like 'as an AI'.")
    if counts.get("low_confidence", 0) >= 2:
        lines.append("Be more confident — avoid 'I don't know' or 'I cannot'.")
    if counts.get("filler_opener", 0) >= 2:
        lines.append("Never start with Sure/Certainly/Of course.")
    if counts.get("possibly_off_topic", 0) >= 2:
        lines.append("Stay focused on what the user actually asked.")

    return "\n".join(lines)


def get_reflection_stats() -> dict:
    """Return statistics about response quality over time."""
    reflections = load_reflections()
    if not reflections:
        return {"total": 0, "avg_score": 0, "top_issues": [], "recent_avg": 0}

    total = len(reflections)
    avg_score = sum(r.get("score", 5) for r in reflections) / total

    recent = reflections[-20:]
    recent_avg = sum(r.get("score", 5) for r in recent) / len(recent)

    issue_counts = {}
    for r in reflections:
        for issue in r.get("issues", []):
            issue_counts[issue] = issue_counts.get(issue, 0) + 1

    top_issues = sorted(issue_counts.items(), key=lambda x: -x[1])[:5]

    worst = sorted(reflections, key=lambda x: x.get("score", 5))[:5]

    return {
        "total": total,
        "avg_score": round(avg_score, 1),
        "recent_avg": round(recent_avg, 1),
        "top_issues": top_issues,
        "worst_responses": worst
    }
