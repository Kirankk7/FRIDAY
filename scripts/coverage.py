#!/usr/bin/env python
"""Functional coverage ledger (registry-driven) -> COVERAGE.md.

Enumerates EVERY tool.action from core.llm_router._VALID_TOOLS (+ crypto +
router-only methods), runs a SAFE smoke on read-only actions, and SKIPs
destructive / network / desktop / needs-dep ones by policy (noting them as
wired-but-not-executed). Answers "is everything working?" at a glance.

PASS = dispatched + returned a well-formed result, no 'unknown action'.
FAIL = exception or unknown-action (wiring broken).
SKIP = policy (write/network/desktop/needs-live-dep) — present but not run here.

Run:  python scripts/coverage.py
"""
import os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from core.tools_registry import execute_tool, TOOLS
from core.llm_router import _VALID_TOOLS

# Read-only actions we actually execute, with minimal safe params.
SAFE = {
    "system.system_info": {}, "system.cpu_usage": {}, "system.ram_usage": {},
    "system.battery_status": {}, "system.browser_status": {}, "system.recall_result": {},
    "friday.list_tasks": {}, "friday.list_goals": {}, "friday.list_notes": {},
    "friday.list_reminders": {}, "friday.show_health": {}, "friday.list_events": {},
    "friday.list_week_events": {}, "friday.next_event": {}, "friday.show_habits": {},
    "friday.generate_password": {}, "friday.calculate_calories": {"food": "2 eggs"},
    "edith.search_memory": {"query": "test"}, "edith.recall_memory": {},
    "edith.get_by_label": {"label": "test"},
    "personal.get_all": {},
    "crypto.crypto": {"op": "base64_encode", "input": "test"}, "crypto.list_ops": {},
    "terminator.list_windows": {},
    "veronica.list_tabs": {},
    "file.list_files": {},
    "routines.list_routines": {},
    "scheduler.list_tasks": {},
    "self_improvement.stats": {},
    "ultron.security_summary": {}, "ultron.system_health": {},
    "ultron.hash_target": {"target": "test", "algorithm": "sha256"},
    "ultron.log_check": {}, "ultron.export_html": {},
    "ultron.scan_localhost": {},  # passive port check (local only)
}

# Why each non-SAFE action is skipped (heuristic by category).
def skip_reason(tool, action):
    a = action.lower()
    if any(w in a for w in ("delete", "remove", "complete", "clear", "cancel", "untrack", "pause", "resume")):
        return "destructive/state-change (not run in coverage)"
    if any(w in a for w in ("add", "set", "store", "create", "log", "schedule", "directive")):
        return "writes user/prod data (skip to avoid seeding)"
    if tool in ("athena",) or any(w in a for w in ("research", "github", "web_search", "news", "crypto_price",
            "currency", "translate", "flight", "sports", "hackernews", "quick_answer", "vt_scan",
            "search_cve", "cve_", "correlate", "trigger", "list_workflows")):
        return "needs network / live API"
    if tool == "terminator" or any(w in a for w in ("type_text", "press_keys", "launch", "click", "focus")):
        return "desktop side-effect"
    if tool == "veronica" or any(w in a for w in ("open_url", "open_app", "summarize", "get_page", "tab")):
        return "browser / navigation"
    if any(w in a for w in ("nmap", "subfinder", "httpx", "nuclei", "katana", "pipeline", "bug_bounty",
            "scan", "recon", "spa_crawl", "screenshot", "export", "find_exploits", "file_scan", "hash_target", "dns_lookup")):
        return "active scan / heavy (local/OOS only, not in coverage)"
    if a in ("plan_day", "plan_week", "study_plan", "plan_workout", "analyze"):
        return "LLM-heavy (skip in coverage)"
    return "not in read-only smoke set"

# Router-only ultron security suite = real methods (check by existence).
ROUTER_METHODS = {
    "ultron": ["idor_check", "graphql_hunt", "threat_intel", "defensive_scan", "spa_crawl",
               "content_discovery", "session_set", "session_list", "replay_as"],
}
# Router-only run()-actions (not in _VALID_TOOLS) — dispatch-check (PASS if recognized, not 'unknown action').
ROUTER_ACTIONS = {
    "file": {"docs_status": "smoke", "index_docs": "dispatch", "ask_docs": "dispatch",
             "read_document": "dispatch", "summarize_document": "dispatch",
             "apply_patch": "skip:writes files", "clear_docs": "skip:destructive"},
    "vision": {"describe_image": "skip:needs llava+image", "screenshot_describe": "skip:needs llava"},
    "echo": {"generate_tool": "skip:LLM codegen", "list_tools": "smoke",
             "run_tool": "skip:executes code", "delete_tool": "skip:destructive"},
    # Daily-driver agents (route deterministically, not in _VALID_TOOLS).
    "finance": {"expense_report": "dispatch", "expense_categories": "dispatch",
                "portfolio_show": "skip:needs network (live pricing)",
                "portfolio_add": "skip:writes user data", "portfolio_remove": "skip:destructive",
                "portfolio_clear": "skip:destructive", "expense_add": "skip:writes user data"},
    "daily": {"find": "dispatch", "docs_watched": "dispatch",
              "weather": "skip:needs network", "will_rain": "skip:needs network",
              "briefing": "skip:needs network/LLM", "cal_export": "skip:writes .ics",
              "cal_import": "skip:needs source file", "watch_docs": "skip:writes/indexes",
              "unwatch_docs": "skip:state-change"},
}


def main():
    rows = []  # (status, name, detail)

    # 1. _VALID_TOOLS actions
    inventory = []
    for tool, actions in _VALID_TOOLS.items():
        for action in sorted(actions):
            inventory.append((tool, action))
    # crypto is regex-only (not in _VALID_TOOLS) — add its actions
    for action in ("crypto", "list_ops"):
        inventory.append(("crypto", action))

    for tool, action in inventory:
        name = f"{tool}.{action}"
        if name in SAFE:
            r = execute_tool(tool, "", action, SAFE[name])
            msg = (r.get("message") or "")[:50]
            if not isinstance(r, dict) or "unknown" in msg.lower():
                rows.append(("FAIL", name, f"unknown-action / bad return: {msg}"))
            else:
                rows.append(("PASS", name, ("ok" if r.get("success") else f"ran (success=False): {msg}")))
        else:
            rows.append(("SKIP", name, skip_reason(tool, action)))

    # 2a. router-only ultron security methods — existence check
    for tool, methods in ROUTER_METHODS.items():
        agent = TOOLS.get(tool)
        for m in methods:
            name = f"{tool}.{m}"
            if agent is not None and callable(getattr(agent, m, None)):
                rows.append(("PASS", name, "wired (security method present)"))
            else:
                rows.append(("FAIL", name, "MISSING method"))

    # 2b. router-only run()-actions — dispatch-check (recognized != 'unknown action')
    for tool, acts in ROUTER_ACTIONS.items():
        for action, mode in acts.items():
            name = f"{tool}.{action}"
            if mode.startswith("skip:"):
                rows.append(("SKIP", name, mode[5:]))
                continue
            r = execute_tool(tool, "", action, {})
            msg = (r.get("message") or "")
            if not isinstance(r, dict) or "unknown action" in msg.lower():
                rows.append(("FAIL", name, f"not dispatched: {msg[:50]}"))
            else:
                rows.append(("PASS", name, "dispatched (action recognized)"))

    npass = sum(1 for s, *_ in rows if s == "PASS")
    nfail = sum(1 for s, *_ in rows if s == "FAIL")
    nskip = sum(1 for s, *_ in rows if s == "SKIP")
    summary = f"{npass} working / {nfail} broken / {nskip} skipped  of {len(rows)} functionalities"

    out = [f"# JARVIS Functional Coverage — {time.strftime('%Y-%m-%d %H:%M')}", "",
           f"**{summary}**", "",
           "PASS = dispatched + well-formed result · SKIP = wired but not executed (destructive/network/"
           "desktop/needs-dep) · FAIL = wiring broken.", ""]
    for status, name, detail in rows:
        box = {"PASS": "x", "FAIL": "!", "SKIP": " "}[status]
        out.append(f"- [{box}] `{name}` — {status} ({detail})")
    with open(os.path.join(ROOT, "COVERAGE.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")

    print(summary)
    for status, name, detail in rows:
        if status == "FAIL":
            print(f"  FAIL {name} — {detail}")
    print(f"-> COVERAGE.md ({len(rows)} functionalities)")
    sys.exit(1 if nfail else 0)


if __name__ == "__main__":
    main()
