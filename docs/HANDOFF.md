# HANDOFF — read this first

Entry point for any assistant, agent or human picking this project up cold. It is
deliberately tool-agnostic: everything below is plain Markdown and JSON, so it works the
same whether you are driving this with Claude, an OpenAI model, a local model, or no model
at all.

## What this project is

A bug-bounty co-pilot for a solo hunter. It is **not** an autonomous scanner. Its proven
strength is *verification* — deciding whether a suspected bug is real, and proving it well
enough to file. Its known weakness is *discovery* — it does not yet originate hypotheses on
its own. Read that sentence again before adding features; it is the whole roadmap.

## The three stores

| Store | Path | Contains | Visibility |
|---|---|---|---|
| **Doctrine + hunt memory** | `~/.claude/projects/<project>/memory/*.md` plus `MEMORY.md` as its index | Standing rules, per-target hunt history, milestones, what has already been ruled out | **PRIVATE.** Names live targets, accounts and identifiers. Never commit to a public repo. |
| **Technique playbook** | `data/playbook.json` | Distilled techniques from *publicly disclosed* reports. Each entry: `class, stack, difficulty, technique, payload, tell, verify, source, validated` | Public-safe. Contains no target, account or credential data. |
| **Methodology docs** | `docs/*.md` | Reusable method, no engagement data | Public-safe |

**Read order when starting cold:** `MEMORY.md` (the index — it links everything) → the
rule files it points to → the target file for whatever is in flight → `data/playbook.json`
only when you need techniques for a specific class.

## Durability

The memory store lives outside any repository by default. That is a **single point of
failure** — it should be mirrored to a private, versioned location. The playbook and docs
live in this repo. Assume nothing else is backed up unless you have checked.

Before any commit that touches `data/playbook.json`, scan for leakage — the repo is public:

```bash
grep -nEi "api[_-]?key|secret|bearer|password|eyJ[A-Za-z0-9_-]{10,}\.|AKIA[0-9A-Z]{16}" data/playbook.json
```

RFC1918 addresses appearing inside quoted technique text are usually examples from
published labs, not infrastructure — check the surrounding entry before "fixing" them.

## The doctrine that actually matters

These are load-bearing. Ignoring them is how findings turn into false positives.

1. **Verdict on state, not on a status code.** A `200` is not a result; a changed record
   is. Re-read the object through the API after every write test.
2. **Every test carries an own-object control that must succeed.** A failed control
   invalidates the test — it does *not* prove the target is safe.
3. **Validation is not enforcement.** A different error message means *untested*. Compare
   every denial against a known-bogus baseline before concluding anything.
4. **Escalate before filing.** Once a bug is confirmed, ask for the maximum honest version
   along two axes only: does N scale, and what is the worst *legitimate* parameter value.
   Bigger numbers of the same thing are padding.
5. **Name the mechanism, not the effect.** Pick the weakness class for *how* it breaks;
   the business damage goes in the impact, not the classification.
6. **Depth beats breadth for logic bugs.** Enumeration finds reachable surface; it does not
   find misplaced trust. Read one request body properly before crawling a hundred routes.
7. **Record negatives.** A class that was tested and enforced is a result worth keeping, as
   is a class deliberately skipped *with its reason*. This is what stops the next session
   re-walking dead ends.

## Scope discipline

Only test targets you are authorised to test, within a programme you are enrolled in, and
follow that programme's rules on tooling, environments and data handling. Prefer sandbox
environments for anything touching money. Clean up artifacts you create. Where a programme
requires a marker in requests, it applies to every tool you drive, not just the browser.

## Current state

See the memory index for what is in flight. At the time of writing: verification,
evidence discipline and reporting are proven; hypothesis generation is not. The active
milestone is to make the *procedure* — not the operator — name the suspect field or broken
invariant first, with the output written down before it is discussed, and reproducible from
a cold session. A methodology draft for that lens is intentionally held out of version
control until it has been tried once for real, so the method and its first result can be
recorded as separate, dated things.

## If you are a fresh assistant

Do not re-derive the doctrine above from scratch, and do not rebuild the verification
layer — it works. Load the memory index, find the target in flight, and ask what the last
verdicted class was. Then continue the sweep.
