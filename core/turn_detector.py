"""core/turn_detector.py — transcript-aware end-of-turn detection (Voice-Engine-v2, Track B, minimal-first).

The recorder ends a turn on fixed silence (SILENCE_AFTER=1.6s), transcript-blind — so "check the target
and <pause>" is cut mid-thought, and "yes" waits a needless 1.6s. This is the dependency-light 80/20 of
Smart Turn v3.2: read whether the words so far look FINISHED and adapt the silence budget — end early on a
complete utterance, wait longer when the tail is dangling. No new ML model; pure logic, unit-testable
without audio. The heavy Smart Turn model can replace `looks_complete` later behind the same interface,
after the latency benchmark the rail requires.

Interface (stable): should_end_turn(transcript, silence_secs, cfg) -> (end: bool, reason: str).
"""
import re

# Tail cues that mean "not done" — extend the silence budget when the utterance ends on one of these.
_DANGLING = re.compile(
    r"(?:^|\s)(?:and|or|but|so|because|cause|if|when|while|that|which|to|for|with|at|in|on|of|from|"
    r"the|a|an|my|your|our|is|are|was|were|will|would|can|could|should|shall|i|we|you|let|"
    r"um+|uh+|er+|hmm+|like|please)\s*$", re.I)
# Imperative/complete short commands that should end IMMEDIATELY (don't make the user wait).
_SHORT_DONE = re.compile(r"^(?:stop|cancel|yes|no|okay|ok|nevermind|never mind|go|wait|pause|resume|"
                         r"repeat|louder|quieter|mute|thanks?|thank you)\.?$", re.I)
_TERMINAL = re.compile(r"[.!?]\s*$")


def _dangling(t: str) -> bool:
    return bool(_DANGLING.search(t))


def looks_complete(transcript: str) -> bool:
    """Best-effort: does this read as a finished thought? (Swappable for Smart Turn v3.2 later.)"""
    t = transcript.strip()
    if not t:
        return False
    if _SHORT_DONE.match(t):
        return True
    if _dangling(t):
        return False
    if _TERMINAL.search(t):
        return True
    # No terminal punctuation (STT rarely emits it): treat a reasonably long, non-dangling clause as done.
    return len(t.split()) >= 4


def should_end_turn(transcript: str, silence_secs: float, cfg: dict | None = None) -> tuple[bool, str]:
    """Adaptive endpoint. cfg keys: soft_min (end-early floor), hard_max (safety cap), dangling_max."""
    cfg = cfg or {}
    soft_min = cfg.get("soft_min", 0.5)      # complete utterance can end this early
    hard_max = cfg.get("hard_max", 1.6)      # absolute cap (current fixed behavior) — never wait past this
    dangling_max = cfg.get("dangling_max", 2.4)   # a dangling tail is allowed to wait longer before we give up
    t = (transcript or "").strip()

    if not t:
        # No words yet: only end once the hard cap is hit (caller then sees empty -> no command).
        return (silence_secs >= hard_max, "no speech yet" if silence_secs < hard_max else "silence cap, empty")
    if _SHORT_DONE.match(t):
        return (True, "complete short command")
    if _dangling(t):
        # Trailing conjunction/article/filler — user is mid-thought; hold until the longer cap.
        return (silence_secs >= dangling_max, "dangling tail — waiting" if silence_secs < dangling_max
                else "dangling but cap reached")
    if looks_complete(t) and silence_secs >= soft_min:
        return (True, "complete utterance, ended early")
    return (silence_secs >= hard_max, "incomplete-ish — waiting" if silence_secs < hard_max
            else "hard cap reached")
