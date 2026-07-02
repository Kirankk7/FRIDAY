from core.memory import (
    load_memory,
    save_memory,
    get_recent_context
)

from core.vector_memory import search_similar, add_to_vector
from core.emotion_memory import (
    detect_emotion,
    save_emotion
)

from core.personality import (
    build_personality_prompt
)

from core.emotion import emotion_state
from core.profile import update_profile
from core.proactive import (
    generate_proactive_suggestion
)

from core.cognitive_loop import (
    run_cognitive_loop,
    run_cognitive_loop_stream
)

from core.llm import ask_llm, ask_llm_stream
from core.personal_memory import get_relevant_context as get_personal_context
from core.state import set_last_agent
from core.routines import routine_manager

# Phrases that end routine recording
_STOP_RECORDING = {
    "stop recording", "end routine", "finish routine", "done recording",
    "stop the recording", "end recording", "save routine",
}
_CANCEL_RECORDING = {"cancel routine", "cancel recording", "discard routine"}


FAST_MESSAGES = {
    "hi", "hello", "hey", "yo", "sup",
    "what's up", "good morning", "good afternoon",
    "good evening", "how are you",
    # JARVIS / FRIDAY name greetings
    "hey jarvis", "hi jarvis", "jarvis",
    "hey, jarvis", "hey, jarvis.", "hi, jarvis",
    "hey friday", "hi friday", "friday",
    "hey, friday", "hey, friday.", "hi, friday",
    "morning", "evening", "afternoon",
    # Conversational acks (browser dogfood 2026-07-02): these were falling to the LLM
    # which returned a canned "Got it, boss." or an empty bubble. Handle instantly instead.
    "thanks", "thank you", "thank you so much", "thanks a lot", "thx", "ty", "cheers",
    "ok", "okay", "k", "kk", "cool", "nice", "great", "awesome", "perfect", "sweet",
    "lol", "haha", "lmao", "hehe", "nvm", "nevermind", "never mind",
    "bye", "goodbye", "cya", "see ya", "see you", "later",
    "you're awesome", "youre awesome", "i love you", "good job", "well done", "nice work",
    # Identity questions — were falling to the LLM and coming back empty.
    "who are you", "what are you", "what's your name", "whats your name",
    "what is your name", "who is this", "your name", "are you there", "can you hear me",
}

# Instant, varied acks — no LLM, no canned "Got it, boss."
_FAST_ACKS = {
    "thanks": ["Anytime, boss.", "You got it.", "Happy to help.", "Anytime."],
    "thank you": ["Anytime, boss.", "You got it.", "Happy to help."],
    "thank you so much": ["Anytime, boss — that's what I'm here for.", "You got it."],
    "thanks a lot": ["Anytime, boss.", "You got it."],
    "thx": ["Anytime.", "You got it."], "ty": ["Anytime.", "You got it."],
    "cheers": ["Cheers, boss.", "Anytime."],
    "ok": ["Standing by, boss.", "Ready when you are.", "Got it."],
    "okay": ["Standing by, boss.", "Ready when you are."],
    "k": ["Standing by.", "Ready when you are."], "kk": ["Standing by.", "Ready when you are."],
    "cool": ["Ready when you are, boss.", "Standing by."],
    "nice": ["Glad you think so, boss.", "Standing by."],
    "great": ["Ready when you are, boss.", "On standby."],
    "awesome": ["Glad it works, boss.", "Standing by."],
    "perfect": ["Ready for the next one, boss.", "Standing by."],
    "sweet": ["Standing by, boss."],
    "lol": ["Heh.", "Glad you're amused, boss."], "haha": ["Heh.", "Glad you're amused, boss."],
    "lmao": ["Heh.", "Glad you're amused, boss."], "hehe": ["Heh."],
    "nvm": ["No worries, boss.", "All good."], "nevermind": ["No worries, boss.", "All good."],
    "never mind": ["No worries, boss.", "All good."],
    "bye": ["Later, boss.", "I'll be here."], "goodbye": ["Later, boss.", "I'll be here."],
    "cya": ["Later, boss."], "see ya": ["Later, boss."], "see you": ["Later, boss."],
    "later": ["Later, boss."],
    "you're awesome": ["Appreciate it, boss.", "Just doing my job."],
    "youre awesome": ["Appreciate it, boss."],
    "i love you": ["Appreciate it, boss.", "Right back at you — now what do you need?"],
    "good job": ["Appreciate it, boss.", "Just doing my job."],
    "well done": ["Appreciate it, boss."], "nice work": ["Appreciate it, boss."],
    "who are you": ["I'm FRIDAY, your local AI assistant, boss. What do you need?"],
    "what are you": ["I'm FRIDAY — a local AI assistant running on your machine, boss."],
    "what's your name": ["FRIDAY, boss."], "whats your name": ["FRIDAY, boss."],
    "what is your name": ["FRIDAY, boss."], "your name": ["FRIDAY, boss."],
    "who is this": ["FRIDAY, boss — your assistant."],
    "are you there": ["Right here, boss.", "Always, boss."],
    "can you hear me": ["Loud and clear, boss.", "I'm here, boss."],
}

import random
import datetime as _dt

def _instant_greeting(text: str) -> str:
    """Zero-LLM responses for common greetings + acks. Sub-50ms."""
    # Conversational acks first (thanks / ok / lol / bye / …) — instant + varied.
    if text in _FAST_ACKS:
        return random.choice(_FAST_ACKS[text])

    hour = _dt.datetime.now().hour
    time_str = "morning" if hour < 12 else "afternoon" if hour < 17 else "evening"

    greetings = {
        "good morning":   [f"Morning, boss. Ready when you are.", f"Good morning. What are we working on?"],
        "good afternoon": [f"Afternoon, boss. What do you need?", f"Good afternoon. What's on the agenda?"],
        "good evening":   [f"Evening, boss. Long day?", f"Good evening. What can I do for you?"],
        "morning":        [f"Morning, boss."],
        "afternoon":      [f"Afternoon, boss."],
        "evening":        [f"Evening, boss."],
        "how are you":    ["Running at full capacity, boss.", "All systems nominal. You?", "Operational. What's up?"],
    }

    # Jarvis/Friday name variants
    name_variants = {
        "hey jarvis", "hi jarvis", "jarvis", "hey, jarvis", "hey, jarvis.",
        "hey friday", "hi friday", "friday", "hey, friday", "hey, friday.", "hi, friday", "hi jarvis",
    }

    if text in name_variants:
        return random.choice([
            f"Right here, boss.",
            f"Online, boss. What do you need?",
            f"Here, boss. What's the move?",
            f"At your service, boss.",
        ])

    generic = [
        f"Hey boss. Good {time_str}.",
        "What's up, boss.",
        "Hey. What do you need?",
        "Online and ready, boss.",
        "Here, boss. What's the plan?",
    ]

    pool = greetings.get(text.lower().strip(), generic)
    return random.choice(pool)


def save_memory_safe(
    local_memory
):
    latest_memory = (
        load_memory()
    )

    tool_context = (
        latest_memory.get(
            "tool_context",
            {}
        )
    )

    history = local_memory.get("history", [])
    # Keep last 40 entries (20 exchanges)
    if len(history) > 40:
        history = history[-40:]

    latest_memory["history"] = history
    latest_memory["tool_context"] = tool_context

    save_memory(latest_memory)


def process_input(
    user_input: str
) -> str:

    raw_input = (
        user_input.strip()
    )

    memory = (
        load_memory()
    )

    text_lower = (
        raw_input.lower()
        .strip()
    )

    # =================================
    # ROUTINE RECORDING — capture commands instead of executing (Phase 43)
    # =================================
    if routine_manager.is_recording():
        if text_lower in _STOP_RECORDING:
            return routine_manager.stop_recording()
        if text_lower in _CANCEL_RECORDING:
            return routine_manager.cancel_recording()
        return routine_manager.add_command(raw_input)

    # =================================
    # FAST PATH — instant, no LLM
    # =================================
    if text_lower in FAST_MESSAGES:
        try:
            set_last_agent("friday")   # greetings are FRIDAY's — not a stale tool agent
            response = _instant_greeting(text_lower)

            memory["history"].append({"role": "user",      "content": raw_input})
            memory["history"].append({"role": "assistant", "content": response})
            save_memory_safe(memory)

            print("[brain] Instant greeting path")

            return response

        except Exception as e:
            print(
                f"[brain] Fast path "
                f"error: {e}"
            )

    # =================================
    # EMOTION
    # =================================
    emotion = (
        detect_emotion(
            raw_input
        )
    )

    save_emotion({
        "text":
        raw_input,
        "emotion":
        emotion
    })

    if emotion == (
        "frustrated"
    ):
        emotion_state.set_mode(
            "alert"
        )

    elif emotion == (
        "excited"
    ):
        emotion_state.set_mode(
            "excited"
        )

    else:
        emotion_state.set_mode(
            "calm"
        )

    recent_context = (
        get_recent_context(
            memory
        )
    )

    related_memories = (
        search_similar(
            raw_input
        )
    )

    context_block = ""

    if recent_context:

        context_block += (
            "Recent "
            "conversation:\n"
        )

        for item in (
            recent_context
        ):
            role = item.get(
                "role"
            )

            content = (
                item.get(
                    "content"
                )
            )

            if (
                role
                and content
            ):
                context_block += (
                    f"{role}: "
                    f"{content}\n"
                )

    if related_memories:

        context_block += (
            "\nRelevant "
            "memory:\n"
        )

        for item in (
            related_memories[:3]
        ):
            context_block += (
                f"- {item}\n"
            )

    personality_prompt = (
        build_personality_prompt(
            emotion
        )
    )

    personal_context = get_personal_context(raw_input)

    enriched_input = f"""
{personality_prompt}

{context_block}

{personal_context}

User:
{raw_input}
"""

    # =================================
    # COGNITIVE LOOP
    # raw_input for routing
    # enriched_input passed for LLM chat
    # =================================
    response = (
        run_cognitive_loop(
            raw_input,
            enriched_input=enriched_input
        )
    )

    print(
        f"[brain] "
        f"response: "
        f"{response[:100]}"
        f"..."
    )

    suggestion = (
        generate_proactive_suggestion(
            raw_input,
            response,
            emotion
        )
    )

    if suggestion:
        response = (
            f"{response}\n\n"
            f"{suggestion}"
        )

    update_profile(
        raw_input,
        response
    )

    add_to_vector(raw_input)

    memory[
        "history"
    ].append({
        "role":
        "user",
        "content":
        raw_input
    })

    memory[
        "history"
    ].append({
        "role":
        "assistant",
        "content":
        response
    })

    save_memory_safe(
        memory
    )

    return response


def process_input_stream(user_input: str):
    """
    Streaming variant of process_input.
    - Fast path (greetings): instant pre-written response, no LLM
    - Chat/LLM path: real token-by-token streaming from Ollama
    - Tool path: executes tool, yields full result in one chunk
    """
    raw_input = user_input.strip()
    memory = load_memory()
    text_lower = raw_input.lower().strip()

    # Routine recording — capture commands instead of executing (Phase 43)
    if routine_manager.is_recording():
        if text_lower in _STOP_RECORDING:
            yield routine_manager.stop_recording()
            return
        if text_lower in _CANCEL_RECORDING:
            yield routine_manager.cancel_recording()
            return
        yield routine_manager.add_command(raw_input)
        return

    # Fast path
    if text_lower in FAST_MESSAGES:
        set_last_agent("friday")   # greetings are FRIDAY's — not a stale tool agent
        response = _instant_greeting(text_lower)
        memory["history"].append({"role": "user",      "content": raw_input})
        memory["history"].append({"role": "assistant", "content": response})
        save_memory_safe(memory)
        yield response
        return

    # Build enriched context (same as process_input)
    emotion = detect_emotion(raw_input)
    save_emotion({"text": raw_input, "emotion": emotion})

    if emotion == "frustrated":
        emotion_state.set_mode("alert")
    elif emotion == "excited":
        emotion_state.set_mode("excited")
    else:
        emotion_state.set_mode("calm")

    recent_context  = get_recent_context(memory)
    related_memories = search_similar(raw_input)

    context_block = ""
    if recent_context:
        context_block += "Recent conversation:\n"
        for item in recent_context:
            role    = item.get("role")
            content = item.get("content")
            if role and content:
                context_block += f"{role}: {content}\n"

    if related_memories:
        context_block += "\nRelevant memory:\n"
        for item in related_memories[:3]:
            context_block += f"- {item}\n"

    personality_prompt = build_personality_prompt(emotion)
    personal_context   = get_personal_context(raw_input)

    enriched_input = f"""
{personality_prompt}

{context_block}

{personal_context}

User:
{raw_input}
"""

    # Real streaming via cognitive loop
    full_response = []
    for token in run_cognitive_loop_stream(raw_input, enriched_input=enriched_input):
        full_response.append(token)
        yield token

    response = "".join(full_response)

    # Post-stream bookkeeping
    suggestion = generate_proactive_suggestion(raw_input, response, emotion)
    if suggestion:
        yield f"\n\n{suggestion}"
        response = f"{response}\n\n{suggestion}"

    update_profile(raw_input, response)
    add_to_vector(raw_input)

    memory["history"].append({"role": "user",      "content": raw_input})
    memory["history"].append({"role": "assistant", "content": response})
    save_memory_safe(memory)