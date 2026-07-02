# JARVIS — Architecture Principles

*Not a roadmap, not implementation notes. The rules the project is built on. When a decision is
unclear, decide the way that honors these. Accumulated + earned, not aspirational.*

---

## 1. Deterministic before LLM
If a job can be done with regex, a lookup table, or plain code, do it that way — not with a model
call. The local 7B is a **capability ceiling**, not a hammer. Determinism buys speed, predictability,
and testability. Routing, follow-up state, evidence objects, summaries, exporters, personality
templates — all deterministic. The LLM is reserved for genuine natural-language generation.

## 2. Correct → Safe → Natural → Personality
Priority order when they conflict. Never sacrifice a correct/complete/safe answer for a prettier one.
This is *why* the "wrap every reply through a composer LLM" idea was rejected — it risked corrupting a
correct answer on a flaky 7B to gain polish.

## 3. Canonical objects, then exporters
Model the thing once (Evidence Object, Timeline). Output formats (markdown, JSON, HTML, PDF,
HackerOne, SARIF) are **exporters that read from the canonical object** — never parallel generators.
Adding a format is an exporter, not a rewrite.

## 4. Immutable, versioned artifacts
Build artifacts once, never edit in place; everything downstream reads them. Every schema carries a
`schema_version` and is bumped when the shape changes. (Evidence Object, Timeline.)

## 5. Contracts over prompt tweaks
Behaviour that must stay consistent is a **contract**, not a moving prompt. `AGENT_VOICES.md` is the
per-agent voice contract; new agents follow it. Personality is design, not an emergent accident.

## 6. Freeze completed layers
When a layer is done + tested + tagged, it's **frozen** — touched only for bug fixes. No "just one more
tweak." The conversation/personality layer is frozen at v1.1. Freezing protects velocity.

## 7. Refactors preserve behaviour
A refactor commit **moves code only** — never changes logic. Full regression after every slice; a
single test flip means a regression. Refactoring and feature work never share a commit. **Measure
complexity reduction, not lines moved** — if the entry point didn't shrink, you moved code, you didn't
refactor.

## 8. Local-first, privacy is the moat
100% local inference (Ollama), no cloud LLM for the core. All personal/runtime state
(memory, tasks, sessions/cookies, scan history, target profiles) is **gitignored — never committed,
never cloned**. A cloner boots a blank instance. Swapping to cloud is a one-function change, but the
default is private.

## 9. Registry-driven coverage
Functionality is enumerated from the code (registry/route tables), not a hand-list that rots. New
actions auto-appear in `COVERAGE.md` as uncovered. "Is everything working?" is one command away.

## 10. Two products, one engine — keep parity
JARVIS (the assistant/platform) and friday-recon (the security CLI) share the Ultron engine. Every
engine feature ships to **both** (F1, F3 ported same-day). Divergence = two maintenance burdens later.

## 11. Reviews are filtered, not obeyed
External review (human or AI) is an input, not an oracle. Accept good ideas regardless of source;
reject ideas that conflict with these principles; adjust plans on evidence (real LOC, tests,
behaviour); know when to stop. The judgement is the asset.

---

*Maturity today: prototype → integrated assistant → **execution platform** (here) → operational →
autonomous. The jump to "platform" was made by adopting these principles, not by any single feature.*
