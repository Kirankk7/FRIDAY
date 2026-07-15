# Hunt Tracker — the north-star dataset

The metric that keeps FRIDAY honest: **not features, but "how many times did a real hunt teach it something
genuinely new?"** Fill one row per real-target session. A build is earned only when a lesson **recurs across 3–5 hunts**.

| # | Date | Target | Time | Candidates | Tested | Confirmed | Dup | Invalid | Lesson (what FRIDAY couldn't have known beforehand) |
|--|------|--------|------|-----------:|-------:|----------:|----:|--------:|------|
| 1 | | MediaMarkt (GraphQL, HAR co-pilot) | | | | | | | |
| 2 | | | | | | | | | |
| 3 | | | | | | | | | |

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
