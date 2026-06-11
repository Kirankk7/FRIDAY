"""
Phase 40a — internal reasoning step (adapted from OpenJarvis think.py).

Gives agents an optional structured "scratchpad" before answering. Use for
multi-step problems where a quick plan improves the final answer. Opt-in per
call-site — not wired into every path (would add latency to simple commands).

    from core.think import think
    plan = think("user wants to scan then summarize results", context="...")
"""
from core.llm import ask_llm_fast

_THINK_PROMPT = """You are the internal reasoning step of an AI assistant.
Think through the problem briefly and privately. Do NOT answer the user.

Problem: {problem}
{context_block}
Produce 2-4 short reasoning steps (one per line, no preamble, no markdown):"""


def think(problem: str, context: str = "", max_tokens: int = 150) -> str:
    """Return a short structured reasoning scratchpad for a problem.
    Returns '' on failure — callers should treat reasoning as best-effort."""
    if not problem or not problem.strip():
        return ""
    context_block = f"Context:\n{context}\n" if context else ""
    prompt = _THINK_PROMPT.format(problem=problem.strip(), context_block=context_block)
    try:
        out = ask_llm_fast(prompt, max_tokens=max_tokens)
        return (out or "").strip()
    except Exception:
        return ""
