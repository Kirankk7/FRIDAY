"""Router group — athena deep research + veronica browser. Extracted VERBATIM from route_single_intent,
same chain position, order preserved. Uses only text/text_raw. Move only — no logic changes.
"""
import re
import os


def try_route(text, text_raw):
    # =====================================
    # ATHENA DEEP RESEARCH
    # =====================================
    if text.startswith("deep research "):

        query = text.replace("deep research ", "").strip()

        return {
            "tool": "athena",
            "action": "deep_research",
            "parameters": {"query": query},
            "confidence": 0.99
        }

    # =====================================
    # RESEARCH WORKFLOW
    # =====================================
    if text.startswith("research "):

        query = text.replace("research ", "").strip()

        return {
            "tool": "veronica",
            "action": "research",
            "parameters": {"query": query},
            "confidence": 0.99
        }

    if text.startswith(
        "search youtube for "
    ):

        return {

            "tool":
            "veronica",

            "action":
            "open_url",

            "parameters": {

                "url":
                text
            },

            "confidence":
            0.99
        }

    if text.startswith(
        "search google for "
    ):

        return {

            "tool":
            "veronica",

            "action":
            "open_url",

            "parameters": {

                "url":
                text
            },

            "confidence":
            0.99
        }

    # ── GitHub code search (Phase 33) — needs token ──
    _m = re.match(r"(?:search|find)\s+code\s+(?:for\s+)?(.+)", text)
    if _m:
        return {"tool": "athena", "action": "github_code",
                "parameters": {"query": _m.group(1).strip()}, "confidence": 0.95}
    _m = re.match(r"github\s+code\s+(?:search\s+)?(.+)", text)
    if _m:
        return {"tool": "athena", "action": "github_code",
                "parameters": {"query": _m.group(1).strip()}, "confidence": 0.95}

    # ── GitHub repo search (Phase 33) — API, no browser ──
    _m = re.match(r"(?:search github(?: repos?| repositories)?(?: for)?|github repos?(?: for)?|search repos?(?: for)?|find(?: github)? repos?(?: for)?)\s+(.+)", text)
    if _m:
        return {"tool": "athena", "action": "github_repos",
                "parameters": {"query": _m.group(1).strip()}, "confidence": 0.94}

    # =====================================
    # CLICK / OPEN RESULT BY INDEX
    # =====================================
    result_index_map = {
        "first": 0,
        "second": 1,
        "third": 2,
        "fourth": 3,
        "fifth": 4,
        "1st": 0,
        "2nd": 1,
        "3rd": 2,
        "4th": 3,
        "5th": 4,
    }

    if text == "click first result":

        return {

            "tool":
            "veronica",

            "action":
            "open_result",

            "parameters": {
                "index": 0
            },

            "confidence":
            0.99
        }

    for word, idx in result_index_map.items():

        if text in [
            f"open {word} result",
            f"click {word} result",
            f"open result {idx + 1}",
        ]:

            return {

                "tool":
                "veronica",

                "action":
                "open_result",

                "parameters": {
                    "index": idx
                },

                "confidence":
                0.99
            }

    # =====================================
    # NAVIGATION
    # =====================================
    if text in ("go back", "back"):

        return {
            "tool": "veronica",
            "action": "go_back",
            "parameters": {},
            "confidence": 0.99
        }

    if text in ("go forward", "forward"):

        return {
            "tool": "veronica",
            "action": "go_forward",
            "parameters": {},
            "confidence": 0.99
        }

    # =====================================
    # PAGE UNDERSTANDING
    # =====================================
    if text in (
        "what page am i on",
        "current page",
        "where am i",
        "what page is this"
    ):
        return {
            "tool": "veronica",
            "action": "current_page",
            "parameters": {},
            "confidence": 0.99
        }

    if text in (
        "read page",
        "get page text",
        "page content"
    ):
        return {
            "tool": "veronica",
            "action": "get_page_text",
            "parameters": {},
            "confidence": 0.99
        }

    if text in (
        "summarize page",
        "summarize this page",
        "summarize website",
        "what is this page about"
    ):
        return {
            "tool": "veronica",
            "action": "summarize_page",
            "parameters": {},
            "confidence": 0.99
        }

    if text in (
        "read readme",
        "read the readme",
        "show readme"
    ):
        return {
            "tool": "veronica",
            "action": "read_readme",
            "parameters": {},
            "confidence": 0.99
        }

    if text in (
        "summarize project",
        "summarize repo",
        "summarize repository",
        "what is this repo about",
        "explain this project"
    ):
        return {
            "tool": "veronica",
            "action": "summarize_repo",
            "parameters": {},
            "confidence": 0.99
        }

    if text in (
        "extract links",
        "show links",
        "list links"
    ):
        return {
            "tool": "veronica",
            "action": "extract_links",
            "parameters": {},
            "confidence": 0.99
        }

    # =====================================
    # TAB MANAGEMENT (Phase 20)
    # =====================================
    # list tabs
    if text in ("list tabs", "show tabs", "what tabs", "what tabs do i have", "tabs", "show open tabs",
                "list my tabs", "list my browser tabs", "my tabs", "browser tabs", "show my tabs"):
        return {"tool": "veronica", "action": "list_tabs", "parameters": {}, "confidence": 0.99}

    # go to / visit / navigate to a URL or domain -> open in browser
    _m = re.match(r"(?:go to|visit|navigate to|browse to|open up)\s+((?:https?://)?[\w-]+(?:\.[\w-]+)+(?:/\S*)?)$",
                  text_raw, re.IGNORECASE)
    if _m:
        url = _m.group(1).strip()
        return {"tool": "veronica", "action": "open_url",
                "parameters": {"url": url if url.startswith("http") else "https://" + url}, "confidence": 0.96}

    # new tab — "open X in a new tab" / "open new tab"
    _m = re.match(r"open (.+?) in (?:a )?new tab", text)
    if _m:
        target = _m.group(1).strip()
        # Check if it's a website shortcut or URL
        return {"tool": "veronica", "action": "new_tab", "parameters": {"label": target, "url": target}, "confidence": 0.99}

    if text in ("new tab", "open new tab", "open a new tab"):
        return {"tool": "veronica", "action": "new_tab", "parameters": {}, "confidence": 0.99}

    # switch tab — "go to the github tab" / "switch to github tab" / "switch to tab github"
    _m = re.match(r"(?:go to|switch to|show|open) (?:the )?(.+?) tab", text)
    if _m:
        label = _m.group(1).strip()
        return {"tool": "veronica", "action": "switch_tab", "parameters": {"label": label}, "confidence": 0.99}

    _m = re.match(r"(?:go to|switch to) tab (.+)", text)
    if _m:
        label = _m.group(1).strip()
        return {"tool": "veronica", "action": "switch_tab", "parameters": {"label": label}, "confidence": 0.99}

    # close tab
    _m = re.match(r"close (?:the )?(.+?) tab", text)
    if _m:
        label = _m.group(1).strip()
        return {"tool": "veronica", "action": "close_tab", "parameters": {"label": label}, "confidence": 0.99}

    if text in ("close tab", "close this tab", "close current tab"):
        return {"tool": "veronica", "action": "close_tab", "parameters": {}, "confidence": 0.99}


    return None
