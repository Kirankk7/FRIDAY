"""Router group — file read/RAG + tool-result recall + vision sports/web/news. Extracted VERBATIM from route_single_intent,
same chain position, order preserved. Uses only text/text_raw. Move only — no logic changes.
"""
import re
import os


def try_route(text, text_raw):
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


    return None
