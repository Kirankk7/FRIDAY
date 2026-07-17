# Hunt Tracker — the north-star dataset

## THE OPERATING CONTRACT (banked 2026-07-16, GPT↔Claude converged — final)
Track ONLY these. If the first six trend right and the last trends down, FRIDAY is healthy:
| metric | goal |
|---|---|
| real hunts completed · lessons extracted · confirmed findings · report accept-rate | ↑ |
| false positives · missed findings | ↓ |
| **new features / LOC / modules** | **↓** |

**4 rules (supersede the scattered cadence notes):**
1. **No new feature** unless **≥3 hunts** reveal the *same* missing capability.
2. **No empty hunts** — every hunt produces one of: finding · FP · missed-opportunity · lesson.
3. **Every 25 hunts** — review the DATA, not the code.
4. **Every 100 hunts** — pay down exactly ONE architectural debt. Nothing more.

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
