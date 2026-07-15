# 2026-07 — crAPI (local dogfood)

- **Program:** crAPI (OWASP deliberately-vulnerable API) — local docker stack, WSL2, `:8888`
- **Scope:** identity + workshop APIs; 2 principals (bolaA / bolaB), each owns 1 vehicle. Authorized (own lab).
- **Date(s):** 2026-07-15
- **FRIDAY version / commit:** JARVIS `2e4251b` (post v1.3 auth-matrix + capability-deepening batch)

## What FRIDAY found
- **BOLA (object-level) — vehicle location — HIGH, live TP.** `idor_check` on
  `/identity/api/v2/vehicle/{A_uuid}/location`: attacker **B** got a response **byte-identical** to owner **A**
  (both 200/169b) while **anon = 401**. Evidence names the R5 discriminator: *"content match, not just length."*
  Manually confirmed the leaked body = A's carId + lat/long + `bolaA83118@t.com`.
- **`auth_matrix` object-axis re-caught the same BOLA** through the matrix (delegation to `idor_check` works end-to-end).
- **`jwt_analyze`** parsed the RS256 token, flagged the `role` claim as **info**, correctly **gated** ("tamper target
  IF a signature bypass holds") — no over-claim on a properly-signed token. Honest by design.

## What FRIDAY MISSED (false negatives) → FOUND + FIXED
- **REAL FN caught on the 2nd pass (real routes from `openapi-spec/`):** `auth_matrix` marked
  `/workshop/api/management/users/all` and `/workshop/api/mechanic/service_requests` as **`ok`** when a normal
  user (role=user) got HTTP 200 on both. `/management/users/all` **leaks every user's email + phone + credit** —
  textbook **BFLA**. Manually confirmed the dump.
- **Root cause:** `_expected_access` regex `/(…|manage|…)(/|$|\?)` — the trailing anchor required the keyword to
  *end* the path segment, so `manage` never matched inside `management`; `mechanic`/`merchant` weren't listed at all.
  → these privileged routes fell through to the `user` default → no BFLA expectation → no finding.
- **This is why "feed the engine real routes" matters:** my 1st pass hand-guessed paths that 404'd and the axis
  looked fine. The spec-derived list is what exposed the defect.

## False positives
- **Zero.** Self-scoped control (`/user/dashboard`, owner vs attacker) returned `findings: []` — R5 content-diff
  correctly did NOT flag two users legitimately seeing their own different dashboards.

## Manual work (engine couldn't do)
- Stood up the stack, reset 2 seed passwords via postgres, logged in for JWTs, and **hand-supplied the endpoint
  list**. The engine validated; the human did discovery + auth setup.

## Feature NOT added
- No *new detection class* built. The BFLA axis already existed — the fix was to its input classifier, not a new probe.

## Feature added / to add
- **FIXED `_expected_access` (both repos, byte-parity):** broadened the privileged-path keyword set to
  `administrator|management|mgmt|mechanic|merchant|staff|moderator|root` (+ existing admin/internal/manage/…).
  Post-fix the same run flags **2 BFLA HIGH + 1 BOLA HIGH**, dashboard control still clean (0 FP).
- **Note on discipline:** this was a *correctness defect* (too-strict regex missing obvious admin paths), not a
  speculative feature — so it's fixed immediately, not gated behind the 2–3× recurrence rule. The recurrence rule
  guards *new capability*, not *bugs in shipped capability*.

## Full `bug_bounty` e2e run (same day, `bugbounty_2026-07-15_110633.md`)
- Ran the complete pipeline (recon → hunt → validate → quality-gate → report → save) with force=True + A/B sessions.
  All 5 stages + LLM analysis + screenshot + report-packaging fired end-to-end, report saved to Desktop. **0 FP.**
- **BUT: 0 findings on a target I manually confirmed has BOLA + 3× BFLA.** Root cause on line: *"Stage 2.6: IDOR
  oracle on **0 id-bearing URL(s)**."* crAPI is a **SPA/API** target — Katana/crawl found 12 HTML endpoints but
  **zero API routes** (`/identity/api/…`, `/workshop/api/…` are XHR-called, never `<a href>` links). So `idor_check`
  got nothing to test, and **`auth_matrix` isn't wired into `bug_bounty` at all.**
- **This is the API-spec-ingestion gap, 2nd occurrence (data point #2).** 1st = `auth_matrix` needed a hand-fed route
  list; now the SAME gap zeroed the entire automated e2e. **The pipeline's PRECISION is fine (0 noise, honest empty
  report); its RECALL on API/SPA targets is ~0 because recon is `<a href>`-crawl-only.**
- **→ Promotes `OpenAPI/spec → route-set ingestion` from "deferred, 1 data point" to "build-justified (2× recurrence)."**
  The build: ingest a spec (or discovered `/openapi.json`/`swagger`), emit the concrete route list, feed it into the
  existing `idor_check` + `auth_matrix` (both already work once handed URLs — proven above). Also **wire `auth_matrix`
  into the `bug_bounty` pipeline** (currently only `idor_check` is, at Stage 2.6). No new detection logic — plumbing.

## Spec-ingestion BUILT + PROVED the fix (same day, `bugbounty_2026-07-15_113525.md`)
- Built `core/openapi.py` (discover `/openapi.json` etc → parse OpenAPI3/Swagger2 `paths` → concrete URLs; fill
  `{id}` params from ids **harvested** off the owner's param-free collection endpoints so routes are *reachable*).
  New `spec_ingest()` + wired into `bug_bounty` Stage **2.6a** (spec→routes into idor pool) + **2.6b**
  (`auth_matrix` over spec routes = wires the keystone into the pipeline) + dedup. Added `spec=` param to
  `bug_bounty` (operator supplies the spec when the target doesn't web-publish it, as crAPI doesn't). No new
  detection — pure plumbing into the EXISTING oracles.
- **Same e2e, before → after: 0 findings → 4 validated HIGH.** Log: *"Stage 2.6a: OpenAPI spec → 32 API route(s)…
  2.6b: auth_matrix over 32 spec route(s) → 4 authz finding(s)."* All **`validated=True`, REPRODUCED (6/7)**, gate
  filtered 0, report + evidence bundle saved:
  - 3× **BFLA** (`/workshop/api/management/users/all`, `/mechanic/`, `/mechanic/service_requests`) — CWE-862
  - 1× **missing-auth** (`/workshop/api/shop/orders/3`) — **confirmed TP**: anon (zero auth) gets robot001's full
    order incl. email + phone. CWE-306.
- Tests: `test_openapi_core` + `test_spec_ingest_ultron` (both repos). JARVIS 453/0/9, recon 65/65, byte-parity.

## Honest residuals (not chased — build goal met)
- **BOLA (vehicle-location) did NOT surface in the auto-4** — but that's environmental: crAPI's
  `/vehicle/{uuid}/location` endpoint went intermittently **timeout (HTTP 000)** this session, so `idor_check`'s
  fetch failed → no finding. The BOLA itself was proven + committed earlier (`9f4c69c`) when the endpoint was
  responsive; `auth_matrix` catches it when it answers.
- **Latent (tiny):** `request_mutator.mutate_url` treats only INT path segments as swappable, not uuids — so
  uuid-keyed routes are dropped from the Stage 2.6 *idor-loop* candidate filter. Redundant-covered by 2.6b
  `auth_matrix` (which classifies by path, no `mutate_url`), so low urgency. Fix when a uuid-BOLA target needs
  the idor-loop path specifically.

## Lessons
- **R5 content-diff is the load-bearing rule** for authz precision: it both *confirms* real BOLA (attacker body ==
  owner body) and *kills* the self-scoped FP. Live-validated twice now (VAmPI `_debug`, crAPI vehicle-location).
- **Recurrence of the known API-spec-ingestion gap:** `auth_matrix`/BFLA is only as good as its endpoint list.
  crAPI ships `openapi-spec/` — a real hunt would feed that in. **Watch for this pattern again:** if the next 1–2
  hunts also stall on "engine had no route list," that's the 2–3× signal to build **OpenAPI → endpoint-set ingestion**
  (already the top deferred item in the roadmap). One data point so far; not yet a build trigger.
- crAPI seed-password reset via postgres (`$2a$` bcrypt, dollar-quoted in a `psql -f` file to survive the
  Windows→WSL→docker→psql quoting layers) is the reliable way to get deterministic principals for authz dogfooding.
