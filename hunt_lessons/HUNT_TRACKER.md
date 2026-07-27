# Hunt Tracker — the north-star dataset

## THE OPERATING CONTRACT (banked 2026-07-16, GPT↔Claude converged — final)
Track ONLY these. If the first six trend right and the last trends down, FRIDAY is healthy:
| metric | goal |
|---|---|
| real hunts completed · lessons extracted · confirmed findings · report accept-rate | ↑ |
| false positives · missed findings | ↓ |
| **new features / LOC / modules** | **↓** |

**6 rules (supersede the scattered cadence notes):**
1. **No new feature** unless **≥3 hunts ACROSS DIFFERENT programs** reveal the *same root-cause* missing capability → then ship the **smallest possible fix**. **External inspiration (GitHub repo, conf talk, blog, paper, another tool) is NEVER sufficient justification** — only *recurring pain in real authorized investigations* is. (banked 2026-07-21, APIHarvester design-review: reviewed → 0 built, 1 watched [path-param templating], because 0/5 hunts proved any gap.)
2. **No empty hunts** — every hunt produces one of: finding · FP · missed-opportunity · lesson.
3. **Every 25 hunts** — review the DATA, not the code.
4. **Every 100 hunts** — pay down exactly ONE architectural debt. Nothing more.
5. **Every hunt runs THE COVERAGE SWEEP (below) — ALL classes, not 1-2.** BOLA is FIRST (highest EV), NEVER ONLY. A hunt isn't "done" until every class is `tested` or `N/A — no surface`. (banked 2026-07-21, hunt-earned: 6/6 hunts tunnel-visioned on BOLA; the session's only confirmed finding — **class #5, not the BOLA we opened with** — surfaced only when the operator forced the wider look. Root cause: "highest-EV-first" silently became "only". Target+class kept private per program disclosure rules.)

6. **DEFINITION OF DONE: a hunt is not complete until its knowledge is recorded IN THE ENGINE.** Not in your head, not in chat, not in a note — `ingest` the capture, run `sweep`, and bank every confirmed *and* ruled-out result against the target profile. Rule #2 says every hunt produces a finding/FP/miss/lesson; this says where that output has to LAND. (banked 2026-07-25: nine consecutive hunts produced real knowledge and the engine received none of it, because recording was treated as optional cleanup instead of part of finishing.)

## THE COVERAGE SWEEP — mandatory per-hunt SOP (the methodology)
**Phase 0 — TARGET MODEL first (before any class).** From the HAR, build the mental model: API type (REST/GraphQL/SPA) · auth (JWT/cookie/key) · roles/tenants · object model + relationships · trust boundaries · external integrations (uploads/payments/search/messaging/imports/exports/webhooks). *Attack classes only make sense after you understand the app — the model tells you WHERE each lens is even relevant.* **Phase 1 — walk EVERY class below** through that model. For each: **test it, or write `N/A — no surface`.** Never default to BOLA and stop. This is a MANUAL co-pilot checklist (the "lenses" you view the same traffic through), NOT new engine code — the engine already has the probes; the gap was the hunt loop.

| # | Class | Surface signal in the HAR → what to test |
|--|-------|-------------------------------------------|
| 1 | **BOLA / IDOR** | object-id in request (int / uuid / base64) → swap across YOUR 2 accounts (read + write) |
| 2 | **BFLA / vertical priv-esc** | role / permission / admin / group-tier params or endpoints → low-priv calls high-priv op |
| 3 | **SQLi / NoSQLi** | search / filter / sort / id params → `'`, `$ne`/`$regex` (encode brackets), DB-error/behavior-diff |
| 4 | **XSS (stored + reflected)** | any input rendered back (profile/bio/name/description/ticket) → `<img onerror>`; check OUTPUT context (HTML vs JSON) |
| 5 | **SSRF / XSPA** | any URL the server fetches (webhook/avatar/document/import/callback/preview) → OOB listener; then internal/metadata |
| 6 | **Mass assignment** | create/update bodies → inject undeclared fields (`role`,`price`,`isVerified`,`isAdmin`); (dead on persisted-query GraphQL) |
| 7 | **Business logic** | price / qty / discount / state / step fields → negative, >100%, overflow, skip-step, replay |
| 8 | **Secrets / info disclosure** | tokens/keys in responses, verbose errors, stack traces, debug/internal endpoints |
| 9 | **Auth / session** | password-reset, MFA, magic-link, token scope/expiry, OAuth redirect |
| 10 | **Injection: cmd/SSTI/XXE/path** | template inputs, file/xml upload, path params → server-side eval signals |

**Rule of the sweep:** model FIRST, then for each class ask *"does this target expose surface for it?"* → test-or-N/A. The bug hides in the class you didn't check. (a live hunt: BOLA/BFLA all ✗, but class #5 hit.)

**RUN IT, don't remember it — `sweep <capture.har|burp.xml>` (built 2026-07-24).** Four consecutive hunts applied this table by hand and the engine was used ~0% of the time (throwaway parsers got written mid-hunt instead), so the SOP is now an artifact: the command reads a capture you ALREADY took and returns, per class, either TESTABLE (which endpoints/params + how verification would work) or `N/A — <reason>`. Offline, deterministic, sends nothing — legal on the scanner-forbidding programs where the rest of the pipeline can't go. It replaces the *bookkeeping*, not the judgement: it names the class, the endpoint and the approach, but **you** decide and send the exact check — by design, not by omission (docs/PRODUCT_BOUNDARIES.md "the sweep's fence"). Phase 0 is still yours. Dogfooding it on the real hunt captures immediately caught what hand-analysis missed (path-borne ids, e.g. `/accounts/{id}/projects`, `/accounts/{id}/files`, `PUT /conversations/{uuid}` — never tested by hand).
**The list is LIVING, not dogma:** the real rule is *"every major vuln class RELEVANT to the target gets considered"* — the 10 rows are today's default, add/drop as the class landscape evolves. **DEFER (engine, not hunt-proven): "rank candidates WITHIN each class" not across** — a `hunt_mode` change GPT proposed; watch, build only if a hunt hurts for it (reject review-inspired code per rule #1).

## Phase 2 — MICRO-CLASSES + AUTH DEEP-DIVE (banked 2026-07-23, hunt-earned: the top-10 alone isn't exhaustive)
After the 10 main classes, walk the micro-tier for any RELEVANT surface (same test-or-N/A). This is what makes a hunt *exhaustive*:
| Micro-class | What to test / the tell |
|---|---|
| **Auth deep-dive (JWT)** | `alg:none` (unsigned accepted?) · **RS256→HS256** key-confusion (needs public key — JWKS endpoint, or recover from 2 sigs via `rsa_sign2n`) · `jku`/`kid` header injection (point verify at attacker key) |
| **File upload** | SVG/HTML/polyglot XSS → **check `Content-Disposition`** (`attachment` = mitigated, esp. if in a SIGNED S3 policy) · path-traversal filename · content-type bypass · served-origin (separate CDN = low sev) |
| **CORS** | reflect `Origin` + `ACAC:true`? — but impact GATED by auth type (cookie = real; **Bearer-header = defanged**, attacker can't ride it) |
| **CSRF** | only if **cookie-auth**; **N/A on Bearer-header auth** |
| **GraphQL-abuse** | introspection · batching · alias-brute · deep-query DoS · field-injection · mass-assign — **ALL DEAD if persisted-queries** (`sha256Hash` locks the schema to pre-registered ops) |
| **Open redirect · JS-bundle secrets · race conditions · web-cache poisoning** | spot as surface appears (open-redirect often policy-non-qual; grep the SPA bundle for hardcoded keys) |

**Every real hunt from 2026-07-23 on = Phase 0 (target model) → Phase 1 (10 classes) → Phase 2 (micro + auth deep-dive), each test-or-N/A.** That's the standard. (Proven exhaustive on the first target it ran against.)

## Coverage taxonomy — Core / Emerging / Tech-Modules (banked 2026-07-27, GPT↔Claude converged; NOTHING built)
A cleaner frame than Phase-1/2 for *what belongs in the sweep*. **All three tiers are governed by Rule #1: a class is promoted only after it hurts in ≥2 real hunts across different programs — a review NEVER earns it.**
- **CORE (always run) = the current 10.** Frozen. Already covers the high-value web space; the work now is *investigating* them better, not adding siblings.
- **EMERGING (deferred, add on 2× recurrence):** Prototype Pollution · Deserialization (Java/​.NET/PHP/pickle/YAML) · HTTP Request Smuggling / desync · Cache Poisoning (CDN/deception/key-confusion). All real, all *uncommon vs the top 10*. **At 13 hunts we've hit ZERO of them → correct to build none.**
- **TECHNOLOGY MODULES (surface only when the sweep detects the tech):** GraphQL (already a micro-class) · cloud storage (S3/Azure/GCP) · Solr/Elasticsearch/Redis/Kafka · WebSockets · k8s/Docker. **These are investigator-bookshelf, NOT engine code** — the sweep already prints `context.servers`; when it flags tech X the operator consults X's playbook mid-hunt. Don't build a module system (YAGNI, no recurring pain).
- **Deferred cosmetic:** split Class 10 (Injection) → "Server-side code exec (CMD/SSTI)" + "File & parser (XXE/path/LFI/RFI)". Cleaner, but cosmetic → only if a hunt makes the conflation actually hurt.
- **The gate (unchanged):** not *"is this a real vuln?"* but *"have we hit it ≥2× in real hunts?"* No → don't build. This keeps the engine a hunting workflow, not an OWASP checklist. See [[phase-shift-hunt-not-build]], [[bank-reviews-rule]].

*What 100 hunts produces isn't features — it's experience the software can't invent without data:
"German retailers consistently expose X", "party-IDs on GraphQL APIs behave like Y". That's the asset.*


The metric that keeps FRIDAY honest: **not features, but "how many times did a real hunt teach it something
genuinely new?"** Fill one row per real-target session. A build is earned only when a lesson **recurs across 3–5 hunts**.

## Why this dataset IS the asset (banked 2026-07-16, operator-experience review)
Software encodes decisions; humans generate them. The engine has eaten the *encodable* bottom of the skill stack
(routing, ranking, FP-suppression, evidence, reports). The next 3 years = the operator climbing the *un-encodable* top
(smell, where-to-look, modeling the builders, "is this real?", when-to-quit). **This log is the only thing that carries
that climb forward** — it's the exhaust the tool learns from AND the record that sharpens your tacit model. Both ratchet.
Capture per hunt (deepen the table below with these when relevant):
- **candidate → tested? → outcome** (confirmed / dup / FP / informative / paid) → **the one-line WHY** (the human's reason).
- **MISSES** — what a human found the tool didn't, + the *tell* the human used. (highest-value rows.)
- **FP corpus** — what fired but wasn't real + the discriminator that killed it.
- **Real-traffic fixtures** — save the actual request/response shapes (also fixes the test-false-confidence debt).
- **Abandon points** — where you quit + whether that was right.
- **"Hunch here" flag** — even a checkbox on the smell moments; crude but signal.
A lesson only becomes an earned build at 3–5× recurrence. Everything else stays human judgment.

## The per-hunt scorecard (added 2026-07-25 — fill one per hunt, no exceptions)
The milestone is **25 real hunts**, and the question at the end of it is *"is this getting more effective,
or just bigger?"* That question is unanswerable unless the numbers are captured **as you go** — retro-fitting
a metric at hunt 25 means 25 hunts of missing data. Deliberately a template and not code: half of it is
already printed by tools you run anyway, and if filling it by hand turns out to hurt across several hunts,
*that* is the recurrence that earns automating it.

| Metric | Where it comes from |
|---|---|
| Capture analyzed | ✓/✗ — did `ingest`/`sweep` actually run, or did the hunt bypass the engine again |
| Attack classes applicable | **X/10** — `sweep` prints this directly |
| Candidates surfaced | N — sum of the TESTABLE counts in the matrix |
| Confirmed findings | N — manual (reproduced ≥2×, impact stated) |
| False reports filed | N — manual. **This one must stay 0** |
| New engine bug found | Y/N — dogfooding hit; if Y, it should have a regression test |
| New regression added | Y/N — the fix that keeps the bug dead |
| New ruled-out knowledge | N — `ruled-out <host>` count, before vs after |

**Read the last three as one signal:** a hunt that finds no vulnerability but hardens the engine and banks
negative knowledge is a *productive* hunt. That is the whole reason this scorecard is not just "findings".
Filled scorecards are per-target records → they live in the PRIVATE hunt log, never here.

## Rules while hunting (the sticky note)
- ❌ Don't add features mid-hunt. ❌ Don't stop to build a "cool subsystem." ❌ Don't patch every miss immediately.
- ✅ Record every miss. ✅ Finish the hunt. ✅ Look for patterns ACROSS hunts. ✅ Only then earn one improvement.
- **Cadence: ~1 feature per 3–5 real hunts.** Ask "what am I going to learn today?", not "what should I build?"

## What "Confirmed" requires (FRIDAY's discipline, applied to you)
Reproduced ≥2×, tested across your 2 accounts, full request/response captured, concrete impact stated, scope + program
rules re-checked, PII redacted. A candidate is a hypothesis; a confirmation is a finding.

## Compliance defaults (per target, fill before hunting)
- Automated scanning allowed? (if NO → Hunt-Mode/HAR offline only, manual single-request verify)
- Required UA tag? (most programs mandate one — copy it EXACTLY from the policy, spaces included)
- Account email convention? (e.g. `@yeswehack.ninja`)
- Min accounts, IDOR only across your OWN accounts, no other-user data.
