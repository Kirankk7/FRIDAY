"""Router group — personal facts + scheduler + echo + edith + self-improvement + recall. Extracted VERBATIM from route_single_intent,
same chain position, order preserved. Uses only text/text_raw. Move only — no logic changes.
"""
import re
import os


def try_route(text, text_raw):
    # =====================================
    # PERSONAL MEMORY — user facts
    # =====================================

    # "what do you know about me" / "my details" / "about me"
    if text in ("what do you know about me", "my details", "about me", "show my profile", "what do you know about yourself",
                "what facts do you know about me", "what facts do you know", "my facts", "facts about me"):
        return {
            "tool": "personal",
            "action": "get_all",
            "parameters": {},
            "confidence": 0.99
        }

    # Weight: "my weight is X" / "i weigh X"
    _m = re.match(r"(?:my weight is|i weigh) (.+)", text)
    if _m:
        return {"tool": "personal", "action": "set_fact",
                "parameters": {"key": "weight", "value": _m.group(1).strip()}, "confidence": 0.99}

    # Location: "i live in X" / "i'm based in X" / "i'm living in X"
    _m = re.match(r"i(?:'m)? (?:live|living|based) in (.+)", text)
    if _m:
        return {"tool": "personal", "action": "set_fact",
                "parameters": {"key": "location", "value": _m.group(1).strip()}, "confidence": 0.99}

    # Name: "my name is X" / "call me X"
    _m = re.match(r"(?:my name is|call me) (.+)", text)
    if _m:
        return {"tool": "personal", "action": "set_fact",
                "parameters": {"key": "name", "value": _m.group(1).strip()}, "confidence": 0.99}

    # Education: "i'm doing a X" / "i'm studying X" / "i'm pursuing X"
    _m = re.match(r"i(?:'m)? (?:doing a?|studying|pursuing) (.+)", text)
    if _m and any(kw in _m.group(1) for kw in ["msc", "master", "degree", "phd", "course", "diploma"]):
        return {"tool": "personal", "action": "set_fact",
                "parameters": {"key": "education", "value": _m.group(1).strip()}, "confidence": 0.99}

    # Certifications: "i'm studying for X" / "i'm preparing for X"
    _m = re.match(r"i(?:'m)? (?:studying for|preparing for|working on) (.+)", text)
    if _m:
        return {"tool": "personal", "action": "set_fact",
                "parameters": {"key": "certifications", "value": _m.group(1).strip()}, "confidence": 0.99}

    # Career: "i work as X" / "i'm a X" / "my job is X" / "my career is X"
    _m = re.match(r"(?:i work as|my job is|my career is|i am a|i'm a) (.+)", text)
    if _m and any(kw in text for kw in ["security", "engineer", "developer", "analyst", "tester", "hacker", "researcher", "manager"]):
        return {"tool": "personal", "action": "set_fact",
                "parameters": {"key": "career", "value": _m.group(1).strip()}, "confidence": 0.99}

    # Investments: "i invest in X" / "my investments are X"
    _m = re.match(r"(?:i invest in|my investments? (?:are|is)) (.+)", text)
    if _m:
        return {"tool": "personal", "action": "set_fact",
                "parameters": {"key": "investments", "value": _m.group(1).strip()}, "confidence": 0.99}

    # Health: "i have X" / "i've had X" — only for known health keywords
    _m = re.match(r"i(?:'ve)? (?:have|had) (.+)", text)
    if _m and any(kw in _m.group(1) for kw in ["lasik", "surgery", "diabetes", "allergy", "condition", "injury"]):
        return {"tool": "personal", "action": "set_fact",
                "parameters": {"key": "health", "value": _m.group(1).strip()}, "confidence": 0.99}

    # Generic: "my X is Y" / "set my X to Y"
    _m = re.match(r"(?:set )?my (\w+) (?:is|to|=) (.+)", text)
    if _m:
        key = _m.group(1).strip()
        val = _m.group(2).strip()
        # Whitelist to avoid false positives
        allowed_keys = {"weight", "height", "age", "name", "location", "city", "career", "goal", "budget"}
        if key in allowed_keys:
            return {"tool": "personal", "action": "set_fact",
                    "parameters": {"key": key, "value": val}, "confidence": 0.99}

    # =====================================
    # SCHEDULER (Phase 26)
    # =====================================
    # "every morning scan my homelab" / "schedule every hour check system health"
    _sched_trigger = re.match(
        r"(?:schedule\s+)?(?:every|each|daily|weekly)\s+.+",
        text,
        re.IGNORECASE
    )
    if _sched_trigger:
        return {"tool": "scheduler", "action": "add_task", "parameters": {"raw": text}, "confidence": 0.95}

    if text in ("list scheduled tasks", "show scheduled tasks", "my scheduled tasks",
                "what tasks are scheduled", "show schedule", "list schedule"):
        return {"tool": "scheduler", "action": "list_tasks", "parameters": {}, "confidence": 0.99}

    _m = re.match(r"(?:cancel|delete|remove) (?:scheduled )?task\s+(.+)", text)
    if _m:
        return {"tool": "scheduler", "action": "remove_task", "parameters": {"name": _m.group(1).strip()}, "confidence": 0.99}

    _m = re.match(r"(?:pause|disable) (?:scheduled )?task\s+(.+)", text)
    if _m:
        return {"tool": "scheduler", "action": "pause_task", "parameters": {"name": _m.group(1).strip()}, "confidence": 0.99}

    _m = re.match(r"(?:resume|enable) (?:scheduled )?task\s+(.+)", text)
    if _m:
        return {"tool": "scheduler", "action": "resume_task", "parameters": {"name": _m.group(1).strip()}, "confidence": 0.99}

    # =====================================
    # ECHO — TOOL GENERATOR (Phase 21)
    # =====================================
    _m = re.match(r"(?:create|build|make|generate) (?:a |an )?tool (?:that |to |for |which )?(.+)", text)
    if _m:
        return {"tool": "echo", "action": "generate_tool", "parameters": {"task": _m.group(1).strip()}, "confidence": 0.99}

    if text in ("list tools", "show tools", "my tools", "show generated tools", "what tools do i have"):
        return {"tool": "echo", "action": "list_tools", "parameters": {}, "confidence": 0.99}

    _m = re.match(r"run tool\s+(\S+)", text)
    if _m:
        return {"tool": "echo", "action": "run_tool", "parameters": {"name": _m.group(1).strip()}, "confidence": 0.99}

    _m = re.match(r"delete tool\s+(\S+)", text)
    if _m:
        return {"tool": "echo", "action": "delete_tool", "parameters": {"name": _m.group(1).strip()}, "confidence": 0.99}

    # =====================================
    # EDITH — PROJECT MEMORY
    # =====================================

    # "remember this" / "remember this as <label>"
    if text == "remember this" or text.startswith("remember this as "):
        label = text.replace("remember this as ", "").strip() if text.startswith("remember this as ") else None
        return {
            "tool": "edith",
            "action": "store_memory",
            "parameters": {"content_from": "last_response", "label": label},
            "confidence": 0.99
        }

    # "remember <specific text>"
    if text.startswith("remember ") and not text.startswith("remember this"):
        content = text[len("remember "):].strip()
        return {
            "tool": "edith",
            "action": "store_memory",
            "parameters": {"content": content},
            "confidence": 0.99
        }

    # "what do you know about X" / "what do you remember about X"
    m = re.match(r"what do you (?:know|remember) about (.+)", text)
    if m:
        return {
            "tool": "edith",
            "action": "search_memory",
            "parameters": {"query": m.group(1).strip()},
            "confidence": 0.99
        }

    # "recall <label>"
    if text.startswith("recall ") and text != "recall memory":
        return {
            "tool": "edith",
            "action": "get_by_label",
            "parameters": {"label": text[len("recall "):].strip()},
            "confidence": 0.99
        }

    # "continue research" / "what was i researching"
    if text in ("continue research", "continue last research", "what was i researching"):
        return {
            "tool": "edith",
            "action": "search_memory",
            "parameters": {"query": "research"},
            "confidence": 0.99
        }

    # "show memory" / "what do you remember" / "recall memory"
    if text in ("show memory", "what do you remember", "show what you remember", "recall memory"):
        return {
            "tool": "edith",
            "action": "recall_memory",
            "parameters": {},
            "confidence": 0.99
        }

    # SYSTEM INFO
    if any(
        phrase in text
        for phrase in [
            "system info",
            "pc info"
        ]
    ):

        return {

            "tool":
            "veronica",

            "action":
            "system_info",

            "parameters":
            {},

            "confidence":
            0.99
        }

    # =====================================
    # BROWSER TOGGLE (runtime enable/disable)
    # =====================================
    if text in (
        "enable browser", "turn on browser", "start browser",
        "enable veronica browser", "browser on", "activate browser"
    ):
        return {"tool": "system", "action": "browser_enable", "parameters": {}, "confidence": 0.99}

    if text in (
        "disable browser", "turn off browser", "stop browser",
        "disable veronica browser", "browser off", "deactivate browser"
    ):
        return {"tool": "system", "action": "browser_disable", "parameters": {}, "confidence": 0.99}

    if text in ("browser status", "is browser enabled", "is veronica enabled"):
        return {"tool": "system", "action": "browser_status", "parameters": {}, "confidence": 0.99}

    # =====================================
    # SELF-IMPROVEMENT (Phase 27)
    # =====================================
    if text in (
        "analyze your responses", "analyze responses", "self analyze",
        "analyze yourself", "run self analysis", "self improvement analyze",
        "improve yourself", "analyze your performance"
    ):
        return {"tool": "self_improvement", "action": "analyze", "parameters": {}, "confidence": 0.99}

    if text in (
        "what are you learning", "what have you learned", "show self improvement",
        "self improvement stats", "response stats", "how are you doing",
        "show your stats", "response quality", "quality stats", "improvement stats"
    ):
        return {"tool": "self_improvement", "action": "stats", "parameters": {}, "confidence": 0.99}

    if text in (
        "show directive", "current directive", "what is your directive",
        "show improvement directive", "self improvement directive"
    ):
        return {"tool": "self_improvement", "action": "directive", "parameters": {}, "confidence": 0.99}

    # "what did the/that <noun> find/say/return" -> recall by keyword
    _m = re.match(r"what did (?:the |that |my )?(\w+) (?:find|say|return|show|report|give)", text)
    if _m:
        return {"tool": "system", "action": "recall_result",
                "parameters": {"keyword": _m.group(1)}, "confidence": 0.9}


    return None
