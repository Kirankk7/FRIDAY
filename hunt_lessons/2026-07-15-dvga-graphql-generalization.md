# 2026-07-15 — DVGA (GraphQL) — generalization test

- **Purpose:** GPT's Stage-3 question — *"does FRIDAY generalize to a different architecture?"* Picked a
  **GraphQL** target (Damn Vulnerable GraphQL App, `dolevf/dvga`) because GraphQL is FRIDAY's untested weak area
  AND the real parked target (MediaMarkt) is GraphQL → this de-risks the live hunt.
- **Target:** DVGA local docker `:5013`, own box (full-speed OK).

## DVGA vulns confirmed live (ground truth)
- **Introspection ENABLED** → full schema leaked (queries: pastes/paste/systemDiagnostics/users/me/… ; mutations:
  createPaste/importPaste/login/…).
- **BOLA/IDOR:** `paste(id:1)` returns a paste marked `public:false` (private) with **no auth** = broken object-level auth.
- **Unauth data dump:** `pastes{}` returns all pastes incl PII (phone number) unauthenticated.
- **Cmd-injection surface:** `systemDiagnostics(username,password,cmd)` (auth-gated here — needs valid creds).
- **SSRF surface:** `importPaste(host,port,path,scheme)`.

## The generalization verdict — GraphQL is FRIDAY's #1 gap
- FRIDAY's active oracles (`idor_check`, `auth_matrix`, `_probe_injection`) are **REST-shaped**: they mutate
  **query-string / path** params and send GET. They **cannot construct or mutate a GraphQL query in a POST body**.
- → Against DVGA, FRIDAY's active engine finds **NONE** of the four vulns above. It can *inventory* GraphQL offline
  (`hunt_mode` parses operations from a HAR) but **cannot actively probe** it.
- **2× recurrence:** DVGA (lab) + MediaMarkt (real target) — both GraphQL, both beyond the active engine. Per the
  freeze/loop rule this is **build-justified** (not speculative): a recurring, real-target-matching miss.

## Infra lesson (banked)
- This box's **WSL2 localhost port-forwarding is chronically unstable** — Windows→WSL proxy drops every few requests
  (5+ collapses this session). **Windows-FRIDAY cannot reliably hunt WSL-hosted labs.** Reliable pattern found:
  **run the probing INSIDE one WSL bash session** (start container + wait + all queries in a single `wsl.exe -lc`),
  localhost within the distro needs no forwarding. `--rm` containers also die on the instability → use `--name` +
  do everything in one shot.

## Direction (mine, vs GPT's "run 4-5 labs")
- The generalization test is **already answered by ONE target** (DVGA) + the real one (MediaMarkt): the gap is GraphQL.
- **Skip** re-running Juice/WebGoat/DVWA — battered this session (0 FP), classic-REST, low new information. Don't grind
  labs to re-confirm a known gap.
- **Earned build:** a minimal **GraphQL probe** — introspection-disclosure check + GraphQL-BOLA (reuse `idor_check`
  logic on `node(id)`-shape ops) + string-arg injection. Deterministic; unblocks DVGA (validate) + the real hunt.
- Scoreboard/recall dataset (GPT): good, banked, but does not gate this fix.
