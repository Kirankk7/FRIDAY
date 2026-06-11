import json
import os
import re
import uuid
import datetime

from core.llm import ask_llm

FRIDAY_FILE = "data/friday_data.json"
os.makedirs("data", exist_ok=True)

_EMPTY = {
    "tasks": [],
    "goals": [],
    "notes": [],
    "health_log": [],
    "reminders": [],
    "habits": [],
    "events": []
}


# ─────────────────────────────────────────
# STORAGE
# ─────────────────────────────────────────

def _load() -> dict:
    if not os.path.exists(FRIDAY_FILE):
        return {k: list(v) for k, v in _EMPTY.items()}
    try:
        with open(FRIDAY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Migration: ensure all keys exist
        for key in _EMPTY:
            if key not in data:
                data[key] = []
        return data
    except Exception:
        return {k: list(v) for k, v in _EMPTY.items()}


def _save(data: dict):
    try:
        with open(FRIDAY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[friday] Save error: {e}")


def _uid() -> str:
    return str(uuid.uuid4())[:6]


def _now() -> str:
    return datetime.datetime.now().isoformat()


def _today() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d")


# ─────────────────────────────────────────
# TASKS
# ─────────────────────────────────────────

def add_task(text: str, priority: str = "normal") -> dict:
    data = _load()
    task = {"id": _uid(), "text": text.strip(), "done": False, "created": _now(), "priority": priority}
    data["tasks"].append(task)
    _save(data)
    return {"success": True, "message": f"Task added, boss: {text}", "data": {"task": task}}


def list_tasks() -> dict:
    data = _load()
    pending = [t for t in data["tasks"] if not t["done"]]
    if not pending:
        return {"success": True, "message": "No pending tasks, boss. Clean slate.", "data": {"tasks": []}}
    lines = [f"{i+1}. {t['text']} [{t['priority']}]" for i, t in enumerate(pending)]
    return {"success": True, "message": "Pending tasks:\n" + "\n".join(lines), "data": {"tasks": pending}}


def complete_task(identifier: str) -> dict:
    data = _load()
    pending = [t for t in data["tasks"] if not t["done"]]
    matched = None
    # Try numeric index
    if identifier.isdigit():
        idx = int(identifier) - 1
        if 0 <= idx < len(pending):
            matched = pending[idx]
    else:
        # Fuzzy text match
        ident_lower = identifier.lower()
        for t in pending:
            if ident_lower in t["text"].lower():
                matched = t
                break
    if not matched:
        return {"success": False, "message": f"No task matching '{identifier}' found.", "data": {}}
    # Mark done in full list
    for t in data["tasks"]:
        if t["id"] == matched["id"]:
            t["done"] = True
    _save(data)
    return {"success": True, "message": f"Done: {matched['text']}. Good work, boss.", "data": {"task": matched}}


def delete_task(identifier: str) -> dict:
    data = _load()
    before = len(data["tasks"])
    if identifier.isdigit():
        pending = [t for t in data["tasks"] if not t["done"]]
        idx = int(identifier) - 1
        if 0 <= idx < len(pending):
            data["tasks"] = [t for t in data["tasks"] if t["id"] != pending[idx]["id"]]
    else:
        ident_lower = identifier.lower()
        data["tasks"] = [t for t in data["tasks"] if ident_lower not in t["text"].lower()]
    removed = before - len(data["tasks"])
    _save(data)
    return {"success": True, "message": f"Removed {removed} task(s).", "data": {}}


# ─────────────────────────────────────────
# GOALS
# ─────────────────────────────────────────

def add_goal(text: str) -> dict:
    data = _load()
    goal = {"id": _uid(), "text": text.strip(), "done": False, "created": _now()}
    data["goals"].append(goal)
    _save(data)
    return {"success": True, "message": f"Goal locked in, boss: {text}", "data": {"goal": goal}}


def list_goals() -> dict:
    data = _load()
    active = [g for g in data["goals"] if not g["done"]]
    if not active:
        return {"success": True, "message": "No active goals. Add one — \"add goal <text>\".", "data": {"goals": []}}
    lines = [f"{i+1}. {g['text']}" for i, g in enumerate(active)]
    return {"success": True, "message": "Active goals:\n" + "\n".join(lines), "data": {"goals": active}}


def complete_goal(identifier: str) -> dict:
    data = _load()
    active = [g for g in data["goals"] if not g["done"]]
    matched = None
    if identifier.isdigit():
        idx = int(identifier) - 1
        if 0 <= idx < len(active):
            matched = active[idx]
    else:
        for g in active:
            if identifier.lower() in g["text"].lower():
                matched = g
                break
    if not matched:
        return {"success": False, "message": f"No goal matching '{identifier}'.", "data": {}}
    for g in data["goals"]:
        if g["id"] == matched["id"]:
            g["done"] = True
    _save(data)
    return {"success": True, "message": f"Goal achieved: {matched['text']}. Let's go, boss.", "data": {}}


# ─────────────────────────────────────────
# NOTES
# ─────────────────────────────────────────

def add_note(text: str) -> dict:
    data = _load()
    note = {"id": _uid(), "text": text.strip(), "created": _now()}
    data["notes"].append(note)
    if len(data["notes"]) > 200:
        data["notes"] = data["notes"][-200:]
    _save(data)
    return {"success": True, "message": "Note saved, boss.", "data": {"note": note}}


def list_notes(n: int = 5) -> dict:
    data = _load()
    recent = data["notes"][-n:]
    if not recent:
        return {"success": True, "message": "No notes yet, boss.", "data": {"notes": []}}
    lines = [f"{i+1}. {note['text'][:120]} ({note['created'][:10]})" for i, note in enumerate(recent)]
    return {"success": True, "message": "Recent notes:\n" + "\n".join(lines), "data": {"notes": recent}}


# ─────────────────────────────────────────
# HEALTH TRACKING
# ─────────────────────────────────────────

def log_health(metric: str, value: str) -> dict:
    data = _load()
    entry = {"metric": metric.lower().strip(), "value": value.strip(), "date": _today(), "time": _now()}
    data["health_log"].append(entry)
    if len(data["health_log"]) > 500:
        data["health_log"] = data["health_log"][-500:]
    _save(data)
    return {"success": True, "message": f"Logged {metric}: {value}. Tracked, boss.", "data": {"entry": entry}}


def show_health(metric: str = None, days: int = 7) -> dict:
    data = _load()
    log = data["health_log"]
    if metric:
        log = [e for e in log if e["metric"] == metric.lower().strip()]
    # Last N days
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    log = [e for e in log if e.get("date", "") >= cutoff]
    if not log:
        return {"success": True, "message": f"No health data{' for '+metric if metric else ''} in last {days} days.", "data": {}}
    lines = [f"{e['date']}: {e['metric']} = {e['value']}" for e in log[-10:]]
    return {"success": True, "message": "Health log:\n" + "\n".join(lines), "data": {"log": log}}


# ─────────────────────────────────────────
# REMINDERS
# ─────────────────────────────────────────

def set_reminder(text: str, minutes: int = 0, hours: int = 0) -> dict:
    data = _load()
    total_minutes = minutes + hours * 60
    if total_minutes <= 0:
        total_minutes = 30  # Default 30 minutes
    due = datetime.datetime.now() + datetime.timedelta(minutes=total_minutes)
    reminder = {
        "id": _uid(),
        "text": text.strip(),
        "due": due.isoformat(),
        "due_str": due.strftime("%H:%M"),
        "fired": False
    }
    data["reminders"].append(reminder)
    _save(data)
    return {
        "success": True,
        "message": f"Reminder set for {due.strftime('%H:%M')}: {text}",
        "data": {"reminder": reminder}
    }


def check_reminders() -> list:
    """Called on each message. Returns list of due reminder texts."""
    data = _load()
    now = datetime.datetime.now()
    fired = []
    changed = False
    for r in data["reminders"]:
        if r.get("fired"):
            continue
        due = datetime.datetime.fromisoformat(r["due"])
        if now >= due:
            fired.append(r["text"])
            r["fired"] = True
            changed = True
    if changed:
        _save(data)
    return fired


def list_reminders() -> dict:
    data = _load()
    pending = [r for r in data["reminders"] if not r.get("fired")]
    if not pending:
        return {"success": True, "message": "No pending reminders, boss.", "data": {}}
    lines = [f"- {r['due_str']}: {r['text']}" for r in pending]
    return {"success": True, "message": "Pending reminders:\n" + "\n".join(lines), "data": {"reminders": pending}}


# ─────────────────────────────────────────
# HABITS
# ─────────────────────────────────────────

def add_habit(name: str) -> dict:
    data = _load()
    existing = [h for h in data["habits"] if h["name"].lower() == name.lower().strip()]
    if existing:
        return {"success": True, "message": f"Habit '{name}' already tracked, boss.", "data": {}}
    habit = {"name": name.strip(), "log": [], "created": _today()}
    data["habits"].append(habit)
    _save(data)
    return {"success": True, "message": f"Tracking habit: {name}. Do it daily, boss.", "data": {"habit": habit}}


def log_habit(name: str) -> dict:
    data = _load()
    today = _today()
    matched = None
    name_lower = name.lower().strip()
    for h in data["habits"]:
        if name_lower in h["name"].lower():
            matched = h
            break
    if not matched:
        # Auto-create
        matched = {"name": name.strip(), "log": [], "created": today}
        data["habits"].append(matched)
    if today not in matched["log"]:
        matched["log"].append(today)
    _save(data)
    streak = _calc_streak(matched["log"])
    return {"success": True, "message": f"Logged: {matched['name']}. Streak: {streak} day(s), boss.", "data": {"streak": streak}}


def _calc_streak(log: list) -> int:
    if not log:
        return 0
    log_sorted = sorted(log, reverse=True)
    streak = 0
    check = datetime.datetime.now().date()
    for date_str in log_sorted:
        d = datetime.date.fromisoformat(date_str)
        if d == check or d == check - datetime.timedelta(days=1):
            streak += 1
            check = d - datetime.timedelta(days=1)
        else:
            break
    return streak


def show_habits() -> dict:
    data = _load()
    if not data["habits"]:
        return {"success": True, "message": "No habits tracked yet, boss. Add one — \"add habit <name>\".", "data": {}}
    lines = []
    for h in data["habits"]:
        streak = _calc_streak(h["log"])
        today_done = _today() in h["log"]
        status = "done today" if today_done else "not done today"
        lines.append(f"{h['name']}: {streak}-day streak ({status})")
    return {"success": True, "message": "Habits:\n" + "\n".join(lines), "data": {}}


# ─────────────────────────────────────────
# PLANNING
# ─────────────────────────────────────────

def plan_day() -> dict:
    data = _load()
    tasks = [t["text"] for t in data["tasks"] if not t["done"]][:8]
    goals = [g["text"] for g in data["goals"] if not g["done"]][:5]
    habits = [h["name"] for h in data["habits"]][:5]

    if not tasks and not goals:
        return {
            "success": True,
            "message": "No tasks or goals set yet, boss. Add some first — \"add task\" or \"add goal\".",
            "data": {}
        }

    context = ""
    if tasks:
        context += "Tasks: " + ", ".join(tasks) + "\n"
    if goals:
        context += "Goals: " + ", ".join(goals) + "\n"
    if habits:
        context += "Habits to maintain: " + ", ".join(habits) + "\n"

    prompt = f"""You are FRIDAY, Tony Stark's AI. Create a practical daily plan for boss.
Keep it tight and actionable. No fluff. Use time blocks.

Context:
{context}
Today: {_today()}

Create a focused daily schedule. Short, punchy, like a smart assistant would present it:"""

    plan = ask_llm(prompt)
    if not plan:
        plan = "\n".join([f"- {t}" for t in tasks])

    return {"success": True, "message": plan, "data": {"tasks": tasks, "goals": goals}}


def plan_week() -> dict:
    data = _load()
    tasks = [t["text"] for t in data["tasks"] if not t["done"]][:10]
    goals = [g["text"] for g in data["goals"] if not g["done"]][:5]

    context = ""
    if tasks:
        context += "Tasks: " + ", ".join(tasks) + "\n"
    if goals:
        context += "Goals: " + ", ".join(goals) + "\n"

    prompt = f"""You are FRIDAY. Create a 7-day weekly plan for boss.
Distribute tasks across the week. Be practical and brief.

Context:
{context}
Week starting: {_today()}

Weekly plan (Monday to Sunday, keep each day short):"""

    plan = ask_llm(prompt)
    if not plan:
        return {"success": False, "message": "LLM unavailable. Add tasks first with \"add task\".", "data": {}}

    return {"success": True, "message": plan, "data": {}}


def study_plan(topic: str) -> dict:
    if not topic:
        return {"success": False, "message": "No study topic given.", "data": {}}

    prompt = f"""You are FRIDAY. Create a structured study plan for: {topic}

Keep it practical. Include:
- Timeline estimate
- Key topics to cover in order
- Resources (types, not specific URLs)
- Daily study goal

Brief and actionable, no fluff:"""

    plan = ask_llm(prompt)
    if not plan:
        return {"success": False, "message": "LLM unavailable.", "data": {}}

    return {"success": True, "message": plan, "data": {"topic": topic}}


# ─────────────────────────────────────────
# CALENDAR — datetime parsing
# ─────────────────────────────────────────

_DAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
         "friday": 4, "saturday": 5, "sunday": 6}

_MONTHS = {"january": 1, "february": 2, "march": 3, "april": 4,
           "may": 5, "june": 6, "july": 7, "august": 8,
           "september": 9, "october": 10, "november": 11, "december": 12}


def _parse_time(time_str: str, base: datetime.datetime) -> datetime.datetime:
    """Parse 'at 3pm', 'at 14:30', 'at noon', 'at midnight' onto a base date."""
    t = time_str.lower().strip()
    if t in ("noon", "12pm", "midday"):
        return base.replace(hour=12, minute=0, second=0, microsecond=0)
    if t in ("midnight", "12am"):
        return base.replace(hour=0, minute=0, second=0, microsecond=0)
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", t)
    if not m:
        return base.replace(hour=9, minute=0, second=0, microsecond=0)
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    meridiem = m.group(3)
    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    return base.replace(hour=hour, minute=minute, second=0, microsecond=0)


def parse_when(text: str) -> datetime.datetime | None:
    """
    Parse natural-language datetime from scheduling text.
    Handles: today/tomorrow/day-name/next-day + optional time.
    Returns None if unparseable.
    """
    now = datetime.datetime.now()
    text = text.lower().strip()
    # Remove "at" prefix for time-only strings
    text_no_at = re.sub(r"^at\s+", "", text)

    # "in X minutes/hours"
    m = re.match(r"in (\d+)\s*(minutes?|hours?)", text)
    if m:
        amount = int(m.group(1))
        if "hour" in m.group(2):
            return now + datetime.timedelta(hours=amount)
        return now + datetime.timedelta(minutes=amount)

    # Extract time part from the string
    time_match = re.search(r"at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?|noon|midnight)", text)
    time_str = time_match.group(1) if time_match else None

    # "today" or just time
    if text.startswith("today") or (not time_match and re.match(r"\d{1,2}", text_no_at)):
        base = now
        return _parse_time(time_str or text_no_at, base)

    # "tomorrow"
    if "tomorrow" in text:
        base = now + datetime.timedelta(days=1)
        return _parse_time(time_str or "9am", base)

    # "next <day>" or just "<day>"
    for day_name, day_num in _DAYS.items():
        if day_name in text:
            current_day = now.weekday()
            days_ahead = day_num - current_day
            if days_ahead <= 0 or "next" in text:
                days_ahead = days_ahead % 7 or 7
            base = now + datetime.timedelta(days=days_ahead)
            return _parse_time(time_str or "9am", base)

    # "on <month> <day>" e.g. "on june 10"
    m = re.search(r"(?:on\s+)?(\w+)\s+(\d{1,2})(?:st|nd|rd|th)?", text)
    if m and m.group(1) in _MONTHS:
        month = _MONTHS[m.group(1)]
        day = int(m.group(2))
        year = now.year if month >= now.month else now.year + 1
        base = now.replace(year=year, month=month, day=day)
        return _parse_time(time_str or "9am", base)

    # Just a time?
    if time_str:
        return _parse_time(time_str, now)

    return None


def _fmt_dt(dt: datetime.datetime) -> str:
    return dt.strftime("%a %b %d at %H:%M")


# ─────────────────────────────────────────
# CALENDAR — CRUD
# ─────────────────────────────────────────

def schedule_event(title: str, when_str: str, duration_min: int = 60, notes: str = "") -> dict:
    if not title or not when_str:
        return {"success": False, "message": "Need a title and time, boss.", "data": {}}

    dt = parse_when(when_str)
    if not dt:
        return {"success": False, "message": f"Couldn't parse time: '{when_str}'. Try 'tomorrow at 3pm' or 'monday at 10am'.", "data": {}}

    data = _load()
    event = {
        "id": _uid(),
        "title": title.strip(),
        "datetime": dt.isoformat(),
        "date": dt.strftime("%Y-%m-%d"),
        "time": dt.strftime("%H:%M"),
        "duration_min": duration_min,
        "notes": notes,
        "created": _now()
    }
    data["events"].append(event)
    _save(data)
    return {
        "success": True,
        "message": f"Scheduled: {title} — {_fmt_dt(dt)} ({duration_min} min).",
        "data": {"event": event}
    }


def list_events_for_date(date_ref: str = "today") -> dict:
    data = _load()
    now = datetime.datetime.now()

    if date_ref == "today":
        target = now.strftime("%Y-%m-%d")
        label = "Today"
    elif date_ref == "tomorrow":
        target = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        label = "Tomorrow"
    else:
        # Try parsing as weekday or date string
        dt = parse_when(date_ref)
        if dt:
            target = dt.strftime("%Y-%m-%d")
            label = dt.strftime("%A %b %d")
        else:
            target = date_ref
            label = date_ref

    events = sorted(
        [e for e in data["events"] if e["date"] == target],
        key=lambda e: e["time"]
    )

    if not events:
        return {"success": True, "message": f"Nothing scheduled for {label}, boss.", "data": {"events": []}}

    lines = [f"{e['time']} — {e['title']} ({e['duration_min']}min)" for e in events]
    return {
        "success": True,
        "message": f"{label}'s schedule:\n" + "\n".join(lines),
        "data": {"events": events, "date": target}
    }


def list_week_events() -> dict:
    data = _load()
    now = datetime.datetime.now()
    week_dates = [(now + datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    events = sorted(
        [e for e in data["events"] if e["date"] in week_dates],
        key=lambda e: e["datetime"]
    )
    if not events:
        return {"success": True, "message": "Nothing scheduled this week, boss.", "data": {}}
    lines = []
    prev_date = None
    for e in events:
        if e["date"] != prev_date:
            dt = datetime.datetime.fromisoformat(e["datetime"])
            lines.append(f"\n{dt.strftime('%A %b %d')}:")
            prev_date = e["date"]
        lines.append(f"  {e['time']} — {e['title']}")
    return {"success": True, "message": "This week:" + "\n".join(lines), "data": {"events": events}}


def next_event() -> dict:
    data = _load()
    now = datetime.datetime.now()
    upcoming = sorted(
        [e for e in data["events"] if datetime.datetime.fromisoformat(e["datetime"]) > now],
        key=lambda e: e["datetime"]
    )
    if not upcoming:
        return {"success": True, "message": "No upcoming events, boss.", "data": {}}
    e = upcoming[0]
    dt = datetime.datetime.fromisoformat(e["datetime"])
    delta = dt - now
    hours = int(delta.total_seconds() // 3600)
    mins = int((delta.total_seconds() % 3600) // 60)
    time_str = f"in {hours}h {mins}m" if hours else f"in {mins}m"
    return {
        "success": True,
        "message": f"Next: {e['title']} — {_fmt_dt(dt)} ({time_str})",
        "data": {"event": e}
    }


def delete_event(identifier: str) -> dict:
    data = _load()
    before = len(data["events"])
    ident_lower = identifier.lower().strip()
    data["events"] = [e for e in data["events"] if ident_lower not in e["title"].lower() and e["id"] != ident_lower]
    removed = before - len(data["events"])
    _save(data)
    if removed:
        return {"success": True, "message": f"Removed {removed} event(s), boss.", "data": {}}
    return {"success": False, "message": f"No event matching '{identifier}' found.", "data": {}}


def set_reminder_at(text: str, when_str: str) -> dict:
    """Set reminder at absolute time — upgrade of set_reminder for Phase 14."""
    dt = parse_when(when_str)
    if not dt:
        return {"success": False, "message": f"Couldn't parse time: '{when_str}'.", "data": {}}
    data = _load()
    reminder = {
        "id": _uid(),
        "text": text.strip(),
        "due": dt.isoformat(),
        "due_str": dt.strftime("%H:%M"),
        "fired": False
    }
    data["reminders"].append(reminder)
    _save(data)
    return {"success": True, "message": f"Reminder set for {_fmt_dt(dt)}: {text}", "data": {"reminder": reminder}}


# ─────────────────────────────────────────
# PHASE 42 — UTILITY FUNCTIONS
# ─────────────────────────────────────────

def generate_password(length: int = 20, symbols: bool = True) -> dict:
    """Cryptographically secure random password. Uses stdlib secrets."""
    import secrets, string
    length = max(8, min(length, 128))
    chars = string.ascii_letters + string.digits
    if symbols:
        chars += "!@#$%^&*()-_=+[]{}|;:,.<>?"
    password = "".join(secrets.choice(chars) for _ in range(length))
    # Ensure at least one of each required category
    while (
        not any(c in string.ascii_uppercase for c in password) or
        not any(c in string.ascii_lowercase for c in password) or
        not any(c in string.digits for c in password)
    ):
        password = "".join(secrets.choice(chars) for _ in range(length))
    return {
        "success": True,
        "message": f"Generated {length}-char password: {password}",
        "data": {"password": password, "length": length, "symbols": symbols}
    }


def calculate_calories(
    gender: str = "",
    age: int = 0,
    height_cm: float = 0,
    weight_kg: float = 0,
    activity: str = "moderate",
    goal: str = "maintain"
) -> dict:
    """
    BMR (Mifflin-St Jeor) + TDEE calculator.
    Activity: sedentary, light, moderate, active, very_active
    Goal: lose, maintain, gain
    """
    # Try to get stats from personal agent if not provided
    if not all([gender, age, height_cm, weight_kg]):
        try:
            from agents.personal.personal_agent import personal_agent as _pa
            facts = _pa.get_all().get("data", {}).get("facts", {})
            if not gender:
                gender = facts.get("gender", "")
            if not age and "age" in facts:
                try:
                    age = int(str(facts["age"]).split()[0])
                except Exception:
                    pass
            if not height_cm and "height" in facts:
                try:
                    h = str(facts["height"])
                    if "cm" in h:
                        height_cm = float(h.replace("cm","").strip())
                except Exception:
                    pass
            if not weight_kg and "weight" in facts:
                try:
                    w = str(facts["weight"])
                    if "kg" in w:
                        weight_kg = float(w.replace("kg","").strip())
                except Exception:
                    pass
        except Exception:
            pass

    if not all([gender, age, height_cm, weight_kg]):
        missing = []
        if not gender:   missing.append("gender (male/female)")
        if not age:      missing.append("age")
        if not height_cm: missing.append("height in cm")
        if not weight_kg: missing.append("weight in kg")
        return {
            "success": False,
            "message": f"Need your {', '.join(missing)}. Say: 'my gender is male, age 25, height 175cm, weight 70kg'",
            "data": {}
        }

    # Mifflin-St Jeor BMR
    g = gender.lower().strip()
    if g in ("male", "man", "m"):
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

    activity_factors = {
        "sedentary": 1.2, "light": 1.375, "moderate": 1.55,
        "active": 1.725, "very_active": 1.9, "very active": 1.9
    }
    factor = activity_factors.get(activity.lower().replace("-", "_"), 1.55)
    tdee = round(bmr * factor)
    bmr = round(bmr)

    goal_calories = {
        "lose": tdee - 500,
        "lose weight": tdee - 500,
        "cut": tdee - 500,
        "maintain": tdee,
        "maintain weight": tdee,
        "gain": tdee + 300,
        "bulk": tdee + 300,
        "build muscle": tdee + 300,
    }
    daily = goal_calories.get(goal.lower(), tdee)

    # Macro split (protein 30%, carbs 40%, fat 30%)
    protein_g = round(daily * 0.30 / 4)
    carbs_g   = round(daily * 0.40 / 4)
    fat_g     = round(daily * 0.30 / 9)

    goal_label = "lose weight" if "lose" in goal.lower() else "gain muscle" if "gain" in goal.lower() or "bulk" in goal.lower() else "maintain"

    return {
        "success": True,
        "message": (
            f"BMR {bmr} kcal/day. TDEE {tdee} kcal/day ({activity} activity). "
            f"To {goal_label}: {daily} kcal/day. "
            f"Macros: {protein_g}g protein, {carbs_g}g carbs, {fat_g}g fat."
        ),
        "data": {"bmr": bmr, "tdee": tdee, "daily_goal": daily, "protein_g": protein_g, "carbs_g": carbs_g, "fat_g": fat_g}
    }


def plan_workout(focus: str = "full body", fitness_level: str = "intermediate") -> dict:
    """
    Push/pull/legs style workout plan based on focus and fitness level.
    Focus: push, pull, legs, full body, chest, back, arms, shoulders
    Level: beginner, intermediate, advanced
    """
    _plans = {
        "push": {
            "beginner":     ["Push-ups 3x10", "Shoulder press (light) 3x12", "Tricep dips 3x10", "Lateral raises 3x12"],
            "intermediate": ["Bench press 4x8", "Overhead press 3x10", "Incline dumbbell press 3x12", "Lateral raises 3x15", "Tricep pushdown 3x12"],
            "advanced":     ["Bench press 5x5", "Overhead press 4x6", "Incline press 4x10", "Dips 4x12", "Lateral raises 4x15", "Tricep skull crushers 3x12"],
        },
        "pull": {
            "beginner":     ["Assisted pull-ups 3x8", "Dumbbell rows 3x12", "Face pulls 3x15", "Bicep curls 3x12"],
            "intermediate": ["Pull-ups 4x8", "Barbell rows 3x10", "Lat pulldown 3x12", "Cable rows 3x12", "Hammer curls 3x12"],
            "advanced":     ["Weighted pull-ups 4x6", "Deadlift 4x5", "Barbell rows 4x8", "Face pulls 4x15", "Barbell curls 4x10"],
        },
        "legs": {
            "beginner":     ["Bodyweight squats 3x15", "Lunges 3x12 each", "Glute bridges 3x15", "Calf raises 3x20"],
            "intermediate": ["Squat 4x8", "Romanian deadlift 3x10", "Leg press 3x12", "Leg curl 3x12", "Calf raises 4x20"],
            "advanced":     ["Back squat 5x5", "Front squat 3x8", "Romanian deadlift 4x8", "Leg press 4x12", "Nordic curl 3x8", "Calf raises 4x25"],
        },
        "full body": {
            "beginner":     ["Squat 3x10", "Push-ups 3x10", "Dumbbell rows 3x10", "Lunges 2x12", "Plank 3x30s"],
            "intermediate": ["Squat 3x8", "Bench press 3x8", "Deadlift 3x6", "Pull-ups 3x8", "OHP 3x10", "Plank 3x45s"],
            "advanced":     ["Squat 4x6", "Bench 4x6", "Deadlift 3x5", "Weighted pull-ups 4x6", "OHP 4x8", "Romanian DL 3x8"],
        },
        "chest": {
            "beginner":     ["Push-ups 4x12", "Dumbbell flyes 3x12", "Incline push-ups 3x12"],
            "intermediate": ["Bench press 4x8", "Incline dumbbell press 3x12", "Dumbbell flyes 3x12", "Cable crossovers 3x15"],
            "advanced":     ["Bench press 5x5", "Incline press 4x8", "Weighted dips 4x10", "Cable crossovers 4x15", "Pec deck 3x15"],
        },
        "back": {
            "beginner":     ["Assisted pull-ups 3x8", "Dumbbell rows 3x12", "Superman holds 3x10"],
            "intermediate": ["Pull-ups 4x8", "Barbell rows 4x8", "Lat pulldown 3x12", "Face pulls 3x15"],
            "advanced":     ["Weighted pull-ups 4x8", "Barbell rows 4x6", "T-bar rows 3x10", "Straight-arm pulldown 3x15"],
        },
    }

    focus_lower = focus.lower().strip()
    level_lower = fitness_level.lower().strip()

    # Find best matching plan
    matched_focus = "full body"
    for key in _plans:
        if key in focus_lower or focus_lower in key:
            matched_focus = key
            break

    matched_level = "intermediate"
    if "begin" in level_lower or "new" in level_lower:
        matched_level = "beginner"
    elif "adv" in level_lower:
        matched_level = "advanced"

    exercises = _plans[matched_focus][matched_level]
    rest_s = {"beginner": 60, "intermediate": 90, "advanced": 120}[matched_level]

    return {
        "success": True,
        "message": (
            f"{matched_focus.title()} workout ({matched_level}): "
            + " | ".join(exercises)
            + f" | Rest {rest_s}s between sets."
        ),
        "data": {
            "focus": matched_focus,
            "level": matched_level,
            "exercises": exercises,
            "rest_seconds": rest_s
        }
    }


# ─────────────────────────────────────────
# AGENT ENTRYPOINT
# ─────────────────────────────────────────

class FridayAgent:

    def run(self, input_text: str, action: str = None, parameters: dict = None) -> dict:
        try:
            parameters = parameters or {}
            if not action:
                return {"success": False, "message": "No Friday action specified.", "data": {}}

            if action == "add_task":
                return add_task(parameters.get("text", input_text), parameters.get("priority", "normal"))
            elif action == "list_tasks":
                return list_tasks()
            elif action == "complete_task":
                return complete_task(parameters.get("identifier", "1"))
            elif action == "delete_task":
                return delete_task(parameters.get("identifier", ""))

            elif action == "add_goal":
                return add_goal(parameters.get("text", input_text))
            elif action == "list_goals":
                return list_goals()
            elif action == "complete_goal":
                return complete_goal(parameters.get("identifier", ""))

            elif action == "add_note":
                return add_note(parameters.get("text", input_text))
            elif action == "list_notes":
                return list_notes(parameters.get("n", 5))

            elif action == "log_health":
                return log_health(parameters.get("metric", ""), parameters.get("value", ""))
            elif action == "show_health":
                return show_health(parameters.get("metric"), parameters.get("days", 7))

            elif action == "set_reminder":
                return set_reminder(
                    parameters.get("text", input_text),
                    parameters.get("minutes", 0),
                    parameters.get("hours", 0)
                )
            elif action == "list_reminders":
                return list_reminders()

            elif action == "add_habit":
                return add_habit(parameters.get("name", input_text))
            elif action == "log_habit":
                return log_habit(parameters.get("name", input_text))
            elif action == "show_habits":
                return show_habits()

            elif action == "plan_day":
                return plan_day()
            elif action == "plan_week":
                return plan_week()
            elif action == "study_plan":
                return study_plan(parameters.get("topic", input_text))

            # Calendar actions
            elif action == "schedule_event":
                return schedule_event(
                    parameters.get("title", input_text),
                    parameters.get("when", "tomorrow at 9am"),
                    parameters.get("duration_min", 60),
                    parameters.get("notes", "")
                )
            elif action == "list_events":
                return list_events_for_date(parameters.get("date_ref", "today"))
            elif action == "list_week_events":
                return list_week_events()
            elif action == "next_event":
                return next_event()
            elif action == "delete_event":
                return delete_event(parameters.get("identifier", ""))
            elif action == "set_reminder_at":
                return set_reminder_at(
                    parameters.get("text", input_text),
                    parameters.get("when", "")
                )

            elif action == "generate_password":
                return generate_password(
                    parameters.get("length", 20),
                    parameters.get("symbols", True)
                )

            elif action == "calculate_calories":
                return calculate_calories(
                    parameters.get("gender", ""),
                    parameters.get("age", 0),
                    parameters.get("height_cm", 0),
                    parameters.get("weight_kg", 0),
                    parameters.get("activity", "moderate"),
                    parameters.get("goal", "maintain")
                )

            elif action == "plan_workout":
                return plan_workout(
                    parameters.get("focus", "full body"),
                    parameters.get("fitness_level", "intermediate")
                )

            return {"success": False, "message": f"Unknown Friday action: {action}", "data": {}}

        except Exception as e:
            return {"success": False, "message": f"Friday error: {str(e)}", "data": {}}


friday_agent = FridayAgent()
