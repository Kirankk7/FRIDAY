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
}

import random
import datetime as _dt

def _instant_greeting(text: str) -> str:
    """Zero-LLM responses for common greetings. Sub-50ms."""
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
                f"🔴 Fast path "
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
        f"🧠 Brain "
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