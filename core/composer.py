"""
Polish pass (Step G) — gated LLM rewrap for raw-dump replies only.

Most JARVIS agents already speak conversationally in their run() returns
("Task added, boss: buy milk"). The exception is long raw dumps — file lists,
scan reports, JSON blobs — that leak through without narration. Wrapping every
reply through an LLM doubles latency for no gain; this fires SELECTIVELY:

  fire iff  len(reply) > MIN_LEN  AND  flag(reply) != []

Heuristic flags mirror chat_review's: raw_path / json_dump / wall / generic.
Single qwen call ("narrate this in 2 sentences"); returns the original on any
LLM error so it can never block.

Off by default — set config.COMPOSER_ENABLED=True to turn on. Reads config
LIVE (not import-time) so toggles take effect without restart.
"""
import re

_PATH_ONLY = re.compile(r"^([A-Za-z]:[\\/]|/)[\w\-./\\ ]+\.(txt|md|pdf|json|csv|log|py|html|jpg|png|mp4)$")
_JSON_LIKE = re.compile(r"^\s*[\{\[]")
_GENERIC = {"done.", "done", "completed.", "completed", "ok.", "ok", "success.", "success"}

MIN_LEN = 600              # below this we leave the reply alone (already fits)
MAX_LEN = 5000             # above this we still try (tool dumps), but truncate input to the LLM


def _enabled() -> bool:
    try:
        import config
        return bool(getattr(config, "COMPOSER_ENABLED", False))
    except Exception:
        return False


def _flags(reply: str) -> list:
    r = (reply or "").strip()
    if not r:
        return []
    flags = []
    if _PATH_ONLY.match(r):
        flags.append("raw_path")
    if _JSON_LIKE.match(r):
        flags.append("json_dump")
    if r.lower() in _GENERIC:
        flags.append("generic")
    # wall = long + few sentence breaks (raw dump suspect)
    if len(r) > MIN_LEN:
        body = r[len(r) // 10: -len(r) // 10]
        if body.count(".") + body.count("!") + body.count("?") < 3:
            flags.append("wall")
    return flags


def should_polish(reply: str) -> bool:
    """Cheap gate — runs every reply. True only when LLM rewrap would help."""
    if not _enabled():
        return False
    if not reply or len(reply) < MIN_LEN:
        return False
    return bool(_flags(reply))


def polish_if_needed(reply: str, user_input: str = "") -> str:
    """If the gate fires, ask qwen to narrate the dump in 2 sentences.
    Returns the original on any LLM error — never blocks the chat path."""
    if not should_polish(reply):
        return reply
    try:
        from core.llm import ask_llm_fast
        snippet = reply if len(reply) <= MAX_LEN else reply[:MAX_LEN] + "\n…[truncated]"
        prompt = (
            "You narrate a tool's raw output back to the user like a polished assistant "
            "(Siri/Gemini tone). 1-2 sentences, conversational, mention the key result. "
            "Do NOT quote the raw output or paste paths/JSON verbatim. No preamble.\n\n"
            f"User asked: {user_input!r}\n"
            f"Tool returned (raw):\n{snippet}\n\n"
            "Your one-sentence reply:"
        )
        out = (ask_llm_fast(prompt, max_tokens=120) or "").strip()
        if not out:
            return reply
        # never make it worse — keep original if LLM dumps a wall back
        if len(out) > len(reply):
            return reply
        return out
    except Exception:
        return reply
