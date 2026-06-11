import json
import os

PROFILE_FILE = "user_profile.json"


def load_profile():
    if not os.path.exists(PROFILE_FILE):
        return {
            "tone": "neutral",
            "verbosity": "medium",
            "style": "balanced",
            "interactions": 0
        }

    with open(PROFILE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_profile(profile):
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)


def update_profile(user_input: str, response: str):
    profile = load_profile()

    text = user_input.lower()

    # Tone detection
    if any(word in text for word in ["bro", "yaar", "dude", "lol"]):
        profile["tone"] = "casual"
    elif any(word in text for word in ["please", "could you", "kindly"]):
        profile["tone"] = "formal"

    # Verbosity detection
    if len(user_input.split()) < 4:
        profile["verbosity"] = "short"
    elif len(user_input.split()) > 15:
        profile["verbosity"] = "detailed"

    # Style detection
    if any(word in text for word in ["quick", "fast", "just tell"]):
        profile["style"] = "direct"
    elif any(word in text for word in ["explain", "detail", "why"]):
        profile["style"] = "explanatory"

    profile["interactions"] += 1

    save_profile(profile)

    return profile