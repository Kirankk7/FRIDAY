"""
Phase 61 — proactive engine.

Makes JARVIS reach OUT instead of only answering. Called from the scheduler's
30s loop; uses internal timers so each check runs at its own cadence. Every
alert goes through core.notify.push (HUD now, Telegram/email later).

  · due reminders        -> fire even when you're not chatting
  · morning digest       -> once/day: tasks / reminders / events
  · defensive delta      -> opt-in: new listening ports / suspicious processes
  · CVE watchlist        -> new critical/high entries since last check
  · target monitor       -> opt-in: re-recon watched targets, alert on change
"""

import time
import datetime

from core.notify import push

# config (graceful defaults; all overridable)
try:
    from config import (PROACTIVE_ENABLED, PROACTIVE_DIGEST_HOUR,
                        PROACTIVE_DEFENSE_MIN, PROACTIVE_CVE_MIN,
                        PROACTIVE_MONITOR_MIN)
except Exception:
    PROACTIVE_ENABLED = True
    PROACTIVE_DIGEST_HOUR = 8
    PROACTIVE_DEFENSE_MIN = 0       # 0 = off (host scan is heavier); set e.g. 60
    PROACTIVE_CVE_MIN = 180
    PROACTIVE_MONITOR_MIN = 0       # 0 = off; set e.g. 360 to re-recon watched targets

_last = {"digest_date": None, "defense": 0.0, "cve": 0.0, "monitor": 0.0, "rag": 0.0}
_seen_cves = set()


def _due(key: str, minutes: int) -> bool:
    if minutes <= 0:
        return False
    now = time.time()
    if now - _last[key] >= minutes * 60:
        _last[key] = now
        return True
    return False


def _check_reminders():
    try:
        from agents.friday.friday_agent import check_reminders
        for text in (check_reminders() or []):
            push(f"Reminder: {text}", kind="reminder")
    except Exception as e:
        print(f"[proactive] reminders skipped: {e}")


def _morning_digest():
    today = datetime.date.today().isoformat()
    hour = datetime.datetime.now().hour
    if _last["digest_date"] == today or hour < PROACTIVE_DIGEST_HOUR:
        return
    _last["digest_date"] = today
    try:
        from agents.friday.friday_agent import _load as _load_friday
        d = _load_friday()
        tasks = [t for t in d.get("tasks", []) if not t.get("done")]
        rem = [r for r in d.get("reminders", []) if not r.get("fired")]
        events = [e for e in d.get("events", []) if e.get("date") == today]
        bits = []
        if tasks:  bits.append(f"{len(tasks)} task{'s' if len(tasks)!=1 else ''} pending")
        if rem:    bits.append(f"{len(rem)} reminder{'s' if len(rem)!=1 else ''}")
        if events: bits.append(f"{len(events)} event{'s' if len(events)!=1 else ''} today")
        summary = ", ".join(bits) if bits else "nothing on the books — clear day"
        push(f"Morning, boss. {summary}.", kind="digest")
    except Exception as e:
        print(f"[proactive] digest skipped: {e}")


def _check_defense():
    if not _due("defense", PROACTIVE_DEFENSE_MIN):
        return
    try:
        from agents.ultron.ultron_agent import ultron_agent
        r = ultron_agent.defensive_scan()
        d = r.get("data", {})
        new_ports = d.get("new_ports", [])
        susp = d.get("suspicious", {})
        if susp.get("ports") or susp.get("procs"):
            push(f"Security alert — {r['message']}", kind="security")
        elif new_ports:
            push(f"Heads up: {len(new_ports)} new listening port(s) since baseline: "
                 f"{', '.join(map(str, new_ports[:6]))}.", kind="security")
    except Exception as e:
        print(f"[proactive] defense check skipped: {e}")


def _check_cves():
    if not _due("cve", PROACTIVE_CVE_MIN):
        return
    try:
        import os, json
        path = "data/cve_watchlist.json"
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data if isinstance(data, list) else list(data.values()) if isinstance(data, dict) else []
        for entry in items:
            cid = entry.get("cve_id") or entry.get("id") or entry.get("cve") if isinstance(entry, dict) else None
            sev = (entry.get("severity") or "" if isinstance(entry, dict) else "").lower()
            if cid and cid not in _seen_cves:
                _seen_cves.add(cid)
                if sev in ("critical", "high"):
                    push(f"Tracked {sev} vuln active: {cid}.", kind="security")
    except Exception as e:
        print(f"[proactive] cve check skipped: {e}")


def _check_targets():
    if not _due("monitor", PROACTIVE_MONITOR_MIN):
        return
    try:
        from agents.ultron.ultron_agent import ultron_agent
        ultron_agent.monitor_targets()   # pushes its own alerts on change
    except Exception as e:
        print(f"[proactive] target monitor skipped: {e}")


def _check_rag_watch():
    # L — keep watched doc folders indexed (every 5 min). Cheap mtime diff; only
    # re-indexes when a folder actually changed.
    if not _due("rag", 5):
        return
    try:
        from core import rag
        n = rag.reindex_watched()
        if n:
            print(f"[proactive] reindexed {n} watched doc folder(s)")
    except Exception as e:
        print(f"[proactive] rag watch skipped: {e}")


def tick():
    """Called every ~30s by the scheduler loop. Each check self-paces."""
    if not PROACTIVE_ENABLED:
        return
    _check_reminders()      # cheap, every tick
    _morning_digest()       # gated to once/day after DIGEST_HOUR
    _check_defense()        # opt-in interval
    _check_cves()           # interval
    _check_targets()        # opt-in: re-recon watched targets, alert on change
    _check_rag_watch()      # L — keep watched doc folders current
