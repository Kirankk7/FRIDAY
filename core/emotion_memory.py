import json
import os

FILE = "emotion_memory.json"


def load_emotions():
    if not os.path.exists(FILE):
        return []

    with open(FILE, "r") as f:
        try:
            data = json.load(f)

            # [hot] FIX: ensure it's a list
            if isinstance(data, list):
                return data
            else:
                return []

        except:
            return []


def save_emotion(entry):
    data = load_emotions()

    data.append(entry)

    with open(FILE, "w") as f:
        json.dump(data, f, indent=2)


def detect_emotion(text: str) -> str:
    text = text.lower()

    if any(word in text for word in ["tired", "exhausted"]):
        return "tired"

    if any(word in text for word in ["angry", "frustrated"]):
        return "frustrated"

    if any(word in text for word in ["excited", "awesome"]):
        return "excited"

    return "neutral"