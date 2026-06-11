import random
from core.profile import load_profile


def generate_proactive_suggestion(user_input: str, response: str, emotion: str):
    text = user_input.lower()
    profile = load_profile()

    suggestions = []

    # --- CONTEXT-BASED SUGGESTIONS ---

    if "tired" in text or emotion == "tired":
        suggestions.append("You might want to take a short break.")

    if "error" in text or "not working" in text:
        suggestions.append("Want me to help debug it step by step?")

    if "news" in text or "war" in text:
        suggestions.append("I can keep tracking updates for you if you want.")

    if "project" in text or "build" in text:
        suggestions.append("We can break this into steps if you want.")

    if "code" in text:
        suggestions.append("I can review or optimize that if needed.")

    # --- PROFILE-BASED FILTERING ---

    if profile.get("style") == "direct":
        # Keep suggestions shorter
        suggestions = [s.split(".")[0] for s in suggestions]

    if not suggestions:
        return None

    # Random but controlled
    return random.choice(suggestions)