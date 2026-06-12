import re


def clean_response(text: str) -> str:
    if not text:
        return ""

    cleaned = text

    # ---------------------------------
    # Strip ANSI colour/escape codes (httpx/nmap/nuclei leak these into chat)
    # \x1b is ASCII, so it survives the non-ASCII filter below — kill it here.
    # ---------------------------------
    cleaned = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", cleaned)

    # ---------------------------------
    # Strip [AGENT] dump tags from compound/multi-step replies
    # e.g. "[ULTRON] ... [EDITH] ..." → drop the bracketed all-caps labels.
    # ---------------------------------
    cleaned = re.sub(r"\[[A-Z][A-Z0-9_ ]{1,20}\]\s*", "", cleaned)

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

    cleaned = cleaned.strip()

    # ---------------------------------
    # Length governor — no walls of text. Trim long replies at a sentence
    # boundary (full reports are saved to file separately).
    # ---------------------------------
    LIMIT = 1200
    if len(cleaned) > LIMIT:
        head = cleaned[:LIMIT]
        cut = max(head.rfind(". "), head.rfind("! "), head.rfind("? "))
        cleaned = (head[:cut + 1] if cut > 400 else head.rstrip()) + " Want the full details?"

    return cleaned