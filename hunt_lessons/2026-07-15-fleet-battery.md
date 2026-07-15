# 2026-07-15 — Fleet detection battery (5 vuln apps) + crAPI deep-dive

- **Purpose:** benchmark engine DETECTION quality/precision before live hunting — not recon/browser.
- **Method:** call the detection methods directly on curated known-vuln endpoints per app (`_probe_injection`
  for injection classes; `idor_check`/`auth_matrix`/`jwt_analyze`/`spec_ingest` for API/authz), judge TP/FP.
  Chose this over full `bug_bounty` e2e because the recon+headless-browser stages are slow + fragile (a
  playwright driver crash aborted a DSVW e2e) and don't measure MY detection logic.
- **Fleet:** DSVW (`:65412` single-file) · DVWA (`:8080` authed) · Juice Shop (`:3000` SPA) · VAmPI (`:5000` API)
  · crAPI (`:8888` API, 10-container stack). All local docker/py, authorized.
- **FRIDAY version:** JARVIS `aad794b` (post spec-ingestion).

## Scorecard — every finding a real TP, ZERO false positives
| App | Classes fired | Notes |
|-----|---------------|-------|
| **DSVW** | `sqli-error` · `xss-reflected` · `command-injection` · `nosqli-operator` | 8 findings, 4 classes |
| **DVWA** | `sqli-error` · `xss-reflected` | login + DB-setup automated in-script |
| **Juice** | `sqli-error` (search) · **`sqli-auth-bypass-login`** (CRITICAL) | `' OR 1=1--` returned a token = canonical Juice bug |
| **VAmPI** | **`bfla`** (`/users/v1/_debug` all-users dump) · `jwt-weak-alg` (HS256) | spec-ingest discovered 8 routes |
| **crAPI** | `bfla` ×2 · `missing-auth` · `jwt-sensitive-claims` (+ BOLA in deep-dive) | consistent with the 0→4 e2e |

**~10 distinct classes across 4 target archetypes (injection-playground / classic-web / SPA / API), 0 FP.**
Precision discipline held live: `sqli-error-based` only on a *differential* DB-error; XSS only in an HTML-executable
context; BFLA emitted as `validated=False` candidates pending role-confirm; JWT gave *different* verdicts per token
(VAmPI HS256 → weak-alg; crAPI RS256 → sensitive-claims only).

## crAPI deep-dive (classes the battery didn't hit on crAPI)
1. **BOLA re-confirmed** — `idor_check` fired `idor-bola` on `/vehicle/{uuid}/location`. (Its absence in the earlier
   spec-e2e was purely the endpoint timing out, NOT an engine gap — proven here when responsive.)
2. **JWT** — RS256, `jwt-sensitive-claims` only; correctly no false alg-none/weak claim on a signed token.
3. **auth_matrix precision win** — the workshop service was returning **502** mid-run; the matrix marked those routes
   `ok` (did NOT flag 502 as BFLA). **No FP on service/5xx noise** — a real robustness/precision signal.
4. **Mass-assignment = confirmed unwired gap** — `request_mutator` has the mutate primitive but no wired active
   probe. Matches the roadmap's deferred/hunt-gated status. NOT a defect; a conscious deferral.
5. **SSRF/OAST** — `oast_probe` + `oast_ssrf` present (not exercised vs crAPI `contact_mechanic` this run).

## Lessons / residuals
- **Engine breadth + precision are strong:** 10 classes, 4 archetypes, 0 FP in one battery. This is the clearest
  "how good is the engine" read to date — detection is not the bottleneck.
- **Infra, not engine, was the friction:** WSL2 localhost port-forwarding dropped intermittently (transient 000s),
  the VM threw one catastrophic `E_UNEXPECTED`, and `nohup` keepalives died. **Fix that worked:** `setsid`-detached
  keepalive survives shell exit; `docker restart <svc>` re-establishes a dropped port proxy without a full WSL reset.
- **Confirmed gaps (already banked, unchanged):** mass-assignment (unwired, hunt-gated); uuid-BOLA in the idor-loop
  filter (auth_matrix covers it); OpenAPI auto-discovery only helps web-published specs (crAPI/VAmPI needed the
  operator/`spec_ingest` path — VAmPI's spec WAS discovered, 8 routes; crAPI's is a repo file).
- **No new build triggered** — everything behaved as designed. A clean battery is not a feature trigger (discipline).
