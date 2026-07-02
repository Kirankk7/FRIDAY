# God-file refactor plan (v1.2 internal cleanup)

*The boring refactor that succeeds. Behavior-preserving, incremental, test-guarded, its OWN
session — never mixed with feature work. Converged Claude/GPT review.*

## The one rule
**Never change behavior in a refactor commit. Move only. No logic edits.**
Every slice: move → run full regression (418) + `coverage.py` → 0 test changes → commit → next slice.
If a single test flips, you introduced a regression — revert the slice.

**Measure complexity, don't just move code.** A split that leaves the main file ~unchanged in size
is a failure. Target the *entry point* shrinking ~60%+.

## Targets (real numbers, 2026-07-02)
- `core/router.py` — **2781 LOC**, one giant `route_single_intent` regex chain.
- `agents/ultron/ultron_agent.py` — **4825 LOC**, one huge stateful class (~80 methods).

---

## Phase A — router.py (do FIRST — low risk, teaches the pattern)
Textbook ordered extraction. `route_single_intent` becomes a **dispatcher**; each cohesive regex
block moves to a helper that returns `decision | None`, called **in the same order**.

```
core/routes/
    security.py    -> try(text, text_raw) -> dict|None   (scan/recon/idor/graphql/cve/...)
    daily.py       -> weather/briefing/portfolio/expenses/find/calendar/crypto-toolkit
    vision.py      -> crypto price/FX/translate/flight/news
    system.py      -> battery/cpu/ram/speedtest/recall
    files.py       -> find-file/read/summarize/docs
```
```python
def route_single_intent(text, ...):
    # pre-filter + exact + follow-up stay inline (they gate everything)
    for grp in (security, daily, vision, system, files):
        d = grp.try_route(text, text_raw, ctx)
        if d: return d
    ...fallback
```
- **Success = 0 route changes** (393+ router tests are the net).
- **Target:** `route_single_intent` + inline guards ≤ ~700 LOC; the rest lives in `routes/`.
- Order-preserving → the only risk is a copy-paste slip, which the tests catch.
- Estimate: 1–2 sessions.

**Exit criteria (router — done when ALL true):**
- [ ] `route_single_intent` (+ inline guards) under ~1000 LOC.
- [ ] Identical routing order — every decision unchanged.
- [ ] 393+ router tests green, **zero behavioral diffs**.
- [ ] No new dependencies; imports remain acyclic.

---

## Phase B — ultron_agent.py (AFTER router — higher risk: shared `self` state)
**Modules + free functions, NOT mixins** (GPT's correction, accepted — no inheritance hierarchy to
trace; navigate files, not MROs). The real hazard is `self.X` written in one method, read in another.

**Extract STATELESS first** (these barely touch `self` — clean, low-risk):
```
agents/ultron/
    report.py    <- _format_bb_report, _build_test_plan, _impact_line, _validate_finding, _detect_db, _md_to_html
    evidence.py  <- _write_evidence_bundle  (delegates to core/evidence.py)
    cve.py       <- search_cve, cve helpers, NVD parsing
    knowledge.py <- kb_methodology, playbook recall, wordlists
```
Each becomes `def fn(target, findings, ...) -> ...` in a module; the agent calls
`from agents.ultron import report; report.format_bb(...)`.

**Defer STATEFUL** (recon/scan/session methods that read+write `self._last_report_md`, scope, cookies,
`_RATE_LAST`, watch state). These extract last, or **stay in agent.py** — moving them is where refactors
die. Don't force it.

- After each module extraction: full regression + friday-recon parity (its ultron is a copy).
- Estimate: 3–4 sessions. **Time-box: if refactoring runs past ~2 weeks, STOP and ship features.**

**Exit criteria (ultron — done when ALL true):**
- [ ] report / evidence / CWE-CVSS / CVE extracted to modules.
- [ ] **No inheritance introduced** (free functions / composition only).
- [ ] Public API (`ultron_agent.run`, method names) unchanged.
- [ ] Full regression + friday-recon parity green.
- [ ] Imports remain acyclic (verify via graphify / import check).

---

## Sequencing (honest — don't let refactor replace velocity)
```
v1.1 ✅
  → Router extraction        (Phase A, clean win)
  → F4 Execution Timeline     (its ultron footprint is LIGHT — timeline hooks, not a subsystem;
                               does NOT need the full ultron split first)
  → Ultron extraction         (Phase B, stateless-first, runs as its own track)
  → v1.2 tag (internal cleanup)
  → Submission package → Phase 3
```
GPT wanted ultron split before F4 ("don't add orchestration to a god file"). Partial-accept: F4's
ultron changes are a handful of `timeline.record()` hooks, not a new subsystem — gating F4 behind a
3–4 session ultron rewrite is the "refactoring replaces velocity" trap. Router first (real win), F4
proceeds, ultron split in parallel.

## Discipline checklist (per slice)
- [ ] Move only — zero logic changes in this commit.
- [ ] `JARVIS_CI=1 python test_regression.py` → same pass count, 0 flips.
- [ ] `python scripts/coverage.py` → 0 broken.
- [ ] friday-recon parity if ultron touched.
- [ ] Commit message: `refactor(router): extract <group> (move only, tests green)`.
- [ ] No "oh while I'm here…" — that's a separate commit, another day.
