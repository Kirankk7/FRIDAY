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
        return {"tool": "ultron", "action": "nmap_scan", "parameters": {"target": target}, "confidence": 0.99}

    if text.startswith("full scan ") or text.startswith("full recon "):
        target = text.replace("full scan ", "").replace("full recon ", "").strip()
        return {"tool": "ultron", "action": "full_recon", "parameters": {"target": target}, "confidence": 0.99}

    _m = re.match(r"(?:recon|run recon on|recon on)\s+(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "full_recon", "parameters": {"target": _m.group(1).strip()}, "confidence": 0.99}

    # Phase 24 — full pipeline
    _m = re.match(r"(?:full pipeline|complete recon|deep recon|pipeline recon|run pipeline on?)\s+(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "full_pipeline", "parameters": {"target": _m.group(1).strip()}, "confidence": 0.99}

    # Phase 54 — bug-bounty workflow (recon -> hunt -> validate -> report)
    _m = re.match(r"(?:bug bounty(?: on)?|bugbounty|full hunt(?: on)?|hunt(?: on)?|bug hunt(?: on)?|run bug bounty on?)\s+(?!notes?\b|methodology\b|playbook\b)(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "bug_bounty", "parameters": {"target": _m.group(1).strip()}, "confidence": 0.98}

    # Phase 59 — multimodal vision (image / screenshot understanding)
    if text in ("what's on my screen", "whats on my screen", "what is on my screen",
                "describe my screen", "look at my screen", "read my screen",
                "what's on screen", "analyze my screen"):
        return {"tool": "vision", "action": "screenshot_describe", "parameters": {}, "confidence": 0.96}

    _img = re.match(
        r"(?:describe|what'?s? (?:in|on)|look at|analy[sz]e|read|caption)\s+(?:this\s+|the\s+)?(?:image|picture|photo|screenshot|img)?\s*(.+\.(?:png|jpe?g|gif|bmp|webp))",
        text, re.IGNORECASE)
    if _img:
        return {"tool": "vision", "action": "describe_image",
                "parameters": {"path": _img.group(1).strip().strip('"\'')}, "confidence": 0.95}

    # Phase 63 — target profiles · burp ingest · github hunt
    if text in ("list targets", "profiled targets", "show targets", "my targets"):
        return {"tool": "ultron", "action": "list_targets", "parameters": {}, "confidence": 0.97}

    if text in ("scope", "show scope", "scope status", "what is my scope", "whats my scope", "current scope"):
        return {"tool": "ultron", "action": "scope_status", "parameters": {}, "confidence": 0.98}

    # ── Target monitor (mapper-lite: watch a target, alert on change) ──
    if text in ("list watched", "watched targets", "list monitored", "monitored targets",
                "what am i watching", "show watchlist"):
        return {"tool": "ultron", "action": "list_watched", "parameters": {}, "confidence": 0.97}
    if text in ("check targets", "check targets now", "monitor now", "monitor targets",
                "scan watched targets", "check for changes"):
        return {"tool": "ultron", "action": "monitor_targets", "parameters": {}, "confidence": 0.97}
    _m = re.match(r"(?:stop watching|unwatch|stop monitoring|remove watch(?: on)?)\s+(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "unwatch_target", "parameters": {"target": _m.group(1).strip()}, "confidence": 0.96}
    _m = re.match(r"(?:watch target|monitor target|start watching|start monitoring|keep an eye on)\s+(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "watch_target", "parameters": {"target": _m.group(1).strip()}, "confidence": 0.95}

    _m = re.match(r"(?:target profile|profile (?:for|of)?|what do (?:we|i) know about|recall target)\s+(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "target_profile", "parameters": {"target": _m.group(1).strip()}, "confidence": 0.95}

    _m = re.match(r"(?:note (?:on|for|about)|add note (?:on|to)?)\s+(\S+)\s*[:,-]?\s*(.+)", text)
    if _m and "routine" not in text:
        return {"tool": "ultron", "action": "profile_note",
                "parameters": {"target": _m.group(1).strip(), "note": _m.group(2).strip()}, "confidence": 0.9}

    _m = re.match(r"(?:ingest burp|burp ingest|import burp|load burp(?: history| export)?)\s+(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "ingest_burp", "parameters": {"path": _m.group(1).strip().strip('"\'')}, "confidence": 0.96}

    _m = re.match(r"(?:github hunt|gh hunt|hunt github|secret hunt|github secret hunt)\s+(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "github_hunt", "parameters": {"org": _m.group(1).strip()}, "confidence": 0.95}

    _m = re.match(r"(?:collect evidence|capture evidence|get evidence|retest|re-?test|validate (?:finding|url))\s+(?:for |on )?(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "collect_evidence", "parameters": {"url": _m.group(1).strip()}, "confidence": 0.94}

    # Phase 62 — Ultron Knowledge Pack (bug-bounty methodology + wordlists)
    _m = re.match(r"(?:list )?(?:bundled )?wordlists?$|wordlists? for\s+(.+)", text)
    if text in ("wordlists", "list wordlists", "bundled wordlists"):
        return {"tool": "ultron", "action": "kb_wordlist", "parameters": {"kind": ""}, "confidence": 0.96}
    _m = re.match(r"(?:wordlist|payload list|payloads?) (?:for |of )?(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "kb_wordlist", "parameters": {"kind": _m.group(1).strip()}, "confidence": 0.95}

    # Playbook — technique library recall + manual add
    _m = re.match(r"(?:remember(?: this)? technique|learn technique|note technique|save technique)\s*:?\s*(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "remember_technique",
                "parameters": {"text": _m.group(1).strip()}, "confidence": 0.95}
    if text in ("find programs", "find bug bounty programs", "program dorks", "bug bounty dorks",
                "find bounty programs", "find rd programs"):
        return {"tool": "ultron", "action": "find_programs", "parameters": {}, "confidence": 0.95}
    _m = re.match(r"(?:find programs?|program dorks?)\s+(?:in\s+)?(\w{2,3})$", text)
    if _m:
        return {"tool": "ultron", "action": "find_programs", "parameters": {"region": _m.group(1)}, "confidence": 0.95}
    _m = re.match(r"(?:target dorks?|recon dorks?|dorks?(?: for| on)?)\s+(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "target_dorks", "parameters": {"target": _m.group(1).strip()}, "confidence": 0.94}
    _m = re.match(r"(?:ingest feed|learn from feed|ingest writeups from|feed ingest|"
                  r"learn from(?: this)? (?:list|index|feed))\s+(https?://\S+)", text)
    if _m:
        return {"tool": "ultron", "action": "ingest_feed", "parameters": {"url": _m.group(1).strip()}, "confidence": 0.95}
    # multi-user authz (Tier-1): session set/list, replay-as, idor check. Match on text_raw
    # (original case) so cookies / tokens / URLs aren't lowercased.
    _m = re.match(r"(?:session set|set session)\s+(\w+)\s+cookie\s+(.+)", text_raw, re.I)
    if _m:
        return {"tool": "ultron", "action": "session_set",
                "parameters": {"name": _m.group(1), "cookie": _m.group(2).strip()}, "confidence": 0.96}
    _m = re.match(r"(?:session set|set session)\s+(\w+)\s+bearer\s+(.+)", text_raw, re.I)
    if _m:
        return {"tool": "ultron", "action": "session_set",
                "parameters": {"name": _m.group(1), "bearer": _m.group(2).strip()}, "confidence": 0.96}
    if text in ("session list", "list sessions", "sessions"):
        return {"tool": "ultron", "action": "session_list", "parameters": {}, "confidence": 0.97}
    _m = re.match(r"(?:idor check|check idor|bola check|idor)\s+(https?://\S+)"
                  r"(?:\s+as\s+(\w+))?(?:\s+(?:vs|versus|against)\s+(\w+))?", text_raw, re.I)
    if _m:
        p = {"url": _m.group(1)}
        if _m.group(2): p["owner"] = _m.group(2)
        if _m.group(3): p["attacker"] = _m.group(3)
        return {"tool": "ultron", "action": "idor_check", "parameters": p, "confidence": 0.95}
    _m = re.match(r"replay\s+(https?://\S+)\s+as\s+(\w+)", text_raw, re.I)
    if _m:
        return {"tool": "ultron", "action": "replay_as",
                "parameters": {"url": _m.group(1), "name": _m.group(2)}, "confidence": 0.95}
    _m = re.match(r"(?:graphql hunt|hunt graphql|graphql)\s+(https?://\S+)(?:\s+as\s+(\w+))?", text_raw, re.I)
    if _m:
        p = {"url": _m.group(1)}
        if _m.group(2): p["as_user"] = _m.group(2)
        return {"tool": "ultron", "action": "graphql_hunt", "parameters": p, "confidence": 0.95}
    _m = re.match(r"(?:ingest writeup|ingest this writeup|learn(?: from)?(?: this)?(?: writeup)?|"
                  r"read(?: this)? writeup|study writeup)\s+(https?://\S+)", text)
    if _m:
        return {"tool": "ultron", "action": "ingest_writeup", "parameters": {"url": _m.group(1).strip()}, "confidence": 0.95}
    _m = re.match(r"(?:playbook|recall techniques?|techniques? for|what techniques?(?: for)?)\s+(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "playbook_recall", "parameters": {"query": _m.group(1).strip()}, "confidence": 0.93}

    _m = re.match(r"(?:methodology|how (?:do i|to)|how can i|steps to|guide to|approach for|"
                  r"bug bounty notes? (?:on|for|about)|notes? (?:on|for|about))\s+(.+)", text)
    if _m and any(w in text for w in (
            "test", "find", "exploit", "hunt", "bypass", "takeover", "recon", "enumerate",
            "ssrf", "xss", "sqli", "idor", "lfi", "rce", "injection", "redirect", "csrf",
            "subdomain", "dork", "methodology", "playbook", "notes")):
        return {"tool": "ultron", "action": "kb_methodology",
                "parameters": {"query": text}, "confidence": 0.9}

    # Phase 59 — defensive / blue-team host monitor
    if text in ("defensive scan", "defense scan", "blue team scan", "check my system",
                "check my system security", "scan my system", "monitor my system",
                "am i compromised", "is my machine compromised", "check for threats",
                "security check", "watch my system"):
        return {"tool": "ultron", "action": "defensive_scan", "parameters": {}, "confidence": 0.97}
    if text in ("set security baseline", "set baseline", "save security baseline",
                "baseline my system", "this is normal", "remember my system state"):
        return {"tool": "ultron", "action": "set_security_baseline", "parameters": {}, "confidence": 0.97}

    # Phase 36 — HackingTool fleet (scoped allowlist, native/WSL/Docker)
    if text in ("ht preflight", "hackingtool preflight", "pentest backend",
                "check pentest backend", "tool backend"):
        return {"tool": "ultron", "action": "ht_preflight", "parameters": {}, "confidence": 0.98}

    _m = re.match(r"(?:ht search|hackingtool search|search (?:hacking ?)?tools?|find (?:hacking ?)?tool)\s+(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "ht_search", "parameters": {"query": _m.group(1).strip()}, "confidence": 0.97}

    # "run <tool_id> on <target>" / "ht run <tool_id> <args>"
    _m = re.match(r"(?:ht run|hackingtool run|run tool)\s+(\S+)(?:\s+(?:on|against|with)?\s*(.+))?$", text)
    if _m:
        return {"tool": "ultron", "action": "ht_run",
                "parameters": {"tool_id": _m.group(1).strip(),
                               "args": (_m.group(2) or "").strip()},
                "confidence": 0.96}

    # multi-page BFS crawl (follow links -> full param surface across sub-pages) — before katana
    _m = re.match(r"(?:multi[\s-]?page[\s-]?crawl|crawl[\s-]?site|site[\s-]?crawl|deep[\s-]?crawl|crawl\s+site|crawl\s+all\s+pages)\s+(?:on\s+)?(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "crawl_site", "parameters": {"target": _m.group(1).strip()}, "confidence": 0.96}
    # Katana crawl
    _m = re.match(r"(?:crawl|katana|spider)\s+(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "katana_crawl", "parameters": {"target": _m.group(1).strip()}, "confidence": 0.99}

    # Content discovery (brute hidden paths/dirs)
    _m = re.match(r"(?:content[\s-]?discovery|(?:dir|directory|content)[\s-]?(?:brute|bust|fuzz)\w*|find (?:hidden|directories|paths)(?:\s+on)?|fuzz (?:dirs?|paths?|directories))\s+(?:on\s+)?(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "content_discovery", "parameters": {"target": _m.group(1).strip()}, "confidence": 0.98}

    # SPA render-crawl (headless browser -> capture JS app's API surface)
    _m = re.match(r"(?:spa[\s-]?crawl|render[\s-]?crawl|(?:crawl|render)\s+spa|js[\s-]?crawl)\s+(?:on\s+)?(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "spa_crawl", "parameters": {"target": _m.group(1).strip()}, "confidence": 0.98}

    # Screenshot
    _m = re.match(r"(?:screenshot|take screenshot of|screengrab)\s+(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "take_screenshot", "parameters": {"target": _m.group(1).strip()}, "confidence": 0.99}

    if text.startswith("find subdomains ") or text.startswith("subdomains ") or text.startswith("enum subdomains "):
        target = re.sub(r"^(find subdomains|subdomains|enum subdomains)\s+", "", text).strip()
        return {"tool": "ultron", "action": "subfinder", "parameters": {"target": target}, "confidence": 0.99}

    if text.startswith("probe ") or text.startswith("httpx ") or text.startswith("check http "):
        target = re.sub(r"^(probe|httpx|check http)\s+", "", text).strip()
        return {"tool": "ultron", "action": "httpx_probe", "parameters": {"target": target}, "confidence": 0.99}

    # ── Nuclei with severity ──
    _m = re.match(r"(?:run nuclei on|nuclei|scan for (?:critical|high|medium) vulns?(?:erabilities)? on?)\s+(.+)", text)
    if _m:
        target = _m.group(1).strip()
        sev = "critical" if "critical" in text else "high,critical" if "high" in text else "medium,high,critical"
        return {"tool": "ultron", "action": "nuclei_scan", "parameters": {"target": target, "severity": sev}, "confidence": 0.99}

    if text in ("system health", "check health", "health check", "check system health"):
        return {"tool": "ultron", "action": "system_health", "parameters": {}, "confidence": 0.99}

    # ── VirusTotal scan (Phase 30b) — file/hash/url/domain reputation ──
    # "is X malicious/safe/dangerous/a virus"
    _m = re.match(r"is\s+(?:this\s+)?(.+?)\s+(?:malicious|safe|dangerous|a virus|infected)\??$", text)
    if _m:
        return {"tool": "ultron", "action": "vt_scan", "parameters": {"target": _m.group(1).strip()}, "confidence": 0.95}

    # "check X on virustotal" / "look up X on virustotal" — target before trailing "on virustotal"
    # (handled before the generic prefix form; note: "scan ..." is shadowed by nmap block above)
    _m = re.match(r"(?:check|look ?up|is)\s+(.+?)\s+on\s+virustotal\??$", text)
    if _m:
        return {"tool": "ultron", "action": "vt_scan", "parameters": {"target": _m.group(1).strip()}, "confidence": 0.96}

    # "virustotal X" / "vt scan X" / "vt X" / "reputation of X" / "virus|malware|threat scan X"
    _m = re.match(
        r"(?:virustotal|vt scan|vt|check virustotal|reputation of|"
        r"virus scan|malware scan|threat scan)\s+(.+)",
        text, re.IGNORECASE
    )
    if _m:
        tgt = _m.group(1).strip().rstrip("?")
        return {"tool": "ultron", "action": "vt_scan", "parameters": {"target": tgt}, "confidence": 0.96}

    # Phase 66 — threat-intel IOC aggregator: "threat intel X" / "ioc X" / "reputation check X" / "is X malicious"
    _m = re.match(
        r"(?:threat intel|threat intelligence|ioc(?: lookup| check)?|reputation check|"
        r"check ioc|intel on|is)\s+(.+?)(?:\s+malicious| dangerous)?\??$",
        text, re.IGNORECASE
    )
    if _m and _m.group(1).strip().lower() not in ("my machine", "my system", "this safe"):
        return {"tool": "ultron", "action": "threat_intel",
                "parameters": {"ioc": _m.group(1).strip().rstrip("?")}, "confidence": 0.94}

    # ── File scan (local heuristic) ──
    _m = re.match(r"(?:scan file|check file|file scan|analyze file)\s+(.+)", text)
    if _m:
        return {"tool": "ultron", "action": "file_scan", "parameters": {"path": _m.group(1).strip()}, "confidence": 0.99}

    # ── Log check ──
    if text in ("check logs", "show logs", "scan logs", "log check", "check system logs", "check event logs"):
        return {"tool": "ultron", "action": "log_check", "parameters": {}, "confidence": 0.99}

    # ── Export HTML ──
    if text in ("export report", "export report html", "save report html", "save report as html", "export html report"):
        return {"tool": "ultron", "action": "export_html", "parameters": {}, "confidence": 0.99}

    # ── CVE Tracker (Phase 23) ──
    _m = re.match(
        r"(?:track|watch|monitor|add)\s+(cve[- ]\d{4}[- ]\d+|\d{4}[- ]\d+)",
        text, re.IGNORECASE
    )
    if _m:
        cve = _m.group(1).replace(" ", "-")
        return {"tool": "ultron", "action": "cve_track", "parameters": {"cve_id": cve}, "confidence": 0.99}

    if text in ("list tracked cves", "show tracked cves", "cve watchlist", "tracked cves", "my cves", "show cves"):
        return {"tool": "ultron", "action": "cve_list", "parameters": {}, "confidence": 0.99}

    # ── CVE -> asset correlation (Phase 51 #9) ──
    if text in (
        "correlate cves", "correlate threats", "threat correlation",
        "am i affected", "am i exposed", "check my exposure", "check exposure",
        "cross reference cves", "correlate cves with scans", "match cves to hosts",
        "which hosts are vulnerable", "what am i exposed to", "correlate"
    ):
        return {"tool": "ultron", "action": "correlate", "parameters": {}, "confidence": 0.99}

    _m = re.match(r"(?:check|update|refresh)\s+(?:tracked\s+)?(?:cve\s+)?(cve[- ]\d{4}[- ]\d+|\d{4}[- ]\d+)", text, re.IGNORECASE)
    if _m:
        cve = _m.group(1).replace(" ", "-")
        return {"tool": "ultron", "action": "cve_check", "parameters": {"cve_id": cve}, "confidence": 0.99}

    if text in ("check tracked cves", "check all cves", "update cve watchlist", "refresh cves"):
        return {"tool": "ultron", "action": "cve_check", "parameters": {}, "confidence": 0.99}

    _m = re.match(r"(?:untrack|stop tracking|remove)\s+(cve[- ]\d{4}[- ]\d+|\d{4}[- ]\d+)", text, re.IGNORECASE)
    if _m:
        cve = _m.group(1).replace(" ", "-")
        return {"tool": "ultron", "action": "cve_untrack", "parameters": {"cve_id": cve}, "confidence": 0.99}

    # ── Exploit PoC finder (Phase 25) ──
    _m = re.match(
        r"(?:find exploits?(?: for)?|search exploits?(?: for)?|find poc(?:s)?(?: for)?|"
        r"exploit search|poc(?:s)? for|exploits? for|check exploits?(?: for)?)\s+(cve[- ]\d{4}[- ]\d+|\d{4}[- ]\d+)",
        text,
        re.IGNORECASE
    )
    if _m:
        cve = _m.group(1).replace(" ", "-")
        return {"tool": "ultron", "action": "find_exploits", "parameters": {"cve_id": cve}, "confidence": 0.99}

    # ── CVE Search — NVD API (Phase 30a) ──
    # "search cve for apache log4j"
    # "find critical CVEs for nginx"
    # "critical CVEs this week"
    # "CVEs for openssl last 30 days"
    # "high severity CVEs for windows"
    _SEV_MAP = {"critical": "CRITICAL", "high": "HIGH", "medium": "MEDIUM", "low": "LOW"}

    _m = re.match(
        r"(?:search|find|show|get|list)\s+"
        r"(?:(critical|high|medium|low)\s+)?"
        r"cves?\s+(?:for|about|related to|affecting)\s+(.+)",
        text, re.IGNORECASE
    )
    if _m:
        _sev = _SEV_MAP.get((_m.group(1) or "").lower(), "")
        _kw = _m.group(2).strip()
        return {"tool": "ultron", "action": "search_cve",
                "parameters": {"keyword": _kw, "severity": _sev, "days_back": 0}, "confidence": 0.97}

    # "critical CVEs this week/today/month"
    _m = re.match(
        r"(critical|high|medium|low)\s+cves?\s+(?:this\s+)?(week|month|today|day)",
        text, re.IGNORECASE
    )
    if _m:
        _sev = _SEV_MAP.get(_m.group(1).lower(), "")
        _period = _m.group(2).lower()
        _days = {"week": 7, "month": 30, "today": 1, "day": 1}.get(_period, 7)
        return {"tool": "ultron", "action": "search_cve",
                "parameters": {"keyword": "", "severity": _sev, "days_back": _days}, "confidence": 0.97}

    # "CVEs for apache this week" / "new CVEs for openssl in last 30 days"
    _m = re.match(
        r"(?:new\s+)?cves?\s+(?:for|about|affecting)\s+(.+?)\s+(?:this\s+)?"
        r"(?:in\s+(?:the\s+)?last\s+(\d+)\s+days?|(week|month|today))",
        text, re.IGNORECASE
    )
    if _m:
        _kw = _m.group(1).strip()
        if _m.group(2):
            _days = int(_m.group(2))
        else:
            _days = {"week": 7, "month": 30, "today": 1}.get(_m.group(3).lower(), 7)
        return {"tool": "ultron", "action": "search_cve",
                "parameters": {"keyword": _kw, "severity": "", "days_back": _days}, "confidence": 0.97}

    # "recent CVEs for X" / "latest CVEs for X"
    _m = re.match(
        r"(?:recent|latest|new)\s+cves?\s+(?:for|about|affecting)\s+(.+)",
        text, re.IGNORECASE
    )
    if _m:
        _kw = _m.group(1).strip()
        return {"tool": "ultron", "action": "search_cve",
                "parameters": {"keyword": _kw, "severity": "", "days_back": 30}, "confidence": 0.96}

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

    # =====================================
    # PHASE 41 — translate / FX / crypto / flight
    # =====================================
    _CCY = {"dollar": "USD", "dollars": "USD", "usd": "USD", "euro": "EUR", "euros": "EUR",
            "eur": "EUR", "pound": "GBP", "pounds": "GBP", "gbp": "GBP", "rupee": "INR",
            "rupees": "INR", "inr": "INR", "yen": "JPY", "jpy": "JPY", "yuan": "CNY"}

    # Currency conversion: "convert 500 usd to eur" / "100 dollars in euros"
    _m = re.match(
        r"(?:convert\s+)?(\d[\d,]*\.?\d*)\s*([a-z]{3}|dollars?|euros?|pounds?|rupees?|yen|yuan)\s+"
        r"(?:to|in|into)\s+([a-z]{3}|dollars?|euros?|pounds?|rupees?|yen|yuan)\b",
        text, re.IGNORECASE
    )
    if _m:
        amt = float(_m.group(1).replace(",", ""))
        frm = _CCY.get(_m.group(2).lower(), _m.group(2).upper())
        to = _CCY.get(_m.group(3).lower(), _m.group(3).upper())
        return {"tool": "vision", "action": "currency_convert",
                "parameters": {"amount": amt, "from": frm, "to": to}, "confidence": 0.97}

    # Translate: "translate X to french" / "how do you say X in spanish"
    _m = re.match(r"(?:translate|how do (?:you|i) say)\s+(.+?)\s+(?:to|in|into)\s+(\w+)\??$", text, re.IGNORECASE)
    if _m:
        return {"tool": "vision", "action": "translate",
                "parameters": {"text": _m.group(1).strip().strip("'\""), "target": _m.group(2).strip()}, "confidence": 0.96}
    # "translate to french: X"
    _m = re.match(r"translate\s+(?:to\s+)?(\w+)\s*[:\-]\s*(.+)", text, re.IGNORECASE)
    if _m:
        return {"tool": "vision", "action": "translate",
                "parameters": {"text": _m.group(2).strip(), "target": _m.group(1).strip()}, "confidence": 0.95}

    # Flight tracking: "track flight EK202" / "flight status BA117"
    _m = re.match(r"(?:track flight|flight status(?: of)?|where is flight|flight)\s+([a-z]{2}\s?\d{1,4}[a-z]?)\b", text, re.IGNORECASE)
    if _m:
        return {"tool": "vision", "action": "track_flight",
                "parameters": {"flight": _m.group(1).strip()}, "confidence": 0.96}

    # Crypto price: "bitcoin price" / "price of ethereum" / "how much is btc"
    _coin_re = r"(bitcoin|btc|ethereum|eth|solana|sol|dogecoin|doge|ripple|xrp|cardano|ada|bnb|binancecoin|litecoin|ltc|polkadot|dot|chainlink|link|avalanche|avax|matic)"
    _m = re.match(rf"{_coin_re}\s+price$", text, re.IGNORECASE)
    if not _m:
        _m = re.match(rf"(?:price of|how much is|what(?:'s| is) (?:the )?price of)\s+{_coin_re}\b", text, re.IGNORECASE)
    if _m:
        return {"tool": "vision", "action": "crypto_price",
                "parameters": {"coins": _m.group(1)}, "confidence": 0.96}
    if text in ("crypto prices", "top crypto", "crypto market", "coin prices"):
        return {"tool": "vision", "action": "crypto_price",
                "parameters": {"coins": "bitcoin,ethereum,solana,bnb,ripple"}, "confidence": 0.95}

    # Broadened vision fallbacks — clear commands the strict patterns above miss, so they route
    # deterministically instead of falling to the (unreliable, local-model) LLM router.
    if re.search(rf"\b{_coin_re}\b.{{0,25}}\bprice\b|\bprice\b.{{0,25}}\b{_coin_re}\b|"
                 rf"how much is\s+(?:the\s+)?{_coin_re}\b|{_coin_re}\s+(?:is\s+)?worth", text, re.IGNORECASE):
        _cm = re.search(_coin_re, text, re.IGNORECASE)
        return {"tool": "vision", "action": "crypto_price",
                "parameters": {"coins": _cm.group(1)}, "confidence": 0.93}
    _m = re.search(r"(\d[\d,]*\.?\d*)\s*([a-z]{3}|dollars?|euros?|pounds?|rupees?|yen|yuan)\s+"
                   r"(?:to|in|into)\s+([a-z]{3}|dollars?|euros?|pounds?|rupees?|yen|yuan)\b", text, re.IGNORECASE)
    if _m:
        return {"tool": "vision", "action": "currency_convert",
                "parameters": {"amount": float(_m.group(1).replace(",", "")),
                               "from": _CCY.get(_m.group(2).lower(), _m.group(2).upper()),
                               "to": _CCY.get(_m.group(3).lower(), _m.group(3).upper())}, "confidence": 0.93}
    _m = re.search(r"what does\s+(.+?)\s+mean(?:\s+in\s+(\w+))?", text, re.IGNORECASE)
    if _m:
        return {"tool": "vision", "action": "translate",
                "parameters": {"text": _m.group(1).strip().strip("'\""),
                               "target": (_m.group(2) or "english").strip()}, "confidence": 0.92}

    # =====================================
    # FILE — READ / SUMMARIZE DOCUMENT (Phase 31 — MarkItDown)
    # =====================================
    # Phase 58 — RAG: chat with your documents
    if text in ("docs status", "document status", "what docs are indexed",
                "what documents are indexed", "indexed documents"):
        return {"tool": "file", "action": "docs_status", "parameters": {}, "confidence": 0.97}
    if text in ("clear docs", "clear documents", "clear document index", "forget my documents"):
        return {"tool": "file", "action": "clear_docs", "parameters": {}, "confidence": 0.97}

    _idx = re.match(r"(?:index|ingest|load|learn)\s+(?:my\s+|the\s+)?(?:docs?|documents?|folder|files?|directory)?\s*(.+)", text)
    if _idx and ("index" in text or "ingest" in text) and not text.startswith("indexed"):
        return {"tool": "file", "action": "index_docs",
                "parameters": {"path": _idx.group(1).strip().strip('"\'')}, "confidence": 0.95}

    # "ask my docs <q>" / "what do my documents/files/notes say about X"
    _ask = re.match(r"(?:ask\s+(?:my\s+)?(?:docs?|documents?|files?|notes?)\s+|"
                    r"(?:what|which|when|who|where|how|does|do|is)\b.*\b(?:docs?|documents?|files?|notes?|papers?)\b)\s*(.*)", text)
    if _ask and any(w in text for w in ("doc", "document", "file", "note", "paper")):
        q = _ask.group(1).strip() or text
        return {"tool": "file", "action": "ask_docs", "parameters": {"query": text}, "confidence": 0.9}

    # "summarize [file]" / "read [file]" / "what's in [file]"
    _doc_m = re.match(
        r"(?:summarize|summarise|read|extract|what(?:'s|\s+is)\s+in|read\s+and\s+summarize)\s+(.+\.(?:pdf|docx?|pptx?|xlsx?|csv|png|jpe?g|mp3|wav|txt|md|html?))",
        text, re.IGNORECASE
    )
    if _doc_m:
        path = _doc_m.group(1).strip().strip('"\'')
        # Strip qualifier words that greedy match may have captured
        path = re.sub(
            r'^(?:the\s+)?(?:file|document|doc|presentation|spreadsheet|pdf)\s+(?:at\s+)?',
            '', path, flags=re.IGNORECASE
        ).strip()
        # Assistant-grade: read/what's-in also SUMMARIZE (never dump raw text).
        # Only "extract" returns the raw content.
        action = "read_document" if re.search(r"\bextract\b", text, re.IGNORECASE) else "summarize_document"
        return {"tool": "file", "action": action, "parameters": {"path": path}, "confidence": 0.95}

    # "summarize the file at <path>" / "read document <path>"
    _doc_m2 = re.match(
        r"(?:summarize|summarise|read|extract)\s+(?:the\s+)?(?:file|document|doc|pdf|spreadsheet|presentation)\s+(?:at\s+)?(.+)",
        text, re.IGNORECASE
    )
    if _doc_m2:
        path = _doc_m2.group(1).strip().strip('"\'')
        action = "read_document" if re.search(r"\bextract\b", text, re.IGNORECASE) else "summarize_document"
        return {"tool": "file", "action": action, "parameters": {"path": path}, "confidence": 0.95}

    # =====================================
    # TOOL-RESULT RECALL (Phase 51 #6) — before sports (which greedily matches "...result")
    # =====================================
    if text in (
        "what was the result", "what was that result", "what was the last result",
        "last result", "show last result", "show me the last result",
        "repeat that result", "what did that find", "what did it find",
        "what did that say", "what did that return", "recall last result",
        "show recent results", "recent results", "show recent tool results"
    ):
        return {"tool": "system", "action": "recall_result", "parameters": {}, "confidence": 0.95}

    # =====================================
    # VISION — SPORTS QUERY (Phase 39)
    # football-data.org API — real match dates, results, standings
    # Intercepts BEFORE generic news block for structured sports data
    # =====================================
    _sports_kw = re.search(
        r"\b(?:next\s+(?:match|game|fixture)|"
        r"play(?:ing)?\s+next|plays?\s+next|"
        r"(?:upcoming\s+)?fixtures?|"
        r"match\s+schedule|"
        r"football\s+(?:match|game)|"
        r"soccer\s+(?:match|game)|"
        r"(?:match|game)\s+results?|"
        r"(?:recent|latest|last)\s+results?|"
        r"next\s+football(?:\s+match)?|"
        r"next\s+game|"
        r"(?:football|soccer|match|team)\s+standings?|"
        r"standings?\s+(?:for\s+)?(?:the\s+)?(?:premier|bundesliga|serie|la\s+liga|ligue|champions|nations)|"
        r"\w+\s+(?:league|cup)\s+standings?|"
        r"(?:club|team)\s+results?)\b",
        text, re.IGNORECASE
    )
    # Also catch "[team name] results/fixtures/standings" suffix pattern
    # e.g. "manchester united results", "premier league standings"
    if not _sports_kw:
        _sports_kw = re.match(
            r"^[a-z][a-z\s]{2,30}\s+(?:results?|fixtures?|standings?)$",
            text, re.IGNORECASE
        ) and not re.search(
            r"\b(?:news|search|election|test|poll|google|click|open|first|second|"
            r"third|fourth|fifth|next|page|tab|link|scan|file|tool|"
            r"what|show)\b",
            text, re.IGNORECASE
        )

    # "did <team> win", "<team> score" — broaden, but only when likely a sports team
    # (multi-word capitalized in raw / known sports tokens). Avoid generic "the test score".
    if not _sports_kw:
        _sports_kw = re.match(r"^did\s+[a-z][a-z\s]{2,30}\s+(?:win|lose|draw)\b", text, re.IGNORECASE)
    if not _sports_kw and re.search(r"\b(?:united|city|fc|football\s+club|madrid|barca|chelsea|"
                                    r"liverpool|arsenal|tottenham|psg|juventus|bayern|dortmund)\b.{0,20}"
                                    r"\b(?:score|result)s?\b", text, re.IGNORECASE):
        _sports_kw = True
    # "show me hacker news" — already covered by hackernews block but the literal "show me X news"
    # ends up here; route news intents away from sports.
    if _sports_kw and re.search(r"\bhacker\s*news\b|\btech\s+news\b", text, re.IGNORECASE):
        _sports_kw = False

    if _sports_kw:
        # Strip common query prefixes to get clean sports query
        _sq = text
        _sq = re.sub(r"^(?:check\s+|look\s+up\s+|find\s+out\s+|tell\s+me\s+)", "", _sq, flags=re.IGNORECASE)
        _sq = re.sub(r"^(?:when\s+(?:is|are|does|will)|what\s+(?:is|are))\s+", "", _sq, flags=re.IGNORECASE)
        return {
            "tool": "vision",
            "action": "sports_query",
            "parameters": {"query": _sq.strip().rstrip("?")},
            "confidence": 0.90,
        }

    # =====================================
    # VISION — WEB SEARCH (Phase 32, DuckDuckGo)
    # "search the web for X" / "web search X" / "search online for X" / "look up X online"
    # =====================================
    _web_m = re.match(
        r"^(?:search\s+(?:the\s+)?web\s+for|web\s+search(?:\s+for)?|"
        r"search\s+online\s+for|duckduckgo|ddg)\s+(.+)",
        text, re.IGNORECASE
    )
    if not _web_m:
        # "look up X online" / "X — search online" trailing form
        _web_m = re.match(r"^look\s+up\s+(.+?)\s+(?:online|on the web)\??$", text, re.IGNORECASE)
    if _web_m:
        return {
            "tool": "vision",
            "action": "web_search",
            "parameters": {"query": _web_m.group(1).strip().rstrip("?")},
            "confidence": 0.92,
        }

    # =====================================
    # VISION — NEWS / FACTUAL QUICK SEARCH
    # Catches "check X", "when is X", "find out X", etc.
    # Bypasses LLM router -> fast RSS response instead of full Athena report.
    # =====================================
    _news_m = re.match(
        r"^(?:check|look up|lookup|find out|when is|when are|when will|"
        r"what's the latest on|latest on|news on|news about|"
        r"any news (?:on|about)|tell me about|what happened (?:to|with)|"
        r"update on|search news for|search news|news for)\s+(.+)",
        text, re.IGNORECASE
    )
    if _news_m:
        query = _news_m.group(1).strip().rstrip("?")
        # Strip nested interrogative prefix ("when is X", "when are X", etc.)
        _q2 = re.match(r"^(?:when\s+(?:is|are|will|does|did)|what\s+(?:is|are))\s+(.+)", query, re.IGNORECASE)
        if _q2:
            query = _q2.group(1).strip()
        return {
            "tool": "vision",
            "action": "quick_answer",
            "parameters": {"query": query},
            "confidence": 0.85,
        }

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

    # type text into focused window
    _m = re.match(r"(?:type|type out|enter text|write)\s+(.+)", text)
    if _m and not re.search(r"\b(?:task|note|goal|reminder|habit)\b", text):
        return {"tool": "terminator", "action": "type_text", "parameters": {"text": _m.group(1).strip()}, "confidence": 0.9}

    # press a key combo
    _m = re.match(r"(?:press|hit|send)\s+(.+)", text)
    if _m and re.search(r"\b(ctrl|alt|shift|enter|tab|esc|escape|space|f\d|delete|backspace)\b", _m.group(1), re.IGNORECASE):
        return {"tool": "terminator", "action": "press_keys", "parameters": {"keys": _m.group(1).strip()}, "confidence": 0.95}

    # click a named element in a window: "click X in Y"
    _m = re.match(r"click\s+(?:the\s+)?(.+?)\s+(?:button\s+)?in\s+(?:the\s+)?(.+)", text)
    if _m:
        return {"tool": "terminator", "action": "click_element",
                "parameters": {"element": _m.group(1).strip(), "window": _m.group(2).strip()}, "confidence": 0.9}

    # =====================================
    # ROUTINES / MACROS (Phase 43)
    # =====================================
    _m = re.match(r"(?:create|new|record|start|make)\s+(?:a\s+)?routine\s+(.+)", text)
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
    if text.startswith(

        (
            "open ",
            "launch ",
            "start "
        )
    ):

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