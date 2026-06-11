"""
Phase 51 #6 — tool-result memory.

Ring buffer of recent tool outputs so the user can ask "what did that scan find?"
without re-running the tool. Persisted to data/tool_results.json (survives restart).
"""
import os
import json
import datetime
import threading
from collections import deque

_FILE = "data/tool_results.json"
_MAX = 20
_lock = threading.Lock()
_buf = deque(maxlen=_MAX)
_loaded = False


def _load():
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        if os.path.exists(_FILE):
            with open(_FILE, "r", encoding="utf-8") as f:
                for item in json.load(f)[-_MAX:]:
                    _buf.append(item)
    except Exception:
        pass


def _save():
    try:
        os.makedirs("data", exist_ok=True)
        with open(_FILE, "w", encoding="utf-8") as f:
            json.dump(list(_buf), f, indent=2)
    except Exception:
        pass


def remember_result(tool: str, action: str, message: str):
    """Record a tool result. Skips empty/trivial outputs."""
    if not message or not message.strip():
        return
    with _lock:
        _load()
        _buf.append({
            "tool": tool,
            "action": action,
            "message": message[:600],
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        })
        _save()


def recent_results(n: int = 3) -> list:
    with _lock:
        _load()
        return list(_buf)[-n:][::-1]   # newest first


def last_result() -> dict | None:
    with _lock:
        _load()
        return _buf[-1] if _buf else None


def search_results(keyword: str) -> list:
    """Most-recent-first results whose tool/action/message contains keyword."""
    kw = (keyword or "").lower().strip()
    with _lock:
        _load()
        items = list(_buf)[::-1]
    if not kw:
        return items
    return [
        it for it in items
        if kw in it.get("tool", "").lower()
        or kw in it.get("action", "").lower()
        or kw in it.get("message", "").lower()
    ]
