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
engine repo   .git/hooks/pre-push          disclosure guard, corpus completeness verified
mirror repo   .git/hooks/pre-commit        closure gate (added 2026-10-06)
engine repo   .claude/settings.json        PreToolUse Write|Edit -> batch_write_guard
                                           (added 2026-10-10, onFailure: block)
```

Three — and the third is a different KIND of owner, which is why it is listed here rather than
folded into the count. The two git hooks sit on an action the model takes deliberately and
rarely. The PreToolUse hook sits on an ordinary tool call, so it fires whether or not anyone
intended a gate to run. That is the first owner in this repo that cannot be reached around by
simply not running a command. Its limit is a different one: it covers the file-write ROUTE only.

Note WHERE the second one lives: coverage matrices are gitignored in the engine repo and tracked in the private
mirror, so the mirror commit is the transition at which a closure claim becomes durable. A gate
placed in the engine repo would have been correct-looking and never fired.

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
| 9 | No class or hunt called CLOSED without a stated denominator | **mirror pre-commit** → `scripts/closure_gate.py` | exit 1; requires a proof carrying per class a verdict from the fixed vocabulary, a stated denominator, and `closure_delta` = 0 from the final review | ✅ **real** (2026-10-06) |

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
| 16 | Every console batch carries a positive control and prints raw context | `scripts/console_batch.py` | ⚠️ **discipline-dependent on the chat route only** — see note B, which corrects what this row used to claim |
| 17 | Bundle keep-pile is `.js`/`.map` only, 30 days | `scripts/prune_bundles.py` | ⚠️ detects, nothing runs it |
| 18 | `EVAL_SET.md` audited at hunt close | — | ❌ memory only |
| 23 | No console batch written to a file without a hypothesis preflight, and none asserting a currently-FALSIFIED hypothesis | **PreToolUse hook** → `scripts/batch_write_guard.py` → `data/hypothesis_ledger.jsonl` | ✅ **real on the file-write route, bypassable on the chat route** — fires unasked, denies on a missing ledger / uncompilable detector / crash; see note B |

**Note B — a claim this document used to make, now falsified in part.** Row 16 previously read
*"no hook can sit between the model and the chat window, so this one is structurally
unenforceable."* The first clause is still true and the conclusion was too broad. A `PreToolUse`
hook sits between the model and the **filesystem**, and a batch that is written before it is
pasted passes through it. So the unenforceable surface is narrower than stated: it is the batch
typed straight into a reply, not batches in general.

What rule 23 therefore is, precisely:

```
ENFORCED   a console batch reaching a file. Denied unless a one-shot preflight token keyed to
           that exact content exists AND no currently-FALSIFIED assumption is spelled out in it.
           Proven live 2026-10-10: a Write asserting the thrice-falsified cookie-auth claim was
           refused, the file never existed, and the refusal is in the control trail.
BYPASSABLE a batch delivered without a file write. CONFIRMED by test, NOT MEASURED - nothing
           counts those attempts, so the trail's numbers describe the guarded route only and no
           bypass rate can be quoted from them.
NOT A      proof that a refusal prevented a wasted operator action. A DENY is a refused write.
CLAIM      The counterfactual needs the batch run against the live surface.
FLOOR      detection is textual. An assumption held but never typed does not match, in the tests
           or in production, so recall is unmeasured and a clean pass is a floor on known
           mistakes rather than a verdict on the batch.
```

## P2 — preferences. The model may deviate with a reason.

| # | rule | owner |
|---|---|---|
| 19 | Commit style: no `Co-Authored-By` footer, tight messages | memory |
| 20 | Bulky scratch on `D:`, never `C:` | memory |
| 21 | One folder per target under `coverage/` and `scratchpad/` | memory |
| 22 | Terse response mode when requested | skill |

## THE COUNT

```
rules enumerated                     23      (#1-#23, row count parsed from this file)
enforced by something unavoidable     2      (#2 pre-push, #9 mirror pre-commit)
automatic on one route, open on one   1      (#23, file-write enforced / chat route open)
structural but bypassable             1      (#1, scope guard)
detects but nothing invokes it        3      (#3, #8, #17)
user-invoked by design                1      (#14)
structurally unenforceable            1      (#16, the chat-paste boundary only)
memory or bare preference alone      14      (#4-7, #10-13, #15, #18-22)
                                     ---
                                      23
```

⚠️ **The previous version of this block summed to 23 for 22 rules.** `#3` was counted once as
"detects but nothing invokes" and again inside the memory bucket, so the memory figure read 16
when the classification supports 14. The buckets now sum to the parsed row count, and that sum is
printed above precisely so the next reader can check it instead of trusting it. A count in prose
is a claim; a count that reconciles is a fact.

**17 of 23 rules still have no EFFECTIVE owner** — the 14 memory-only rules plus the 3 that have
a working detector nothing ever calls. Of the four that drifted most in hunt #43 — mirror sync,
matrix update, post-hunt retro, state the denominator — one has an owner and three do not. That
the drifting four were all in the memory column is not a coincidence worth noting; it is the
entire finding. #23 is the first entry added to this file whose owner was built before the rule
was written down, rather than after the rule was broken.

## WHAT THIS CHANGES

A rule with no owner is a prediction about model behaviour, and the record says those predictions
fail at a measurable rate. Three consequences:

1. **Do not respond to drift by strengthening the wording.** Capitalising a rule that has no owner
   produces a louder prediction, not a stronger guarantee. The signature `C-08 ADDENDUM` already
   records this: *the signature existed and did not change the behaviour.*
2. **An owner must be named before a rule is written down.** A new rule whose enforcement field
   reads "memory" is a note, and should be filed as one rather than as doctrine.
3. **#9 moved out of the memory column on 2026-10-06**, because `git` is the one place the model
   cannot route around. The next candidates by observed damage are #11 (matrix updated after
   every test) and #12 (mirror sync) — both are also `git`-adjacent, so both are reachable by
   the same method. #3 and #8 need a different answer: they have working detectors that nothing
   invokes, so the build there is a caller, not a checker.

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
