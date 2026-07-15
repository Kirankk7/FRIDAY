# 2026-07-15 — Damn Vulnerable RESTaurant API (FastAPI) — last diversity lab

- **Purpose:** GPT's final diversity check — does FRIDAY generalize to a **FastAPI** stack? Expectation (agreed):
  confirmation, not bugs; one lesson max, then stop labs.
- **Target:** `theowni/Damn-Vulnerable-RESTaurant-API-Game`, docker-compose (FastAPI + Postgres), `:8091`.

## What was confirmed
- **Spec-ingestion generalizes to FastAPI.** Pulled the live `/openapi.json` — **16 routes** (standard OpenAPI 3):
  `/token` (JWT), `/orders/{order_id}` + `/orders/status/{order_id}` (BOLA surface), `/menu/{item_id}` PUT/DELETE +
  `/admin/stats/disk` (BFLA surface), `/users/update_role` (priv-esc/mass-assign). FRIDAY's `core/openapi` parser is
  **format-based, not stack-based** → it handles FastAPI's OpenAPI identically to crAPI's. No adapter needed. Confirmation.

## Why the active hunt was NOT completed (honest)
- **Lab dependency rot:** the RESTaurant web image crashes on a `passlib`/`bcrypt` incompat (`module 'bcrypt' has no
  attribute '__about__'`, the known bcrypt≥4.1 break) — boots, serves ~20s, then exits. Not fixable without dep surgery.
- **WSL2 networking wedged** (session-long): Windows→WSL forwarding dead on both localhost AND the WSL-IP; WSL python
  lacks FRIDAY's deps (psutil) + PEP-668 blocks pip. Windows-FRIDAY simply could not reach the WSL-hosted container.
- **Neither is an engine gap.** Both are operational/environment.

## The one lesson (operational, banked)
- **Not every lab is worth running.** A dep-rotted image + an unstable local runtime can cost more effort than a
  *predicted-clean confirmation* is worth. Recognizing "this lab isn't runnable, and it was low-yield anyway → stop"
  IS the disciplined move (freeze-era: don't grind low-ROI infra).
- **Crucially — this DOESN'T block the real hunt.** Real bug-bounty targets are on the public internet, reachable by
  Windows-FRIDAY DIRECTLY (no WSL forwarding involved). The WSL instability only ever affected *local labs*.

## Verdict — labs are DONE
8 architectures covered (PHP/Python/Flask/microservices/GraphQL + FastAPI spec-confirmed). GraphQL was the only real
gap; it's shipped. **Per the plan: stop labs → hunt real programs.** Next = the first real hunt (Windows-FRIDAY direct,
no WSL), or the MediaMarkt GraphQL HAR co-pilot workflow.
