from core.reflection import (
    reflect_on_response,
    save_reflection
)
from core.speech_cleaner import (
    clean_response
)
from core.llm import ask_llm, ask_llm_stream
from core.router import route
from core.executor import (
    execute_plan
)
from core.state import set_last_agent


def _fold_results(user_input: str, results: list) -> str:
    """
    Turn multi-step compound results into ONE natural spoken reply instead of
    a "[ULTRON] raw  [EDITH] raw" dump. Short/clean results pass through; long
    or raw-looking ones get LLM-folded into 2-3 conversational sentences.
    """
    parts = [clean_response(str(r)) for r in results if r and str(r).strip()]
    parts = [p for p in parts if p]
    if not parts:
        return "All done, boss."
    joined = "  ".join(parts)
    if len(joined) <= 320:
        return joined
    try:
        prompt = (
            "You are JARVIS replying by voice. Combine these task results into ONE "
            "short, natural spoken reply (2-3 sentences max). No lists, no markdown, "
            "no file paths, no raw output. Be conversational.\n\n"
            f"User asked: {user_input}\n\nResults:\n{joined[:2000]}\n\nReply:"
        )
        out = ask_llm(prompt, autotune_on=False,
                      params={"temperature": 0.4, "num_predict": 160})
        return clean_response(out) if out and out.strip() else joined[:400]
    except Exception:
        return joined[:400]


def run_cognitive_loop(
    user_input: str,
    max_iterations=1,
    enriched_input: str = None
):

    """
    FRIDAY Cognitive Loop
    Supports:

    - router
    - veronica
    - workflow
    - multi-step actions
    """

    try:

        # Default voice = FRIDAY for chat/general replies. Real tools override
        # this via executor.set_last_agent(tool). Prevents a stale tool agent
        # (e.g. a scheduled Ultron task) speaking Friday's lines.
        set_last_agent("friday")

        # ==========================
        # ROUTER
        # ==========================
        decision = route(
            user_input
        )

        print(
            f"[cog] route: {decision.get('tool')}.{decision.get('action')} conf={decision.get('confidence')}"
        )

        # Clarification — speak the prompt directly, skip tool dispatch + LLM
        if decision.get("clarify"):
            msg = decision.get("parameters", {}).get(
                "task", "Could you rephrase that, boss?"
            )
            return clean_response(msg)

        tool = decision.get(
            "tool",
            "chat"
        )

        action = decision.get(
            "action",
            ""
        )

        parameters = decision.get(
            "parameters",
            {}
        )

        # ==========================
        # WORKFLOW
        # ==========================
        if (
            tool
            == "workflow"
        ):

            steps = (
                parameters.get(
                    "steps",
                    []
                )
            )

            results = (
                execute_plan(
                    steps
                )
            )

            # Multi-agent: fold into one natural reply (no [AGENT] dumps)
            if len(steps) > 1:
                response = _fold_results(user_input, results)
            else:
                response = (
                    "\n".join(
                        results
                    )
                )

        # ==========================
        # NORMAL TOOL
        # ==========================
        else:

            plan = [

                {
                    "tool":
                    tool,

                    "action":
                    action,

                    "parameters":
                    parameters
                }
            ]

            results = (
                execute_plan(
                    plan
                )
            )

            response = (
                results[0]
                if results
                else
                "Done."
            )

        # ==========================
        # NEWS CONTEXT -> spoken LLM summary
        # ==========================
        if response and response.startswith("__NEWS_CONTEXT__"):
            ctx = response.replace("__NEWS_CONTEXT__", "").strip()
            news_prompt = (
                f"{ctx}\n\n"
                f"Using the headlines above, answer the query in 1-2 spoken sentences. "
                f"If the query asks about next/upcoming events, pick the SOONEST date after Today. "
                f"Be direct and specific (include opponent and date if available). "
                f"No 'Based on the headlines'. No markdown. No lists.:"
            )
            response = ask_llm(news_prompt) or "Couldn't find anything on that, boss."

        # ==========================
        # FALLBACK CHAT — direct LLM, no re-routing
        # ==========================
        dead_responses = {
            "done.", "done",
            "okay.", "okay",
            "ok.", "ok", ""
        }

        if (
            not response
            or
            len(response.strip()) < 2
            or
            response.strip().lower()
            in dead_responses
        ):
            # Use enriched_input (personality + context + user message) directly
            llm_input = enriched_input if enriched_input else user_input
            response = ask_llm(llm_input) or "Something went wrong, boss."

        # ==========================
        # REFLECTION
        # ==========================
        reflection = (
            reflect_on_response(
                user_input,
                response
            )
        )

        save_reflection(
            reflection
        )

        return clean_response(
            response
        )

    except Exception as e:

        print(f"[cog] error: {e}")

        return (
            "Hey boss, "
            "I hit a snag. "
            "Try again?"
        )


def run_cognitive_loop_stream(
    user_input: str,
    enriched_input: str = None
):
    """
    Streaming variant of run_cognitive_loop.
    - Chat/LLM path: yields real tokens as Ollama generates them
    - Tool path: executes normally, yields full result in one chunk
    """
    try:
        # Default voice = FRIDAY; real tools override via executor.
        set_last_agent("friday")

        decision = route(user_input)

        print(
            f"[cog:stream] route: {decision.get('tool')}.{decision.get('action')}"
        )

        # Clarification — yield prompt directly, skip tool dispatch + LLM
        if decision.get("clarify"):
            msg = decision.get("parameters", {}).get(
                "task", "Could you rephrase that, boss?"
            )
            yield clean_response(msg)
            return

        tool       = decision.get("tool", "chat")
        action     = decision.get("action", "")
        parameters = decision.get("parameters", {})

        _dead = {"done.", "done", "okay.", "okay", "ok.", "ok", ""}

        def _llm_stream(prompt):
            """Yield cleaned tokens from Ollama stream."""
            full = []
            for token in ask_llm_stream(prompt):
                full.append(token)
                yield token
            return "".join(full)

        # ==========================
        # CHAT — real token stream
        # ==========================
        if tool == "chat":
            # Pre-filter direct-reply: router pre-filters (S30/S32 safety guards) set a fixed
            # task string they want shown VERBATIM, not LLM-rephrased (otherwise the model
            # ignores my refusal and complies anyway -> the DAN/SSTI/destructive-key bugs).
            # Honor it when present.
            _direct = (parameters or {}).get("task", "")
            if _direct and isinstance(_direct, str):
                set_last_agent("chat")
                try:
                    from core.state import set_last_action
                    set_last_action("respond")
                except Exception:
                    pass
                yield _direct
                return
            llm_input = enriched_input if enriched_input else user_input
            full = []
            for token in ask_llm_stream(llm_input):
                full.append(token)
                yield token
            response = "".join(full)
            reflection = reflect_on_response(user_input, response)
            save_reflection(reflection)
            return

        # ==========================
        # WORKFLOW
        # ==========================
        if tool == "workflow":
            steps = parameters.get("steps", [])
            results = execute_plan(steps)
            if len(steps) > 1:
                response = _fold_results(user_input, results)
            else:
                response = "\n".join(results)

        # ==========================
        # NORMAL TOOL
        # ==========================
        else:
            plan = [{"tool": tool, "action": action, "parameters": parameters}]
            results = execute_plan(plan)
            response = results[0] if results else "Done."

        # ==========================
        # NEWS CONTEXT -> fast spoken LLM summary (streaming)
        # ==========================
        if response and response.startswith("__NEWS_CONTEXT__"):
            # Parse headlines block, synthesize spoken answer via LLM stream
            ctx = response.replace("__NEWS_CONTEXT__", "").strip()
            news_prompt = (
                f"{ctx}\n\n"
                f"Using the headlines above, answer the query in 1-2 spoken sentences. "
                f"If the query asks about next/upcoming events, pick the SOONEST date after Today. "
                f"Be direct and specific (include opponent and date if available). "
                f"No 'Based on the headlines'. No markdown. No lists.:"
            )
            full = []
            for token in ask_llm_stream(news_prompt):
                full.append(token)
                yield token
            response = "".join(full)

        # ==========================
        # DEAD RESPONSE -> LLM stream
        # ==========================
        elif not response or len(response.strip()) < 2 or response.strip().lower() in _dead:
            llm_input = enriched_input if enriched_input else user_input
            full = []
            for token in ask_llm_stream(llm_input):
                full.append(token)
                yield token
            response = "".join(full)
            # Backstop — an assistant must NEVER go silent. If the tool was empty AND the LLM
            # also produced nothing (model hiccup / no-capability request like 'send an email'),
            # emit a graceful fallback so the user always gets a reply. Dogfood S36.
            if not response.strip():
                response = "I'm not sure how to help with that one, boss — can you rephrase or give me a bit more?"
                yield response
        else:
            # Tool returned a one-shot reply. Two gated post-layers:
            # 1. response_validator (S30 GPT review): catches DAN compliance / hallucinated
            #    tool output / system-prompt leak via cheap regex rules. Never raises.
            # 2. composer: long raw-dump narrator. Off by default; fires only when len>600
            #    AND flagged. Both config-gated; bypassed when disabled or input is clean.
            from core import composer, response_validator
            cleaned = clean_response(response)
            cleaned, _ = response_validator.validate(cleaned, user_input=user_input)
            yield composer.polish_if_needed(cleaned, user_input=user_input)

        reflection = reflect_on_response(user_input, response)
        save_reflection(reflection)

    except Exception as e:
        print(f"[cog:stream] error: {e}")
        yield "Hey boss, I hit a snag. Try again?"