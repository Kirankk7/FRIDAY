# JARVIS — project instructions

## 🔴 BEFORE ANY BUG-BOUNTY HUNT WORK: read `docs/HUNT_PROTOCOL.md`

Read the file itself — do not work from memory of it. This applies whenever the session involves a
live target: recon, capture analysis, lane selection, testing, or closing a hunt. Kiran should not
have to paste it; loading it is my job, and skipping it is the failure the file exists to prevent.

The one-line test from §8, which governs every "done / closed / enforced / fortress" claim:

> **Can I state the denominator?**
> Required for BOTH breadth (N/M surfaces) and depth (N/M transitions).
> Neither can be inferred from the number of requests sent.

If I cannot state it, the enumeration is unfinished — say what is untested instead of banking.

## ⚠️ One session spans many hunts

Kiran does NOT open a new session per hunt — one session runs for days across several targets. So
this file loading at SESSION start does not cover a hunt that begins mid-session.

**Per-hunt trigger: the `hunt-start` skill (`/hunt`).** It reloads `docs/HUNT_PROTOCOL.md` and the
target file, then reports phase + denominators + lane verdicts before any work. Invoke it myself
whenever the session pivots to a new target or resumes one — do not wait to be asked.

## Hunt order (from HUNT_PROTOCOL §2–§3)

```
gate  →  authorised capture  →  cold lens (sealed)  →  surface enumeration  →  lane selection
```

- The lens run is staged and **sealed before any lane discussion**. I cannot be the cold context.
- Surface enumeration comes before lane *selection*, not before the first capture.
- Every probe ships with a positive control in the same batch. Control fails ⇒ **UNREADABLE**, no
  verdict in either direction.
- Verdict vocabulary is fixed: ENFORCED · FALSIFIED · UNTESTABLE · UNREADABLE · N/A · NOT TESTED.
  "Untestable" never becomes "safe".

## Standing operational rules

- Sync the doctrine mirror **unprompted** after every hunt, filed report, new rule, or session wrap:
  `bash /d/hunt-doctrine/sync.sh` + commit + push.
- HARs and hunt artefacts live in the **scratchpad only** — never the Desktop or Downloads, deleted
  at hunt close. They carry session cookies, CSRF tokens and sometimes credentials.
- `hunt-doctrine` is PRIVATE; `FRIDAY` and the other repos are PUBLIC — scrub programme, account and
  credential data from every diff destined for a public repo. Enumerate every pre-push hook hit
  individually before considering `--no-verify`.
- Never self-assign severity on a report. State what was and was not achieved; frame the finding as
  their missing control.
- Post-hunt retro, unprompted and honest: what moved the needle, what I got wrong, what Kiran caught,
  and a grade on process rather than luck.

## Engine modules worth remembering

- `core/schema_surface.py` — introspection dump → complete attack surface (arguments, input fields of
  every type, enums, custom scalars, query root) + which operations sit outside the tenant gate.
  Confirm `self-check: clean` before quoting any number from it.
- `core/lens_run.py` — stage / seal / verify / grade the invariant-lens experiment.
- `core/oast.py` — internet-reachable OOB listeners; never falls back to loopback.
