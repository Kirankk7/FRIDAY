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

## Lessons
- **R5 content-diff is the load-bearing rule** for authz precision: it both *confirms* real BOLA (attacker body ==
  owner body) and *kills* the self-scoped FP. Live-validated twice now (VAmPI `_debug`, crAPI vehicle-location).
- **Recurrence of the known API-spec-ingestion gap:** `auth_matrix`/BFLA is only as good as its endpoint list.
  crAPI ships `openapi-spec/` — a real hunt would feed that in. **Watch for this pattern again:** if the next 1–2
  hunts also stall on "engine had no route list," that's the 2–3× signal to build **OpenAPI → endpoint-set ingestion**
  (already the top deferred item in the roadmap). One data point so far; not yet a build trigger.
- crAPI seed-password reset via postgres (`$2a$` bcrypt, dollar-quoted in a `psql -f` file to survive the
  Windows→WSL→docker→psql quoting layers) is the reliable way to get deterministic principals for authz dogfooding.
