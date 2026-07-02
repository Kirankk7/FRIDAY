"""
G — calendar ICS import / export (no OAuth, plain iCalendar text). Bridges friday's
internal events to Google/Apple/Outlook (all export .ics).
"""
import os
import re
import datetime


def _events() -> list:
    from agents.friday import friday_agent as fa
    return fa._load().get("events", [])


def _dtstart(ev: dict) -> str:
    """Best-effort DTSTART (YYYYMMDDTHHMMSS) from an event's date/time fields."""
    date = ev.get("date") or ev.get("day") or ""
    t = ev.get("time") or "09:00"
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(date))
    if not m:
        return ""
    hh, mm = (t.split(":") + ["00"])[:2]
    try:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}T{int(hh):02d}{int(mm):02d}00"
    except Exception:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}T090000"


def export_ics(path: str = "") -> dict:
    path = path or os.path.join("data", "jarvis_calendar.ics")
    evs = _events()
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//JARVIS//friday//EN"]
    n = 0
    for ev in evs:
        dt = _dtstart(ev)
        title = ev.get("title") or ev.get("name") or "Event"
        if not dt:
            continue
        lines += ["BEGIN:VEVENT", f"UID:{ev.get('id', n)}@jarvis",
                  f"DTSTART:{dt}", f"SUMMARY:{title}"]
        if ev.get("notes"):
            lines.append(f"DESCRIPTION:{ev['notes']}")
        lines.append("END:VEVENT")
        n += 1
    lines.append("END:VCALENDAR")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\r\n".join(lines))
    return {"success": True, "message": f"Exported {n} event(s) to {path}.", "data": {"path": path, "count": n}}


def _read_source(src: str) -> str:
    if re.match(r"^https?://", src or ""):
        import requests
        return requests.get(src, timeout=10).text
    with open(os.path.expanduser(src), "r", encoding="utf-8") as f:
        return f.read()


def import_ics(src: str) -> dict:
    try:
        text = _read_source(src)
    except Exception as e:
        return {"success": False, "message": f"Couldn't read that calendar: {str(e)[:60]}", "data": {}}
    from agents.friday import friday_agent as fa
    added = 0
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.S):
        sm = re.search(r"SUMMARY:(.+)", block)
        dm = re.search(r"DTSTART[^:]*:(\d{8})(?:T(\d{2})(\d{2}))?", block)
        if not (sm and dm):
            continue
        title = sm.group(1).strip()
        y, mo, d = dm.group(1)[:4], dm.group(1)[4:6], dm.group(1)[6:8]
        hh, mm = dm.group(2) or "09", dm.group(3) or "00"
        when = f"{y}-{mo}-{d} {hh}:{mm}"
        try:
            fa.schedule_event(title, when)
            added += 1
        except Exception:
            pass
    return {"success": True, "message": f"Imported {added} event(s) from the calendar.",
            "data": {"count": added}}
