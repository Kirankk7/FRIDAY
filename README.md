# FRIDAY (JARVIS) — Local AI Personal Assistant

A privacy-first, fully-local AI assistant with a multi-agent architecture, voice I/O, and a built-in cybersecurity toolkit. Runs entirely on your own machine — no cloud inference, no API keys for the core LLM.

> *FRIDAY is the default conversational agent; the system as a whole is JARVIS.*

---

## Highlights

- **100% local LLM inference** via [Ollama](https://ollama.com) (`qwen2.5:7b`) — no OpenAI/Gemini/cloud
- **Multi-agent architecture** — 12 specialized agents behind a dual-path intent router
- **Voice in + out** — faster-whisper STT (CUDA) + Kokoro-82M neural TTS (per-agent voices), edge-tts fallback
- **Cybersecurity agent (Ultron)** — Nmap, Subfinder, HTTPX, Nuclei, Katana, NVD CVE search, VirusTotal, CVE→asset correlation, one-command bug-bounty workflow with PoC report
- **Reliability engineering** — circuit breaker, LRU routing cache, structured rotating logs, 176-test regression suite
- **Streaming** — token-by-token SSE responses with sentence-chunked TTS

---

## Architecture

```
            Browser UI  ──SSE──►  Flask (app.py)
                                      │
                          brain.process_input_stream
                          (emotion · memory · personality enrichment)
                                      │
                          cognitive_loop  (route → execute → reflect)
                                      │
              ┌───────────────────────┼───────────────────────────┐
          router                  executor ──► tools_registry ──► 12 agents
   (regex fast-path →           (per-step dispatch)                 │
    LLM classify → clarify)                                  ask_llm() ──► Ollama
                                                          (circuit breaker + LRU cache)
```

- **Router**: regex fast-path (instant) → LLM intent classifier (cached) → confidence-gated clarification → safe fallback
- **ask_llm()**: single gateway to Ollama — protected by a circuit breaker (fail-fast when down) and an LRU cache
- **No import cycles** (verified via knowledge-graph analysis)

## Agents

| Agent | Role |
|-------|------|
| **FRIDAY** | Conversational assistant — tasks, goals, notes, habits, health, calendar, reminders |
| **Ultron** | Cybersecurity — recon, vuln scanning, CVE tracking/correlation, VirusTotal, bug-bounty workflow |
| **Athena** | Deep research — multi-source aggregation |
| **Vision** | News, web search (DuckDuckGo), sports data, Hacker News |
| **Veronica** | Browser automation (Playwright) — search, navigate, extract |
| **Edith** | Project/long-term memory |
| **Echo** | Dynamic tool generation |
| **Personal** | User facts & profile |
| **System** | OS/CPU/RAM, battery, speed test, tool-result recall |
| **File** | Read/summarize documents (PDF/DOCX/audio via MarkItDown), apply patches |
| **Scheduler** | Recurring background tasks |
| **Self-Improvement** | Response-quality analysis |

## Cybersecurity capabilities (Ultron)

- **Recon**: Nmap (with scan diffing), Subfinder, HTTPX, Katana, screenshots
- **Vuln scanning**: Nuclei (severity-filtered)
- **Threat intel**: NVD CVE search, CVE tracking/watchlist, VirusTotal (file/hash/URL/domain/IP)
- **Correlation**: cross-links tracked CVEs against scanned host services ("am I exposed?")
- **Bug-bounty workflow**: `bug bounty <target>` → recon → parse findings → exploit lookup → validate → clean PoC report
- **Hardening built-in**: SSRF guard (blocks internal/metadata IPs), shell-command allowlist + injection sanitizer
- *Authorized targets only.*

---

## Tech Stack

**Backend**: Python · Flask (SSE streaming) · Ollama (qwen2.5:7b)
**Voice**: faster-whisper (CUDA) · Kokoro-82M TTS · edge-tts (fallback)
**Memory**: TF-IDF vector memory · JSON stores · knowledge-graph analysis
**Security tooling**: Nmap · Nuclei · Subfinder · HTTPX · Katana · NVD API · VirusTotal API
**Other**: Playwright · MarkItDown · DuckDuckGo search · football-data.org

## Setup

```bash
# 1. Install Ollama + pull a model
ollama pull qwen2.5:7b

# 2. Python deps
pip install -r requirements.txt
playwright install chromium

# 3. Config
cp .env.example .env          # add API keys (all optional except features that use them)

# 4. Run
python app.py                 # → http://localhost:5000
```

**Optional API keys** (features degrade gracefully without them): NVD, VirusTotal, football-data.org.
**Security tools** (for Ultron's recon): Nmap + ProjectDiscovery suite (subfinder/httpx/nuclei/katana) on PATH.

## Testing

```bash
python test_regression.py     # 28 sections, 176 tests, HTML report
```

Covers all agents, router patterns, security helpers, SSRF guard, circuit breaker, memory, TTS, and live-API integrations (skipped when offline).

---

## Status

Active development. Core assistant + voice + cybersecurity toolkit functional and tested. Roadmap: translation/finance/flight tools, n8n automation, 3-mode HUD interface.

*Built as a learning project exploring local LLM orchestration, multi-agent design, and AI-assisted security workflows.*
