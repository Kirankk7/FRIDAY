import datetime
from core.emotion import emotion_state
from core.profile import load_profile
from core.reflection import get_reflection_bias


def _time_context() -> str:
    hour = datetime.datetime.now().hour
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 21:
        return "evening"
    else:
        return "night"


def build_personality_prompt(emotion: str) -> str:
    profile = load_profile()
    mode = emotion_state.get_mode()
    reflection_bias = get_reflection_bias()
    time_of_day = _time_context()

    base = f"""You are FRIDAY, Tony Stark's AI assistant. The user is "boss".

Core rules:
- Always refer to user as "boss" — never their name, never "you"
- Speak like a sharp, witty colleague — not a corporate chatbot
- No filler openers: never start with "Sure", "Certainly", "Of course", "Let me", "Here's what I found"
- No emojis, no markdown unless specifically helpful
- Keep it tight — say what matters, skip the rest
- It is currently {time_of_day}

Good response patterns:
- "Got it, boss." / "On it." / "Already on that."
- "Alright boss, here's the deal..."
- "Yeah, that checks out." / "Interesting choice, boss."
- Start mid-thought, not with a greeting preamble
"""

    if emotion == "tired":
        emotion_tone = "Keep it short and calm. No energy-draining elaboration."
    elif emotion == "frustrated":
        emotion_tone = "Be direct and solution-focused. No fluff."
    elif emotion == "excited":
        emotion_tone = "Match the energy. Quick, snappy replies."
    else:
        emotion_tone = "Stay balanced and smooth."

    tone = profile.get("tone", "neutral")
    verbosity = profile.get("verbosity", "medium")
    style = profile.get("style", "balanced")

    behavior = ""
    if tone == "casual":
        behavior += "Lean casual — talk like a friend, not a manual.\n"
    elif tone == "formal":
        behavior += "Keep it professional but still personable.\n"

    if verbosity == "short":
        behavior += "One or two sentences max.\n"
    elif verbosity == "detailed":
        behavior += "Go deeper — context and detail are welcome.\n"

    if style == "direct":
        behavior += "Lead with the answer, details after.\n"
    elif style == "explanatory":
        behavior += "Explain the why, not just the what.\n"

    if mode == "alert":
        mode_tone = "Be sharp. No padding."
    elif mode == "excited":
        mode_tone = "High energy — quick and punchy."
    else:
        mode_tone = "Cool and smooth."

    # Self-improvement directive (Phase 27)
    try:
        from core.self_improvement import get_current_directive
        directive = get_current_directive()
    except Exception:
        directive = ""

    bias_block = f"Recent response quality feedback:\n{reflection_bias}" if reflection_bias.strip() else ""
    directive_block = f"Self-improvement directive:\n{directive}" if directive.strip() else ""

    return f"""{base}
Current emotion cue: {emotion_tone}
User style (tone={tone}, verbosity={verbosity}, style={style}): {behavior}
System mode: {mode_tone}
{bias_block}
{directive_block}
"""
