"""Router group — friday personal assistant (tasks/notes/goals/reminders/health/habits/calendar). Extracted VERBATIM from route_single_intent,
same chain position, order preserved. Uses only text/text_raw. Move only — no logic changes.
"""
import re
import os


def try_route(text, text_raw):
    # =====================================
    # FRIDAY — PERSONAL ASSISTANT
    # =====================================

    # ── Tasks ──
    _m = re.match(r"(?:add (?:a )?task|todo|add to (?:my )?(?:list|tasks?)):?\s+(.+)", text)
    if _m:
        return {"tool": "friday", "action": "add_task", "parameters": {"text": _m.group(1).strip()}, "confidence": 0.99}

    if text in ("list tasks", "show tasks", "my tasks", "what are my tasks", "show my tasks", "task list",
                "list my tasks", "todo list", "what's on my todo list", "whats on my todo list"):
        return {"tool": "friday", "action": "list_tasks", "parameters": {}, "confidence": 0.99}

    _m = re.match(r"(?:done|complete|finish|completed?|mark done)\s+(?:task\s+)?(.+)", text)
    if _m:
        return {"tool": "friday", "action": "complete_task", "parameters": {"identifier": _m.group(1).strip()}, "confidence": 0.99}

    _m = re.match(r"(?:delete|remove)\s+task\s+(.+)", text)
    if _m:
        return {"tool": "friday", "action": "delete_task", "parameters": {"identifier": _m.group(1).strip()}, "confidence": 0.99}

    # ── Goals ──
    _m = re.match(r"(?:add (?:a )?goal|my goal is|set (?:a )?goal|goal:)\s+(.+)", text)
    if _m:
        return {"tool": "friday", "action": "add_goal", "parameters": {"text": _m.group(1).strip()}, "confidence": 0.99}

    if text in ("list goals", "show goals", "my goals", "what are my goals", "list my goals"):
        return {"tool": "friday", "action": "list_goals", "parameters": {}, "confidence": 0.99}

    _m = re.match(r"(?:achieved?|completed?) goal\s+(.+)", text)
    if _m:
        return {"tool": "friday", "action": "complete_goal", "parameters": {"identifier": _m.group(1).strip()}, "confidence": 0.99}

    # ── Notes ──
    _m = re.match(r"(?:add (?:a )?note|note:|note to self:?|write this down:?)\s+(.+)", text)
    if _m:
        return {"tool": "friday", "action": "add_note", "parameters": {"text": _m.group(1).strip()}, "confidence": 0.99}

    if text in ("list notes", "show notes", "my notes", "show my notes", "list my notes"):
        return {"tool": "friday", "action": "list_notes", "parameters": {}, "confidence": 0.99}

    # ── Health tracking ──
    _m = re.match(r"(?:log|track) (?:my )?weight\s+(.+)", text)
    if _m:
        return {"tool": "friday", "action": "log_health", "parameters": {"metric": "weight", "value": _m.group(1).strip()}, "confidence": 0.99}

    _m = re.match(r"weight:?\s+(\d[\d.]*\s*(?:kg|lbs?|pounds?)?)", text)
    if _m:
        return {"tool": "friday", "action": "log_health", "parameters": {"metric": "weight", "value": _m.group(1).strip()}, "confidence": 0.99}

    _m = re.match(r"(?:log|track) (?:workout|exercise|gym|run|running)\s*(.*)", text)
    if _m:
        val = _m.group(1).strip() or "workout done"
        return {"tool": "friday", "action": "log_health", "parameters": {"metric": "workout", "value": val}, "confidence": 0.99}

    if text in ("i worked out", "workout done", "gym done", "done gym", "logged workout"):
        return {"tool": "friday", "action": "log_health", "parameters": {"metric": "workout", "value": "done"}, "confidence": 0.99}

    _m = re.match(r"(?:log|track) sleep\s+(.+)", text)
    if _m:
        return {"tool": "friday", "action": "log_health", "parameters": {"metric": "sleep", "value": _m.group(1).strip()}, "confidence": 0.99}

    if text in ("show health", "health stats", "my health", "health log", "show health stats"):
        return {"tool": "friday", "action": "show_health", "parameters": {}, "confidence": 0.99}

    _m = re.match(r"show (\w+) stats?", text)
    if _m and _m.group(1) in ("weight", "workout", "sleep", "calories", "health"):
        return {"tool": "friday", "action": "show_health", "parameters": {"metric": _m.group(1)}, "confidence": 0.99}

    # ── Reminders ──
    # "remind me at <time> to <text>" — absolute time (must check BEFORE generic "remind me to")
    _m = re.match(r"remind me at (.+?) to (.+)", text)
    if _m:
        return {"tool": "friday", "action": "set_reminder_at",
                "parameters": {"when": _m.group(1).strip(), "text": _m.group(2).strip()}, "confidence": 0.99}

    # "remind me in X minutes to do Y" / "remind me to do Y in X minutes"
    _m = re.match(r"remind me (?:in (\d+) (minutes?|hours?) (?:to )?(.+)|to (.+) in (\d+) (minutes?|hours?))", text)
    if _m:
        if _m.group(1):  # "in X min to Y"
            amount = int(_m.group(1))
            unit = _m.group(2)
            msg = _m.group(3).strip()
        else:  # "to Y in X min"
            msg = _m.group(4).strip()
            amount = int(_m.group(5))
            unit = _m.group(6)
        mins = amount if "min" in unit else 0
        hrs = amount if "hour" in unit else 0
        return {"tool": "friday", "action": "set_reminder", "parameters": {"text": msg, "minutes": mins, "hours": hrs}, "confidence": 0.99}

    # "remind me to X" / "set a reminder to X" (default 30 min)
    _m = re.match(r"(?:remind me (?:to )?|set (?:a |an )?reminder (?:to |for )?|create (?:a )?reminder (?:to )?)(.+)", text)
    if _m and not any(x in text for x in ["know about", "remember about"]):
        return {"tool": "friday", "action": "set_reminder", "parameters": {"text": _m.group(1).strip(), "minutes": 30}, "confidence": 0.99}

    if text in ("list reminders", "show reminders", "my reminders", "pending reminders"):
        return {"tool": "friday", "action": "list_reminders", "parameters": {}, "confidence": 0.99}

    # ── Habits ──
    _m = re.match(r"(?:add habit|track habit|new habit):?\s+(.+)", text)
    if _m:
        return {"tool": "friday", "action": "add_habit", "parameters": {"name": _m.group(1).strip()}, "confidence": 0.99}

    _m = re.match(r"(?:did|done|completed?|log habit|habit done):?\s+(.+)", text)
    if _m and "task" not in text:
        return {"tool": "friday", "action": "log_habit", "parameters": {"name": _m.group(1).strip()}, "confidence": 0.99}

    if text in ("show habits", "my habits", "habit tracker", "habits"):
        return {"tool": "friday", "action": "show_habits", "parameters": {}, "confidence": 0.99}

    # ── Calendar ──
    # "schedule <title> [for/on/at] <when>"
    _m = re.match(r"schedule (?:a )?(?:meeting |call |event |appointment )?(?:with .+? )?(.+?) (?:for|on|at) (.+)", text)
    if _m:
        return {"tool": "friday", "action": "schedule_event",
                "parameters": {"title": _m.group(1).strip(), "when": _m.group(2).strip()}, "confidence": 0.99}

    # "add event <title> <when>"
    _m = re.match(r"add (?:event|meeting|appointment) (.+?) (?:for|on|at) (.+)", text)
    if _m:
        return {"tool": "friday", "action": "schedule_event",
                "parameters": {"title": _m.group(1).strip(), "when": _m.group(2).strip()}, "confidence": 0.99}

    # "what do i have today/tomorrow/this week/on monday/..."
    _m = re.match(r"what (?:do i have|(?:is )?(?:on my )?(?:calendar|schedule)) (?:for |on )?(today|tomorrow|this week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)", text)
    if _m:
        ref = _m.group(1)
        if ref == "this week":
            return {"tool": "friday", "action": "list_week_events", "parameters": {}, "confidence": 0.99}
        return {"tool": "friday", "action": "list_events", "parameters": {"date_ref": ref}, "confidence": 0.99}

    if text in ("show calendar", "show schedule", "my schedule", "today's schedule", "what's today",
                "whats today", "show today", "calendar today"):
        return {"tool": "friday", "action": "list_events", "parameters": {"date_ref": "today"}, "confidence": 0.99}

    if text in ("tomorrow's schedule", "show tomorrow", "calendar tomorrow", "whats tomorrow"):
        return {"tool": "friday", "action": "list_events", "parameters": {"date_ref": "tomorrow"}, "confidence": 0.99}

    if text in ("show this week", "this week's schedule", "weekly schedule", "week calendar"):
        return {"tool": "friday", "action": "list_week_events", "parameters": {}, "confidence": 0.99}

    if text in ("next event", "what's next", "whats next", "upcoming event",
                "what's my next event", "whats my next event", "my next event"):
        return {"tool": "friday", "action": "next_event", "parameters": {}, "confidence": 0.99}

    _m = re.match(r"(?:cancel|remove|delete) (?:event |meeting |appointment )?(.+)", text)
    if _m and any(kw in text for kw in ["event", "meeting", "appointment", "cancel"]):
        return {"tool": "friday", "action": "delete_event",
                "parameters": {"identifier": _m.group(1).strip()}, "confidence": 0.99}

    # ── Planning ──
    if text in ("plan my day", "daily plan", "plan today", "what should i do today"):
        return {"tool": "friday", "action": "plan_day", "parameters": {}, "confidence": 0.99}

    if text in ("plan my week", "weekly plan", "plan this week"):
        return {"tool": "friday", "action": "plan_week", "parameters": {}, "confidence": 0.99}

    _m = re.match(r"(?:study plan|learning plan) (?:for )?(.+)", text)
    if _m:
        return {"tool": "friday", "action": "study_plan", "parameters": {"topic": _m.group(1).strip()}, "confidence": 0.99}


    return None
