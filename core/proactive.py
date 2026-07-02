import random
import re
from core.profile import load_profile


def generate_proactive_suggestion(user_input: str, response: str, emotion: str):
    """An OCCASIONAL conversational nudge — never stapled onto every reply.

    Browser dogfood 2026-07-02: the old version substring-matched the input and
    appended to EVERY response, so 'base64 decode' (matches 'code') got
    'I can review or optimize that if needed.' and every news query got a
    tracking offer. Now: word-boundary matched, fires ~20% of the time, and
    never on a tool/command result (only genuinely conversational turns)."""
    text = (user_input or "").lower()
    resp = response or ""

    # Never nudge on a structured tool result (lists, decodes, prices, reports,
    # errors) — those are complete answers, not conversations.
    if any(sig in resp for sig in (":", "•", "1.", "REFUSED", "Decoded", "encoded",
                                   "$", "%", "CVE-", "Battery", "usage")):
        return None

    # Rare by design.
    if random.random() > 0.2:
        return None

    suggestions = []
    if emotion == "tired" or re.search(r"\btired\b", text):
        suggestions.append("You might want to take a short break.")
    if re.search(r"\bnot working\b|\berror\b", text):
        suggestions.append("Want me to help debug it step by step?")
    if re.search(r"\b(project|build)\b", text):
        suggestions.append("We can break this into steps if you want.")
    if re.search(r"\bcode\b", text):
        suggestions.append("I can review or optimize that if needed.")

    if not suggestions:
        return None
    if load_profile().get("style") == "direct":
        suggestions = [s.split(".")[0] for s in suggestions]
    return random.choice(suggestions)
