# 🔒 TOOL PERMISSIONS

TOOL_PERMISSIONS = {
    "chat": "safe",
    "news_search": "safe",
    "summarize": "safe",
    "system_info": "safe",
    # future tools:
    # "execute_command": "dangerous",
    # "file_delete": "dangerous"
}


# 🔒 BLOCKED KEYWORDS
BLOCKED_KEYWORDS = [
    "delete all files",
    "format disk",
    "shutdown system",
    "hack",
    "exploit",
    "attack"
]


def is_safe_input(user_input):
    text = user_input.lower()

    for word in BLOCKED_KEYWORDS:
        if word in text:
            return False

    return True


def check_tool_permission(tool_name):
    return TOOL_PERMISSIONS.get(tool_name, "unknown")


def requires_confirmation(tool_name):
    level = check_tool_permission(tool_name)

    return level == "dangerous"