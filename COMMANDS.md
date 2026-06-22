# FRIDAY / JARVIS — Command Reference

Everything you can say (or type) to FRIDAY. Commands below were **live-fired end-to-end
(2026-06-23)** — they route deterministically *and* return real responses. Replace
`example.com` / placeholders with your own.

> Voice or text — same commands. Security tools: **authorized targets only.**

**Demo notes (live-tested):**
> - Most personal/security/info commands respond **instantly** (≤1.5s).
> - LLM-backed ones (`how do I test for X`, `deep research X`, full reports) take **~10–40s** — that's the local model thinking, normal.
> - `content discovery` needs **ffuf or gobuster** installed (else it says so gracefully — no results).
> - Some need a **key/dep**: VirusTotal (VT key) · `describe my screen` (llava model) · n8n (running server) · Telegram bridge (bot token) · `hackingtool` (WSL/Docker).
> - `search cve for X` hits the live NVD API — occasionally times out. Don't rely on it on camera; use the local KB (`how do I test for X`) instead.
> - Browser commands (`open chrome…`, `read page`) need the browser session started; desktop commands (`launch app`, `type`) need a GUI session.
> - Prefer `check battery` / `network speed test` over `how much RAM` (the latter falls back to the slower LLM router).

---

## 🔒 Ultron — Security & Bug Bounty

| Command | What it does |
|---------|--------------|
| `scan example.com` | Nmap port scan (with scan diffing) |
| `full recon example.com` | Full pipeline: nmap → subfinder → httpx → nuclei → katana → report |
| `bug bounty example.com` | Full hunt → injection probe → validation gate → **tailored test plan + PoC report** |
| `content discovery example.com` | Brute-force hidden paths/dirs (ffuf/gobuster) |
| `crawl example.com` | Katana web crawl (endpoint inventory) |
| `spa crawl example.com` | Headless-render a JS/SPA app → capture its API surface (the endpoints katana can't see) |
| `search cve for log4j` | NVD CVE lookup by keyword |
| `check log4j on virustotal` | VirusTotal scan (file/hash/URL/domain/IP) |
| `correlate cves with scans` | Cross-link tracked CVEs ↔ scanned host services ("am I exposed?") |
| `list tracked cves` / `cve watchlist` | Show CVE watchlist |
| `defensive scan` | Blue-team: flag new listening ports / suspicious processes |
| `set security baseline` | Snapshot baseline for the defensive scan |
| `how do I test for subdomain takeover` | Methodology KB — grounded, cited answer |
| `methodology for ssrf` | Bug-bounty playbook from the local KB |
| `wordlist for ssrf` / `list wordlists` | Resolve / list bundled wordlists |
| `target profile example.com` | What we know about a target across hunts |
| `list targets` | All profiled targets |
| `scope` / `show scope` | Show in/out-of-scope rules from `data/scope.json` (bug-bounty scope guard) |
| `ingest burp export.xml` | Parse Burp history → endpoints + auto-tags (JWT/GraphQL/API/auth/tech) |
| `github hunt acme` | Enumerate an org's repos → flag secret-prone files |
| `collect evidence https://t.com/finding` | Re-probe a finding → capture confirmed evidence |
| `ht search amass` | Search the 180+ HackingTool fleet |
| `hackingtool preflight` | Check WSL/Docker backend for the fleet |
| `hash sha256 of mypassword` | Hash a value (md5/sha1/sha256/…) |

## 🧠 Athena — Deep Research

| Command | What it does |
|---------|--------------|
| `deep research quantum cryptography` | Multi-source aggregation → synthesized report |
| `search github for jwt library` | GitHub repo search |
| `continue research` | Resume the last deep-research session |

## 🌐 Vision — Live Info

| Command | What it does |
|---------|--------------|
| `bitcoin price` / `crypto prices` | Live crypto (CoinGecko, no key) |
| `convert 500 usd to eur` | Currency conversion |
| `translate hello to spanish` | Translation |
| `flight status BA117` | Flight tracking |
| `search news for AI` | News / web search (DuckDuckGo) |
| `search the web for owasp top 10` | Web search |
| `hackernews` | Top Hacker News |
| `describe my screen` | Vision: describe what's on screen (needs llava) |

## 👤 FRIDAY — Personal Assistant

| Command | What it does |
|---------|--------------|
| `add task buy milk` / `list tasks` | Tasks |
| `add note call mom` / `list notes` | Notes |
| `add goal learn rust` / `list goals` | Goals |
| `add habit meditate` / `show habits` | Habit tracking |
| `remind me in 10 minutes to stretch` / `list reminders` | Reminders |
| `schedule gym for 6pm` | Calendar event |
| `plan a push workout` | Fitness planning |

## 🖥️ System · Files · Browser · Desktop

| Command | What it does |
|---------|--------------|
| `check battery` | Battery status |
| `network speed test` | Internet speed test |
| `how much RAM` | CPU/RAM/system info |
| `browser status` | Is the Playwright browser on |
| `summarize report.pdf` | Read & summarize a document (PDF/DOCX/audio) |
| `index docs ./folder` then `ask docs "what's the deadline"` | Chat-with-your-docs (local RAG) |
| `open chrome and search owasp` | Browser automation (Veronica) |
| `read page` / `extract links` / `where am i` | Read / extract from the current page |
| `click first result` | Click in the browser |
| `list open windows` | List desktop windows (Terminator) |
| `launch notepad` / `focus chrome` / `type hello world` | Desktop control (pywinauto) |

## ⚙️ Automation

| Command | What it does |
|---------|--------------|
| `list workflows` / `run workflow my-flow` | Trigger self-hosted n8n workflows |
| `list routines` / `create routine morning` | Record & replay command-sequence macros |

---

## 💻 friday-recon — Standalone Security CLI

The offensive core as a dependency-light CLI (`cd friday-recon`):

```bash
python cli.py bugbounty example.com    # full hunt → validated PoC report + test plan
python cli.py recon example.com        # full recon pipeline
python cli.py scan example.com         # nmap
python cli.py cve log4j                # CVE lookup
python cli.py kb "how do I test for IDOR"   # methodology KB
python cli.py discover example.com     # content discovery
python cli.py github-hunt acme         # org repo secret hunt
python cli.py profile example.com      # target profile
python cli.py burp export.xml          # ingest Burp history
python cli.py defensive                # blue-team host scan
```

---

## 🎬 Suggested Demo Flow (≈5 min)

1. `python cli.py bugbounty testaspnet.vulnweb.com` → **2 SQLi confirmed, MSSQL payloads, sqlmap command, tailored manual checklist**
2. Open `Desktop/Ultron Reports/testaspnet.vulnweb.com/` → per-site folder + `_index.md`
3. `python deep_hunt.py testaspnet.vulnweb.com` → **sqlmap confirms the DB live** (the money shot)
4. `how do I test for IDOR` → the methodology brain (grounded, cited)
5. `defensive scan` → flip to blue-team (offense **and** defense)
6. `bitcoin price` / `deep research X` → it's a full assistant, not just security

> Note: drop `scan my system` from any script — it mis-parses as an nmap target. Use `check battery` / `network speed test` for the system demo.
