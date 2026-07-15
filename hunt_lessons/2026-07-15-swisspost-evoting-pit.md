# 2026-07-15 — Swiss Post e-voting PIT (first real authorized target)

- **Program:** Swiss Post e-voting Public Intrusion Test (PIT), via YesWeHack. **LIVE 06–24 Jul 2026**, legal
  safe-harbour under Swiss Penal Code 143/143bis/144bis. Web scope `https://pit.evoting.ch`, source
  `gitlab.com/swisspost-evoting`, demo `demo.evoting.ch`. Release 1.5.4.0.
- **Outcome: NO-GO on engine-fit, decided by ~10 min of compliant recon (no build, no scanning).**

## Hard constraints that shaped the approach
- **Rules forbid automated scanning:** B.1 — *"refrain from using automated tools, and limit yourself about
  requests per second."* → FRIDAY's active pipeline (nuclei/katana/injection-fuzz at rate) is DISALLOWED against
  the live site; would also risk the safe-harbour (conditional on rule-compliance). Chose the compliant lane:
  build locally → hunt your own instance → reproduce manually on pit. Never pointed the auto-engine at the live site.
- **Value is cryptographic, not web:** the €40k–230k special bounties are vote-manipulation / tallying /
  privacy-break = crypto-protocol attacks. Out of FRIDAY's domain (web/API vuln detection).

## What the compliant recon found (public source + one normal page-load)
- Live voter portal = thin **Angular SPA**, `main.js` 425KB with a **single** quoted path (`/assets/i18n/`) —
  client-side WASM crypto (Argon2id), REST URLs built dynamically. Near-zero exposed web surface.
- Published `e-voting` repo = **crypto backend / control-components** (control-component, domain,
  secure-data-manager, message-broker). Only ~4 Spring REST mappings, all **internal trusted-component** APIs
  (`api/v1/disputeresolver`, `.../verificationcards`) — NOT a voter-facing CRUD/REST attack surface.
- Security by design lives in the **protocol + trusted components**, not a broad web app.

## Verdict + lesson
- **Poor fit for the engine.** FRIDAY wants a broad REST/API surface (BOLA/BFLA/injection/route-inventory). This
  target deliberately minimizes that; the real bugs are cryptographic. A years-pentested, source-public,
  crypto-expert-built system → near-zero web-bug odds.
- **The loop worked:** cheap, compliant recon established the mismatch in minutes, BEFORE a 15GB / ~25-min-build /
  multi-hour infra commitment on already-flaky WSL/Docker. **Recognizing wrong-target-fast IS the win** (freeze-era
  discipline: don't waste effort).
- **TARGET-SELECTION lesson (banked):** match the target to the engine's strengths. Next real hunt = a
  **broad-web/API** program (SaaS / fintech / marketplace / dashboards) where the authz + injection + route-inventory
  spine actually bites. E-voting = crypto-research, not web-hunting. Also: always read the program's automated-tool
  rules FIRST — many forbid the exact thing an auto-engine does, which dictates the local-build-then-reproduce lane.
