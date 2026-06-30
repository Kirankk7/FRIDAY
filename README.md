# FRIDAY (JARVIS) — Local AI Personal Assistant

![tests](https://github.com/Kirankk7/FRIDAY/actions/workflows/test.yml/badge.svg)

A privacy-first, fully-local AI assistant with a multi-agent architecture, voice I/O, a 3-mode Iron-Man HUD, and a built-in cybersecurity toolkit. Runs entirely on your own machine — no cloud inference, no API keys for the core LLM.

> *FRIDAY is the default conversational agent; the system as a whole is JARVIS.*

---

## Screenshot

> _Command Mode — arc-reactor core, live system telemetry, 16-agent fleet._

![JARVIS HUD](docs/hud_command.png)
<!-- Drop a screenshot of http://localhost:5000 here. Operations & Cyber tabs in docs/ too. -->

---

## Highlights

- **100% local LLM inference** via [Ollama](https://ollama.com) (`qwen2.5:7b`) — no OpenAI/Gemini/cloud
- **3-mode HUD** (Command / Operations / Cyber) — arc-reactor orb, live `/health` telemetry, 16-agent fleet, all vanilla JS + Canvas
- **Multi-agent architecture** — 16 agents behind a dual-path intent router: **6 substantial** (Ultron, FRIDAY, Veronica, File, Vision, Athena), 6 support modules, and 4 thin adapters — honestly tiered in the [Agents](#agents) table, not all equal
- **Voice in + out** — faster-whisper STT (CUDA) + Kokoro-82M neural TTS (per-agent voices + earcons), barge-in interrupt, edge-tts fallback
- **AutoTune** — context-adaptive sampling (classifies each query → code/analytical/creative/conversational/chaotic → tunes temperature/top-p/etc) with 👍/👎 EMA online learning
- **Cybersecurity agent (Ultron)** — native recon suite + a HackingTool index of 180+ tools **gated down to ~25 runnable** (capability allowlist, offensive categories blocked), NVD CVE search, VirusTotal, CVE→asset correlation, one-command bug-bounty workflow with a 7-question validation gate (kills noise/unconfirmed findings) + platform-ready PoC report
- **Blue-team defensive mode** — host monitor: baselines listening ports + processes, flags new/suspicious ones (known backdoor ports + attacker tooling) — offense *and* defense
- **Local multimodal vision** — "what's on my screen" / describe any image via an Ollama vision model (llava etc), all on-device
- **Bug-bounty knowledge pack** — Ultron RAG-indexes real methodology notes (recon, takeover, SQLi/XSS/SSRF/IDOR playbooks, OSINT) + bundled wordlists; ask "how do I test for subdomain takeover" and get a grounded, sourced answer, all local
- **Chat with your documents (RAG)** — index a file or folder, then ask questions and get grounded answers with source citations. Local TF-IDF retrieval + MarkItDown — no cloud, no embeddings model
- **Unified memory + telemetry** — one facade across the vector/edith/tool/personal stores; SQLite-backed long-term memory; live per-agent telemetry feeding the HUD
- **Gated critic pass** — optional self-review (critique → revise) on high-stakes Ultron/Athena reports
- **Crypto toolkit** — 29-op encode/decode/hash agent (base64/32/58, hex, url, html, unicode, rot13, caesar, morse, md5/sha*, jwt, aes, **auto-detect**) — CTF/bug-bounty payload decoding, all local
- **Reliability engineering** — circuit breaker, LRU routing cache, shared API rate-throttle, startup config validator, structured rotating logs, **393-test regression suite**
- **Proactive engine** — JARVIS reaches out: morning digest, security alerts (new ports / suspicious processes), CVE-watchlist hits, and reminders pushed to the HUD (Telegram/email sinks pluggable)
- **Streaming** — token-by-token SSE responses with sentence-chunked TTS

---

## Architecture

```
            Browser UI (3-mode HUD)  ──SSE──►  Flask (app.py)
                                                  │
                                  brain.process_input_stream
                                  (emotion · memory · personality · routine-record)
                                                  │
                                  cognitive_loop  (route → execute → reflect)
                                                  │
              ┌───────────────────────────────────┼───────────────────────────┐
          router                              executor ──► tools_registry ──► 16 agents
   (regex fast-path + O(1) exact →           (per-step dispatch)                 │
    LLM classify → clarify → fallback)                                    ask_llm()  ──► Ollama
                                                            (circuit breaker · LRU cache · AutoTune · per-agent model routing)
```

- **Router**: O(1) exact-command table + regex fast-path (instant) → LLM intent classifier (cached) → confidence-gated clarification → safe fallback
- **ask_llm()**: single gateway to Ollama — circuit breaker (fail-fast when down), LRU cache, AutoTune sampling, and per-agent model routing all funnel through this one node
- **No import cycles** (verified via knowledge-graph analysis, 904 nodes)

## Agents

Not all 16 are equal — they're tiered by how much real logic each carries (**Core** = substantial,
**Support** = moderate, **Adapter** = thin wrapper over a library/endpoint). Honest by design.

| Agent | Codename | Tier | Role |
|-------|----------|------|------|
| **Ultron** | ULTRON | Core | Cybersecurity — recon, vuln scanning, CVE tracking/correlation, VirusTotal, HackingTool fleet, bug-bounty workflow |
| **FRIDAY** | FRIDAY | Core | Conversational assistant — tasks, goals, notes, habits, health, calendar, reminders |
| **Veronica** | VERONICA | Core | Browser automation (Playwright) — search, navigate, extract |
| **File** | ARCHIVE | Core | Read/summarize documents (PDF/DOCX/audio via MarkItDown), **RAG (chat with your docs)**, apply patches |
| **Vision** | VISION | Core | News, web search, sports, crypto/FX, translation, flight tracking, Hacker News, **image/screenshot understanding** |
| **Athena** | ATHENA | Core | Deep research — multi-source aggregation, GitHub repo/code search |
| **Echo** | ECHO | Support | Dynamic tool generation |
| **System** | SENTRY | Support | OS/CPU/RAM, battery, speed test, tool-result recall |
| **Terminator** | TERMINATOR | Support | Windows desktop control (pywinauto) — focus/type/click/launch apps |
| **Edith** | EDITH | Support | Project/long-term memory (SQLite-backed) |
| **Scheduler** | CHRONOS | Support | Recurring background tasks + proactive engine |
| **Crypto** | CIPHER | Support | Encode/decode/hash toolkit — 29 ops (base64/32/58, hex, rot13, caesar, morse, md5/sha*, jwt, aes, auto-detect) |
| **n8n** | RELAY | Adapter | Trigger self-hosted n8n automation workflows (webhook POST) |
| **Personal** | JOCASTA | Adapter | User facts & profile store |
| **Routines** | MACRO | Adapter | Record & replay command-sequence macros |
| **Self-Improvement** | PHOENIX | Adapter | Response-quality analysis |

## Cybersecurity capabilities (Ultron)

- **Recon**: Nmap (with scan diffing), Subfinder, HTTPX, Katana, screenshots
- **HackingTool fleet**: 180+ pentest/OSINT tools (Amass, theHarvester, Holehe, Maigret, SpiderFoot, TruffleHog, Nuclei, …) run via WSL/Docker, behind a scoped allowlist — recon/OSINT/audit tools enabled, offensive categories blocked, no arbitrary shell
- **Vuln scanning**: Nuclei (severity-filtered)
- **Threat intel**: NVD CVE search, CVE tracking/watchlist, VirusTotal (file/hash/URL/domain/IP)
- **Correlation**: cross-links tracked CVEs against scanned host services ("am I exposed?")
- **Bug-bounty workflow**: `bug bounty <target>` → recon → parse → exploit lookup → validate → **quality gate** (7-question + never-submit blacklist + P1-P5 payout tiers) → platform-ready PoC report
- **Multi-user authz / IDOR oracle**: register principals (`session set`), cross-account `idor check` / `bola check` (owner vs attacker vs anon control), `replay as`, `graphql hunt` (introspection + privileged-mutation) — the money-bug class, live-confirmed on OWASP Juice Shop
- **Threat intel**: `threat intel <ioc>` aggregates IP/domain/URL/hash reputation across feeds (DShield no-key + optional URLhaus/AbuseIPDB/OTX)
- **Target memory graph**: per-host profiles — scans, findings, endpoints, notes + typed intel buckets (APIs / JWT / auth / GraphQL / tech) across hunts
- **Burp ingestion + tagging** (Community-friendly): parse a Burp HTTP-history export → endpoint/param inventory, auto-tagging JWT/GraphQL/API/auth-boundary/tech → typed target profile → nuclei/httpx (no Burp Pro / API key)
- **Evidence/retest loop**: re-probe a finding, capture confirmed request/response evidence into the profile + report (bug-bounty value is in the evidence)
- **GitHub org secret hunt**: enumerate an org/user's repos + flag secret-prone files, recommend a TruffleHog deep-scan
- **Hardening built-in**: SSRF guard (redirect- + encoding-aware), tool execution via argv arrays (no shell), capability allowlist, shared API rate-throttle
- *Authorized targets only.*

## Security & threat model

This is an offensive-security tool, so its own attack surface is documented openly in
**[THREAT_MODEL.md](THREAT_MODEL.md)** — 7 trust boundaries, the attacker model (indirect
prompt injection is primary), controls in place, and known weaknesses (W1–W7) with their fixes.
The command-injection and SSRF weaknesses (W1–W4) are closed; remaining items (prompt-injection
isolation, scan-authorization enforcement) are tracked there. Single-user, localhost-only by
design — do not bind `app.py` to an untrusted network (an optional `JARVIS_TOKEN` header gate
exists for reverse-proxy setups).

## Companion repo — friday-recon

The Ultron offensive-security core is also extracted into **[friday-recon](https://github.com/Kirankk7/friday-recon)**:
the same engine (recon · bug-bounty · validation gate · Burp ingest · methodology KB) as a
focused, dependency-light **CLI** — no Flask / HUD / voice, ~30 MB, runs fully local against
Ollama. Use JARVIS for the full assistant; use friday-recon when you just want the security
toolkit on the command line.

---

## Tech Stack

**Backend**: Python · Flask (SSE streaming) · Ollama (qwen2.5:7b)
**Frontend**: vanilla JS + Canvas HUD (no framework) · 3-mode Command Center
**Voice**: faster-whisper (CUDA) · Kokoro-82M TTS · edge-tts (fallback) · barge-in
**Cognition**: AutoTune adaptive sampling + EMA feedback · per-agent model routing
**Memory**: TF-IDF vector memory · JSON stores · knowledge-graph analysis
**Security tooling**: Nmap · Nuclei · Subfinder · HTTPX · Katana · HackingTool fleet (WSL/Docker) · NVD · VirusTotal
**Other**: Playwright · pywinauto · MarkItDown · DuckDuckGo · football-data.org · n8n

## Setup

```bash
# 1. Install Ollama + pull a model
ollama pull qwen2.5:7b

# 2. Python deps
pip install -r requirements.txt
playwright install chromium

# 3. Config
cp .env.example .env          # add API keys (all optional)

# 4. Run
python app.py                 # → http://localhost:5000
```

**Full command list:** see **[COMMANDS.md](COMMANDS.md)** — every voice/text command + the friday-recon CLI, each with an inline comment. Functional coverage ledger in **[COVERAGE.md](COVERAGE.md)**; an honest end-to-end audit in **[FINAL_VERDICT.md](FINAL_VERDICT.md)**.

On boot, a **config validator** prints a readiness summary (Ollama reachable, model pulled, optional keys, security tools, HackingTool backend) — loud about what's missing, never fatal.

**Optional API keys** (features degrade gracefully without them): NVD, VirusTotal, football-data.org, GitHub token, n8n.
**Security tools**: Nmap + ProjectDiscovery suite on PATH for the native fast-path; WSL or Docker Desktop for the 180+ HackingTool fleet.

## Testing

```bash
python test_regression.py     # 393 tests (402 total, 9 skipped offline), HTML report
python scripts/coverage.py    # → COVERAGE.md — every action PASS / SKIP / FAIL
```

Covers all 16 agents, router patterns, security helpers + HackingTool gates, SSRF guard, circuit breaker, AutoTune + model routing, API throttle, config validator, memory, TTS, and live-API integrations (skipped when offline).

---

## Status

Feature-complete core. Local assistant + voice + 3-mode HUD + cybersecurity toolkit, all functional and tested (393 tests green). Hardened over a 56-session dogfood campaign — chat front-door proven 0-misroute/0-crash, the security engine live-confirmed (SQLi/NoSQLi/XSS/IDOR) on OWASP Juice Shop + DVWA.

*Built as a learning project exploring local LLM orchestration, multi-agent design, adaptive cognition, and AI-assisted security workflows.*
