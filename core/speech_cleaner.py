import re


def clean_response(text: str) -> str:
    if not text:
        return ""

    cleaned = text

    # ---------------------------------
    # Remove robotic AI phrases
    # ---------------------------------
    bad_phrases = [
        "Sure, here's",
        "Here's what I found",
        "Let me break it down for you",
        "I apologize,",
        "As an AI,",
        "Certainly,",
        "Of course,"
    ]

    for phrase in bad_phrases:
        cleaned = cleaned.replace(
            phrase,
            ""
        )

    # ---------------------------------
    # Remove markdown
    # ---------------------------------
    cleaned = re.sub(
        r"\*\*(.*?)\*\*",
        r"\1",
        cleaned
    )

    cleaned = re.sub(
        r"\*(.*?)\*",
        r"\1",
        cleaned
    )

    cleaned = re.sub(
        r"`(.*?)`",
        r"\1",
        cleaned
    )

    # ---------------------------------
    # Remove emojis
    # ---------------------------------
    cleaned = re.sub(
        r"[^\x00-\x7F]+",
        "",
        cleaned
    )

    # ---------------------------------
    # Remove weird symbols
    # ---------------------------------
    cleaned = re.sub(
        r"[•►▶️★☆✓✔️🔥💀😊😂🙂😍😭🤖]",
        "",
        cleaned
    )

    # ---------------------------------
    # Clean whitespace
    # ---------------------------------
    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned
    )

    return cleaned.strip()