"""Router group — crypto toolkit + daily-driver features.

Extracted VERBATIM from route_single_intent (crypto/weather/briefing/portfolio/
expenses/find/calendar ICS/rag-watch/scheduled-routines). Behaviour-identical: the
dispatcher calls try_route() in the exact position this block used to occupy, so the
regex-chain order is preserved. Uses only text (lowercased) + text_raw (original case).
Returns a decision dict, or None to fall through to the next group.

Refactor discipline: move only — no logic changes.
"""
import re


def try_route(text: str, text_raw: str):
    # ── Crypto / encoding toolkit (deterministic; payload captured case-sensitively) ──
    _CSCHEME = {"base64": "base64", "b64": "base64", "base32": "base32", "base58": "base58",
                "hex": "hex", "url": "url", "html": "html", "unicode": "unicode",
                "rot13": "rot13", "morse": "morse", "caesar": "caesar", "jwt": "jwt"}

    def _crypto_op(scheme, verb):
        base = _CSCHEME[scheme]
        if base == "rot13":
            return "rot13" if verb == "encode" else "rot13_decode"
        return f"{base}_{verb}"

    _scheme_alt = "base64|b64|base32|base58|hex|url|html|unicode|rot13|morse|caesar|jwt"
    # "md5 X" / "sha256 hash of X"
    _m = re.match(r"(md5|sha1|sha256|sha512)\s+(?:hash\s+(?:of\s+)?|of\s+)?(.+)$", text_raw, re.I)
    if _m:
        return {"tool": "crypto", "action": "crypto",
                "parameters": {"op": f"{_m.group(1).lower()}_hash", "input": _m.group(2)},
                "confidence": 0.97}
    # "base64 decode SGVsbG8="
    _m = re.match(rf"({_scheme_alt})\s+(encode|decode)\s+(.+)$", text_raw, re.I)
    if _m:
        return {"tool": "crypto", "action": "crypto",
                "parameters": {"op": _crypto_op(_m.group(1).lower(), _m.group(2).lower()),
                               "input": _m.group(3)}, "confidence": 0.97}
    # "decode base64 SGVsbG8=" (optional this/the)
    _m = re.match(rf"(encode|decode)\s+(?:this\s+|the\s+)?({_scheme_alt})\s+(.+)$", text_raw, re.I)
    if _m:
        return {"tool": "crypto", "action": "crypto",
                "parameters": {"op": _crypto_op(_m.group(2).lower(), _m.group(1).lower()),
                               "input": _m.group(3)}, "confidence": 0.97}
    # "rot13 uryyb" shorthand (self-inverse)
    _m = re.match(r"rot13\s+(.+)$", text_raw, re.I)
    if _m:
        return {"tool": "crypto", "action": "crypto",
                "parameters": {"op": "rot13", "input": _m.group(1)}, "confidence": 0.95}
    if text in ("crypto ops", "list crypto", "list crypto ops", "crypto tools", "encoding tools"):
        return {"tool": "crypto", "action": "list_ops", "parameters": {}, "confidence": 0.97}
    # bare "decode <single-token>" -> auto-detect (no scheme matched above)
    _m = re.match(r"(?:auto[\s-]?decode|decode this|decode)\s+(\S+)\s*$", text_raw, re.I)
    if _m:
        return {"tool": "crypto", "action": "crypto",
                "parameters": {"op": "auto_decode", "input": _m.group(1)}, "confidence": 0.9}

    # ── Daily-driver features (A weather · B briefing · D find · E portfolio · G calendar · H expenses) ──
    # Weather (open-meteo, no key)
    _m = re.match(r"(?:what'?s? the |show me the |current )?weather(?:\s+(?:in|for|at)\s+(.+))?$", text_raw, re.I)
    if _m:
        return {"tool": "daily", "action": "weather",
                "parameters": {"place": (_m.group(1) or "").strip()}, "confidence": 0.95}
    _m = re.match(r"(?:weather )?forecast(?:\s+(?:in|for)\s+)?\s*(.+)?$", text_raw, re.I)
    if _m and text.startswith(("forecast", "weather forecast")):
        return {"tool": "daily", "action": "weather",
                "parameters": {"place": (_m.group(1) or "").strip()}, "confidence": 0.9}
    _m = re.match(r"will it rain(?:\s+(tomorrow|today))?(?:\s+(?:in|at)\s+(.+))?$", text_raw, re.I)
    if _m:
        return {"tool": "daily", "action": "will_rain",
                "parameters": {"day": (_m.group(1) or "today"), "place": (_m.group(2) or "").strip()},
                "confidence": 0.95}

    # Morning briefing (B)
    if text in ("brief me", "briefing", "morning briefing", "daily briefing", "my briefing",
                "what's my day", "whats my day", "brief me boss"):
        return {"tool": "daily", "action": "briefing", "parameters": {}, "confidence": 0.95}

    # Portfolio (E)
    _m = re.match(r"(?:add holding|buy)\s+([\d.]+)\s+([a-z]{2,6})$", text, re.I) or \
         re.match(r"add\s+([\d.]+)\s+([a-z]{2,6})\s+to (?:my )?portfolio$", text, re.I)
    if _m:
        return {"tool": "finance", "action": "portfolio_add",
                "parameters": {"amount": _m.group(1), "coin": _m.group(2)}, "confidence": 0.9}
    if text in ("portfolio", "my portfolio", "how's my portfolio", "hows my portfolio",
                "how is my portfolio", "show portfolio", "portfolio value", "show my portfolio"):
        return {"tool": "finance", "action": "portfolio_show", "parameters": {}, "confidence": 0.95}
    if text in ("clear portfolio", "reset portfolio"):
        return {"tool": "finance", "action": "portfolio_clear", "parameters": {}, "confidence": 0.95}
    _m = re.match(r"remove\s+(?:holding\s+)?([a-z]{2,6})\s+from (?:my )?portfolio$", text, re.I)
    if _m:
        return {"tool": "finance", "action": "portfolio_remove",
                "parameters": {"coin": _m.group(1)}, "confidence": 0.9}

    # Expenses (H)
    _m = re.match(r"(?:spent|paid|log(?:ged)?)\s+\$?([\d.]+)\s+(?:on|for)\s+(.+)$", text_raw, re.I)
    if _m:
        return {"tool": "finance", "action": "expense_add",
                "parameters": {"amount": _m.group(1), "category": _m.group(2).strip()}, "confidence": 0.92}
    _m = re.match(r"how much(?: did i| have i)? spen[dt](?:\s+this\s+(week|month))?(?:\s+(today))?", text, re.I)
    if _m:
        return {"tool": "finance", "action": "expense_report",
                "parameters": {"window": _m.group(1) or _m.group(2) or "week"}, "confidence": 0.92}
    if text in ("spending by category", "expenses by category", "expense breakdown", "where did my money go"):
        return {"tool": "finance", "action": "expense_categories", "parameters": {"window": "all"}, "confidence": 0.93}

    # Unified find (D) — generic "find <x>" (specific finds already returned above) or "search my <store> for <x>"
    _m = re.match(r"find\s+(.+)$", text_raw, re.I)
    if not _m:
        _m = re.match(r"search\s+my\s+(?:notes?|tasks?|goals?|stuff|memory)\s+(?:for\s+)?(.+)$", text_raw, re.I)
    if _m:
        return {"tool": "daily", "action": "find",
                "parameters": {"query": _m.group(1).strip()}, "confidence": 0.72}

    # Calendar ICS (G)
    if text in ("export calendar", "export my calendar", "export events", "save calendar"):
        return {"tool": "daily", "action": "cal_export", "parameters": {}, "confidence": 0.93}
    _m = re.match(r"import calendar\s+(.+)$", text_raw, re.I)
    if _m:
        return {"tool": "daily", "action": "cal_import", "parameters": {"src": _m.group(1).strip()}, "confidence": 0.93}

    # Auto-RAG watch folder (L)  — "watch docs <folder>" (before F2 target-watch, which needs "watch target")
    _m = re.match(r"watch docs?\s+(.+)$", text_raw, re.I)
    if _m:
        return {"tool": "daily", "action": "watch_docs", "parameters": {"folder": _m.group(1).strip()}, "confidence": 0.93}
    _m = re.match(r"(?:unwatch|stop watching) docs?\s+(.+)$", text_raw, re.I)
    if _m:
        return {"tool": "daily", "action": "unwatch_docs", "parameters": {"folder": _m.group(1).strip()}, "confidence": 0.93}
    if text in ("list watched docs", "watched docs", "which docs are watched"):
        return {"tool": "daily", "action": "docs_watched", "parameters": {}, "confidence": 0.93}

    # Scheduled routines (K) — routines can't self-schedule; wire them to the scheduler.
    # "schedule routine morning every day at 8am"  ("run routine morning" w/o a time stays immediate)
    _m = re.match(r"(?:schedule routine|run routine)\s+([\w-]+)\s+((?:every|daily|weekly|at)\b.+)$", text, re.I)
    if _m:
        return {"tool": "scheduler", "action": "add_task",
                "parameters": {"raw": _m.group(2), "tool": "routines",
                               "task_action": "run_routine",
                               "task_parameters": {"name": _m.group(1)}}, "confidence": 0.9}

    return None
