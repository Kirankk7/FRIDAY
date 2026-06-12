"""
Phase 26 — Autonomous Scheduler
Background thread fires agent tasks on a schedule.
Tasks persist in data/scheduled_tasks.json.
"""

import os
import json
import uuid
import time
import threading
import datetime
import re

TASKS_FILE = "data/scheduled_tasks.json"
os.makedirs("data", exist_ok=True)

_lock = threading.Lock()


# ─────────────────────────────────────────
# SCHEDULE PARSING
# ─────────────────────────────────────────
_TIME_PATTERNS = [
    # "every morning" → 09:00 daily
    (r"every morning",         "daily", "09:00"),
    (r"every evening",         "daily", "18:00"),
    (r"every night",           "daily", "22:00"),
    (r"every noon",            "daily", "12:00"),
    # "every day at 3pm" / "daily at 09:30"
    (r"(?:every day|daily) at (\d{1,2})(?::(\d{2}))?\s*(am|pm)?",  "daily_at", None),
    # "every X hours"
    (r"every (\d+) hours?",    "interval_h", None),
    # "every X minutes"
    (r"every (\d+) mins?(?:utes?)?", "interval_m", None),
    # "every hour"
    (r"every hour",            "interval_h", "1"),
    # "every 30 minutes" (duplicate catch)
    (r"every half hour",       "interval_m", "30"),
    # "every day" / "daily" (fallback)
    (r"(?:every day|daily)",   "daily", "09:00"),
    # "every week" / "weekly"
    (r"(?:every week|weekly)", "weekly", "09:00"),
]


def _parse_schedule(raw: str):
    """
    Extract schedule type + time from raw text.
    Returns (schedule_type, schedule_time, task_text_remaining).
    schedule_type: "daily" | "interval" | "weekly"
    schedule_time: "HH:MM" for daily/weekly, int minutes for interval
    """
    text = raw.lower().strip()

    for pattern, stype, default_time in _TIME_PATTERNS:
        m = re.search(pattern, text)
        if not m:
            continue

        # Remove matched schedule phrase from text to get the task portion
        task_text = re.sub(pattern, "", text, count=1).strip()
        task_text = re.sub(r"^(schedule|set up|create a? task|to|and)\s+", "", task_text).strip()

        if stype == "daily_at":
            hour = int(m.group(1))
            minute = int(m.group(2)) if m.group(2) else 0
            ampm = m.group(3)
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            return "daily", f"{hour:02d}:{minute:02d}", task_text

        if stype == "interval_h":
            hours = int(m.group(1)) if not default_time else int(default_time)
            return "interval", hours * 60, task_text

        if stype == "interval_m":
            mins = int(m.group(1)) if not default_time else int(default_time)
            return "interval", mins, task_text

        return stype, default_time, task_text

    return None, None, raw


def _next_run(stype: str, stime) -> str:
    """Compute ISO next_run datetime string."""
    now = datetime.datetime.now()

    if stype == "interval":
        return (now + datetime.timedelta(minutes=int(stime))).isoformat()

    if stype in ("daily", "weekly"):
        h, m = map(int, stime.split(":"))
        candidate = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if candidate <= now:
            candidate += datetime.timedelta(days=1)
        if stype == "weekly":
            # Advance to next Monday if not already
            days_ahead = (7 - candidate.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            candidate += datetime.timedelta(days=days_ahead)
        return candidate.isoformat()

    return (now + datetime.timedelta(minutes=60)).isoformat()


def _advance_next_run(task: dict) -> str:
    """Compute next_run after a task fires."""
    stype = task["schedule_type"]
    stime = task["schedule_time"]

    if stype == "interval":
        return (datetime.datetime.now() + datetime.timedelta(minutes=int(stime))).isoformat()

    if stype in ("daily", "weekly"):
        h, m = map(int, str(stime).split(":"))
        base = datetime.datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
        delta = datetime.timedelta(days=7 if stype == "weekly" else 1)
        next_dt = base + delta
        return next_dt.isoformat()

    return (datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat()


# ─────────────────────────────────────────
# PERSISTENCE
# ─────────────────────────────────────────
def _load() -> list:
    if not os.path.exists(TASKS_FILE):
        return []
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save(tasks: list):
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)


# ─────────────────────────────────────────
# SCHEDULER CLASS
# ─────────────────────────────────────────
class Scheduler:

    def __init__(self):
        self._thread = None
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[scheduler] Started — background task runner active")

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            try:
                self._check_due()
            except Exception as e:
                print(f"[scheduler] Loop error: {e}")
            # Phase 61 — proactive engine (reminders/digest/alerts), self-paced
            try:
                from core.proactive_engine import tick
                tick()
            except Exception as e:
                print(f"[scheduler] proactive tick error: {e}")
            time.sleep(30)  # Check every 30 seconds

    def _check_due(self):
        with _lock:
            tasks = _load()
        now = datetime.datetime.now()

        for task in tasks:
            if not task.get("enabled", True):
                continue
            next_run_str = task.get("next_run")
            if not next_run_str:
                continue
            try:
                next_run = datetime.datetime.fromisoformat(next_run_str)
            except Exception:
                continue

            if now >= next_run:
                print(f"[scheduler] Firing task: {task['name']}")
                self._fire(task)

                task["last_run"] = now.isoformat()
                task["next_run"] = _advance_next_run(task)

                with _lock:
                    tasks = _load()
                    for i, t in enumerate(tasks):
                        if t["id"] == task["id"]:
                            tasks[i] = task
                            break
                    _save(tasks)

    def _fire(self, task: dict):
        """Execute task tool/action and speak result."""
        try:
            from core.tools_registry import execute_tool
            from core.voice import speak_async
            from core.state import set_last_agent, set_last_action
            from core.speech_cleaner import clean_response

            tool = task["tool"]
            action = task["action"]
            params = task.get("parameters", {})

            set_last_agent(tool)
            set_last_action(action)

            result = execute_tool(tool_name=tool, input_text="", action=action, parameters=params)
            msg = result.get("message", "Task completed.")
            cleaned = clean_response(msg)

            voice_msg = f"Scheduled task: {task['name']}. {cleaned[:400]}"
            speak_async(voice_msg, agent=tool)

            # Auto-save result to EDITH memory
            try:
                from core.tools_registry import execute_tool as _et
                _et(
                    tool_name="edith",
                    input_text="",
                    action="store_memory",
                    parameters={
                        "content": f"[{task['name']}] {cleaned[:800]}",
                        "label": f"schedule_{task['name'].replace(' ', '_')}"
                    }
                )
            except Exception:
                pass

            print(f"[scheduler] Task '{task['name']}' fired OK.")

        except Exception as e:
            print(f"[scheduler] Fire error for '{task.get('name')}': {e}")

    # ─────────────────────────────────────
    # ADD TASK
    # ─────────────────────────────────────
    def add_task(self, raw: str, tool: str = None, action: str = None, parameters: dict = None) -> dict:
        """
        Parse raw text or use explicit tool/action/parameters.
        If tool not provided, parse schedule + route task text.
        """
        stype, stime, task_text = _parse_schedule(raw)

        if not stype:
            return {
                "success": False,
                "message": "Could not parse schedule. Try: 'every morning', 'every hour', 'daily at 3pm'.",
                "data": {}
            }

        # Route task text to get tool/action/params if not explicit
        if not tool:
            try:
                from core.router import route_single_intent
                decision = route_single_intent(task_text)
                if decision and decision.get("tool") != "chat":
                    tool = decision["tool"]
                    action = decision["action"]
                    parameters = decision.get("parameters", {})
                else:
                    return {
                        "success": False,
                        "message": f"Could not understand task: '{task_text}'. Be more specific.",
                        "data": {}
                    }
            except Exception as e:
                return {"success": False, "message": f"Task routing failed: {e}", "data": {}}

        task_id = str(uuid.uuid4())[:8]
        name = task_text[:50].strip() or f"task_{task_id}"

        task = {
            "id": task_id,
            "name": name,
            "raw": raw,
            "schedule_type": stype,
            "schedule_time": stime,
            "tool": tool,
            "action": action,
            "parameters": parameters or {},
            "last_run": None,
            "next_run": _next_run(stype, stime),
            "enabled": True,
            "created": datetime.datetime.now().isoformat()
        }

        with _lock:
            tasks = _load()
            tasks.append(task)
            _save(tasks)

        # Human-readable schedule description
        if stype == "interval":
            sched_str = f"every {stime} minutes"
        elif stype == "daily":
            sched_str = f"daily at {stime}"
        elif stype == "weekly":
            sched_str = f"weekly on Mondays at {stime}"
        else:
            sched_str = str(stime)

        next_dt = datetime.datetime.fromisoformat(task["next_run"])
        next_str = next_dt.strftime("%a %b %d at %H:%M")

        return {
            "success": True,
            "message": f"Scheduled '{name}' to run {sched_str}. Next run: {next_str}.",
            "data": task
        }

    # ─────────────────────────────────────
    # LIST TASKS
    # ─────────────────────────────────────
    def list_tasks(self) -> dict:
        tasks = _load()
        if not tasks:
            return {"success": True, "message": "No scheduled tasks. Say 'every morning scan homelab' to add one.", "data": {"tasks": []}}

        lines = []
        for t in tasks:
            status = "enabled" if t.get("enabled", True) else "paused"
            next_run = t.get("next_run", "?")
            try:
                next_dt = datetime.datetime.fromisoformat(next_run).strftime("%a %H:%M")
            except Exception:
                next_dt = next_run
            lines.append(f"  [{t['id']}] {t['name']} — {status}, next: {next_dt}")

        msg = f"Scheduled tasks ({len(tasks)}):\n" + "\n".join(lines)
        return {"success": True, "message": msg, "data": {"tasks": tasks}}

    # ─────────────────────────────────────
    # REMOVE TASK
    # ─────────────────────────────────────
    def remove_task(self, name_or_id: str) -> dict:
        with _lock:
            tasks = _load()
            before = len(tasks)
            tasks = [t for t in tasks if t["id"] != name_or_id and name_or_id.lower() not in t["name"].lower()]
            if len(tasks) == before:
                return {"success": False, "message": f"No task found matching '{name_or_id}'.", "data": {}}
            _save(tasks)
        removed = before - len(tasks)
        return {"success": True, "message": f"Removed {removed} scheduled task(s).", "data": {}}

    # ─────────────────────────────────────
    # PAUSE / RESUME
    # ─────────────────────────────────────
    def pause_task(self, name_or_id: str) -> dict:
        return self._set_enabled(name_or_id, False)

    def resume_task(self, name_or_id: str) -> dict:
        return self._set_enabled(name_or_id, True)

    def _set_enabled(self, name_or_id: str, enabled: bool) -> dict:
        with _lock:
            tasks = _load()
            found = False
            for t in tasks:
                if t["id"] == name_or_id or name_or_id.lower() in t["name"].lower():
                    t["enabled"] = enabled
                    found = True
            if not found:
                return {"success": False, "message": f"Task '{name_or_id}' not found.", "data": {}}
            _save(tasks)
        state = "resumed" if enabled else "paused"
        return {"success": True, "message": f"Task '{name_or_id}' {state}.", "data": {}}

    # ─────────────────────────────────────
    # STANDARD RUN INTERFACE
    # ─────────────────────────────────────
    def run(self, input_text: str = "", action: str = None, parameters: dict = None) -> dict:
        parameters = parameters or {}

        if action == "add_task":
            return self.add_task(
                raw=parameters.get("raw", input_text),
                tool=parameters.get("tool"),
                action=parameters.get("task_action"),
                parameters=parameters.get("task_parameters", {})
            )

        if action == "list_tasks":
            return self.list_tasks()

        if action == "remove_task":
            return self.remove_task(parameters.get("name", ""))

        if action == "pause_task":
            return self.pause_task(parameters.get("name", ""))

        if action == "resume_task":
            return self.resume_task(parameters.get("name", ""))

        return {"success": False, "message": f"Unknown scheduler action: {action}", "data": {}}


# Singleton
scheduler = Scheduler()
