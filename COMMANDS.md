# FRIDAY / JARVIS — Command Reference

Everything you can say (or type) to FRIDAY, plus the friday-recon CLI. Verbs verified against
source (`core/router.py`, `friday-recon/cli.py`) on **2026-06-30**.

> Voice or text — same commands. Security tools: **authorized targets only.**

**Notes:**
> - Most personal/security/info commands respond instantly (≤1.5s).
> - LLM-backed ones (`how do I test for X`, `deep research X`, full reports) take ~10–40s — local model thinking, normal.
> - `content discovery` needs ffuf/gobuster · `describe my screen` needs llava · VirusTotal needs VT key · n8n needs a running server · `ht search` needs WSL/Docker.
> - Browser commands need the Playwright session; desktop commands need a GUI session.

---

## ▶️ Run / Launch

```bash
# ── MAIN JARVIS (D:\JARVIS) ──
python app.py                            # web HUD + voice → http://127.0.0.1:5000  (main entry)
python main.py                           # headless CLI voice loop (wake word "friday")
JARVIS_CI=1 python test_regression.py    # full regression suite (393 tests)
python scripts/coverage.py               # → COVERAGE.md (every action PASS/SKIP/FAIL)
python scripts/chat_battery.py --inproc  # chat corpus, no server needed
python scripts/chat_battery.py           # chat corpus against running /chat_stream
python scripts/chat_review.py --report   # → CHAT_REVIEW.md (flagged-reply review)
python scripts/dogfood.py                # all-agent + probe_lab TP/FP smoke
python scripts/dogfood_friday.py         # friday-recon smoke

# ── FRIDAY-RECON (D:\friday-recon) ──
python cli.py <verb> ...                 # see CLI section at bottom
python -m pytest                         # recon test suite
python deep_hunt.py <target>             # sqlmap deep-confirm (money shot)
```

---

## 🔒 Ultron — Security & Bug Bounty

```bash
scan example.com                         # nmap port scan (with scan diffing)
full recon example.com                   # pipeline: nmap→subfinder→httpx→nuclei→katana→sitemap→report
bug bounty example.com                   # full hunt → probe → gate → test plan + PoC report
content discovery example.com            # brute-force hidden paths/dirs (ffuf/gobuster), standalone
#   note: subfinder auto-uses the registrable apex (www.x.com → x.com); sitemap.xml + robots.txt
#   paths are ALWAYS pulled into recon/hunt reports; ffuf/gobuster dir-brute is OPT-IN (see --discover)
crawl example.com                        # katana web crawl (endpoint inventory)
spa crawl example.com                    # headless-render JS/SPA → capture API surface
search cve for log4j                     # NVD CVE lookup by keyword
check log4j on virustotal                # VirusTotal scan (file/hash/URL/domain/IP)
correlate cves with scans                # cross-link tracked CVEs ↔ scanned services
list tracked cves                        # show CVE watchlist  (alias: cve watchlist)
defensive scan                           # blue-team: new listening ports / suspicious procs
set security baseline                    # snapshot baseline for the defensive scan
how do I test for subdomain takeover     # methodology KB — grounded, cited answer
methodology for ssrf                     # bug-bounty playbook from local KB
wordlist for ssrf                        # resolve a wordlist  (or: list wordlists)
target profile example.com               # what we know about a target across hunts
list targets                             # all profiled targets
scope                                    # show in/out-of-scope rules  (or: show scope)
ingest burp export.xml                   # parse Burp history → endpoints + auto-tags
github hunt acme                         # enumerate org repos → flag secret-prone files
collect evidence https://t.com/finding   # re-probe a finding → capture evidence
ht search amass                          # search the 180+ HackingTool fleet
hackingtool preflight                    # check WSL/Docker backend for the fleet
hash sha256 of mypassword                # hash a value (md5/sha1/sha256/…)
```

### Multi-user authz & IDOR (the money-bug stack)

```bash
idor check <url>                         # cross-account IDOR/BOLA: owner vs attacker vs anon
bola check <url>                         # alias of idor check
graphql hunt <url>                       # GraphQL introspection + privileged-mutation inventory
session set bob cookie <value>           # register a principal by cookie (authz testing)
session set bob bearer <token>           # register a principal by bearer token
sessions                                 # list registered authz principals (or: list sessions)
replay as bob <url>                      # replay a request as a registered principal
threat intel <ioc>                       # IOC reputation across feeds (IP/domain/URL/hash)
reputation check <x>                     # alias of threat intel  (or: is <x> malicious)
```

## 🔐 Crypto — Encode / Decode / Hash (29 ops)

```bash
base64 encode hello                      # encode in a named scheme
base64 decode SGVsbG8=                   # decode in a named scheme
decode base64 SGVsbG8=                   # verb-first form (optional this/the)
rot13 uryyb                              # ROT13 shorthand (self-inverse)
decode SGVsbG8=                          # AUTO-DETECT the scheme on a single token
list crypto ops                          # list every supported operation (or: crypto tools)
# schemes: base64 b64 base32 base58 hex url html unicode rot13 morse caesar jwt
# hashes:  md5 sha1 sha256 sha512  ·  also: aes, auto_decode
```

## 🧠 Athena — Deep Research

```bash
deep research quantum cryptography       # multi-source aggregation → synthesized report
search github for jwt library            # GitHub repo search
continue research                        # resume the last deep-research session
```

## 🌐 Vision — Live Info

```bash
bitcoin price                            # live crypto (CoinGecko, no key)  (or: crypto prices)
convert 500 usd to eur                   # currency conversion
translate hello to spanish               # translation
flight status BA117                      # flight tracking
search news for AI                       # news / web search (DuckDuckGo)
search the web for owasp top 10          # web search
hackernews                               # top Hacker News
describe my screen                       # vision: describe screen (needs llava)
```

## 👤 FRIDAY — Personal Assistant

```bash
add task buy milk                        # add a task         (list: list tasks)
add note call mom                        # add a note         (list: list notes)
add goal learn rust                      # add a goal         (list: list goals)
add habit meditate                       # track a habit      (list: show habits)
remind me in 10 minutes to stretch       # set a reminder     (list: list reminders)
schedule gym for 6pm                     # add a calendar event
plan a push workout                      # fitness planning
```

## 🖥️ System · Files · Browser · Desktop

```bash
check battery                            # battery status
network speed test                       # internet speed test
cpu usage                                # CPU usage  (also: ram usage / how much RAM)
browser status                           # is the Playwright browser on
summarize report.pdf                     # read & summarize a doc (PDF/DOCX/audio)
index docs ./folder                      # build local RAG index over a folder
ask docs "what's the deadline"           # chat-with-your-docs (after index docs)
open chrome and search owasp             # browser automation (Veronica)
read page                                # read current page  (also: extract links / where am i)
click first result                       # click in the browser
list open windows                        # list desktop windows (Terminator)
launch notepad                           # desktop control  (also: focus chrome / type hello world)
```

## ⚙️ Automation

```bash
list workflows                           # list self-hosted n8n workflows
run workflow my-flow                     # trigger an n8n workflow
list routines                            # list command-sequence macros
create routine morning                   # record & replay a macro
```

---

## 💻 friday-recon — Standalone Security CLI

The offensive core as a dependency-light CLI (`cd D:\friday-recon`). Same engine (Ultron), no
Flask/HUD/voice. **Authorized targets only.**

```bash
python cli.py scan <target> [--type basic]                 # nmap port scan
python cli.py recon <target> [--force] [--discover]        # full recon pipeline (+sitemap; --discover = ffuf/gobuster)
python cli.py bugbounty <target> [--force] [--discover]    # full hunt → validated PoC report + plan
#   --discover = ALSO brute hidden paths (ffuf/gobuster) — slower & noisier, off by default.
#   sitemap.xml + robots.txt paths are pulled in ALWAYS (passive, cheap). subfinder auto-apexes www.
python cli.py write-bola <url> --field email --owner A --attacker B [--verify-url <read-url>]  # write-BOLA oracle (opt-in)
python cli.py cve <keyword>                                # NVD CVE lookup
python cli.py kb "how do I test for IDOR"                  # methodology knowledge base
python cli.py discover <target>                            # content discovery (ffuf/gobuster)
python cli.py spacrawl <target>                            # render SPA → capture API surface
python cli.py crawl <target>                               # multi-page BFS crawl → param'd URLs
python cli.py graphql <url>                                # GraphQL introspection + mutation hunt
python cli.py idor <url> [--owner userA --attacker userB]  # IDOR/BOLA owner-vs-attacker check
python cli.py session-set <name> <cookie>                  # register a principal (authz testing)
python cli.py sessions                                     # list authz-test sessions
python cli.py threat-intel <ioc>                           # IOC reputation across feeds
python cli.py github-hunt <org>                            # enumerate org repos + flag secrets
python cli.py profile <host>                               # stored target profile
python cli.py targets                                      # list profiled targets
python cli.py evidence <url>                               # re-probe a finding → capture evidence
python cli.py burp <export.xml>                            # ingest Burp HTTP-history export
python cli.py scope                                        # show in/out-of-scope rules
python cli.py scope-setup <policyfile>                     # parse a program policy → set scope
python cli.py defensive                                    # blue-team host scan
python cli.py playbook "<query>"                           # recall attack techniques
python cli.py ingest-writeup <url>                         # learn a public writeup → playbook
python cli.py ingest-feed <url>                            # ingest a writeup-index → learn each
python cli.py wordlist [kind]                              # list bundled wordlists
```

---

## 🎬 Suggested Demo Flow (≈5 min)

```bash
python cli.py bugbounty testaspnet.vulnweb.com   # 2 SQLi confirmed, MSSQL payloads, sqlmap cmd
# open Desktop/Ultron Reports/testaspnet.vulnweb.com/   → per-site folder + _index.md
python deep_hunt.py testaspnet.vulnweb.com       # sqlmap confirms the DB live (money shot)
idor check http://localhost:3000/rest/basket/1   # authz oracle (owner vs attacker)
how do I test for IDOR                            # methodology brain (grounded, cited)
defensive scan                                   # flip to blue-team (offense AND defense)
bitcoin price                                    # it's a full assistant, not just security
# NOTE: avoid "scan my system" — mis-parses as an nmap target. Use "check battery" instead.
```
