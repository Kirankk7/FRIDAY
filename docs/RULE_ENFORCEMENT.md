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
engine repo   .claude/settings.json        PreToolUse Write|Edit|Bash|PowerShell -> batch_write_guard
                                           (added 2026-10-10, onFailure: block)
engine repo   .git/hooks/pre-commit        staged control file -> its suites rerun via run_check
                                           (added 2026-10-10; fails closed)
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
| 23 | No console batch written to a file without a hypothesis preflight, and none asserting a currently-FALSIFIED hypothesis | **PreToolUse hook** → `scripts/batch_write_guard.py` → `data/hypothesis_ledger.jsonl` | ✅ **real on Write/Edit (ledger + token) and on visible Bash/PowerShell .js writes into scratch (ledger only); bypassable via chat, interpreter-written files, cp/mv, terminal panel** — fails closed; see note B |
| 24 | A changed control is not committed until its suites pass, and no hunt is fully closed without valid execution evidence for every required check | **engine pre-commit** → `scripts/precommit_checks.py`; **mirror pre-commit** → `closure_gate.py` → `core/check_evidence.py` | ✅ **real** — see note C |

**Note C — execution evidence.** `scripts/run_check.py` is the only writer of
`workspace/check_runs.jsonl`. A check id maps to one fixed command in
`core/check_evidence.REGISTRY` (4 checks, cap 5); no command can be passed in. Each run keeps its
full output as an artefact and records the artefact hash and a hash of the files the check covers.
A record is valid only if: latest for its id, command equals the registry, exit 0, artefact
present and unaltered, covered files unchanged since the run (else STALE — and unchanged controls
keep their evidence, so nothing reruns without a reason). The closure gate reads ONLY these
records and ignores any check status written into a proof. Applies to hunts whose matrix closes
on/after 2026-10-11. **Not tamper-proof:** records are local JSONL and can be forged; the test
suite forges them openly to exercise each rule. Close dates are read from the matrix, so a
backdated close would dodge the cutoff. Suites run against the working tree, not the staged
snapshot. Proven live 2026-10-10: a deliberately broken control was staged, the real hook
reran its suite, the commit was refused, HEAD did not move.

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
SHELL      (added 2026-10-10) Bash and PowerShell are matched too. A shell command that
ROUTE      visibly writes a .js into workspace/scratch - `>` / `>>` (heredoc bodies included),
           `tee`, Out-File / Set-Content / Add-Content, relative targets resolved against cwd -
           gets the LEDGER check only. The preflight TOKEN is NOT required on this route:
           content is not cleanly separable from command text, and `curl ... > bundle.js` into
           scratch is routine bundle mining that must keep working. Proven live: a real Bash
           heredoc asserting AUTH-001 was refused, file never created, event carries the host's
           tool_use_id as action_id. Cost: ~76-105 ms added to every Bash/PowerShell call.
BYPASSABLE CONFIRMED by test, NOT MEASURED - nothing counts these, so no bypass rate exists:
           batches typed into chat; an interpreter or script that opens the file itself
           (`python -c`, `node -e`, a .py) - asserted AS a limit by test L1; variables or command
           substitution in the target; cp / mv of an existing file; and the terminal panel,
           which is not a matched tool. That last one was found the hard way: when the guard
           crashed on import, onFailure:block locked Write/Edit/Bash/PowerShell all at once, and
           the terminal panel was the only route left to repair it.
LOCKOUT    a guard crash blocks EVERY matched call. Fail-closed is deliberate; the price is that
RISK       a bad edit to the guard blocks the tools needed to fix it. Repair route: the terminal
           panel. Run scripts/hypothesis_check.py before trusting any guard edit.
MUTATION   scripts/mutation_check.py removes one property at a time from a COPY of the guard
           (14 mutants) and requires the suite to go red. 14/14 killed by failed assertions,
           0 survived, 0 crash-kills. Covers the guard only - not the ledger or preflight scripts.
BOUND TO   the token binds to the SHA-256 of the batch CONTENT. It does NOT bind to the
WHAT       destination path, so the same cleared content may be written to a different filename;
           and `declared` hypothesis ids are RECORDED in the token but not enforced against the
           ids the detector matched. Both verified by test, both deliberate - the paste is the
           content, not the path - and both stated here rather than implied to be tighter.
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
rules enumerated                     24      (#1-#24, row count parsed from this file)
enforced by something unavoidable     3      (#2 pre-push, #9 mirror pre-commit, #24 both pre-commits)
automatic on one route, open on one   1      (#23, file-write enforced / chat route open)
structural but bypassable             1      (#1, scope guard)
detects but nothing invokes it        3      (#3, #8, #17)
user-invoked by design                1      (#14)
structurally unenforceable            1      (#16, the chat-paste boundary only)
memory or bare preference alone      14      (#4-7, #10-13, #15, #18-22)
                                     ---
                                      24
```

⚠️ **The previous version of this block summed to 23 for 22 rules.** `#3` was counted once as
"detects but nothing invokes" and again inside the memory bucket, so the memory figure read 16
when the classification supports 14. The buckets now sum to the parsed row count, and that sum is
printed above precisely so the next reader can check it instead of trusting it. A count in prose
is a claim; a count that reconciles is a fact.

**17 of 24 rules still have no EFFECTIVE owner** — the 14 memory-only rules plus the 3 that have
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
