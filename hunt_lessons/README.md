# hunt_lessons/

One doc per real hunt. This folder is the **requirement source for Phase 3 (Knowledge Acquisition)** —
see [`docs/V1_3_ROADMAP.md`](../docs/V1_3_ROADMAP.md).

## Rule
Every live/dogfood hunt → one file: `YYYY-MM-<target>.md` (copy `_TEMPLATE.md`).
Record what FRIDAY **found**, **missed** (FN), **false-positived** (FP), and the **manual work** a human
had to do the engine couldn't. A miss is a datum, not a bug to reflex-patch.

## The loop this feeds
```
Real hunt → miss → record HERE → recurred across 2–3 hunts? → yes → small deterministic improvement → ship
                                                              → no  → leave it (no speculative build)
```

`Feature NOT added` is a first-class field: recording a deliberate non-build is as valuable as a build.
Six months of these = patterns you can't see today. Do NOT skip the boring hunts.

## Privacy / scope
- Authorized targets only. Redact creds/tokens/PII before committing.
- If a hunt touches a private program under NDA, keep the file local/gitignored; commit only the *lesson*, not the target detail.
