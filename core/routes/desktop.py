"""Router group — terminator desktop + veronica/routines. Extracted VERBATIM from route_single_intent,
same chain position, order preserved. Uses only text/text_raw. Move only — no logic changes.
"""
import re
import os


def try_route(text, text_raw):
    # =====================================
    # TERMINATOR — Windows desktop control (Phase 35)
    # =====================================
    if text in ("list windows", "show windows", "what windows are open",
                "list open windows", "show open windows", "open windows"):
        return {"tool": "terminator", "action": "list_windows", "parameters": {}, "confidence": 0.97}

    # focus / switch to a WINDOW (tab variants handled earlier -> veronica)
    _m = re.match(r"(?:focus|switch to|bring(?: up)?|go to|activate)\s+(?:the\s+)?(.+?)\s+window", text)
    if _m:
        return {"tool": "terminator", "action": "focus_window", "parameters": {"title": _m.group(1).strip()}, "confidence": 0.95}
    # "focus chrome" / "focus on notepad" — single app name, no "window" suffix
    _m = re.match(r"focus(?:\s+on)?\s+(?:the\s+)?(\w[\w.-]*)$", text)
    if _m:
        return {"tool": "terminator", "action": "focus_window", "parameters": {"title": _m.group(1).strip()}, "confidence": 0.9}

    # read a window's text
    _m = re.match(r"(?:read|what'?s in|get text from|show me)\s+(?:the\s+)?(.+?)\s+window", text)
    if _m:
        return {"tool": "terminator", "action": "get_window_text", "parameters": {"title": _m.group(1).strip()}, "confidence": 0.95}

    # type text into focused window — REQUIRE explicit target ("into X") or quoted text.
    # Was firing on "write me a function..." / "type my password into the chat" (treating chat
    # questions as literal keystroke commands -> typed gibberish into whatever window was up).
    # Dogfood S32 finding.
    _m = re.match(r'(?:type|type out|enter text)\s+(?:"([^"]+)"|\'([^\']+)\'|(.+?))\s+(?:in|into)\s+(?:the\s+)?(.+)', text)
    if _m and not re.search(r"\b(?:task|note|goal|reminder|habit)\b", text):
        _content = _m.group(1) or _m.group(2) or _m.group(3)
        return {"tool": "terminator", "action": "type_text",
                "parameters": {"text": _content.strip(), "window": _m.group(4).strip()}, "confidence": 0.9}

    # press a key combo — REQUIRE the press-shape to be SHORT (real shortcut form), and
    # destructive combos (alt+f4, ctrl+w, ctrl+q, ctrl+shift+t) refuse without explicit confirm.
    # Was: "press alt f4" -> closed whatever window was focused. Dogfood S32 finding.
    _m = re.match(r"(?:press|hit|send)\s+(.+)$", text)
    if _m and re.search(r"\b(ctrl|alt|shift|enter|tab|esc|escape|space|f\d+|delete|backspace)\b",
                       _m.group(1), re.IGNORECASE):
        _keys = _m.group(1).strip()
        # only treat as a shortcut if it's short (no full sentence after the modifier)
        if len(_keys.split()) <= 4:
            # destructive: refuse with confirm-required
            if re.search(r"\balt\s*[\+ ]?\s*f4\b|\bctrl\s*[\+ ]?\s*[wq]\b|\bctrl\s*[\+ ]?\s*shift\s*[\+ ]?\s*t\b",
                         _keys, re.IGNORECASE):
                return {"tool": "chat", "action": "respond", "confidence": 0.99,
                        "parameters": {"task": f"That's a destructive shortcut ({_keys}) — refusing. "
                                               f"Say 'force press {_keys}' if you really mean it."}}
            return {"tool": "terminator", "action": "press_keys",
                    "parameters": {"keys": _keys}, "confidence": 0.95}

    # click a named element in a window: "click X in Y"
    _m = re.match(r"click\s+(?:the\s+)?(.+?)\s+(?:button\s+)?in\s+(?:the\s+)?(.+)", text)
    if _m:
        return {"tool": "terminator", "action": "click_element",
                "parameters": {"element": _m.group(1).strip(), "window": _m.group(2).strip()}, "confidence": 0.9}

    # =====================================
    # ROUTINES / MACROS (Phase 43)
    # =====================================
    _m = re.match(r"(?:create|new|record|start|make)\s+(?:a\s+)?routine\s+(?:called\s+|named\s+)?(.+)", text)
    if _m:
        return {"tool": "routines", "action": "create_routine",
                "parameters": {"name": _m.group(1).strip()}, "confidence": 0.97}
    _m = re.match(r"(?:run|play|execute|do)\s+(?:the\s+)?routine\s+(.+)", text)
    if _m:
        return {"tool": "routines", "action": "run_routine",
                "parameters": {"name": _m.group(1).strip()}, "confidence": 0.97}
    _m = re.match(r"(?:delete|remove|forget)\s+(?:the\s+)?routine\s+(.+)", text)
    if _m:
        return {"tool": "routines", "action": "delete_routine",
                "parameters": {"name": _m.group(1).strip()}, "confidence": 0.97}

    # =====================================
    # n8n AUTOMATION (Phase 53) — trigger a workflow
    # =====================================
    _m = re.match(r"(?:run|trigger|execute|fire|start)\s+(?:the\s+)?(?:n8n\s+)?(?:workflow|automation)\s+(.+)", text)
    if _m:
        return {"tool": "n8n", "action": "trigger",
                "parameters": {"workflow": _m.group(1).strip()}, "confidence": 0.96}

    # =====================================
    # OPEN APP
    # =====================================
    # Strip polite/paraphrase prefixes so "can you open chrome" / "could you bring up X" /
    # "fire up X" / "i need X" all reach the open_app block (dogfood S27 found these falling
    # through to the LLM router which then misroutes to edith).
    _open_text = text
    for _pfx in ("can you ", "could you ", "would you ", "please ", "i need to ",
                 "let's ", "lets ", "i want to ", "i'd like to "):
        if _open_text.startswith(_pfx):
            _open_text = _open_text[len(_pfx):]
            break
    # paraphrase verbs -> canonical "open "
    for _alt in ("bring up ", "fire up ", "boot up ", "pull up ", "i need "):
        if _open_text.startswith(_alt):
            _open_text = "open " + _open_text[len(_alt):]
            break

    if _open_text.startswith(

        (
            "open ",
            "launch ",
            "start "
        )
    ):
        text = _open_text       # use the normalized form below

        app = (

            text.replace(
                "open ",
                ""
            )

            .replace(
                "launch ",
                ""
            )

            .replace(
                "start ",
                ""
            )

            .strip()
        )

        # A domain / URL (e.g. "open google.com") belongs in the browser, not the
        # desktop app launcher — route those to open_url instead of open_app.
        if re.match(r"^https?://", app) or re.match(r"^[\w-]+(\.[\w-]+)+(/\S*)?$", app):
            return {"tool": "veronica", "action": "open_url",
                    "parameters": {"url": app}, "confidence": 0.97}

        return {

            "tool":
            "veronica",

            "action":
            "open_app",

            "parameters": {

                "app":
                app
            },

            "confidence":
            0.99
        }


    return None
