# Hunt Tracker — the north-star dataset

The metric that keeps FRIDAY honest: **not features, but "how many times did a real hunt teach it something
genuinely new?"** Fill one row per real-target session. A build is earned only when a lesson **recurs across 3–5 hunts**.

| # | Date | Target | Time | Candidates | Tested | Confirmed | Dup | Invalid | Lesson (what FRIDAY couldn't have known beforehand) |
|--|------|--------|------|-----------:|-------:|----------:|----:|--------:|------|
| 1 | 2026-07-16 | MediaMarkt (GraphQL, HAR co-pilot) | ~2h | 5 ranked | 1 (in progress) | — | — | 3 productId FPs | see lessons below |
| 2 | | | | | | | | | |
| 3 | | | | | | | | | |

### Hunt #1 lessons (MediaMarkt) — 2 EARNED fixes shipped
1. **GraphQL lives in the URL query string, not the body.** MediaMarkt = `GET /api/v1/graphql?operationName=X&variables={…}`. hunt_mode parsed only the body → saw **2 of 51 ops**. Fixed → 30 ops (`e5af3f0` predecessor). Blocking miss = earned fix.
2. **user-scoped vs public IDs + missing `dashboard` hint.** Ranker flagged `productId`/`wishlist` ops (public catalog = NOT BOLA) AND missed `GetDashboardDataV3(partyId)` (the REAL candidate — `dashboard` wasn't an owner-hint). Fixed: `_USER_ID`/`_PUBLIC_ID` split + weighted score + `dashboard` (`e5af3f0`). Result: partyId op 90→**125 (#1)**, productId op 90→**5 (last)**.

**The strong candidate:** `GetDashboardDataV3` sends a **client-supplied 10-digit `partyId`** (X=1705194262, Y=1705195689). Every sibling owner op is session-only. TEST PENDING (cookie expired): as Y, swap partyId→X's; if Y gets X's data = BOLA, enumerable = high sev. **Discipline note:** 2 fixes on hunt #1 = the *edge* of the cadence rule, both were blocking/precision bugs (not features). **NO more hunt_mode changes until the partyId test runs + ≥2 more hunts** — banked (not built): response-side PII signal (#4), `_id_pairs` len-catch tighten (#5).

## Rules while hunting (the sticky note)
- ❌ Don't add features mid-hunt. ❌ Don't stop to build a "cool subsystem." ❌ Don't patch every miss immediately.
- ✅ Record every miss. ✅ Finish the hunt. ✅ Look for patterns ACROSS hunts. ✅ Only then earn one improvement.
- **Cadence: ~1 feature per 3–5 real hunts.** Ask "what am I going to learn today?", not "what should I build?"

## What "Confirmed" requires (FRIDAY's discipline, applied to you)
Reproduced ≥2×, tested across your 2 accounts, full request/response captured, concrete impact stated, scope + program
rules re-checked, PII redacted. A candidate is a hypothesis; a confirmation is a finding.

## Compliance defaults (per target, fill before hunting)
- Automated scanning allowed? (if NO → Hunt-Mode/HAR offline only, manual single-request verify)
- Required UA tag? (e.g. MediaMarkt: ` -MMS-BugBounty `)
- Account email convention? (e.g. `@yeswehack.ninja`)
- Min accounts, IDOR only across your OWN accounts, no other-user data.
