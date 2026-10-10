# HUNT #42 — MACHINE-DERIVED QUANTITATIVE RETROSPECTIVE

Measured 2026-10-10 from artefacts on disk and git history. Every row carries a label:

- **MD** = MACHINE-DERIVED — reproducible by re-running the stated command
- **HO** = HUMAN-OBSERVED — seen in terminal output or chat, **no durable artefact**
- **UM** = UNMEASURABLE — no artefact exists; not estimated

> ⚠️ **The headline finding is about the measurement system, not the hunt.**
> `console_batch.py`, `closure_gate.py` and `prepush_scan.py` each have **0 append-calls**. They
> print to stdout and exit. **No control except `scope_guard` records anything.** Therefore every
> "the gate blocked X" statement made today is **HO**, not MD — and the #44 accountability
> experiment, as designed, is currently **unmeasurable**. Fix that before measuring anything else.

---

## 1 · CLOSURE GATE

| metric | value | label | source |
|---|---|---|---|
| matrices on disk | 7 | MD | `coverage/*matrix*.md` (private mirror) |
| claiming a close date | 6 / 7 | MD | regex on the `closed` header row |
| with a closure proof | 6 / 6 | MD | `coverage/*_closure.json` |
| of those, **GRANDFATHERED** (assert nothing) | **4** | MD | `grandfathered: true` |
| **MEASURED proofs** | **2** | MD | hunt #43, hunt #42 |
| hunts closed **through** the gate | **1** | MD | hunt #42, 2026-10-10 |
| hunts closed **before** the gate existed | 5 | MD | gate created 2026-10-06 |
| proof fields missing on measured proofs | **0** | MD | all of `hunt/target/second_pass/hygiene/classes` present |
| classes lacking a denominator | **0 / 22** | MD | across both measured proofs |
| classes lacking an integer `closure_delta` | **0 / 22** | MD | |
| **block events logged** | **UNMEASURABLE** | UM | the gate writes no log |
| closure claims the gate refused | 2 observed | **HO** | terminal only — padded 11/11, hygiene lie |

⚠️ **One gate-mediated closure is not a success rate.** The denominator is 1. Nothing here
supports a claim about how often the gate catches a bad closure.

## 2 · INVENTORY / DENOMINATOR INTEGRITY

| denominator | claimed | actual | abs error | error |
|---|---|---|---|---|
| product A profile leaf fields | 270 | **549** | 279 | **51%** |
| product B SPA routes | 40 | **10** | 30 | **300%** |
| passive corpus URLs (one capped pull vs accounted walk) | 109,937 | **614,425** | 504,488 | **82%** |

- claims independently re-derived: **3** · found wrong: **3 (100%)** — MD, recorded in the matrix
- unsupported completion claims identified: **1** (MD) — phase header reading *"all reachable
  leads closed"* printed directly above counts showing 2 of 11
- **Archive completeness is scoped, not absolute.** The CDX walk was COMPLETE for that walk
  (`expected=attempted=ok=227, failed=0`, MD) — **this is not proof the archive is exhausted.**
  Two runs with identical parameters returned 440,286 and 614,425, so the index is not stable
  between pulls and every count remains a floor.

## 3 · HYPOTHESIS RETRIEVAL

| metric | value | label |
|---|---|---|
| machine-readable hypothesis ledger present | **NO** | MD — no such file exists |
| preflight enforced before operator actions | **NO** | MD — not built; proposal only |
| experiments where prior contradicting evidence existed | 1 family (cookie-vs-XSRF auth) | **HO** |
| …where that evidence was retrieved before planning | **0** | **HO** |
| …where it was not, and an operator action was wasted | **3 pastes** | **HO** |
| prior occurrences of the same assumption | 2 (2026-09-17, 2026-09-22) — **this was the 3rd** | MD — both written in `hunt #42.md` |

The 2026-09-22 note is verbatim: *"I then wrote a probe that relied on `credentials:'include'` and
attached no token. **The evidence to build it correctly was already in my own notes.**"
**The failure is retrieval, not stubbornness** — and there is no artefact that would have forced
the lookup.

## 4 · OPERATOR EFFICIENCY

| metric | value | label |
|---|---|---|
| browser-console pastes, this session | 10 | **HO** |
| productive | 6 | **HO** |
| avoidable — wrong auth model | 3 | **HO** |
| avoidable — oracle unavailable (`plan-client` 500) | 1 | **HO** |
| non-productive share | **40%** | HO |
| pastes per class **advanced** | 10 / 2 = **5.0** | HO |
| pastes per class **fully closed** | 10 / 0 = **undefined** — no class fully closed this session | HO |
| active operator time | **UNMEASURABLE** | UM |
| elapsed wall-clock vs waiting time | **UNMEASURABLE** | UM |

⚠️ **The comparison with the previous hunt does not survive its own definition.** hunt #43's 8
pastes / 2 classes **closed two classes**; this session's 10 pastes **advanced** two and closed
none. `4.0 → 5.0` compares different units and should not be quoted as a 25% regression.
The defensible statement is narrower: **40% of this session's operator actions were avoidable,
and 30 points of that were one repeated, already-documented assumption.**

## 5 · CONTROLS AND TESTS

| metric | value | label |
|---|---|---|
| `run_test` call sites in the suite | 498 | MD |
| suite executed this session | **NO** — deliberately, per operator instruction | MD |
| pass/fail/skip counts | **UNMEASURABLE** this session | UM |
| commits citing a test or demonstration | 3 | MD |
| **synthetic acceptance tests** (fixtures, forced branches) | present and durable | MD — in code + commits |
| **real block events** | **not recorded anywhere** | UM |
| defects caught by deterministic controls | 2 observed (validator refused a `PUT` batch; invariant caught a 62% record loss) | **HO** |
| defects caught by reading raw output | ~6 observed | **HO** |

**Synthetic acceptance tests and real block events must not be conflated.** The first are durable
and reproducible; the second currently leave no trace.

## 6 · EVIDENCE AND CLOSURE QUALITY — hunt #42 proof

| metric | value | label |
|---|---|---|
| verdicts | 11 | MD |
| with a stated denominator | **11 / 11** | MD |
| with an integer `closure_delta` | **11 / 11** | MD |
| ENFORCED | 5 | MD |
| UNTESTABLE (tier / missing state) | 3 | MD |
| **fully_closed** | **2 / 11** | MD |
| reopenings recorded | 0 | MD |
| `closure_delta` from the final review | **0 findings** | MD |
| ENFORCED claims without matching evidence | **0** | MD — each cites a raw-context observation |

The review surfaced **5 coverage corrections** and **0 new findings**. Those are different things
and are counted separately in the proof.

---

## 7 · DECISION

**Largest measured source of wasted operator effort:** repeated use of an assumption already
contradicted by a written note — **3 of 10 pastes, third occurrence, both priors in the same file.**

**But the smallest control is not the preflight.** The preflight's own effect would be
unmeasurable, because no control writes a log. So:

```
CONTROL  make the three controls append one JSONL line per invocation
         {ts, tool, target, decision: PASS|BLOCK, reason}
COST     ~10 lines each
WHY      without it, "the gate blocked N bad batches" stays HUMAN-OBSERVED forever, and #44
         reproduces exactly the self-reported evidence the experiment exists to escape
```

**Then** the preflight + hypothesis ledger, whose acceptance test is the exact historical failure:
a cookie-auth batch write is **refused before any paste is generated**, unless new evidence
justifies reopening the hypothesis.

**Regression test + acceptance criteria**

```
TEST   attempt to write a console batch asserting cookie authentication for the CP
PASS   PreToolUse refuses the write; a BLOCK line appears in the control log; no paste produced
PASS   supplying new contradicting evidence permits the write and logs REOPEN
FAIL   the write succeeds, or succeeds with no log line
MEASURE  blocked_before_paste / (blocked_before_paste + wasted_pastes), from the log, not from me
```

⚠️ **Documented bypass, to be measured rather than hidden:** the hook guards the *file-write*
path. A batch typed directly into chat never touches it. That path stays observable and manual,
and the control is named `CONSOLE_BATCH_WRITE_REQUIRES_PREFLIGHT` rather than anything broader.

---

## SCORECARD — supported metrics only

```
closure proofs: 6 of 6 closed hunts | 2 MEASURED, 4 GRANDFATHERED
gate-mediated closures: 1            (denominator 1 - not a rate)
proof completeness: 22/22 classes carry denominator + integer delta
denominators re-derived: 3 | wrong: 3 (51%, 300%, 82% error)
unsupported completion claims found: 1
hunt #42 verdicts: 11 | fully_closed 2 | ENFORCED without evidence: 0
closure_delta final review: 0 findings | 5 coverage corrections
controls that write a durable log: 1 of 4 (scope_guard only)
```

## CANNOT YET BE MEASURED

- real block events from any control except `scope_guard` — **no log**
- operator active time, wall-clock, waiting time — **not instrumented**
- paste counts — **chat-only, no artefact**
- gate catch-rate — **denominator is 1**
- suite pass/fail/skip this session — suite deliberately not run
- whether any control *prevented* a failure — only two were observed, neither traced
