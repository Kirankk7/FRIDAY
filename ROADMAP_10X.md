# JARVIS / friday-recon — 10x Roadmap

*What actually makes this 10x more valuable — grounded in the current code, honest about the ceiling.*

---

## The honest framing (read this first)

Capability is **model-bound** — qwen-7B local. No feature makes the *reasoning* smarter; that's settled
(`local_vs_cloud_llm`, `ultron_roadmap`). So "10x" cannot mean "finds cleverer bugs." It means removing
everything that sits **between you and a real, paid finding**:

1. **Kill the manual friction** — today a real hunt needs a manual Burp export before the authz oracle can
   run. That exact gap stalled the HotelTonight engagement ("next depth needs app-traffic capture").
2. **Work while you sleep** — recon that re-runs and *alerts on new attack surface* = first-mover edge.
3. **Get paid more per finding** — payout ∝ evidence/report quality, not payload cleverness.
4. **Catch the class single requests miss** — multi-step BOLA / broken-flow.

Everything below is **plumbing, not intelligence** — which is why it's safe to build against a 7B model.

**What this roadmap deliberately does NOT add** (per `ultron_roadmap` / rejected before): no new scanners or
probe classes, no agent "swarms," no SAST, no cloud-LLM swap for ultron/recon, no web-dashboard rebuild, no
response-composer-over-everything. More scanners ≠ more value at this model ceiling.

---

## Sequenced build order

| # | Feature | Tier | Why it's 10x | Effort | New dep |
|---|---------|------|--------------|--------|---------|
| **F1** | Live intercept proxy → auto authz-feed | Bounty capability | removes the #1 manual-friction gap | M | mitmproxy |
| **F2** | Continuous attack-surface monitoring + diff alerts | Bounty capability | recon while you sleep | L–M | none |
| **F3** | Evidence bundle + platform submission draft | Payout multiplier | payout ∝ report quality | M | none |
| **F4** | Multi-step authenticated flow replay (BOLA) | Payout multiplier | catches broken-flow single reqs miss | M–H | builds on F1 |
| **F5** | Two-way Telegram command & control | Reach | localhost toy → always-on phone tool | L–M | none |
| **F6** | Playbook auto-learn from confirmed findings | Compounding | tool sharpens with every real TP | L | none |

F1 + F2 are the real 10x. Do them first. F3/F4 multiply what a finding is worth. F5/F6 are reach + compounding.

---

## F1 — Live intercept proxy → live inventory + authz auto-feed  ⭐ highest leverage

**What.** A local mitmproxy addon. You browse a target *through it* (authenticated, as a normal user); it
streams every request into the **same endpoint/param/auth-tag inventory** `burp_ingest._tag()` already
produces — no manual XML export. Captured login flow auto-registers a `session_manager` principal. One
command then runs `idor_check` across every captured object-id endpoint.

**Why 10x.** This is the exact blocker from the HotelTonight engagement: read-only recon was exhausted, "next
depth needs app-traffic capture." Today `burp_ingest` needs a manual Burp export; `session_manager` needs a
hand-pasted cookie. F1 closes both automatically. Reuses existing tagging + session code → mostly wiring.

**Acceptance criteria.**
- [ ] `python cli.py proxy --port 8081` starts mitmproxy; a CA-install hint prints once.
- [ ] Browsing ~20 requests through it writes `data/capture/<host>.json` with `{endpoints, params, tags}` in the **same schema** `burp_ingest.parse_export` returns (verified by a shared schema test).
- [ ] A captured login response auto-registers a principal (cookie **or** `Bearer` extracted) retrievable via `sessions`.
- [ ] `idor scan-captured <host>` runs `idor_check` on every captured endpoint carrying a numeric/uuid id param, owner vs a 2nd registered principal, and reports **only** true cross-account reads (gate confidence ≥ `candidate`).
- [ ] End-to-end: browse → stop proxy → inventory ready in < 5s; **zero** manual export step.
- [ ] Regression: a recorded-flow fixture → asserts ≥1 authz candidate surfaced, 0 uncaught exceptions.
- [ ] HTTPS handled via mitmproxy CA; guarded so a cert failure degrades gracefully (clear message, no crash).

**Notes.** mitmproxy is the one meaningful new dependency — justified: it *is* the concrete need, not
speculative. Local, Python, no cloud. Passive capture only; active scanning stays nuclei's job.

---

## F2 — Continuous attack-surface monitoring + diff alerts

**What.** `watch <target>` registers a monitored target. The **existing** scheduler re-runs
subfinder + httpx + katana + JS-endpoint-extract on the **existing** `PROACTIVE_MONITOR_MIN` interval, diffs
each run vs the last snapshot, and pushes **new** subdomains / live hosts / endpoints / JS files through the
**existing** `notify` sink (HUD + Telegram).

**Why 10x.** A newly-appeared subdomain or API endpoint is a first-mover bounty. Recon that runs itself and
alerts you is a force-multiplier no manual workflow matches. Scheduler, proactive_engine, notify, and the
`PROACTIVE_MONITOR_MIN` knob already exist — this is assembly, not new machinery.

**Acceptance criteria.**
- [ ] `watch <target>` / `watch list` / `unwatch <target>` manage monitored targets (persisted `data/watch/targets.json`).
- [ ] Scheduler fires a re-scan every `PROACTIVE_MONITOR_MIN` (0 = off); snapshots saved `data/watch/<target>/<ts>.json`.
- [ ] Diff emits exactly **one** alert per genuinely-new surface item; an unchanged re-run emits **zero** (dedup verified by test).
- [ ] Injecting a synthetic new host into the prior snapshot → precisely one "new surface" notification.
- [ ] A missing recon binary → that source is skipped gracefully; the watch loop never crashes the scheduler.
- [ ] Alerts carry target + item + type + first-seen timestamp; visible in `/notifications` and (if configured) Telegram.

---

## F3 — Evidence bundle + one-click platform submission draft

**What.** For every gate-passed finding, auto-capture a proof bundle and generate a platform-ready
submission. Upgrades `_validate_finding` output + `_format_bb_report`.

**Why 10x.** Bounty payout tracks **report quality**, not payload novelty. A finding with a captured
request/response, a `curl` repro, a screenshot, a CWE id, and a CVSS vector gets triaged faster and paid more.

**Acceptance criteria.**
- [ ] Each gate-passed finding writes `evidence/<finding>/` containing: raw request, raw response, a `curl` one-liner that reproduces it, and (web findings) a Playwright screenshot.
- [ ] `_format_bb_report` output includes a **CWE id** and a **CVSS 3.1 vector string** per finding.
- [ ] `export submission <finding>` writes a `.md` with title / severity / steps-to-reproduce / impact / remediation / evidence-links — a lint check asserts every required section is non-empty.
- [ ] The `curl` repro, run against the target, reproduces the documented response (manual spot-check documented in the log).
- [ ] Report renders with 0 ANSI, real file paths, correct payout tier.

---

## F4 — Multi-step authenticated flow replay (BOLA / broken-flow)

**What.** Extend single-request `idor_check` to **ordered sequences**. `flow record <name>` captures a
request sequence (via the F1 proxy); `flow replay <name> as <principal>` re-runs it swapping the principal
and flags when principal B completes an action scoped to A's object.

**Why 10x.** The high-value BOLA / broken-object-flow class (add-to-cart → checkout-as-other,
create → read-as-other) is invisible to single-request tests. This is where real API bounties live.

**Acceptance criteria.**
- [ ] `flow record <name>` (via F1 proxy) saves an ordered sequence to `data/flows/<name>.json`.
- [ ] `flow replay <name> as <principal>` re-issues the sequence with the swapped principal's headers.
- [ ] Detects a cross-principal success (B reads/changes A's object) → `candidate`; a properly-scoped app → clean.
- [ ] Read-only by default; state-changing replay requires an explicit `--allow-writes` flag.
- [ ] Fixture: one vulnerable flow → asserts a broken-flow candidate; one patched flow → asserts clean.

---

## F5 — Two-way Telegram command & control

**What.** A Telegram bot: issue recon/watch commands from your phone, get findings + watch alerts pushed
back. The outbound sink hook (`notify.register_sink`) already exists; this adds the inbound half.

**Why 10x.** Converts a localhost-only tool into an always-on service you drive from anywhere — the
difference between a demo and a tool you actually use daily.

**Acceptance criteria.**
- [ ] `/recon <t>`, `/watch <t>`, `/status`, `/findings` work from Telegram; long ops run async and push the result when done.
- [ ] Only `TELEGRAM_CHAT_ID` may issue commands; any other chat id is ignored (auth test).
- [ ] Watch alerts (F2) + confirmed findings (F3) arrive via the existing sink, unchanged.
- [ ] No token configured → bot stays fully dormant (existing behavior preserved, verified).

---

## F6 — Playbook auto-learn from your own confirmed findings

**What.** On a **reproduced** gate-passed finding, append a `[PROVEN]` technique entry (class, payload,
endpoint-shape, stack fingerprint) to the local playbook (`playbook.py`), so the next hunt on a similar stack
recalls what actually worked for you.

**Why 10x.** The tool compounds — every real TP makes the next hunt sharper. Local, private, yours.

**Acceptance criteria.**
- [ ] A finding with confidence `reproduced` appends exactly one `[PROVEN]` entry (class + payload + endpoint-shape + tech tag).
- [ ] `playbook <class>` recalls proven-first, then KB, then PortSwigger.
- [ ] No duplicate entries on the same technique+stack (dedup verified).
- [ ] Playbook file stays local / gitignored; off if it introduces recall noise.
- [ ] A confirmed Juice Shop SQLi run → exactly one new proven entry, recallable next run.

---

---

# Part 2 — All-aspect (daily-driver) features

*Not cyber. Reviewed the full codebase; these fill real gaps in the assistant / proactive / memory
surface. Same rule: plumbing, not model-intelligence. Confirmed gaps: **no weather anywhere**,
**Telegram is send-only** (`telegram_sink._send`, no inbound `getUpdates`), **morning digest is thin**
(tasks/reminders/events only), **no unified search** across the silos, **no portfolio tracker**.*

**Status:** F1 is **built** (code + tests written, pending the single batch regression). A–H below are
**not started**.

### Verified against the codebase (2026-07-02)

Grepped `core/router.py` + every agent to confirm none of these already exist:

- **A Weather** — confirmed absent (only appears in routines/knowledge text; no weather API, no route). NEW.
- **B Briefing** — a digest *does* exist: `proactive_engine._morning_digest` (tasks/reminders/events only,
  fires once/day after `PROACTIVE_DIGEST_HOUR`). B **enriches** it (weather+news+crypto) and adds an
  on-demand `brief me` — not a new digest.
- **C Telegram** — `telegram_sink` is **send-only** (`_send` via `register_sink`); no inbound `getUpdates`.
  The inbound half is NEW.
- **D Unified find** — NEW. The existing `find <x>` (router:500) is **filename-only, scoped to one
  remembered folder**; "find anything" at router:584 is just an error string. D must broaden this **without
  breaking** the filename path (gate D so it doesn't hijack the existing behavior).
- **E Portfolio** — confirmed absent. NEW.
- **G Calendar ICS** — friday has internal events; no `.ics` import/export anywhere. NEW.
- **H Expenses** — confirmed absent. Note: `my budget` exists only as a personal-fact **key**
  (router:2096/2541) — a stored string, not expense tracking. Unrelated; no collision.

## A — Weather agent

**What.** A `core/weather.py` on open-meteo (geocode + forecast, **no API key**). "weather in Dubai",
"weather", "will it rain tomorrow", "forecast <place>". Wired as a `vision` action (live-info aligns).

**Why 10x.** A daily-driver assistant with no weather is a glaring hole; near-zero cost to fix.

**Acceptance criteria.**
- [ ] `weather in <place>` → current temp + condition + today high/low + rain-chance, one spoken line.
- [ ] Bare `weather` uses a default place (config `DEFAULT_CITY`, fallback a sane constant).
- [ ] "will it rain (tomorrow)" → precipitation-probability answer for today/tomorrow.
- [ ] Unknown place → graceful "couldn't find that place, boss" (no crash); network down → graceful.
- [ ] No key required; weather_code mapped to human text; regression test with a mocked response.

## B — Rich morning briefing

**What.** Extend the existing `proactive_engine._morning_digest` (today tasks/reminders/events) to also
fold in **weather (A) + top news headline(s) + crypto snapshot**, and expose it on demand: "morning
briefing" / "brief me" returns the same assembled brief any time.

**Why 10x.** One "good morning" = the whole day in a breath. Pure assembly of agents that already exist.

**Acceptance criteria.**
- [ ] `brief me` / `morning briefing` → one reply with: today's tasks + next event + reminders + weather + 1–2 news headlines + BTC/ETH price.
- [ ] The daily proactive digest (after `PROACTIVE_DIGEST_HOUR`) uses the same assembler.
- [ ] Any source failing (news/crypto/weather down) degrades gracefully — the brief still returns with the rest.
- [ ] Length-governed, no ANSI/markdown dump; regression test asserts the assembler runs with a stubbed set and returns all present sections.

## C — Two-way Telegram

**What.** Add the inbound half to `telegram_sink` (currently send-only): a `getUpdates` poller that
accepts commands from your phone, dispatches through `brain.process_input`, and replies. Outbound
digest/alerts already flow via the registered sink.

**Why 10x.** Turns a localhost-only assistant into an always-on tool you drive from anywhere.

**Acceptance criteria.**
- [ ] `/task buy milk`, "what's my day", "weather in Dubai", "recon <t>" from Telegram → executed, reply pushed back.
- [ ] **Only `TELEGRAM_CHAT_ID`** may issue commands; any other chat id is ignored (auth test).
- [ ] Poller starts from `app.py` only when a bot token is set; fully dormant otherwise (existing behavior preserved).
- [ ] Long ops don't block the poll loop (runs on its own thread); a failing update never kills the loop.
- [ ] Regression test: auth gate rejects a wrong chat id; a stubbed update routes to `process_input`.

## D — Unified "find anything"

**What.** `core/unified_find.py` — one query fans out across friday tasks/notes/goals + edith memory +
vector memory + file-RAG docs, returns a ranked, grouped result. "find <x>", "search my notes/tasks for <x>".

**Why 10x.** Kills the silo problem — today each store is searched separately. One front door to everything you've saved.

**Acceptance criteria.**
- [ ] `find <x>` returns grouped hits (Tasks / Notes / Goals / Memory / Docs) with the source labeled.
- [ ] Each source failing independently degrades gracefully (partial results, no crash).
- [ ] Empty query → clarify; no matches → honest "nothing found for <x>".
- [ ] Router sends it to a single handler; result is length-governed. Regression test seeds one item per store and asserts each surfaces.

## E — Crypto portfolio watchlist

**What.** `core/portfolio.py` — a local holdings store (`data/portfolio.json`, gitignored) valued live via
the existing `vision.crypto_price`. "add holding 0.5 btc", "how's my portfolio", "remove btc".

**Why 10x.** Turns the one-off "bitcoin price" into a personal, persistent finance view. Extends existing code.

**Acceptance criteria.**
- [ ] `add holding <amount> <coin>` persists; `how's my portfolio` → per-coin value + total, live-priced.
- [ ] `remove <coin>` / `portfolio clear`; empty portfolio → friendly prompt to add one.
- [ ] Live pricing reuses `vision.crypto_price` (no new key); price fetch failing → shows holdings without value, no crash.
- [ ] Numbers formatted (not raw floats); regression test adds/values/removes with a stubbed price.

## G — Calendar ICS import / export

**What.** friday already holds internal events but has **no interchange** with real calendars. Add
`export calendar` → writes an `.ics` (standard VEVENTs) and `import calendar <file/url>` → pulls events
from an `.ics` (Google/Outlook/Apple all export this). No OAuth — plain iCalendar text.

**Why 10x.** Bridges the assistant's calendar to the ones you actually use — one-way sync without the
OAuth tax.

**Acceptance criteria.**
- [ ] `export calendar` writes a valid `.ics` (opens in Google/Apple Calendar) of upcoming friday events.
- [ ] `import calendar <path|url>` parses VEVENTs → friday events (title/date/time), de-duped on (title, date).
- [ ] Malformed/empty `.ics` → graceful message, no crash; network fetch failure handled.
- [ ] Regression test: round-trips a small fixture (export → import → same events).

## H — Expense / spending log

**What.** `core/expenses.py` — a local spend log (`data/expenses.json`, gitignored), the finance
companion to E. "spent 40 on groceries", "how much did I spend this week", "spending by category".

**Why 10x.** Turns the assistant into a lightweight money tracker; pure local, no bank integration.

**Acceptance criteria.**
- [ ] `spent <amount> on <category/note>` persists with a timestamp.
- [ ] `how much did I spend (this week/month)` → total for the window; `spending by category` → grouped totals.
- [ ] Empty log → friendly prompt; amounts formatted, not raw floats.
- [ ] Regression test: logs two, queries the window total + a category breakdown.

## Considered & deliberately deferred (honest)

- **Email read/send** — real value, but needs OAuth / app-password + a trust boundary; heavy against the
  lean, no-cloud-creds ethos. Revisit only on concrete need.
- **Spotify / media control** — niche; OS-level media keys via `terminator` already cover play/pause.
- **Conversation-history export / search** — largely covered by **D** (unified find) + vector memory; not
  worth a separate feature.
- **More scanners / SAST / agent swarms** — still rejected (model ceiling), same as Part 1.

## Suggested build order (Part 2)

`A → B` (B depends on A) `→ E → H → D → G → C`. A/B/E/H are small; D/G medium; C is the biggest (threaded
poller). Batch build, then **one** regression covering F1 + the selected Part-2 features.

---

---

# Part 3 — By subsystem (HUD / voice / automation / memory)

*The aspects you named. Verified against code: each is a real gap, not already built.*

## I — Interactive command HUD

**What.** `hud_command.html` today only **polls** `/metrics` + `/notifications` — it's a dashboard, it
can't *act*. Make it interactive: click an agent tile / command chip → fires via `/chat_stream`, streams
the reply in-panel; a live **findings feed** (new `/findings` endpoint) listing gate-passed findings; a
one-click "run recon / bug-bounty on `<target>`" with a link to the saved report.

**Why 10x.** Turns the showpiece HUD from a pretty gauge into the actual cockpit — the demo *and* the tool.

**Acceptance criteria.**
- [ ] Clicking an agent/command tile runs it via `/chat_stream` and streams the reply in a HUD panel.
- [ ] A findings panel polls `/findings` → gate-passed findings (target / severity / tier), newest first.
- [ ] A target input launches recon/bug-bounty and links the saved report.
- [ ] The 3 existing HUD modes still work; any endpoint down → panel degrades, no blank HUD.

**Effort:** M (frontend + one `/findings` route).

## J — Voice upgrades  *(env-limited: full verify needs mic/speaker)*

**What.** J1 — unhardcode `voice_loop._transcribe` (`language='en'`); add config `VOICE_LANG`
(`auto|en|hi|…`) + a Kokoro voice per language. J2 — voice memos: speak → `/transcribe` (Whisper) →
`friday.add_note` ("take a voice note").

**Why 10x.** Multilingual = usable by way more people; voice-memo→note is the killer hands-free capture.

**Acceptance criteria.**
- [ ] `VOICE_LANG` drives STT language; `auto` lets Whisper detect (code-verifiable; audio path env-limited).
- [ ] A transcribed voice memo lands as a friday note; empty/failed transcription → graceful.
- [ ] Kokoro voice selected per language; falls back cleanly when a voice isn't available.

**Effort:** S–M.

## K — Scheduled & event-triggered routines  ⭐ biggest automation gap

**What.** Routines record/replay, but there is **no link to the scheduler** and **no event triggers**.
Wire them: `run <routine> every day at 8am` → scheduler fires `routines.run_routine`; event bindings — on
a watch-alert (F2) or a new finding, auto-run a named routine.

**Why 10x.** Turns one-shot macros into real automations — the thing that makes "automation" actually
automatic. Scheduler + routines both already exist; this is the wiring between them.

**Acceptance criteria.**
- [ ] `schedule routine <name> <when>` registers a scheduler task that runs the routine at time; `unschedule routine <name>` removes it.
- [ ] Scheduled routines persist and survive a restart (`data/`-backed, like other scheduler tasks).
- [ ] An event (watch alert / new finding) can run a bound routine; bindings are listable.
- [ ] A missing routine / bad schedule string → graceful, never crashes the scheduler loop.

**Effort:** M.

## L — Auto-RAG watch folder

**What.** `index docs <folder>` is one-shot. Add `watch docs <folder>` — the scheduler re-indexes changed
files on an interval, so `ask docs` is always current over your notes / Obsidian vault.

**Why 10x.** "Chat with my notes" stops going stale — it tracks the folder instead of needing a manual reindex.

**Acceptance criteria.**
- [ ] `watch docs <folder>` registers it; changed files re-index on the interval (mtime diff).
- [ ] `ask docs "<q>"` answers over the latest content with no manual reindex.
- [ ] Binary/locked/oversize files skipped gracefully; nothing crashes the loop.

**Effort:** S–M.

## Part 3 build order

`K → L → I → J`. K is the highest-leverage (real automation); L small; I is the visible showpiece; J last
(env-limited verification).

---

## Definition of done (the whole roadmap)

- Each feature: acceptance criteria all green + a regression test locked in + `scripts/dogfood.py` and the
  relevant suite green + committed (no Co-Authored-By footer, per `commit-style`).
- `COVERAGE.md` refreshed — new actions appear and are PASS or a justified SKIP.
- Ported to friday-recon where CLI-relevant (F1/F2/F3/F4/F6) via `recon_drift.py`; JARVIS keeps F5 (Telegram).
- The 10x is proven the honest way: **F1** demoed capturing a live authed session and surfacing a real
  authz candidate with zero manual export — the friction that stalled HotelTonight, gone.

**Priority if you only build two: F1 + F2.** That's the jump from "impressive portfolio project" to "a tool
that finds paid bugs while you sleep."
