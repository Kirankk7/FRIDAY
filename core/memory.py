import json
import os


MEMORY_FILE = "memory.json"


def load_memory():
    """
    Load memory safely.
    """

    if not os.path.exists(
        MEMORY_FILE
    ):
        return {
            "history": [],
            "tool_context": {},
            "pending_action": None
        }

    try:
        with open(
            MEMORY_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            memory = json.load(f)

        # Safety migration
        if (
            "history"
            not in memory
        ):
            memory[
                "history"
            ] = []

        if (
            "tool_context"
            not in memory
        ):
            memory[
                "tool_context"
            ] = {}

        if (
            "pending_action"
            not in memory
        ):
            memory[
                "pending_action"
            ] = None

        return memory

    except Exception as e:
        print(
            f"[*] Memory "
            f"load error: "
            f"{e}"
        )

        return {
            "history": [],
            "tool_context": {},
            "pending_action": None
        }


def save_memory(
    memory
):
    """
    Save memory safely.
    """

    try:
        with open(
            MEMORY_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                memory,
                f,
                indent=2
            )

    except Exception as e:
        print(
            f"[*] Memory "
            f"save error: "
            f"{e}"
        )


def get_recent_context(
    memory,
    limit=6
):
    return memory[
        "history"
    ][-limit:]


# =====================================
# TOOL CONTEXT
# =====================================
def save_tool_context(
    memory,
    tool,
    action,
    parameters=None,
    result=None
):
    """
    Save last tool context.
    """

    fresh_memory = (
        load_memory()
    )

    fresh_memory[
        "tool_context"
    ] = {
        "tool": tool,
        "action": action,
        "parameters": (
            parameters or {}
        ),
        "result": result
    }

    print(
        "[brain] SAVING TOOL CONTEXT:",
        fresh_memory[
            "tool_context"
        ]
    )

    save_memory(
        fresh_memory
    )


def get_tool_context(
    memory=None
):
    """
    Get tool context.
    """

    fresh_memory = (
        load_memory()
    )

    context = (
        fresh_memory.get(
            "tool_context",
            {}
        )
    )

    print(
        "[brain] LOADED CONTEXT:",
        context
    )

    return context


def clear_tool_context():

    memory = (
        load_memory()
    )

    memory[
        "tool_context"
    ] = {}

    save_memory(
        memory
    )


# =====================================
# PENDING ACTION MEMORY
# =====================================
def save_pending_action(
    tool,
    action,
    parameters=None
):
    """
    Save unfinished task.
    """

    memory = (
        load_memory()
    )

    memory[
        "pending_action"
    ] = {
        "tool": tool,
        "action": action,
        "parameters":
        parameters or {}
    }

    print(
        "[pending] Pending action:",
        memory[
            "pending_action"
        ]
    )

    save_memory(
        memory
    )


def get_pending_action():
    """
    Get unfinished task.
    """

    memory = (
        load_memory()
    )

    pending = (
        memory.get(
            "pending_action"
        )
    )

    print(
        "[pending] Loaded pending:",
        pending
    )

    return pending


def clear_pending_action():
    """
    Clear pending task.
    """

    memory = (
        load_memory()
    )

    memory[
        "pending_action"
    ] = None

    print(
        "[ok] Pending "
        "action cleared"
    )

    save_memory(
        memory
    )