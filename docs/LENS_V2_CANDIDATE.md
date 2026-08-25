# Invariant Lens — v2 CANDIDATE SPEC (NOT LIVE)

⛔ **DO NOT PASTE THIS INTO `core/lens_run.py`.** The live `_PROMPT` is the experimental baseline and
stays frozen until the current 4-question lens has been run cold and graded. Applying this early
destroys the comparison against the graded-B baseline.

Agreed 2026-08-25. Source: method mined from `Agentic-Bug-Hunter` (`SKILL.md`, `chain-builder.md`)
plus the business-logic taxonomy from `deep-eye`, screened per `downloaded-artefacts-not-authority`.

## Stage plan — one variable per stage

| stage | input | lens | status |
|---|---|---|---|
| BASELINE | single request | 4 questions | **LIVE**, graded **B** (10 hypotheses, 0 survived) |
| VAR 1 | single request | **6 questions** (this file) | only if baseline fails again |
| VAR 2 | feature-scope | 6 questions | only if VAR 1 fails |

Changing reasoning and context together makes any result unattributable.

## The two questions to append after Q4

```
 5. DEVELOPER INTENT — what was the simplest implementation that produces this request? What shortcut
    would a tired developer take? Where is the check most likely enforced: controller, middleware, or
    the data layer? What happens if this request arrives without the request that normally precedes it?

 6. DIFFERENTIAL — is there a second implementation of this same contract (v1 vs v2, mobile vs web,
    documented API vs console API, free vs paid)? Name the one whose enforcement you would compare.
```

## The vocabulary line to append before OUTPUT FORMAT

```
Name each invariant with a mechanism, not a class: check-and-consume atomicity, counterparty-fixed
immutability, entitlement selection, workflow-state trust, quota accounting, refund direction.
```

## Rationale

The live lens asks what a field **assumes**. These ask **why the code assumes it**, which is the
generator the lens currently lacks — it produces plausible fields but has never named a load-bearing
one. The vocabulary matters because "check-and-consume must be atomic" points at a technique while
"try mass assignment" points at nothing.

Not in scope for v2: sibling/A→B sweeping (`pb0667`) is a POST-finding move, not a hypothesis
generator, and belongs in the hunt loop rather than the lens.
