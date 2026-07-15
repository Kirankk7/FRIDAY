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

## What FRIDAY MISSED (false negatives)
- **None on the object axis.** The BFLA (function-level) axis returned nothing — but that was **operator error**,
  not an engine miss: I hand-guessed admin/mechanic paths (`/auth/admin/users`, `/workshop/api/mechanic/`) that
  don't exist at those URLs. The engine can only test endpoints it's given.

## False positives
- **Zero.** Self-scoped control (`/user/dashboard`, owner vs attacker) returned `findings: []` — R5 content-diff
  correctly did NOT flag two users legitimately seeing their own different dashboards.

## Manual work (engine couldn't do)
- Stood up the stack, reset 2 seed passwords via postgres, logged in for JWTs, and **hand-supplied the endpoint
  list**. The engine validated; the human did discovery + auth setup.

## Feature NOT added
- No new detection built from this hunt. BOLA/R5/jwt all behaved as designed → nothing to change. (Discipline:
  a green dogfood is not a feature trigger.)

## Feature added / to add
- (blank — no recurring miss yet)

## Lessons
- **R5 content-diff is the load-bearing rule** for authz precision: it both *confirms* real BOLA (attacker body ==
  owner body) and *kills* the self-scoped FP. Live-validated twice now (VAmPI `_debug`, crAPI vehicle-location).
- **Recurrence of the known API-spec-ingestion gap:** `auth_matrix`/BFLA is only as good as its endpoint list.
  crAPI ships `openapi-spec/` — a real hunt would feed that in. **Watch for this pattern again:** if the next 1–2
  hunts also stall on "engine had no route list," that's the 2–3× signal to build **OpenAPI → endpoint-set ingestion**
  (already the top deferred item in the roadmap). One data point so far; not yet a build trigger.
- crAPI seed-password reset via postgres (`$2a$` bcrypt, dollar-quoted in a `psql -f` file to survive the
  Windows→WSL→docker→psql quoting layers) is the reliable way to get deterministic principals for authz dogfooding.
