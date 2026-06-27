from core.tools_registry import execute_tool
from core.router import route

from core.memory import (
    load_memory,
    save_tool_context,
    get_tool_context,
    save_pending_action,
    get_pending_action,
    clear_pending_action
)


KNOWN_APPS = {
    "chrome",
    "edge",
    "firefox",
    "vscode",
    "notepad",
    "calculator",
    "cmd"
}


FOLLOW_UP_SITES = {
    "youtube": "https://youtube.com",
    "gmail": "https://gmail.com",
    "google": "https://google.com",
    "github": "https://github.com",
    "linkedin": "https://linkedin.com",
    "chatgpt": "https://chat.openai.com",
    "reddit": "https://reddit.com"
}


def clarification_response(
    tool,
    action,
    parameters
):
    """
    Smart clarification.
    """

    if (
        tool == "veronica"
        and action == "open_app"
    ):
        app = (
            str(
                parameters.get(
                    "app",
                    ""
                )
            )
            .lower()
            .strip()
        )

        # Browser clarification
        if app == "browser":

            save_pending_action(
                tool=
                "veronica",
                action=
                "open_app",
                parameters={
                    "app":
                    "browser"
                }
            )

            return (
                "Which browser "
                "should I open?\n\n"
                "Chrome, Edge, "
                "or Firefox?"
            )

    # File creation clarification
    if (
        tool == "file"
        and action
        == "create_file"
    ):
        path = (
            parameters.get(
                "path",
                ""
            )
        )

        if not path:

            save_pending_action(
                tool=
                "file",
                action=
                "create_file"
            )

            return (
                "What should "
                "I name the file?"
            )

    return None


def try_pending_action(
    prompt
):
    """
    Continue unfinished tasks.
    """

    pending = (
        get_pending_action()
    )

    if not pending:
        return None

    text = (
        prompt.lower()
        .strip()
    )

    print(f"[skills] pending: {pending}")

    tool = (
        pending.get(
            "tool"
        )
    )

    action = (
        pending.get(
            "action"
        )
    )

    # =================================
    # Browser continuation
    # =================================
    if (
        tool == "veronica"
        and action
        == "open_app"
    ):

        if text in {
            "chrome",
            "edge",
            "firefox"
        }:

            clear_pending_action()

            result = execute_tool(
                tool_name=
                "veronica",
                input_text=
                prompt,
                action=
                "open_app",
                parameters={
                    "app":
                    text
                }
            )

            return result.get(
                "message"
            )

    # =================================
    # File creation continuation
    # =================================
    if (
        tool == "file"
        and action
        == "create_file"
    ):

        filename = (
            prompt.strip()
        )

        clear_pending_action()

        result = execute_tool(
            tool_name=
            "file",
            input_text=
            prompt,
            action=
            "create_file",
            parameters={
                "path":
                filename
            }
        )

        return result.get(
            "message"
        )

    return None


def try_follow_up(
    prompt,
    memory
):
    """
    Context-aware followups.
    """

    text = (
        str(prompt)
        .lower()
        .strip()
    )

    print(f"[skills] follow-up text: '{text[:80]}'")

    context = (
        get_tool_context(
            memory
        )
    )

    print(f"[skills] context: {context}")

    if not context:
        return None

    last_tool = (
        str(
            context.get(
                "tool",
                ""
            )
        )
        .lower()
        .strip()
    )

    last_action = (
        str(
            context.get(
                "action",
                ""
            )
        )
        .lower()
        .strip()
    )

    last_params = (
        context.get(
            "parameters",
            {}
        )
    )

    last_app = (
        str(
            last_params.get(
                "app",
                ""
            )
        )
        .lower()
        .strip()
    )

    print(f"[skills] last_app: '{last_app}'")

    # =================================
    # Browser continuation
    # =================================
    browser_apps = {
        "chrome",
        "edge",
        "firefox"
    }

    if (
        last_tool
        == "veronica"
        and last_action
        == "open_app"
        and last_app
        in browser_apps
    ):

        normalized_text = (
            text
            .replace(
                "open ",
                ""
            )
            .replace(
                ".com",
                ""
            )
            .strip()
        )

        print(f"[skills] normalized: '{normalized_text}'")

        if (
            normalized_text
            in FOLLOW_UP_SITES
        ):

            print("[skills] browser follow-up detected")

            url = (
                FOLLOW_UP_SITES[
                    normalized_text
                ]
            )

            result = execute_tool(
                tool_name=
                "veronica",
                input_text=
                prompt,
                action=
                "open_url",
                parameters={
                    "url":
                    url
                }
            )

            return result.get(
                "message"
            )

    return None


def run_skill(
    prompt: str
) -> str:

    try:
        memory = (
            load_memory()
        )

        # =================================
        # PENDING ACTION FIRST
        # =================================
        pending_result = (
            try_pending_action(
                prompt
            )
        )

        if pending_result:

            print(
                "[pending] Pending "
                "workflow used"
            )

            return pending_result

        # =================================
        # FOLLOW-UP
        # =================================
        followup = (
            try_follow_up(
                prompt,
                memory
            )
        )

        if followup:

            print("[skills] follow-up context used")

            return followup

        # =================================
        # ROUTER
        # =================================
        decision = (
            route(prompt)
        )

        tool = decision.get(
            "tool",
            "chat"
        )

        action = decision.get(
            "action",
            "respond"
        )

        parameters = (
            decision.get(
                "parameters",
                {}
            )
        )

        confidence = (
            decision.get(
                "confidence",
                0.0
            )
        )

        print(f"[skills] route: {tool}.{action} conf={confidence}")

        if confidence < 0.55:
            tool = "chat"

        # =================================
        # CLARIFICATION
        # =================================
        clarification = (
            clarification_response(
                tool,
                action,
                parameters
            )
        )

        if clarification:
            return clarification

        # =================================
        # CHAT
        # =================================
        if tool == "chat":

            from core.llm import (
                ask_llm
            )

            response = (
                ask_llm(
                    prompt
                )
            )

            return (
                response
                or
                "I'm not sure "
                "how to respond."
            )

        # =================================
        # TOOL EXECUTION
        # =================================
        result = execute_tool(
            tool_name=
            tool,
            input_text=
            prompt,
            action=
            action,
            parameters=
            parameters
        )

        message = result.get(
            "message",
            "Done."
        )

        print("[skills] saving tool context")

        save_tool_context(
            memory,
            tool,
            action,
            parameters,
            message
        )

        return message

    except Exception as e:
        print(f"[skills] error: {e}")

        return (
            "Something "
            "went wrong."
        )