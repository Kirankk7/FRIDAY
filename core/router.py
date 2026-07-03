import os
import re

from core.folder_memory import (
    get_folder_context,
    save_last_match,
    get_last_match,
    save_folder_context
)


def safe_fallback():

    print(
        "[router] SAFE FALLBACK USED"
    )

    return {

        "tool":
        "chat",

        "action":
        "respond",

        "parameters":
        {},

        "confidence":
        0.0
    }


# =====================================
# CLARIFICATION (Phase 51 #5)
# When both routers miss but the text contains command-like keywords,
# ask the user which action they meant instead of silently chatting.
# Only implemented intents listed — never suggest a feature that doesn't exist.
# =====================================
_CLARIFY_HINTS = [
    (r"\b(scan|nmap|ports?|recon|probe|httpx|nuclei|subdomain)\b",
     "scan a target", "scan example.com"),
    (r"\b(cve|vulnerab\w*|exploit|poc)\b",
     "look up a vulnerability", "search cve for log4j"),
    (r"\b(search|google|look\s?up|find out|news)\b",
     "search news or the web", "search news for AI"),
    (r"\b(youtube|video|watch|play)\b",
     "search YouTube", "search youtube for lofi"),
    (r"\b(remind|reminder)\b",
     "set a reminder", "remind me in 10 minutes to stretch"),
    (r"\b(schedule|calendar|meeting|appointment|event)\b",
     "schedule an event", "schedule gym for 6pm"),
    (r"\b(task|todo|to-do)\b",
     "manage a task", "add task buy milk"),
    (r"\b(note|notes)\b",
     "save a note", "add note call mom"),
    (r"\b(file|document|pdf|docx|folder|summarize|read)\b",
     "read or list files", "summarize report.pdf"),
    (r"\b(hash|md5|sha256|sha512|checksum)\b",
     "hash a value", "hash sha256 of mypassword"),
    (r"\b(habit|streak)\b",
     "track a habit", "add habit meditate"),
    (r"\b(workout|calories|macros|gym|exercise)\b",
     "fitness planning", "plan a push workout"),
]


def suggest_clarification(text: str):
    """Return a clarify decision if text looks command-ish but didn't route. Else None."""
    t = text.lower().strip()

    # Too short -> let normal chat handle it
    if len(t) < 3:
        return None

    words = t.split()

    # Long input = likely conversation, not a terse missed command
    if len(words) > 7:
        return None

    # Narrative/statement openers ("i had a workout", "my day was...") = chat, not command
    if re.match(r"^(i|i'm|im|i've|ive|my|we|he|she|they|it|that|this|there|you|your)\b", t):
        return None

    # Question words that aren't command-shaped -> let chat/LLM handle
    if re.match(r"^(why|how come|do you think|what do you think|tell me a)\b", t):
        return None

    hits = []
    seen = set()
    for pat, desc, example in _CLARIFY_HINTS:
        if re.search(pat, t) and desc not in seen:
            seen.add(desc)
            hits.append((desc, example))

    if not hits:
        return None

    if len(hits) == 1:
        desc, ex = hits[0]
        msg = f"Not sure what you meant there, boss. Did you want to {desc}? Try: \"{ex}\"."
    else:
        opts = "; ".join(f"{d} (e.g. \"{e}\")" for d, e in hits[:3])
        msg = f"Not sure what you meant, boss. Did you want to {opts}?"

    return {
        "tool": "chat",
        "action": "respond",
        "parameters": {"task": msg},
        "confidence": 0.5,
        "clarify": True,
    }


# =====================================
# EXACT-COMMAND FAST DISPATCH (Phase 51 #7)
# O(1) lookup for parameterless, state-independent commands — checked before
# the regex chain. Only unambiguous fixed phrases here (verified by the
# regression suite). Parameterized/stateful commands stay in the regex chain.
# =====================================
_EXACT_ROUTES = {
    # ── Browser navigation / page (veronica) ──
    "go back": ("veronica", "go_back"), "back": ("veronica", "go_back"),
    "go forward": ("veronica", "go_forward"), "forward": ("veronica", "go_forward"),
    "current page": ("veronica", "current_page"), "where am i": ("veronica", "current_page"),
    "what page am i on": ("veronica", "current_page"), "what page is this": ("veronica", "current_page"),
    "read page": ("veronica", "get_page_text"), "get page text": ("veronica", "get_page_text"),
    "page content": ("veronica", "get_page_text"),
    "read readme": ("veronica", "read_readme"), "read the readme": ("veronica", "read_readme"),
    "show readme": ("veronica", "read_readme"),
    "extract links": ("veronica", "extract_links"), "show links": ("veronica", "extract_links"),
    "list links": ("veronica", "extract_links"),
    # ── Friday lists ──
    "list tasks": ("friday", "list_tasks"), "show tasks": ("friday", "list_tasks"),
    "my tasks": ("friday", "list_tasks"), "show my tasks": ("friday", "list_tasks"),
    "what are my tasks": ("friday", "list_tasks"), "task list": ("friday", "list_tasks"),
    "list goals": ("friday", "list_goals"), "show goals": ("friday", "list_goals"),
    "my goals": ("friday", "list_goals"), "what are my goals": ("friday", "list_goals"),
    "list notes": ("friday", "list_notes"), "show notes": ("friday", "list_notes"),
    "my notes": ("friday", "list_notes"), "show my notes": ("friday", "list_notes"),
    "show habits": ("friday", "show_habits"), "my habits": ("friday", "show_habits"),
    "habit tracker": ("friday", "show_habits"), "habits": ("friday", "show_habits"),
    "list reminders": ("friday", "list_reminders"), "show reminders": ("friday", "list_reminders"),
    "my reminders": ("friday", "list_reminders"), "pending reminders": ("friday", "list_reminders"),
    "what are my reminders": ("friday", "list_reminders"), "list my reminders": ("friday", "list_reminders"),
    # ── System / status ──
    "browser status": ("system", "browser_status"),
    "is browser enabled": ("system", "browser_status"),
    # ── n8n automation ──
    "list workflows": ("n8n", "list_workflows"), "show workflows": ("n8n", "list_workflows"),
    "my workflows": ("n8n", "list_workflows"), "list automations": ("n8n", "list_workflows"),
    # ── routines / macros ──
    "list routines": ("routines", "list_routines"), "show routines": ("routines", "list_routines"),
    "my routines": ("routines", "list_routines"), "list macros": ("routines", "list_routines"),
    "list my routines": ("routines", "list_routines"), "show my routines": ("routines", "list_routines"),
    "stop recording": ("routines", "stop_recording"), "end routine": ("routines", "stop_recording"),
    "finish routine": ("routines", "stop_recording"),
}


# =====================================
# SINGLE INTENT ROUTER
# =====================================
def route_single_intent(
    text: str
):

    text_raw = (text or "").strip()        # original case — for case-sensitive captures (cookies, URLs, tokens)
    text = (
        text.lower()
        .strip()
    )

    # ── Adversarial / null input pre-filter (dogfood S30 — caught by user/GPT review) ──
    # Punctuation-only or 0-1 char inputs would otherwise fall through to the LLM router and
    # get misclassified (e.g. '"' -> ultron, '.' -> friday with leaked context). Catch them
    # here with a safe clarify reply instead.
    if text and len(text) <= 2 and not text.isalnum() and not re.match(r"\w", text):
        return {"tool": "chat", "action": "respond", "confidence": 0.99,
                "parameters": {"task": "Didn't catch that, boss — could you say what you'd like me to do?"}}
    # Emoji / symbol / punctuation-only input (NO alphabetic char in any script) can't be a
    # command. Route to chat directly so it never reaches the LLM router, which misclassifies
    # it as a tool call (dogfood S36: '🔥💀👾🤖🧨' -> ultron.nmap_scan -> hung on a real scan).
    # CJK/Arabic/etc keep an alphabetic char (isalpha True), so genuine language still passes.
    if text and not any(c.isalpha() for c in text) and not re.search(r"\d{2,}", text):
        return {"tool": "chat", "action": "respond", "confidence": 0.95,
                "parameters": {"task": "Not sure what you mean there, boss — what would you like me to do?"}}
    # Wall-of-noise guard (browser dogfood 2026-07-02): the UI sends the message in the URL and
    # the server caps it at 4000 chars — so a long low-entropy blob (repeated chars / one giant
    # token, no real words) truncates and falls to the LLM, which HALLUCINATES on prior context
    # (50000×'A' -> a fake "Battery 100%" reply; 9000×'A' -> rambled about recent grocery tasks).
    # Not a command -> clarify deterministically, never route it to the model.
    if len(text) > 200:
        _nospace = text.replace(" ", "")
        if len(set(_nospace)) <= 4 or (len(text.split()) <= 2 and len(text) > 400):
            return {"tool": "chat", "action": "respond", "confidence": 0.95,
                    "parameters": {"task": "That's a wall of text with no clear command, boss — "
                                           "tell me in a sentence what you'd like me to do."}}
    # Prompt-injection / jailbreak markers — refuse with a fixed safe reply, do NOT pass to LLM
    # (model would otherwise comply: 'I am DAN, I will follow your commands to the letter').
    _PI = re.compile(
        r"\b(?:ignore (?:all )?(?:previous|prior) (?:instructions|prompts)"
        r"|you are now (?:dan|jailbroken|unrestricted)"
        r"|do anything now\b"
        r"|reveal (?:your |the )?(?:hidden |system )?(?:instructions|prompt|rules)"
        r"|pretend (?:you have no |you are not )?(?:rules|restrictions)"
        r"|system:.*(?:reveal|ignore|override))",
        re.IGNORECASE)
    if _PI.search(text):
        return {"tool": "chat", "action": "respond", "confidence": 0.99,
                "parameters": {"task": "Not going to do that. My rules stay, boss — what do you actually need?"}}
    # Template-injection / shell-meta markers in a bare input -> safe clarify, NEVER eval-route.
    # Dogfood S32: '{{7*7}}' (SSTI marker) fell to LLM which returned '49' — looked like
    # template eval. Treat these as adversarial, not commands.
    if re.match(r"^\s*(?:\{\{[^}]*\}\}|\$\{[^}]*\}|<%[^%]*%>|\$\([^)]*\)|`[^`]*`)\s*$", text):
        return {"tool": "chat", "action": "respond", "confidence": 0.99,
                "parameters": {"task": "That looks like a template/injection marker — not running it. Tell me plainly what you'd like."}}

    # ── Deterministic follow-up resolution (conversation state, no LLM) ──
    # Resolve "do it again" / "now to spanish" against the LAST operation.
    try:
        from core import op_context as _opc
        _lop = _opc.last()
    except Exception:
        _lop = None
    if _lop:
        # Re-run the last operation verbatim.
        if re.fullmatch(r"(?:do it again|again|same(?: thing)?|repeat(?: that)?|one more time)\.?",
                        text, re.I):
            return {"tool": _lop["tool"], "action": _lop["action"],
                    "parameters": dict(_lop["parameters"]), "confidence": 0.9}
        # Re-translate the last source into a new language — needs a connective
        # ("now/and/to/in/translate that to X") so a bare word can't hijack it.
        if _lop.get("action") == "translate" and _lop["parameters"].get("text"):
            _fm = re.fullmatch(
                r"(?:now|and|then)\s+(?:translate (?:that|it)\s+)?(?:to |in |into )?([a-z]{3,})\??|"
                r"translate (?:that|it)\s+(?:to |in |into )?([a-z]{3,})\??|"
                r"(?:to|in|into)\s+([a-z]{3,})\??", text, re.I)
            if _fm:
                _lang = next((g for g in _fm.groups() if g), None)
                if _lang and _lang.lower() not in ("it", "that", "again", "the", "same"):
                    _p = dict(_lop["parameters"]); _p["target"] = _lang.strip()
                    return {"tool": "vision", "action": "translate", "parameters": _p, "confidence": 0.9}

    # Exact-command fast path — O(1) before the regex chain (Phase 51 #7)
    _exact = _EXACT_ROUTES.get(text)
    if _exact:
        return {"tool": _exact[0], "action": _exact[1], "parameters": {}, "confidence": 0.99}

    remembered = (
        get_folder_context()
    )

    remembered_folder = (
        remembered.get(
            "folder"
        )
    )

    remembered_files = (
        remembered.get(
            "files",
            []
        )
    )

      # =====================================
    # SHOW FILE TYPES
    # =====================================
    # File-type intercept — ONLY for actual file categories ("show me pdfs/images/videos/
    # documents"). Plain "show me X" must fall through (was hijacking "show me hacker news"
    # etc -> chat/respond, an over-grab found in dogfood S17).
    _show_me_cats = {"pdfs", "images", "videos", "documents", "pdf", "image", "video", "document"}
    _show_me_cat = text[8:].strip() if text.startswith("show me ") else ""
    if _show_me_cat in _show_me_cats:

        if not remembered_files:

            return {

                "tool":
                "chat",

                "action":
                "respond",

                "parameters": {

                    "task":
                    (
                        "I don't have "
                        "any folder context yet. "
                        "Open a folder and "
                        "list files first."
                    )
                },

                "confidence":
                0.99
            }

        file_filters = {

            "pdfs": [
                ".pdf"
            ],

            "images": [
                ".png",
                ".jpg",
                ".jpeg",
                ".gif",
                ".bmp",
                ".webp"
            ],

            "videos": [
                ".mp4",
                ".mkv",
                ".avi",
                ".mov",
                ".wmv"
            ],

            "documents": [
                ".doc",
                ".docx",
                ".txt",
                ".pdf",
                ".ppt",
                ".pptx",
                ".xls",
                ".xlsx"
            ]
        }

        category = (
            text.replace(
                "show me ",
                ""
            )
            .strip()
        )

        extensions = (
            file_filters.get(
                category
            )
        )

        # =====================================
        # UNKNOWN FILE TYPE
        # =====================================
        if not extensions:

            return {

                "tool":
                "chat",

                "action":
                "respond",

                "parameters": {

                    "task":
                    (
                        "I don't know "
                        "that file type. "
                        "Try PDFs, images, "
                        "videos, or "
                        "documents."
                    )
                },

                "confidence":
                0.99
            }

        filtered_files = []

        for file_name in remembered_files:

            lower_file = (
                file_name.lower()
            )

            if any(

                lower_file.endswith(ext)

                for ext in extensions
            ):

                filtered_files.append(
                    file_name
                )

        if filtered_files:

            save_folder_context(

                folder_path=
                remembered_folder,

                files=
                filtered_files
            )

            preview = (
                filtered_files[:10]
            )

            return {

                "tool":
                "chat",

                "action":
                "respond",

                "parameters": {

                    "task":
                    (
                        f"Found "
                        f"{len(filtered_files)} "
                        f"{category}:\n"
                        +
                        "\n".join(
                            preview
                        )
                    )
                },

                "confidence":
                0.99
            }

        return {

            "tool":
            "chat",

            "action":
            "respond",

            "parameters": {

                "task":
                (
                    f"No "
                    f"{category} "
                    f"found."
                )
            },

            "confidence":
            0.99
        }   
     # =====================================
    # YOUTUBE SEARCH
    # =====================================
    if (

        text.startswith(
            "open youtube and search "
        )

        or

        text.startswith(
            "search youtube for "
        )

        or

        "search youtube for"
        in text

    ):

        if (
            "open youtube and search "
            in text
        ):

            query = (
                text.replace(
                    "open youtube and search ",
                    ""
                )
                .strip()
            )

        elif (
            "search youtube for "
            in text
        ):

            query = (
                text.split(
                    "search youtube for "
                )[1]
                .strip()
            )

        else:

            query = ""

        return {

            "tool":
            "veronica",

            "action":
            "open_url",

            "parameters": {

                "url":
                (
                    f"search youtube for "
                    f"{query}"
                )
            },

            "confidence":
            0.99
        }

    # =====================================
    # FIND FILE
    # =====================================
    if (
        text.startswith(
            "find "
        )
        and
        remembered_files
    ):

        keyword = (
            text.replace(
                "find ",
                ""
            )
            .strip()
            .lower()
        )

        matches = []

        for file_name in (
            remembered_files
        ):

            if (
                keyword
                in
                file_name.lower()
            ):

                matches.append(
                    file_name
                )

        if matches:

            selected = (
                matches[0]
            )

            full_path = (
                os.path.join(
                    remembered_folder,
                    selected
                )
            )

            save_last_match(
                full_path
            )

            return {

                "tool":
                "chat",

                "action":
                "respond",

                "parameters": {

                    "task":
                    (
                        f"Found "
                        f"{selected}"
                    )
                },

                "confidence":
                0.99
            }

        return {

            "tool":
            "chat",

            "action":
            "respond",

            "parameters": {

                "task":
                (
                    "I couldn't "
                    "find anything "
                    "matching that."
                )
            },

            "confidence":
            0.99
        }

    # =====================================
    # OPEN FIRST FILE
    # =====================================
    if remembered_files:

        index_map = {

            "first": 0,
            "second": 1,
            "third": 2,
            "fourth": 3,
            "fifth": 4
        }

        for word, index in (
            index_map.items()
        ):

            if text in [

    f"open {word} file",

    f"open the {word} one",

    f"open {word} one"
]:

                if (
                    index
                    <
                    len(
                        remembered_files
                    )
                ):

                    selected = (
                        remembered_files[
                            index
                        ]
                    )

                    full_path = (
                        os.path.join(
                            remembered_folder,
                            selected
                        )
                    )

                    return {

                        "tool":
                        "file",

                        "action":
                        "open_file",

                        "parameters": {

                            "path":
                            full_path
                        },

                        "confidence":
                        0.99
                    }

    # =====================================
    # LIST FILES
    # =====================================
    if text in ("list files", "list my files", "list my documents", "list documents", "show my files"):
        return {"tool": "file", "action": "list_files",
                "parameters": {"path": remembered_folder or ""}, "confidence": 0.97}

    # =====================================
    # SEARCHES
    # =====================================
    # =====================================
    # ULTRON SECURITY
    # =====================================

    # ── Nmap variants ──
    _m = re.match(r"(?:quick scan|fast scan)\s+(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "nmap_scan", "parameters": {"target": _m.group(1).strip(), "scan_type": "quick"}, "confidence": 0.99}

    _m = re.match(r"(?:service scan|version scan)\s+(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "nmap_scan", "parameters": {"target": _m.group(1).strip(), "scan_type": "service"}, "confidence": 0.99}

    _m = re.match(r"(?:deep scan|full port scan)\s+(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "nmap_scan", "parameters": {"target": _m.group(1).strip(), "scan_type": "full"}, "confidence": 0.99}

    if text.startswith("scan "):
        target = text.replace("scan ", "").strip()
        # "scan my computer / my system / my pc" -> local defensive scan, NOT nmap a target.
        if re.search(r"\b(my (?:computer|system|pc|laptop|machine|network)|localhost|this (?:pc|machine))\b", target):
            return {"tool": "ultron", "action": "defensive_scan", "parameters": {}, "confidence": 0.95}
        # Only nmap when the target LOOKS like a host (domain / IP / host:port). Otherwise
        # 'scan it' / 'scan reminder note translate' would launch a scan on garbage (hang/
        # wrong-target). Dogfood S35.
        if re.match(r"^(?:https?://)?(?:\d{1,3}(?:\.\d{1,3}){3}|[\w-]+(?:\.[\w-]+)+)(?::\d+)?(?:/\S*)?$", target):
            return {"tool": "ultron", "action": "nmap_scan", "parameters": {"target": target}, "confidence": 0.99}
        return {"tool": "chat", "action": "respond", "confidence": 0.95,
                "parameters": {"task": f"Scan what exactly, boss? Give me a host or IP "
                                       f"(e.g. 'scan example.com'), or say 'scan my computer' for a local check."}}

    if text.startswith("full scan ") or text.startswith("full recon "):
        target = text.replace("full scan ", "").replace("full recon ", "").strip()
        return {"tool": "ultron", "action": "full_recon", "parameters": {"target": target}, "confidence": 0.99}

    _m = re.match(r"(?:recon|run recon on|recon on)\s+(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "full_recon", "parameters": {"target": _m.group(1).strip()}, "confidence": 0.99}

    # Router group: ultron security + recon cluster (extracted -> core/routes/security.py).
    from core.routes import security as _rt_sec
    _s = _rt_sec.try_route(text, text_raw)
    if _s:
        return _s

    # =====================================
    # PHASE 42 — QUICK WINS BATCH
    # =====================================

    # Speed test — keyword match (tolerant of paraphrases, not just exact phrases)
    if re.search(r"\b(?:speed[\s-]?test|internet speed|network speed|connection speed|"
                 r"how fast is (?:my|the) (?:internet|wifi|connection|network)|"
                 r"test (?:my )?(?:internet|connection|network|download) speed)\b", text):
        return {"tool": "system", "action": "speed_test", "parameters": {}, "confidence": 0.98}

    # Battery — keyword match
    if re.search(r"\bbatter(?:y|ies)\b|\bam i charging\b|\bhow charged\b", text):
        return {"tool": "system", "action": "battery_status", "parameters": {}, "confidence": 0.98}

    # CPU / RAM / system info / recall — keyword (were exact-only / missing -> LLM misroute)
    if re.search(r"\b(?:cpu|processor)\s+(?:usage|load|utili[sz]ation|use)\b", text) or text in ("cpu", "cpu usage"):
        return {"tool": "system", "action": "cpu_usage", "parameters": {}, "confidence": 0.97}
    if re.search(r"\b(?:ram|memory)\s+(?:usage|used|use)\b|how much (?:ram|memory)", text):
        return {"tool": "system", "action": "ram_usage", "parameters": {}, "confidence": 0.97}
    # NOTE: "system info" intentionally NOT routed here — veronica.system_info owns it (legacy design).
    if re.search(r"\brecall (?:the )?last result\b|\bwhat was the last result\b", text):
        return {"tool": "system", "action": "recall_result", "parameters": {}, "confidence": 0.95}

    # Router group: crypto toolkit + daily-driver features (extracted -> core/routes/daily.py).
    from core.routes import daily as _rt_daily
    _d = _rt_daily.try_route(text, text_raw)
    if _d:
        return _d

    # DNS lookup — only when target is domain/IP shaped (avoids grabbing "look up <topic>")
    _dns_m = re.match(r"(?:dns lookup|look ?up|nslookup|resolve|who owns|reverse dns|ip of|ip for)\s+(\S+)", text)
    if _dns_m:
        _dns_t = _dns_m.group(1).strip()
        # domain (foo.bar) or IPv4 — otherwise it's a topic lookup, not DNS
        if re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", _dns_t, re.IGNORECASE) or \
           re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", _dns_t):
            return {"tool": "ultron", "action": "dns_lookup", "parameters": {"target": _dns_t}, "confidence": 0.95}

    # Hash
    _hash_m = re.match(r"(?:hash|md5|sha256|sha512|sha1|checksum|get hash of|calculate hash(?: of)?)\s+(.+)", text)
    if _hash_m:
        algo_map = {"md5": "md5", "sha1": "sha1", "sha256": "sha256", "sha512": "sha512", "sha3": "sha3_256"}
        algo = next((a for a in algo_map if text.startswith(a)), "sha256")
        target = _hash_m.group(1).strip()
        # "hash sha256 X" — strip leading algo word from target, use it as algorithm
        _lead = target.split()[0].lower() if target.split() else ""
        if _lead in algo_map:
            algo = algo_map[_lead]
            target = target[len(target.split()[0]):].strip()
        if target.lower().startswith("of "):   # "hash sha256 OF mypassword" -> drop the "of"
            target = target[3:].strip()
        return {"tool": "ultron", "action": "hash_target", "parameters": {"target": target, "algorithm": algo}, "confidence": 0.95}

    # Password generator
    _pwd_m = re.match(r"(?:generate|create|make)(?: a)? (?:secure |random |strong )?password(?: of (\d+) chars?)?", text)
    if _pwd_m or text in ("generate password", "random password", "secure password", "new password"):
        length = 20
        if _pwd_m and _pwd_m.group(1):
            try:
                length = int(_pwd_m.group(1))
            except Exception:
                pass
        return {"tool": "friday", "action": "generate_password", "parameters": {"length": length}, "confidence": 0.99}

    # Calories calculator
    if re.search(r"\b(?:calories?|macros?|tdee|bmr|daily\s+calories?|how\s+much\s+(?:should\s+i\s+eat|calories))\b", text, re.IGNORECASE):
        if re.search(r"\b(?:calculate|how\s+many|what(?:'s|\s+is)|my|should\s+i|daily|need|eat)\b", text, re.IGNORECASE):
            # Extract optional inline params
            params = {}
            _g = re.search(r"\b(male|female|man|woman)\b", text, re.IGNORECASE)
            if _g: params["gender"] = _g.group(1)
            _age = re.search(r"\b(\d{1,2})\s*(?:years?\s*old|yo|yr)\b", text, re.IGNORECASE)
            if _age: params["age"] = int(_age.group(1))
            _goal = "lose" if "lose" in text else "gain" if "gain" in text or "bulk" in text else "maintain"
            params["goal"] = _goal
            return {"tool": "friday", "action": "calculate_calories", "parameters": params, "confidence": 0.90}

    # Workout planner
    _workout_m = re.match(
        r"(?:plan|give me|create|make)(?: a)? (?:(\w+(?:\s+\w+)?)\s+)?(?:workout|training|exercise\s+plan|gym\s+plan)",
        text, re.IGNORECASE
    )
    if _workout_m or text in ("workout plan", "gym plan", "workout", "exercise plan"):
        focus = _workout_m.group(1).strip() if _workout_m and _workout_m.group(1) else "full body"
        level = "beginner" if "begin" in text else "advanced" if "adv" in text else "intermediate"
        return {"tool": "friday", "action": "plan_workout", "parameters": {"focus": focus, "fitness_level": level}, "confidence": 0.90}

    # HackerNews
    if re.search(r"\b(?:hacker\s*news|hackernews|hn|tech\s+news|what(?:'s|\s+is)\s+on\s+hacker\s*news)\b", text, re.IGNORECASE):
        return {"tool": "vision", "action": "hackernews", "parameters": {"n": 5}, "confidence": 0.95}

    # Router group: vision live-info — currency/translate/flight/crypto-price (extracted -> core/routes/vision.py).
    from core.routes import vision as _rt_vision
    _v = _rt_vision.try_route(text, text_raw)
    if _v:
        return _v

    # =====================================
    from core.routes import info as _rt_info
    _r = _rt_info.try_route(text, text_raw)
    if _r:
        return _r
    from core.routes import research as _rt_research
    _r = _rt_research.try_route(text, text_raw)
    if _r:
        return _r
    from core.routes import desktop as _rt_desktop
    _r = _rt_desktop.try_route(text, text_raw)
    if _r:
        return _r
    from core.routes import friday as _rt_friday
    _r = _rt_friday.try_route(text, text_raw)
    if _r:
        return _r
    from core.routes import personal as _rt_personal
    _r = _rt_personal.try_route(text, text_raw)
    if _r:
        return _r
    return None


# =====================================
# MAIN ROUTER
# =====================================
def fast_route(
    user_input: str
):

    text = (
        user_input.lower()
        .strip()
    )

    # =====================================
    # DIRECT YOUTUBE SEARCH
    # =====================================
    if text.startswith(
        "open youtube and search "
    ):

        return route_single_intent(
            text
        )

    # =====================================
    # OPEN CHROME + ACTION
    # SMART BROWSER AUTOMATION
    # =====================================
    if (
        text.startswith(
            "open chrome and "
        )
    ):

        second_action = (
            text.replace(
                "open chrome and ",
                ""
            )
            .strip()
        )

        # =====================================
        # BROWSER AUTOMATION
        # DON'T OPEN EXTRA CHROME
        # =====================================
        if (

            second_action.startswith(
                "search youtube for "
            )

            or

            second_action.startswith(
                "search google for "
            )

            or

            second_action.startswith(
                "search github for "
            )

            or

            second_action.startswith(
                "open youtube and search "
            )

        ):

            return route_single_intent(
                second_action
            )

        # =====================================
        # NORMAL CHROME WORKFLOW
        # =====================================
        return {

            "tool":
            "workflow",

            "action":
            "multi_step",

            "parameters": {

                "steps": [

                    {
                        "tool":
                        "veronica",

                        "action":
                        "open_app",

                        "parameters": {

                            "app":
                            "chrome"
                        }
                    },

                    route_single_intent(
                        second_action
                    )
                ]
            },

            "confidence":
            0.99
        }

    folders = [

        "downloads",
        "documents",
        "desktop",
        "pictures",
        "videos",
        "music"
    ]

    for folder in folders:

        if (
            f"open {folder}"
            in text
        ):

            steps = [

                {
                    "tool":
                    "veronica",

                    "action":
                    "open_app",

                    "parameters": {

                        "app":
                        folder
                    }
                }
            ]

            if (
                "list files"
                in text
            ):

                steps.append({

                    "tool":
                    "file",

                    "action":
                    "list_files",

                    "parameters": {

                        "path":
                        f"~/{folder.capitalize()}"
                    }
                })

            if (
                "find "
                in text
            ):

                keyword = (
                    text.split(
                        "find "
                    )[-1]
                    .split(
                        " and open it"
                    )[0]
                    .strip()
                )

                route = (
                    route_single_intent(
                        f"find {keyword}"
                    )
                )

                if route:

                    steps.append({

                        "tool":
                        route["tool"],

                        "action":
                        route["action"],

                        "parameters":
                        route.get(
                            "parameters",
                            {}
                        )
                    })

            if (
                "and open it"
                in text
            ):

                route = (
                    route_single_intent(
                        "open it"
                    )
                )

                if route:

                    steps.append({

                        "tool":
                        route["tool"],

                        "action":
                        route["action"],

                        "parameters":
                        route.get(
                            "parameters",
                            {}
                        )
                    })

            return {

                "tool":
                "workflow",

                "action":
                "multi_step",

                "parameters": {

                    "steps":
                    steps
                },

                "confidence":
                0.99
            }

    # Don't split personal memory commands on "and" — "invest in X and Y" is one fact
    _personal_prefixes = (
        "my weight", "i weigh", "i live in", "i'm based in", "my name is",
        "call me", "i invest in", "my investment", "i'm studying for",
        "i'm preparing for", "i work as", "i'm a ", "my job is", "my career is",
        "i have lasik", "i've had", "i am a ", "i'm doing a", "i'm pursuing",
        "what do you know about me", "my details", "my age", "my height",
        "my budget", "my goal", "set my",
    )
    if any(text.startswith(p) for p in _personal_prefixes):
        return route_single_intent(text)

    parts = re.split(
        r"\s+(?:and|then)\s+",
        text
    )

    if len(parts) > 1:

        steps = []

        for part in parts:

            route = (
                route_single_intent(
                    part
                )
            )

            if route:

                steps.append({

                    "tool":
                    route["tool"],

                    "action":
                    route["action"],

                    "parameters":
                    route.get(
                        "parameters",
                        {}
                    )
                })

        if steps:

            return {

                "tool":
                "workflow",

                "action":
                "multi_step",

                "parameters": {

                    "steps":
                    steps
                },

                "confidence":
                0.99
            }

    # fall through to the full router — pass the ORIGINAL input (not the lowercased `text`)
    # so route_single_intent's text_raw can preserve case for cookies / URLs / session names
    # (idor/replay/session-set/graphql). Lowercasing here broke "userA" -> "usera".
    return route_single_intent(
        user_input
    )


def route(
    user_input: str
):

    # ==========================
    # COORDINATOR — multi-agent compound commands
    # Runs before regex to catch cross-agent intent
    # ==========================
    try:
        from core.coordinator import should_coordinate, coordinate
        if should_coordinate(user_input):
            print("[router] COORDINATOR CHECK")
            coord_result = coordinate(user_input)
            if coord_result:
                print(f"[router] COORDINATOR USED: {len(coord_result['parameters']['steps'])} steps")
                return coord_result
    except Exception as e:
        print(f"[router] Coordinator error: {e}")

    quick = (
        fast_route(
            user_input
        )
    )

    if quick:

        print(
            "[router] FAST ROUTER USED"
        )

        print(
            f"[router] Decision: "
            f"{quick}"
        )

        return quick

    # Regex missed — try LLM intent classification
    try:
        from core.llm_router import llm_classify_intent
        llm_route = llm_classify_intent(user_input)
        if llm_route:
            print(f"[router] LLM ROUTER USED: {llm_route}")
            return llm_route
    except Exception as e:
        print(f"[router] LLM router error: {e}")

    # Both routers missed — if text looks command-ish, ask for clarification
    clar = suggest_clarification(user_input)
    if clar:
        print("[router] CLARIFICATION OFFERED")
        return clar

    return safe_fallback()