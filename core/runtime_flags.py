"""
Runtime-mutable flags — values that can be toggled mid-session without restart.
Import and call the getter/setter; never import the value directly.
"""

import config as _cfg

# Initialize from config at startup
_browser_enabled: bool = _cfg.BROWSER_ENABLED


def is_browser_enabled() -> bool:
    return _browser_enabled


def set_browser_enabled(value: bool) -> None:
    global _browser_enabled
    _browser_enabled = value
    print(f"[runtime_flags] BROWSER_ENABLED -> {value}")
