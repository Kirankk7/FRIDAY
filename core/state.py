# Shared in-process state — set by executor, read by app.py
_last_agent = "friday"
_last_action = ""


def set_last_agent(agent: str):
    global _last_agent
    _last_agent = agent.lower().strip()


def get_last_agent() -> str:
    return _last_agent


def set_last_action(action: str):
    global _last_action
    _last_action = action


def get_last_action() -> str:
    return _last_action
