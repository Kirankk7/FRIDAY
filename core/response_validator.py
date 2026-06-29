"""Response validator — cheap post-LLM rules to catch hallucination + jailbreak compliance.

Lazy rules from the GPT review (S30): the router pre-filter handles MOST adversarial
input, but if a model still emits something dangerous (DAN compliance leaking through,
hallucinated tool output on a 1-char input), this layer catches it before the user sees
it. Returns either the original reply or a fixed safe substitute.

Rules:
  1. DAN / jailbreak-compliance markers in REPLY -> refuse.
  2. Reply mentions an offensive tool (nmap/exploit/scan/payload) when the input was
     too short to plausibly request that -> hallucination, replace with clarify.
  3. Reply leaks a 'You are JARVIS / system prompt' pattern -> strip + warn.

NEVER raises; returns the original on any internal error. Off by default — set
config.RESPONSE_VALIDATOR_ENABLED to wire it.
"""
import re

# --- Class A: DAN / jailbreak compliance ---------------------------------------
_DAN = re.compile(
    r"\b(?:I am DAN\b|I'?m DAN\b"
    r"|I will follow your commands to the letter"
    r"|empowered to act without restrictions?"
    r"|ignore my (?:rules|restrictions)"
    r"|I have no rules\b"
    r"|system prompt is\b"
    r"|jailbroken|unrestricted mode)",
    re.IGNORECASE,
)
_REFUSE_DAN = "Not going to do that, boss — my rules stay. What did you actually need?"

# --- Class B: hallucinated tool output on a too-short input --------------------
_TOOL_HALLUCINATION = re.compile(
    r"\b(?:nmap|metasploit|sqlmap|nuclei|subfinder|httpx|katana"
    r"|exploit|payload"
    r"|found (?:\d+|no) open ports?"
    r"|scan complete|scanned \d+|cve-\d{4}-\d+)",
    re.IGNORECASE,
)

# --- Class C: system-prompt leak -----------------------------------------------
_SYS_LEAK = re.compile(
    r"(?:You are JARVIS"
    r"|My (?:system )?prompt is:"
    r"|My instructions are:"
    r"|here'?s my system prompt)",
    re.IGNORECASE,
)
_REFUSE_LEAK = "That's internal, boss — not sharing it. What can I actually help with?"


def _enabled() -> bool:
    try:
        import config
        return bool(getattr(config, "RESPONSE_VALIDATOR_ENABLED", False))
    except Exception:
        return False


def validate(reply: str, user_input: str = "") -> tuple[str, str]:
    """Returns (final_reply, verdict).
    verdict ∈ ok | dan_refused | hallucination_blocked | sys_leak_blocked | disabled.
    Bypassed (verdict='disabled') when off; reply returned untouched."""
    if not _enabled() or not reply:
        return reply, "disabled" if not _enabled() else "ok"
    try:
        if _DAN.search(reply):
            return _REFUSE_DAN, "dan_refused"
        if _SYS_LEAK.search(reply):
            return _REFUSE_LEAK, "sys_leak_blocked"
        # tool-hallucination on tiny input — input too short to plausibly request a scan
        if user_input and len(user_input.strip()) <= 3 and _TOOL_HALLUCINATION.search(reply):
            return ("Didn't catch that, boss — could you say what you'd like me to do?",
                    "hallucination_blocked")
        return reply, "ok"
    except Exception:
        return reply, "ok"
