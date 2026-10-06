# RULE ENFORCEMENT MAP

> **The test this document applies, to every rule:**
> **Who or what enforces this?** If the answer is *"the model is instructed to remember it"*,
> the rule is **not enforced**. It is a preference with strong wording.

Written 2026-10-06, after an audit found that the one guard everybody trusted was reporting
"clean, 72 target name(s) checked" while structurally unable to see three live programmes. The
guard was not broken. It was reporting completeness it had never verified, and nothing in the
system could tell the difference.

A module is not an enforcement mechanism. A module becomes one only when something the model
cannot bypass invokes it at the transition where violation matters.

## ENFORCEMENT OWNERS THAT ACTUALLY EXIST

```
.git/hooks/pre-push        the only unavoidable automatic entry point in the repository
```

That is the complete list. There are no pre-commit hooks, no `.claude/hooks`, no settings-level
hooks. Everything else in the table below is either invoked by convention or by memory.

## P0 — hard invariants. Violation must block.

| # | rule | enforcement owner | violation behaviour | real? |
|---|---|---|---|---|
| 1 | No request outside authorised scope | `core/scope_guard.py` via `core/net.py` | raises `ScopeError`; transport failure raises `TransportError` so DENY and dead-host are different types | ⚠️ **structural but opt-in** — see note A |
| 2 | No programme name or credential material in a public diff | **pre-push hook** → `prepush_scan.py` → generated corpus | exit 1, push blocked, with the offending file and line | ✅ **real**, and completeness now verified |
| 3 | No verdict without a passing positive control | `core/instrument_check.py` | prints a verdict; nothing consumes it | ❌ **not wired to any verdict** |
| 4 | Never self-assign severity on a report | — | — | ❌ memory only |
| 5 | Never use a third party's data or identifier | — | — | ❌ memory only |
| 6 | Never buy a paid plan to reach a lane | — | — | ❌ memory only |
| 7 | No DoS, brute force, spam, or social engineering | — | — | ❌ memory only, and programme-specific |
| 8 | HARs and session artefacts in the scratchpad only, deleted at hunt close | `scripts/prune_bundles.py` covers the `.js`/`.map` keep-pile only | prints intruders, exits non-zero — **and nothing runs it** | ⚠️ **detects, never fires** |
| 9 | No class or hunt called CLOSED without a stated denominator | — | — | ❌ memory only — **this is the P0-B target** |

**Note A.** 19 modules import an HTTP library directly rather than going through `core/net.py`,
so the guard is a convention rather than a choke point. Inspected: the target-reaching ones
(`takeover.py`, `vdp_sweep.py`) do reference scope, and the five that looked like raw bypasses
were all benign on reading the call site — three `localhost:11434` (local model), one
`127.0.0.1:7000` loopback, and `url_guard.py`, which runs `assert_safe_url` on every redirect
hop. So nothing is currently bypassing it. But nothing *prevents* the next module from doing so,
and that difference is the whole point of this document.

## P1 — workflow invariants. Violation should block or reopen.

| # | rule | enforcement owner | real? |
|---|---|---|---|
| 10 | Coverage matrix created at the FIRST capture with every row `NOT TESTED` | — | ❌ memory only. Violated: one matrix was created five days late, another never at all |
| 11 | Matrix updated after every test | — | ❌ memory only. This is the "I tested it yesterday, the matrix says open" failure |
| 12 | Doctrine mirror synced after every hunt, filed report, new rule or wrap | — | ❌ memory only |
| 13 | Post-hunt retro, unprompted | — | ❌ memory only |
| 14 | `HUNT_PROTOCOL.md` reread at every hunt boundary | `/hunt` skill | ⚠️ **user-invoked** — enforced only when the operator types it, which is by design (the boundary is the operator's to declare) but means it is not automatic |
| 15 | Route-table sweep done and written before lane selection | — | ❌ memory only |
| 16 | Every console batch carries a positive control and prints raw context | `scripts/console_batch.py` | ⚠️ **discipline-dependent** — no hook can sit between the model and the chat window, so this one is structurally unenforceable; it works by making the check the same keystroke as producing the batch |
| 17 | Bundle keep-pile is `.js`/`.map` only, 30 days | `scripts/prune_bundles.py` | ⚠️ detects, nothing runs it |
| 18 | `EVAL_SET.md` audited at hunt close | — | ❌ memory only |

## P2 — preferences. The model may deviate with a reason.

| # | rule | owner |
|---|---|---|
| 19 | Commit style: no `Co-Authored-By` footer, tight messages | memory |
| 20 | Bulky scratch on `D:`, never `C:` | memory |
| 21 | One folder per target under `coverage/` and `scratchpad/` | memory |
| 22 | Terse response mode when requested | skill |

## THE COUNT

```
rules enumerated                     22
enforced by something unavoidable     1      (#2, pre-push)
structural but bypassable             1      (#1, scope guard)
detects but nothing invokes it        2      (#8, #17)
user-invoked by design                1      (#14)
structurally unenforceable            1      (#16, operator-paste boundary)
enforced by model memory alone        16
```

**16 of 22 rules have no enforcement owner.** And the four that drifted most in the last hunt —
mirror sync, matrix update, post-hunt retro, state the denominator — are all in that 16. That is
not a coincidence worth noting; it is the entire finding.

## WHAT THIS CHANGES

A rule with no owner is a prediction about model behaviour, and the record says those predictions
fail at a measurable rate. Three consequences:

1. **Do not respond to drift by strengthening the wording.** Capitalising a rule that has no owner
   produces a louder prediction, not a stronger guarantee. The signature `C-08 ADDENDUM` already
   records this: *the signature existed and did not change the behaviour.*
2. **An owner must be named before a rule is written down.** A new rule whose enforcement field
   reads "memory" is a note, and should be filed as one rather than as doctrine.
3. **The next build is the one that moves #9 out of the memory column** — a pre-commit hook that
   refuses a matrix marked closed unless a closure proof exists beside it and passes. That is
   available today because `git` is the one place the model cannot route around.

## HOW TO REGENERATE THIS

Not automatically — it is a judgement about what the owner of each rule really is, and a script
counting imports would answer a different question. What *is* mechanical, and worth re-running
whenever this file is doubted:

```bash
ls .git/hooks | grep -v sample                 # what can fire without being asked
grep -rln --include=*.py -E "^\s*(import|from)\s+(requests|httpx|urllib\.request|aiohttp)" core/ scripts/
```

The second command lists every module that can reach the network without the guard. It returned
19 on 2026-10-06, all inspected and benign. A growing number there is the signal that rule #1 has
slipped from convention to fiction.
