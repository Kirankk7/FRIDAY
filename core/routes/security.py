"""Router group — ultron security + recon (scan/pipeline/bug-bounty/idor/graphql/
threat-intel/defense/hackingtool/CVE/burp/github/playbook + the 2 vision describe-screen
routes that live in this cluster). Extracted VERBATIM from route_single_intent, same
chain position, order preserved. Uses only text/text_raw. Returns a decision or None.

Refactor discipline: move only — no logic changes.
"""
import re
import os


def try_route(text, text_raw):
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

    return None
