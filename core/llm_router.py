import json
import re
from collections import OrderedDict
from core.llm import ask_llm_fast

# ─── LRU cache for LLM classification (Phase 51 #1) ───────────────────────────
# llm_classify_intent is deterministic (temp=0) and stateless — safe to cache.
# Regex routes (some stateful: folder context, last_match) are NOT cached;
# they stay instant and always recompute correctly.
_LLM_CACHE     = OrderedDict()
_LLM_CACHE_MAX = 200

# Tools exposed to LLM router — only actionable tools, not chat
TOOLS_SCHEMA = """
ultron:
  - nmap_scan(target: str, scan_type: str)  — port scan (scan_type: basic/quick/service/full)
  - full_recon(target: str)                 — full recon: nmap + subfinder + httpx + nuclei
  - subfinder(target: str)                  — find subdomains for a domain
  - httpx_probe(target: str)                — probe HTTP/HTTPS endpoints
  - nuclei_scan(target: str, severity: str) — vulnerability scan (severity: critical/high/medium)
  - system_health()                         — CPU/RAM health check
  - file_scan(path: str)                    — local heuristic file risk check
  - vt_scan(target: str)                    — VirusTotal reputation: file path, hash, URL, or domain ("is X malicious")
  - log_check()                             — check system logs for suspicious entries
  - export_html()                           — export last report as HTML to Desktop
  - full_pipeline(target: str)              — full 5-stage pipeline: nmap+subfinder+httpx+nuclei+katana+screenshot
  - bug_bounty(target: str)                 — full bug-bounty hunt: recon → parse findings → CVE/exploit lookup → validate → PoC report
  - katana_crawl(target: str)               — crawl target URLs with Katana
  - take_screenshot(target: str)            — headless screenshot of a URL
  - find_exploits(cve_id: str)              — search GitHub + NVD + Exploit-DB for CVE PoCs
  - search_cve(keyword: str, severity: str, days_back: int) — search NVD for CVEs by keyword/severity (severity: CRITICAL/HIGH/MEDIUM/LOW)
  - cve_track(cve_id: str)                  — add CVE to watchlist and fetch initial data
  - cve_list()                              — show all tracked CVEs with CVSS + PoC counts
  - cve_check(cve_id: str)                  — re-check CVE (or all if no cve_id) for new PoCs
  - cve_untrack(cve_id: str)                — remove CVE from watchlist
  - correlate()                             — cross-link tracked CVEs with scanned hosts ("am I exposed")
  - dns_lookup(target: str)                 — forward/reverse DNS resolution
  - hash_target(target: str, algorithm: str) — hash a string or file (md5/sha1/sha256/sha512)

athena:
  - deep_research(query: str)        — multi-source research report (GitHub + news + web)

veronica:
  - open_url(url: str)               — open a URL or "search X for Y" string
  - open_app(app: str)               — open an app or website by name
  - summarize_page()                 — summarize current browser page
  - get_page_text()                  — read current browser page
  - research(query: str)             — browser research workflow on a query
  - new_tab(label: str, url: str)    — open a new browser tab, optionally at URL
  - switch_tab(label: str)           — switch to tab by name
  - list_tabs()                      — show all open browser tabs
  - close_tab(label: str)            — close a tab by name

vision:
  - search_news(query: str)          — search news headlines
  - summarize_news()                 — summarize fetched news articles
  - quick_answer(query: str)         — fast factual/news lookup via RSS (use for "when is X", "latest on X")
  - web_search(query: str)           — live web search via DuckDuckGo (general "search the web for X")
  - sports_query(query: str)         — football match dates, results, standings
  - hackernews(n: int)               — top N Hacker News stories
  - crypto_price(coins: str)         — live crypto prices (bitcoin/eth/sol...)
  - currency_convert(amount: float, from: str, to: str) — live FX conversion
  - translate(text: str, target: str) — translate text to a language
  - track_flight(flight: str)        — live flight tracking by flight number

file:
  - list_files(path: str)            — list files in a folder
  - open_file(path: str)             — open a file
  - create_file(name: str)           — create a new file
  - delete_file(path: str)           — delete a file

edith:
  - store_memory(content: str, label: str)  — save a note to memory
  - search_memory(query: str)              — search stored notes
  - recall_memory()                         — show recent memory entries
  - get_by_label(label: str)               — recall a memory by its label

system:
  - system_info()                    — OS/CPU/RAM system information
  - browser_enable()                 — turn on Veronica browser features
  - browser_disable()                — turn off Veronica browser features
  - browser_status()                 — check if browser is enabled
  - recall_result(keyword: str)      — recall a recent tool result ("what did that scan find")

personal:
  - set_fact(key: str, value: str)   — save a personal fact (weight, location, etc.)
  - get_all()                        — show all personal facts

scheduler:
  - add_task(raw: str)               — schedule a recurring task from natural language
  - list_tasks()                     — list all scheduled tasks
  - remove_task(name: str)           — delete a scheduled task
  - pause_task(name: str)            — pause a scheduled task
  - resume_task(name: str)           — resume a paused task

friday:
  - add_task(text: str)              — add a task/todo
  - list_tasks()                     — show pending tasks
  - complete_task(identifier: str)   — mark task done
  - delete_task(identifier: str)     — delete a task
  - add_goal(text: str)              — add a goal
  - list_goals()                     — show active goals
  - complete_goal(identifier: str)   — mark goal achieved
  - add_note(text: str)              — save a note
  - list_notes()                     — show recent notes
  - log_health(metric: str, value: str) — log health metric (weight, workout, sleep)
  - show_health(metric: str)         — show health log
  - set_reminder(text: str, minutes: int) — set a reminder
  - set_reminder_at(when: str, text: str) — set reminder at absolute time
  - list_reminders()                 — show pending reminders
  - add_habit(name: str)             — add habit tracker
  - log_habit(name: str)             — mark habit done today
  - show_habits()                    — show habits and streaks
  - plan_day()                       — generate daily plan
  - plan_week()                      — generate weekly plan
  - study_plan(topic: str)           — generate study plan for topic
  - schedule_event(title: str, when: str) — add a calendar event
  - list_events(date_ref: str)       — list events for today/tomorrow/a weekday
  - list_week_events()               — list this week's events
  - next_event()                     — show next upcoming event
  - delete_event(identifier: str)    — cancel a calendar event
  - generate_password(length: int)   — generate a secure random password
  - calculate_calories(gender: str, age: int, goal: str) — daily calorie/macro target
  - plan_workout(focus: str, fitness_level: str) — generate a workout plan

self_improvement:
  - analyze()                        — analyze recent responses, generate improvement directive
  - stats()                          — show response quality stats and top issues
  - directive()                      — show current active improvement directive

n8n:
  - trigger(workflow: str)           — run an n8n automation workflow (email/Telegram/pipelines)
  - list_workflows()                 — list available n8n workflows

routines:
  - create_routine(name: str)        — start recording a named command sequence
  - stop_recording()                 — save the routine being recorded
  - run_routine(name: str)           — replay a saved routine's commands
  - list_routines()                  — list saved routines
  - delete_routine(name: str)        — delete a routine

terminator:
  - list_windows()                   — list open Windows app windows
  - focus_window(title: str)         — bring a window to the front
  - get_window_text(title: str)      — read a window's visible text
  - type_text(text: str)             — type text into the focused window
  - press_keys(keys: str)            — press a key combo (e.g. "ctrl+s", "enter")
  - launch_app(name: str)            — launch a Windows app
  - click_element(window: str, element: str) — click a named button/element in a window
"""

_VALID_TOOLS = {
    "ultron": {"nmap_scan", "full_recon", "subfinder", "httpx_probe", "nuclei_scan", "system_health", "file_scan", "log_check", "export_html", "full_pipeline", "katana_crawl", "take_screenshot", "find_exploits", "search_cve", "cve_track", "cve_list", "cve_check", "cve_untrack", "correlate", "dns_lookup", "hash_target", "vt_scan", "bug_bounty", "scan_localhost", "security_summary"},
    "athena": {"deep_research"},
    "veronica": {"open_url", "open_app", "summarize_page", "get_page_text", "research", "new_tab", "switch_tab", "list_tabs", "close_tab"},
    "vision": {"search_news", "summarize_news", "quick_answer", "web_search", "sports_query", "hackernews", "crypto_price", "currency_convert", "translate", "track_flight"},
    "file": {"list_files", "open_file", "create_file", "delete_file"},
    "edith": {"store_memory", "search_memory", "recall_memory", "get_by_label"},
    "personal": {"set_fact", "get_all"},
    # NOTE: echo intentionally NOT LLM-routable — it generates+executes code.
    # Only the explicit regex ("create a tool that ...") may reach it. Arbitrary
    # questions misclassified as generate_tool produced broken-code errors.
    "scheduler": {"add_task", "list_tasks", "remove_task", "pause_task", "resume_task"},
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
        "generate_password", "calculate_calories", "plan_workout",
    },
    "self_improvement": {"analyze", "stats", "directive"},
    "terminator": {"list_windows", "focus_window", "get_window_text", "type_text", "press_keys", "launch_app", "click_element"},
    "n8n": {"trigger", "list_workflows"},
    "routines": {"create_routine", "stop_recording", "cancel_recording", "run_routine", "list_routines", "delete_routine"},
    "system": {"system_info", "cpu_usage", "ram_usage", "browser_enable", "browser_disable", "browser_status", "speed_test", "battery_status", "recall_result"},
}

_PROMPT = """You are a command router for a voice assistant called JARVIS.
Map the user's command to the correct tool and action from the list below.

{tools}

User command: "{input}"

Rules:
- Respond ONLY with valid JSON on one line
- If command clearly maps to a tool: {{"tool": "name", "action": "action", "parameters": {{...}}}}
- If no tool fits (casual chat, questions, opinions): {{"tool": "chat", "action": "respond", "parameters": {{}}}}
- Parameters must include all required args for the action
- For search/research queries extract the query string as "query"
- For scan/recon extract the target as "target"

JSON:"""


def llm_classify_intent(user_input: str) -> dict | None:
    """
    Ask LLM to classify intent as a structured route (LRU-cached).
    Returns route dict or None. Called only when regex router misses.
    """
    key = (user_input or "").lower().strip()
    if not key:
        return None

    # Cache hit (stores None too, so repeated unknown/chat inputs skip Ollama)
    if key in _LLM_CACHE:
        _LLM_CACHE.move_to_end(key)
        cached = _LLM_CACHE[key]
        print(f"[llm_router] CACHE HIT ({'route' if cached else 'none'})")
        return dict(cached) if cached else None

    result = _classify_uncached(user_input)

    _LLM_CACHE[key] = dict(result) if result else None
    _LLM_CACHE.move_to_end(key)
    if len(_LLM_CACHE) > _LLM_CACHE_MAX:
        _LLM_CACHE.popitem(last=False)

    return dict(result) if result else None


def _classify_uncached(user_input: str) -> dict | None:
    """Actual LLM classification — uncached. See llm_classify_intent for caching."""
    if not user_input or not user_input.strip():
        return None

    prompt = _PROMPT.format(tools=TOOLS_SCHEMA, input=user_input.strip())

    try:
        raw = ask_llm_fast(prompt, max_tokens=80)
        if not raw:
            return None

        # Extract outermost JSON object — handles nested braces
        start = raw.find('{')
        if start == -1:
            return None
        depth = 0
        end = -1
        for i, ch in enumerate(raw[start:], start):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end == -1:
            return None

        data = json.loads(raw[start:end + 1])
        tool = data.get("tool", "").lower().strip()
        action = data.get("action", "").lower().strip()
        parameters = data.get("parameters", {})

        # Validate — reject unknown tools/actions
        if tool == "chat":
            return None  # Falls through to normal LLM chat

        if tool not in _VALID_TOOLS:
            print(f"[llm_router] Unknown tool: {tool}")
            return None

        if action not in _VALID_TOOLS[tool]:
            print(f"[llm_router] Unknown action: {tool}.{action}")
            return None

        print(f"[llm_router] Classified: {tool}.{action} {parameters}")
        return {
            "tool": tool,
            "action": action,
            "parameters": parameters if isinstance(parameters, dict) else {},
            "confidence": 0.7
        }

    except (json.JSONDecodeError, Exception) as e:
        print(f"[llm_router] Parse error: {e}")
        return None
