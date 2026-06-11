"""
Phase 19 — Multi-Agent Coordinator
Detects compound commands and decomposes into ordered agent steps.
Called before regex router when input looks multi-intent.
"""

import json
import re
from core.llm import ask_llm

# Agents + valid actions (mirrors llm_router._VALID_TOOLS)
_VALID_TOOLS = {
    "ultron": {"nmap_scan", "full_recon", "subfinder", "httpx_probe", "nuclei_scan", "system_health", "file_scan", "log_check", "export_html", "full_pipeline", "katana_crawl", "take_screenshot", "find_exploits", "cve_track", "cve_list", "cve_check", "cve_untrack"},
    "athena": {"deep_research"},
    "veronica": {"open_url", "open_app", "summarize_page", "get_page_text", "research", "new_tab", "switch_tab", "list_tabs", "close_tab"},
    "vision": {"search_news", "summarize_news"},
    "file": {"list_files", "open_file", "create_file", "delete_file"},
    "edith": {"store_memory", "search_memory", "recall_memory", "get_by_label"},
    "personal": {"set_fact", "get_all"},
    "friday": {
        "add_task", "list_tasks", "complete_task", "delete_task",
        "add_goal", "list_goals", "complete_goal",
        "add_note", "list_notes",
        "log_health", "show_health",
        "set_reminder", "list_reminders",
        "add_habit", "log_habit", "show_habits",
        "plan_day", "plan_week", "study_plan",
        "schedule_event", "list_events", "list_week_events",
        "next_event", "delete_event", "set_reminder_at",
    },
    "self_improvement": {"analyze", "stats", "directive"},
    "system": {"system_info", "cpu_usage", "ram_usage", "browser_enable", "browser_disable", "browser_status"},
}

# Signals that suggest compound/multi-agent intent
_COMPOUND_SIGNALS = re.compile(
    r"\b(and (then|also|after|scan|research|find|check|open|list|show|tell)|"
    r"then (scan|research|find|check|open|list|show)|"
    r"after that|plus also|as well)\b",
    re.IGNORECASE
)

# Domain keywords per agent — used for quick multi-domain detection
_DOMAIN_HINTS = {
    "ultron":  r"\b(scan|nmap|subfinder|nuclei|httpx|recon|port|vuln|probe|subdom)",
    "athena":  r"\b(research|deep research|investigate|study|analyze|report on)",
    "veronica": r"\b(open|browse|google|youtube|github|search|go to|navigate)",
    "vision":  r"\b(news|headline|latest|article)",
    "friday":  r"\b(remind|task|todo|goal|habit|schedule|plan|note|workout|weight)",
    "file":    r"\b(file|folder|directory|list files|open file|create file)",
    "edith":   r"\b(remember|recall|memory|what do you know|save this)",
}


def _count_domains(text: str) -> list[str]:
    """Return list of agents whose domain keywords appear in text."""
    found = []
    for agent, pattern in _DOMAIN_HINTS.items():
        if re.search(pattern, text, re.IGNORECASE):
            found.append(agent)
    return found


def should_coordinate(user_input: str) -> bool:
    """
    Fast heuristic — no LLM. Returns True if input likely needs multiple agents.
    Keeps latency near zero on single-intent commands.
    """
    text = user_input.strip().lower()

    # Explicit compound signals
    if _COMPOUND_SIGNALS.search(text):
        domains = _count_domains(text)
        if len(domains) >= 2:
            return True

    # Multi-domain without explicit connective (long input, 2+ distinct domains)
    if len(text.split()) >= 8:
        domains = _count_domains(text)
        if len(domains) >= 2:
            return True

    return False


_COORD_PROMPT = """You are a command decomposer for JARVIS, a local AI assistant.
Break the user command into an ordered list of agent steps.

Available agents and actions:
- ultron: nmap_scan(target), full_recon(target), subfinder(target), httpx_probe(target), nuclei_scan(target), system_health()
- athena: deep_research(query)
- veronica: open_url(url), open_app(app), summarize_page(), get_page_text(), research(query)
- vision: search_news(query), summarize_news()
- file: list_files(path), open_file(path), create_file(name), delete_file(name)
- edith: store_memory(content, label), search_memory(query), recall_memory()
- friday: add_task(text), list_tasks(), add_reminder(text, minutes), plan_day(), add_note(text)
- personal: set_fact(key, value), get_all()

User command: "{input}"

Rules:
- Return ONLY a JSON array of steps, no prose
- Each step: {{"tool": "name", "action": "action_name", "parameters": {{...}}}}
- Order matters — steps run sequentially
- If a step needs no parameters, use {{}}
- If command is NOT multi-agent (single clear intent), return []
- Maximum 4 steps

JSON array:"""


def coordinate(user_input: str) -> dict | None:
    """
    Use LLM to decompose compound command into ordered workflow steps.
    Returns workflow route dict or None if decomposition fails/unnecessary.
    """
    prompt = _COORD_PROMPT.format(input=user_input.strip())

    try:
        raw = ask_llm(prompt)
        if not raw:
            return None

        # Extract JSON array
        start = raw.find('[')
        if start == -1:
            return None
        depth = 0
        end = -1
        for i, ch in enumerate(raw[start:], start):
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end == -1:
            return None

        steps_raw = json.loads(raw[start:end + 1])

        if not steps_raw or not isinstance(steps_raw, list):
            return None

        # Validate each step
        steps = []
        for s in steps_raw:
            tool = s.get("tool", "").lower().strip()
            action = s.get("action", "").lower().strip()
            params = s.get("parameters", {})

            if tool not in _VALID_TOOLS:
                print(f"[coord] Unknown tool: {tool} — skipping step")
                continue
            if action not in _VALID_TOOLS[tool]:
                print(f"[coord] Unknown action: {tool}.{action} — skipping step")
                continue

            steps.append({
                "tool": tool,
                "action": action,
                "parameters": params if isinstance(params, dict) else {}
            })

        if len(steps) < 2:
            # Single step — not a compound command, let normal router handle it
            return None

        print(f"[coord] Decomposed into {len(steps)} steps: {[(s['tool'], s['action']) for s in steps]}")

        return {
            "tool": "workflow",
            "action": "multi_step",
            "parameters": {"steps": steps},
            "confidence": 0.85
        }

    except (json.JSONDecodeError, Exception) as e:
        print(f"[coord] Error: {e}")
        return None
