"""
Phase 52 #5 — Telemetry layer.

In-memory per-agent request counters + latency, plus a small rolling event log.
Feeds the Cyber/Operations HUD with real numbers instead of static labels.
Resets on restart (telemetry, not persistence). Thread-safe, dependency-free.
"""

import time
import threading
from collections import deque

_lock = threading.Lock()
_started = time.time()

# agent -> {calls, errors, total_ms, last_ms, last_ts}
_agents = {}
# rolling log of recent calls (newest last)
_events = deque(maxlen=50)


def record(agent: str, latency_ms: float, ok: bool, action: str = "") -> None:
    """Record one tool/agent invocation."""
    agent = (agent or "unknown").lower()
    with _lock:
        a = _agents.setdefault(agent, {
            "calls": 0, "errors": 0, "total_ms": 0.0, "last_ms": 0.0, "last_ts": 0.0,
        })
        a["calls"] += 1
        if not ok:
            a["errors"] += 1
        a["total_ms"] += latency_ms
        a["last_ms"] = latency_ms
        a["last_ts"] = time.time()
        _events.append({
            "agent": agent, "action": action, "ms": round(latency_ms),
            "ok": ok, "ts": time.time(),
        })


def snapshot() -> dict:
    """Full telemetry snapshot for the /metrics endpoint + HUD."""
    with _lock:
        total_calls = sum(a["calls"] for a in _agents.values())
        total_errors = sum(a["errors"] for a in _agents.values())
        per_agent = {
            name: {
                "calls": a["calls"],
                "errors": a["errors"],
                "avg_ms": round(a["total_ms"] / a["calls"]) if a["calls"] else 0,
                "last_ms": round(a["last_ms"]),
            }
            for name, a in sorted(_agents.items(), key=lambda kv: -kv[1]["calls"])
        }
        busiest = next(iter(per_agent), None)
        recent = [dict(e) for e in list(_events)[-10:][::-1]]
    return {
        "uptime_s": round(time.time() - _started),
        "total_calls": total_calls,
        "total_errors": total_errors,
        "agents": per_agent,
        "busiest": busiest,
        "recent": recent,
    }


def reset() -> None:
    """Clear all telemetry (tests)."""
    global _started
    with _lock:
        _agents.clear()
        _events.clear()
        _started = time.time()
