# skill_scanner — vendored

**Origin:** `awesome-llm-apps` → `agent_skills/evals/tools/skill_scanner.py`
**Upstream licence:** Apache License 2.0 (full text in `LICENSE`, unmodified)
**Vendored:** 2026-09-27
**Upstream self-description:** *"[vendored] Repo-side CI copy. Origin: the
agent-security-auditor skill (revamp branch)."* — so this is a vendored copy of a
vendored copy; if that skill ever ships upstream, prefer it as the source of truth.

## Why it is here

Adopted during the 2026-09-06 screen of that repo — the one genuinely useful thing in
166 apps. A static scanner for agent skills, mapped to the OWASP Agentic Skills Top 10
(AST01–AST10). Stdlib only, makes no network calls, never executes the code it scans.

**It was adopted and then not kept.** On 2026-09-27 a 79-skill pack arrived and could not
be scanned with the tool adopted for exactly that job, because the tool was not in the
repo. *Keeping the finding is not keeping the capability* — EVAL_SET, roadmap P2.

## Modifications (Apache 2.0 §4b)

One change from upstream, marked inline with `[JARVIS MODIFICATION 2026-09-27]`:

**cp1252 crash on Windows.** The scanner prints `U+2192` in its own finding text. On a
Windows console that raises `UnicodeEncodeError` and the process dies **mid-scan** — in
our case after emitting exactly 3 WARNs, having reached only the first of eight skills.
`stdout`/`stderr` are now wrapped in UTF-8 with `errors="replace"`.

⚠️ This matters beyond ergonomics: our recorded result for this tool was *"0 CRITICAL /
3 WARN on our 8"*, and a crashed run produces exactly that shape. **A truncated run and a
complete run look identical from the outside.** The verified complete result is below.

## Verified result, 2026-09-27 (complete run, 8 skills)

```
0 CRITICAL   3 WARN   1 INFO      exit 0
```

All three warnings are in one skill:

```
META03  graphify/SKILL.md:1      frontmatter name 'graphify-windows' != directory 'graphify'
                                 typosquat/impersonation signal
PIN01   graphify/SKILL.md:638    unpinned pip install — version can drift to a compromised release
PIN01   graphify/references/add-watch.md:30   unpinned pip install
```

Upstream's own verdict line is worth repeating: *"a clean pattern scan is necessary but
not sufficient (OWASP AST08)."* It is a tripwire, not an assurance.

## Usage

```bash
python vendor/skill_scanner/skill_scanner.py <skill-dir-or-parent>
python vendor/skill_scanner/skill_scanner.py <path> --json
```

Exit codes: `0` no CRITICAL, `1` at least one CRITICAL, `2` usage error.
